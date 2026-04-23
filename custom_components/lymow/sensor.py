"""Sensor platform for Lymow."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
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
    async_add_entities([LymowStatusSensor(coordinator), LymowMotionDeltaSensor(coordinator)])


class LymowStatusSensor(LymowEntity, SensorEntity):
    """Reports mower state (mowing/docked/idle/unknown)."""

    _attr_name = "Mower Status"
    _attr_unique_id = "lymow_status"
    _attr_icon = "mdi:robot-mower"

    @property
    def native_value(self):
        return self.coordinator.data.status


class LymowMotionDeltaSensor(LymowEntity, SensorEntity):
    """Diagnostic motion delta from image differencing."""

    _attr_name = "Motion Delta"
    _attr_unique_id = "lymow_motion_delta"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "px"
    _attr_icon = "mdi:chart-bell-curve-cumulative"

    @property
    def native_value(self):
        value = self.coordinator.data.average_delta
        return round(value, 2) if value is not None else None
