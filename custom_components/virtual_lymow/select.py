"""Select entity for manual Lymow state override/debugging."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, OVERRIDE_OPTIONS
from .entity import LymowEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([LymowStateSelect(coordinator)])


class LymowStateSelect(LymowEntity, SelectEntity):
    """UI-friendly state selector for forcing mower status."""

    _attr_name = "State"
    _attr_unique_id = "virtual_lymow_state"
    _attr_options = OVERRIDE_OPTIONS
    _attr_icon = "mdi:tune-variant"

    @property
    def current_option(self) -> str:
        return self.coordinator.override_state

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_override_state(option)
