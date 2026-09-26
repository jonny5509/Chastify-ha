from __future__ import annotations

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
        data = self.coordinator.data
        value = field(data, self._data_key)

        # Chastify documents this as lockData.unlockable, but accept
        # equivalent names in case the API response varies by version.
        if self._data_key == "unlockable":
            # Prefer the documented lockData.unlockable value, then fall
            # back to equivalent spellings anywhere in the session payload.
            payload = lock_data(data)
            value = payload.get("unlockable", value)
            if value is None:
                value = _find_value(data, {"readyToUnlock", "ready_to_unlock"})

        if value is None:
            return None
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "on"}
        return bool(value)



def _find_value(value, keys: set[str]):
    """Find a boolean-like field in nested Chastify response data."""
    if isinstance(value, dict):
        for key in keys:
            if key in value:
                return value[key]
        for child in value.values():
            found = _find_value(child, keys)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_value(child, keys)
            if found is not None:
                return found
    return None
