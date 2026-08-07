from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import VotronicCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up Votronic diagnostic sensors."""

    coordinator: VotronicCoordinator = entry.runtime_data

    async_add_entities(
        [
            VotronicRawSensor(
                coordinator,
                entry,
                "main",
                "Votronic RAW Battery",
            ),
            VotronicRawSensor(
                coordinator,
                entry,
                "solar",
                "Votronic RAW Solar",
            ),
        ]
    )


class VotronicRawSensor(
    CoordinatorEntity[VotronicCoordinator],
    SensorEntity,
):
    """Temporary raw Votronic sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VotronicCoordinator,
        entry: ConfigEntry,
        data_key: str,
        name: str,
    ) -> None:
        """Initialize sensor."""

        super().__init__(coordinator)

        self._data_key = data_key

        self._attr_name = name
        self._attr_unique_id = (
            f"{entry.entry_id}_{data_key}_raw"
        )

    @property
    def native_value(self):
        """Return latest raw packet."""

        if not self.coordinator.data:
            return None

        return self.coordinator.data.get(
            self._data_key
        )
        
