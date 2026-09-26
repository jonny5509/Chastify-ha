from __future__ import annotations

import json
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ChastifyCoordinator, field, lock_data


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
        if not self.coordinator.data:
            return None

        if self._data_key == "unlockable":
            value = _find_value(
                self.coordinator.data,
                {"unlockable", "readyToUnlock", "ready_to_unlock", "isUnlockable", "canUnlock"},
            )
        else:
            value = field(self.coordinator.data, self._data_key)

        if value is None:
            return None
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "on"}
        return bool(value)


def _find_value(value, keys: set[str]):
    """Find an unlock state anywhere in the Chastify response."""
    normalized_keys = {key.lower() for key in keys}

    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in normalized_keys:
                return child
        for child in value.values():
            found = _find_value(child, keys)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_value(child, keys)
            if found is not None:
                return found
    elif isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return None
        if isinstance(decoded, (dict, list)):
            return _find_value(decoded, keys)

    return None
