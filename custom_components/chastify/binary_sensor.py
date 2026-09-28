from __future__ import annotations

import json

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
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

    registry = er.async_get(hass)
    allowed = {"Locked", "Ready to unlock", "Frozen", "Task Assigned"}
    for entity in list(registry.entities.values()):
        if entity.config_entry_id == entry.entry_id and entity.domain == "binary_sensor":
            if (entity.original_name or entity.name or "") not in allowed:
                registry.async_remove(entity.entity_id)

    async_add_entities([
        ChastifyBinary(coordinator, entry, "frozen", "Frozen", "frozen"),
        ChastifyBinary(coordinator, entry, "locked", "Locked", "locked"),
        ChastifyBinary(coordinator, entry, "ready_to_unlock", "Ready to unlock", "unlockable"),
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
            return False

        if self._data_key == "unlockable":
            payload = lock_data(self.coordinator.data)
            value = payload.get("unlockable")
            if value is None:
                value = _find_value(
                    self.coordinator.data,
                    {"unlockable", "readyToUnlock", "ready_to_unlock", "isUnlockable", "canUnlock"},
                )
        elif self._data_key == "locked":
            value = bool(self.coordinator.data)
        else:
            value = field(self.coordinator.data, self._data_key)

        return _as_bool(value)


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return False
        return _as_bool(decoded) if decoded != value else False
    return False


def _find_value(value, keys: set[str]):
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
