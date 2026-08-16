from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import VotronicCoordinator

AMPERE_HOUR = "Ah"


@dataclass(frozen=True, kw_only=True)
class VotronicSensorDescription(SensorEntityDescription):
    data_key: str


SENSORS = (
    VotronicSensorDescription(
        key="battery_voltage", data_key="battery_voltage", name="Battery voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    VotronicSensorDescription(
        key="starter_voltage", data_key="starter_voltage", name="Starter battery voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    VotronicSensorDescription(
        key="battery_current", data_key="battery_current", name="Battery current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    VotronicSensorDescription(
        key="battery_soc", data_key="battery_soc", name="State of charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    VotronicSensorDescription(
        key="battery_remaining_capacity", data_key="battery_remaining_capacity",
        name="Remaining capacity", native_unit_of_measurement=AMPERE_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    VotronicSensorDescription(
        key="solar_voltage", data_key="solar_voltage", name="Solar voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    VotronicSensorDescription(
        key="solar_panel_voltage", data_key="solar_panel_voltage",
        name="Solar panel voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    VotronicSensorDescription(
        key="solar_current", data_key="solar_current", name="Solar current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    VotronicSensorDescription(
        key="solar_power", data_key="solar_power", name="Solar power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    VotronicSensorDescription(
        key="solar_total_charge", data_key="solar_total_charge",
        name="Solar yield since reset",
        native_unit_of_measurement=AMPERE_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    VotronicSensorDescription(
        key="solar_total_energy", data_key="solar_total_energy",
        name="Solar energy since reset",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
    VotronicSensorDescription(
        key="solar_status_code", data_key="solar_status_code", name="Solar status code",
    ),
    VotronicSensorDescription(
        key="solar_raw",
        data_key="solar_raw",
        name="Solar raw data",
        icon="mdi:code-tags",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    coordinator: VotronicCoordinator = entry.runtime_data
    async_add_entities(
        VotronicSensor(coordinator, entry, description) for description in SENSORS
    )


class VotronicSensor(CoordinatorEntity[VotronicCoordinator], SensorEntity):
    _attr_has_entity_name = True
    entity_description: VotronicSensorDescription

    def __init__(
        self,
        coordinator: VotronicCoordinator,
        entry: ConfigEntry,
        description: VotronicSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.entity_description.data_key)
