"""Camera entity for latest Lymow snapshot."""

from __future__ import annotations

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LymowEntity

_SNAPSHOT_UNIQUE_ID_SUFFIX = "snapshot"
LEGACY_SNAPSHOT_UNIQUE_IDS = {
    "mower_snapshot",
    "snapshot",
    "virtual_lymow_camera",
    "virtual_lymow_mower_snapshot",
    "virtual_lymow_snapshot",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    new_unique_id = f"{entry.entry_id}_{_SNAPSHOT_UNIQUE_ID_SUFFIX}"
    entity_registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if entity_entry.domain != "camera":
            continue
        if entity_entry.unique_id not in LEGACY_SNAPSHOT_UNIQUE_IDS:
            continue
        entity_registry.async_update_entity(
            entity_entry.entity_id,
            new_unique_id=new_unique_id,
        )

    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([LymowSnapshotCamera(coordinator)])


class LymowSnapshotCamera(LymowEntity, Camera):
    """Exposes most recent snapshot as a camera entity."""

    _unique_id_suffix = _SNAPSHOT_UNIQUE_ID_SUFFIX
    _attr_name = "Snapshot"

    def __init__(self, coordinator) -> None:
        LymowEntity.__init__(self, coordinator)
        Camera.__init__(self)

    async def async_camera_image(self, width=None, height=None):
        if self.coordinator.data is None or self.coordinator.data.image_bytes is None:
            await self.coordinator.async_request_refresh()
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.image_bytes
