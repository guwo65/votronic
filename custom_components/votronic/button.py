from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import VotronicCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the reset button."""
    coordinator: VotronicCoordinator = entry.runtime_data
    async_add_entities([VotronicResetSolarYieldButton(coordinator, entry)])


class VotronicResetSolarYieldButton(
    CoordinatorEntity[VotronicCoordinator], ButtonEntity
):
    """Reset the calculated solar Ah and Wh counters."""

    _attr_has_entity_name = True
    _attr_name = "Reset solar yield"
    _attr_icon = "mdi:restart"

    def __init__(
        self, coordinator: VotronicCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_reset_solar_yield"

    async def async_press(self) -> None:
        """Reset both accumulated values."""
        await self.coordinator.async_reset_solar_yield()