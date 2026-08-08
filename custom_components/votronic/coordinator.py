from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from bleak.exc import BleakError
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    establish_connection,
)

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CHAR_MAIN,
    CHAR_SOLAR,
    DOMAIN,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class VotronicCoordinator(DataUpdateCoordinator[dict[str, str | None]]):
    """Fetch raw data from a Votronic Bluetooth connector."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize coordinator."""

        self.entry = entry
        self.address = entry.data["address"]

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.address}",
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, str | None]:
        """Connect to Votronic and read raw characteristics."""

        ble_device = bluetooth.async_ble_device_from_address(
            self.hass,
            self.address,
            connectable=True,
        )

        if ble_device is None:
            raise UpdateFailed(
                f"Votronic device {self.address} is not currently reachable"
            )

        client = None

        try:
            _LOGGER.debug(
                "Connecting to Votronic device %s",
                self.address,
            )

            client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                name=f"Votronic {self.address}",
                disconnected_callback=None,
            )

            _LOGGER.debug(
                "Connected to Votronic device %s",
                self.address,
            )

            result: dict[str, str | None] = {}

            result["main"] = await self._read_characteristic(
                client,
                CHAR_MAIN,
                "MAIN",
            )

            result["solar"] = await self._read_characteristic(
                client,
                CHAR_SOLAR,
                "SOLAR",
            )

            return result

        except BleakError as err:
            raise UpdateFailed(
                f"Bluetooth communication failed: {err}"
            ) from err

        except asyncio.CancelledError:
            # Wichtig: CancelledError niemals in einen normalen
            # UpdateFailed-Fehler umwandeln.
            raise

        except Exception as err:
            raise UpdateFailed(
                f"Unexpected Votronic error: {err}"
            ) from err

        finally:
            if client is not None:
                try:
                    if client.is_connected:
                        await client.disconnect()

                        _LOGGER.debug(
                            "Disconnected from Votronic device %s",
                            self.address,
                        )

                except Exception:
                    _LOGGER.debug(
                        "Error while disconnecting from %s",
                        self.address,
                        exc_info=True,
                    )

    async def _read_characteristic(
        self,
        client,
        uuid: str,
        label: str,
    ) -> str | None:
        """Read one GATT characteristic with a timeout."""

        try:
            async with asyncio.timeout(5):
                raw = await client.read_gatt_char(uuid)

        except TimeoutError:
            _LOGGER.warning(
                "Timeout reading Votronic %s characteristic %s",
                label,
                uuid,
            )
            return None

        except asyncio.CancelledError:
            raise

        except Exception as err:
            _LOGGER.warning(
                "Unable to read Votronic %s characteristic %s: %s",
                label,
                uuid,
                err,
            )
            return None

        hex_data = bytes(raw).hex(" ").upper()

        _LOGGER.info(
            "VOTRONIC RAW %-8s [%s]: %s",
            label,
            uuid,
            hex_data,
        )

        return hex_data
