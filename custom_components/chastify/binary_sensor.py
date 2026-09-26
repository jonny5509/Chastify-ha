from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ChastifyCoordinator, field


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([
        ChastifyBinary(coordinator, entry, "frozen", "Frozen", "frozen"),
        ChastifyBinary(coordinator, entry, "ready_to_unlock", "Ready to unlock", "unlockable"),
        ChastifyBinary(coordinator, entry, "trusted", "Trusted", "trusted"),
        ChastifyBinary(coordinator, entry, "task_assigned", "Task Assigned", "taskAssigned"),
    ])


class ChastifyBinary(CoordinatorEntity[ChastifyCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:lock-check"

    def __init__(self, coordinator, entry, key, name, data_key, device_id="my_lock", device_name="Session"):
        super().__init__(coordinator)
        self._data_key = data_key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{device_id}")},
            name=device_name,
            manufacturer="Chastify",
            model="Chastify Lock" if device_id == "my_lock" else "Chastify Keyholder",
        )

    @property
    def is_on(self) -> bool | None:
        value = field(self.coordinator.data, self._data_key)
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "on"}
        return bool(value)
