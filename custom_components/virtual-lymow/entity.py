"""Shared Lymow entity base."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import LymowCoordinator


class LymowEntity(CoordinatorEntity[LymowCoordinator]):
    """Base class for Lymow entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LymowCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = {
            "identifiers": {("lymow", coordinator.entry.entry_id)},
            "name": "Lymow Mower",
            "manufacturer": "Lymow",
            "model": "RTSP Snapshot",
        }
