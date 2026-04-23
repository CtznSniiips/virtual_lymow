"""Camera entity for latest Lymow snapshot."""

from __future__ import annotations

from homeassistant.components.camera import Camera
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
    async_add_entities([LymowSnapshotCamera(coordinator)])


class LymowSnapshotCamera(LymowEntity, Camera):
    """Exposes most recent snapshot as a camera entity."""

    _attr_name = "Mower Snapshot"
    _attr_unique_id = "lymow_snapshot"

    async def async_camera_image(self, width=None, height=None):
        if self.coordinator.data.image_bytes is None:
            await self.coordinator.async_request_refresh()
        return self.coordinator.data.image_bytes
