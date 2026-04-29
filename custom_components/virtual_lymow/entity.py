"""Shared Lymow entity base."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MOWER_NAME
from .coordinator import LymowCoordinator


class LymowEntity(CoordinatorEntity[LymowCoordinator]):
    """Base class for Lymow entities."""

    _attr_has_entity_name = True
    _unique_id_suffix: str  # each subclass declares this

    def __init__(self, coordinator: LymowCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{self._unique_id_suffix}"
        self._attr_device_info = {
            "identifiers": {("virtual_lymow", coordinator.entry.entry_id)},
            "name": coordinator.entry.data.get(CONF_MOWER_NAME, "Lymow Mower"),
            "manufacturer": "Lymow",
            "model": "RTSP Snapshot",
        }
