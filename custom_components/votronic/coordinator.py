from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.storage import Store

from .bluez_agent import BlueZAgentRegistration
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

CHAR_MAIN = "9a082a4e-5bcc-4b1d-9958-a97cfccfa5ec"
CHAR_SOLAR = "971ccec2-521d-42fd-b570-cf46fe5ceb65"

NOTIFY_WAIT_SECONDS = 15
PAIR_TIMEOUT_SECONDS = 20

# The connector is already bonded. Leave this False for normal operation.
# Set it to True only for one manual pairing attempt after clearing all bonds
# on the SC-Connector. Set it back to False after pairing succeeds.
PAIR_ON_NEXT_CONNECTION = False

STORAGE_VERSION = 1
MAX_INTEGRATION_GAP_SECONDS = 60


def _uint16_le(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little", signed=False)


def _int24_le(data: bytes, offset: int) -> int:
    value = int.from_bytes(data[offset : offset + 3], "little", signed=False)
    return value - (1 << 24) if value & (1 << 23) else value


def _decode_main(data: bytes) -> dict[str, Any]:
    if len(data) < 20:
        raise ValueError(f"MAIN packet is too short: {len(data)} bytes")

    # Bytes 13/14 contain the configured maximum battery capacity in 0.1 Ah.
    nominal_capacity = _uint16_le(data, 13) / 10
    state_of_charge = data[8]

    return {
        "battery_voltage": _uint16_le(data, 0) / 100,
        "starter_voltage": _uint16_le(data, 2) / 100,
        "battery_nominal_capacity": nominal_capacity,
        "battery_soc": state_of_charge,
        "battery_current": _int24_le(data, 10) / 1000,
        # The packet contains the configured nominal capacity, not a directly
        # reported remaining capacity. Derive the latter from the displayed SoC.
        "battery_remaining_capacity": round(
            nominal_capacity * state_of_charge / 100, 1
        ),
        "main_raw": data.hex(" ").upper(),
    }


def _decode_solar(data: bytes) -> dict[str, Any]:
    # This SC-Connector consistently sends 19-byte solar packets.
    if len(data) < 19:
        raise ValueError(f"SOLAR packet is too short: {len(data)} bytes")

    battery_voltage = _uint16_le(data, 0) / 100
    panel_voltage = _uint16_le(data, 2) / 100
    current = _uint16_le(data, 4) / 10

    return {
        "solar_voltage": battery_voltage,
        "solar_panel_voltage": panel_voltage,
        "solar_current": current,
        # Power is calculated from the two confirmed live measurements.
        "solar_power": round(battery_voltage * current, 1),
        "solar_status_code": data[9],
        "solar_raw": data.hex(" ").upper(),
    }


class VotronicCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch and decode data from a Votronic Bluetooth connector."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.address = entry.data["address"]
        self._store: Store[dict[str, float]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.solar_yield"
        )
        self._solar_total_charge = 0.0
        self._solar_total_energy = 0.0
        self._last_sample_time: float | None = None
        self._last_current: float | None = None
        self._last_power: float | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.address}",
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )

    async def async_load_solar_yield(self) -> None:
        """Restore the user-resettable solar counters after a restart."""
        stored = await self._store.async_load()
        if stored:
            self._solar_total_charge = float(stored.get("charge_ah", 0.0))
            self._solar_total_energy = float(stored.get("energy_wh", 0.0))

    def _stored_solar_yield(self) -> dict[str, float]:
        return {
            "charge_ah": self._solar_total_charge,
            "energy_wh": self._solar_total_energy,
        }

    def _update_solar_yield(self, result: dict[str, Any]) -> None:
        """Integrate current and power, ignoring implausibly long data gaps."""
        now = time.monotonic()
        current = max(0.0, float(result["solar_current"]))
        power = max(0.0, float(result["solar_power"]))

        if self._last_sample_time is not None:
            elapsed = now - self._last_sample_time
            if 0 < elapsed <= MAX_INTEGRATION_GAP_SECONDS:
                previous_current = self._last_current or 0.0
                previous_power = self._last_power or 0.0
                hours = elapsed / 3600
                self._solar_total_charge += (
                    previous_current + current
                ) / 2 * hours
                self._solar_total_energy += (
                    previous_power + power
                ) / 2 * hours

        self._last_sample_time = now
        self._last_current = current
        self._last_power = power
        result["solar_total_charge"] = round(self._solar_total_charge, 3)
        result["solar_total_energy"] = round(self._solar_total_energy, 2)
        self._store.async_delay_save(self._stored_solar_yield, 30)

    async def async_reset_solar_yield(self) -> None:
        """Reset both calculated counters and persist the reset immediately."""
        self._solar_total_charge = 0.0
        self._solar_total_energy = 0.0
        self._last_sample_time = time.monotonic()

        if self.data:
            self._last_current = max(0.0, float(self.data.get("solar_current", 0.0)))
            self._last_power = max(0.0, float(self.data.get("solar_power", 0.0)))
            updated = dict(self.data)
            updated["solar_total_charge"] = 0.0
            updated["solar_total_energy"] = 0.0
            self.async_set_updated_data(updated)

        await self._store.async_save(self._stored_solar_yield())

    async def _async_update_data(self) -> dict[str, Any]:
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise UpdateFailed(f"Votronic device {self.address} is not reachable")

        client = None
        pairing_agent: BlueZAgentRegistration | None = None
        main_notify_started = False
        solar_notify_started = False
        result: dict[str, Any] = {}
        main_event = asyncio.Event()
        solar_event = asyncio.Event()

        def main_callback(sender: Any, data: bytearray) -> None:
            raw = bytes(data)
            try:
                result.update(_decode_main(raw))
            except ValueError as err:
                _LOGGER.warning("Invalid Votronic MAIN packet: %s", err)
                return
            _LOGGER.debug("Votronic MAIN RX: %s", result["main_raw"])
            main_event.set()

        def solar_callback(sender: Any, data: bytearray) -> None:
            raw = bytes(data)
            try:
                result.update(_decode_solar(raw))
            except ValueError as err:
                _LOGGER.warning("Invalid Votronic SOLAR packet: %s", err)
                return
            _LOGGER.debug("Votronic SOLAR RX: %s", result["solar_raw"])
            solar_event.set()

        try:
            client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                name=f"Votronic {self.address}",
                disconnected_callback=None,
            )

            if PAIR_ON_NEXT_CONNECTION:
                pairing_agent = BlueZAgentRegistration(self.address)
                try:
                    await pairing_agent.register()
                    async with asyncio.timeout(PAIR_TIMEOUT_SECONDS):
                        await client.pair()
                except TimeoutError as err:
                    raise UpdateFailed(
                        f"Votronic pairing timed out after {PAIR_TIMEOUT_SECONDS} seconds"
                    ) from err
                except Exception as err:
                    raise UpdateFailed(f"Votronic pairing failed: {err}") from err
                finally:
                    await pairing_agent.unregister()
                    pairing_agent = None

            if not client.is_connected:
                raise UpdateFailed("Votronic disconnected before subscriptions")

            await client.start_notify(CHAR_MAIN, main_callback)
            main_notify_started = True
            await client.start_notify(CHAR_SOLAR, solar_callback)
            solar_notify_started = True

            try:
                async with asyncio.timeout(NOTIFY_WAIT_SECONDS):
                    await asyncio.gather(main_event.wait(), solar_event.wait())
            except TimeoutError as err:
                raise UpdateFailed(
                    "Timeout waiting for Votronic data "
                    f"(MAIN={main_event.is_set()}, SOLAR={solar_event.is_set()})"
                ) from err

            self._update_solar_yield(result)
            return result

        except BleakError as err:
            raise UpdateFailed(f"Bluetooth communication failed: {err}") from err
        except asyncio.CancelledError:
            raise
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Unexpected Votronic error: {err}") from err
        finally:
            if pairing_agent is not None:
                await pairing_agent.unregister()

            if client is not None and client.is_connected:
                if main_notify_started:
                    try:
                        await client.stop_notify(CHAR_MAIN)
                    except Exception:
                        _LOGGER.debug("Could not stop MAIN notifications", exc_info=True)
                if solar_notify_started:
                    try:
                        await client.stop_notify(CHAR_SOLAR)
                    except Exception:
                        _LOGGER.debug("Could not stop SOLAR notifications", exc_info=True)
                try:
                    await client.disconnect()
                except Exception:
                    _LOGGER.debug("Could not disconnect Votronic", exc_info=True)
