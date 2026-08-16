from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import VotronicCoordinator

PLATFORMS = ["sensor", "button"]


async def async_setup(
    hass: HomeAssistant,
    config: dict,
) -> bool:
    """Set up Votronic."""
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up Votronic from a config entry."""

    coordinator = VotronicCoordinator(
        hass,
        entry,
    )

    await coordinator.async_load_solar_yield()
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload a Votronic config entry."""

    return await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )
    