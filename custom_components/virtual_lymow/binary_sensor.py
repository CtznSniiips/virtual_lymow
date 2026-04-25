"""Binary sensors for Lymow."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
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
    async_add_entities([LymowMotionBinarySensor(coordinator), LymowDockedGuessBinarySensor(coordinator)])


class LymowMotionBinarySensor(LymowEntity, BinarySensorEntity):
    """Binary sensor for inferred mower motion."""

    _attr_name = "Motion"
    _attr_unique_id = "virtual_lymow_motion"
    _attr_icon = "mdi:motion-sensor"

    @property
    def is_on(self):
        return self.coordinator.data.motion


class LymowDockedGuessBinarySensor(LymowEntity, BinarySensorEntity):
    """Binary sensor for guessed docked state."""

    _attr_name = "Docked Guess"
    _attr_unique_id = "virtual_lymow_docked_guess"
    _attr_icon = "mdi:ev-station"

    @property
    def is_on(self):
        return self.coordinator.data.docked_guess
