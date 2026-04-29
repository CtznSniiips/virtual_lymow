"""Sensor platform for Lymow."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LymowEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            LymowStatusSensor(coordinator),
            LymowMotionDeltaSensor(coordinator),
            LymowLastSnapshotSuccessSensor(coordinator),
            LymowLastSnapshotErrorSensor(coordinator),
        ]
    )


class LymowStatusSensor(LymowEntity, SensorEntity):
    """Reports mower state (Mowing/Docked/Idle/Unknown/Charging)."""

    _unique_id_suffix = "status"
    _attr_name = "Status"
    _attr_icon = "mdi:robot-mower"

    @property
    def native_value(self):
        return self.coordinator.data.status


class LymowMotionDeltaSensor(LymowEntity, SensorEntity):
    """Diagnostic motion delta from image differencing."""

    _unique_id_suffix = "motion_delta"
    _attr_name = "Motion Delta"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "px"
    _attr_icon = "mdi:chart-bell-curve-cumulative"

    @property
    def native_value(self):
        value = self.coordinator.data.average_delta
        return round(value, 2) if value is not None else None


class LymowLastSnapshotSuccessSensor(LymowEntity, SensorEntity):
    """Diagnostic timestamp of the last successful snapshot capture."""

    _unique_id_suffix = "last_snapshot_success"
    _attr_name = "Last Snapshot Success"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:camera-check"
    _attr_entity_registry_enabled_default = False

    @property
    def native_value(self):
        return self.coordinator.last_successful_snapshot_time


class LymowLastSnapshotErrorSensor(LymowEntity, SensorEntity):
    """Diagnostic details for the most recent snapshot error."""

    _unique_id_suffix = "last_snapshot_error"
    _attr_name = "Last Snapshot Error"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:camera-alert"
    _attr_entity_registry_enabled_default = False

    @property
    def native_value(self):
        return self.coordinator.last_snapshot_error

    @property
    def extra_state_attributes(self):
        return {
            "error_type": self.coordinator.last_snapshot_error_type,
            "error_message": self.coordinator.last_snapshot_error_message,
        }
