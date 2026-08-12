from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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


def _uint16_le(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little", signed=False)


def _int24_le(data: bytes, offset: int) -> int:
    value = int.from_bytes(data[offset : offset + 3], "little", signed=False)
    return value - (1 << 24) if value & (1 << 23) else value


def _decode_main(data: bytes) -> dict[str, Any]:
    if len(data) < 20:
        raise ValueError(f"MAIN packet is too short: {len(data)} bytes")

    return {
        "battery_voltage": _uint16_le(data, 0) / 100,
        "starter_voltage": _uint16_le(data, 2) / 100,
        "battery_nominal_capacity": _uint16_le(data, 4),
        "battery_soc": data[8],
        "battery_current": _int24_le(data, 10) / 1000,
        "battery_remaining_capacity": _uint16_le(data, 13) / 10,
        "main_raw": data.hex(" ").upper(),
    }


def _decode_solar(data: bytes) -> dict[str, Any]:
    # This SC-Connector consistently sends 19-byte solar packets.
    if len(data) < 19:
        raise ValueError(f"SOLAR packet is too short: {len(data)} bytes")

    voltage = _uint16_le(data, 0) / 100
    current = _uint16_le(data, 2) / 1000

    return {
        "solar_voltage": voltage,
        "solar_current": current,
        # Power is calculated from the two confirmed live measurements.
        "solar_power": round(voltage * current, 1),
        "solar_status_code": data[9],
        "solar_total_charge": _uint16_le(data, 13),
        "solar_total_energy": _uint16_le(data, 15) / 100,
        "solar_raw": data.hex(" ").upper(),
    }


class VotronicCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch and decode data from a Votronic Bluetooth connector."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.address = entry.data["address"]

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.address}",
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )

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