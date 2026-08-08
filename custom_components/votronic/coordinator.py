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

NOTIFY_WAIT_SECONDS = 8


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
    def _log_gatt_structure(self, client) -> None:
        """Log all discovered GATT services and characteristics."""
    
        _LOGGER.warning("===== VOTRONIC GATT STRUCTURE START =====")
    
        for service in client.services:
            _LOGGER.warning(
                "SERVICE %s",
                service.uuid,
            )
    
            for characteristic in service.characteristics:
                properties = ", ".join(characteristic.properties)
    
                _LOGGER.warning(
                    "  CHAR %s | properties=[%s] | handle=%s",
                    characteristic.uuid,
                    properties,
                    characteristic.handle,
                )
    
                for descriptor in characteristic.descriptors:
                    _LOGGER.warning(
                        "    DESCRIPTOR %s | handle=%s",
                        descriptor.uuid,
                        descriptor.handle,
                    )
    
        _LOGGER.warning("===== VOTRONIC GATT STRUCTURE END =====") 
    async def _async_update_data(self) -> dict[str, str | None]:
        """Connect to Votronic and receive notifications."""

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

        result: dict[str, str | None] = {
            "main": None,
            "solar": None,
        }

        main_event = asyncio.Event()
        solar_event = asyncio.Event()

        def main_callback(sender, data: bytearray) -> None:
            """Handle MAIN notification."""

            hex_data = bytes(data).hex(" ").upper()

            result["main"] = hex_data

            _LOGGER.info(
                "VOTRONIC NOTIFY MAIN [%s]: %s",
                CHAR_MAIN,
                hex_data,
            )

            main_event.set()

        def solar_callback(sender, data: bytearray) -> None:
            """Handle SOLAR notification."""

            hex_data = bytes(data).hex(" ").upper()

            result["solar"] = hex_data

            _LOGGER.info(
                "VOTRONIC NOTIFY SOLAR [%s]: %s",
                CHAR_SOLAR,
                hex_data,
            )

            solar_event.set()

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

            _LOGGER.debug(
                "Starting Votronic MAIN notifications"
            )

            await client.start_notify(
                CHAR_MAIN,
                main_callback,
            )

            _LOGGER.debug(
                "Starting Votronic SOLAR notifications"
            )

            await client.start_notify(
                CHAR_SOLAR,
                solar_callback,
            )

            try:
                async with asyncio.timeout(NOTIFY_WAIT_SECONDS):
                    await asyncio.gather(
                        main_event.wait(),
                        solar_event.wait(),
                    )

            except TimeoutError:
                _LOGGER.warning(
                    "Timeout waiting for Votronic notifications "
                    "(MAIN received=%s, SOLAR received=%s)",
                    main_event.is_set(),
                    solar_event.is_set(),
                )

            return result

        except BleakError as err:
            raise UpdateFailed(
                f"Bluetooth communication failed: {err}"
            ) from err

        except asyncio.CancelledError:
            raise

        except Exception as err:
            raise UpdateFailed(
                f"Unexpected Votronic error: {err}"
            ) from err

        finally:
            if client is not None:
                try:
                    if client.is_connected:

                        try:
                            await client.stop_notify(CHAR_MAIN)
                        except Exception:
                            _LOGGER.debug(
                                "Could not stop MAIN notification",
                                exc_info=True,
                            )

                        try:
                            await client.stop_notify(CHAR_SOLAR)
                        except Exception:
                            _LOGGER.debug(
                                "Could not stop SOLAR notification",
                                exc_info=True,
                            )

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
                    
