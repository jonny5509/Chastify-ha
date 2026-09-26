from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
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
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities([
        ChastifySensor(coordinator, entry, "keyholder_last_seen", "Keyholder Last Seen", "keyholderLastSeenTimestamp"),
        ChastifySensor(coordinator, entry, "keyholder_username", "Keyholder Username", "keyholderUsername"),
        ChastifySensor(coordinator, entry, "lock_title", "Lock Title", "lockTitle"),
        ChastifyDurationSensor(coordinator, entry, "max_time_remaining", "Maximum Time Remaining", "maxTimeRemainingSeconds"),
        ChastifyDurationSensor(coordinator, entry, "session_role", "Session Role", "role"),
        ChastifyNumberSensor(coordinator, entry, "task_points", "Task Points", "taskPoints"),
        ChastifyDerivedNumberSensor(coordinator, entry, "task_points_remaining", "Task Points Remaining", _task_points_remaining),
        ChastifyNumberSensor(coordinator, entry, "task_points_required", "Task Points Required", "taskPointsRequired"),
        ChastifyDurationSensor(coordinator, entry, "time_locked", "Time Locked", "timeLockedSeconds"),
        ChastifyDurationSensor(coordinator, entry, "time_remaining", "Time Remaining", "timeRemainingSeconds"),
        ChastifySensor(coordinator, entry, "wearer_last_seen", "Wearer Last Seen", "wearerLastSeenTimestamp"),
        ChastifySensor(coordinator, entry, "wearer_username", "Wearer Username", "wearerUsername"),
    ])


class ChastifyBaseSensor(CoordinatorEntity[ChastifyCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:lock"

    def __init__(
        self, coordinator: ChastifyCoordinator, entry: ConfigEntry,
        key: str, name: str, device_id: str = "my_lock", device_name: str = "Session"
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{device_id}")},
            name=device_name,
            manufacturer="Chastify",
            model="Chastify Lock" if device_id == "my_lock" else "Chastify Keyholder",
        )


class ChastifySensor(ChastifyBaseSensor):
    _attr_icon = "mdi:account"

    def __init__(self, coordinator, entry, key, name, data_key, device_id="my_lock", device_name="Session"):
        super().__init__(coordinator, entry, key, name, device_id, device_name)
        self._data_key = data_key

    @property
    def native_value(self) -> str | None:
        value = field(self.coordinator.data, self._data_key)
        if value is None:
            return None

        if self._data_key.endswith("LastSeenTimestamp"):
            try:
                timestamp = float(value)
                # Chastify returns Unix timestamps in milliseconds.
                if timestamp > 10_000_000_000:
                    timestamp /= 1000
                self._attr_device_class = None
                return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%H:%M:%S")
            except (TypeError, ValueError, OverflowError):
                return None

        return str(value)


class ChastifyNumberSensor(ChastifyBaseSensor):
    _attr_icon = "mdi:star"
    _attr_native_unit_of_measurement = "points"

    def __init__(self, coordinator, entry, key, name, data_key, device_id="my_lock", device_name="Session"):
        super().__init__(coordinator, entry, key, name, device_id, device_name)
        self._data_key = data_key

    @property
    def native_value(self) -> int | float | None:
        return _number(field(self.coordinator.data, self._data_key))


class ChastifyDurationSensor(ChastifyBaseSensor):
    _attr_icon = "mdi:timer-outline"


    def __init__(self, coordinator, entry, key, name, data_key, device_id="my_lock", device_name="Session"):
        super().__init__(coordinator, entry, key, name, device_id, device_name)
        self._data_key = data_key

    @property
    def native_value(self) -> str | None:
        value = _number(field(self.coordinator.data, self._data_key))
        if value is None:
            return None
        total_seconds = max(0, int(value))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class ChastifyDerivedNumberSensor(ChastifyBaseSensor):
    _attr_icon = "mdi:chart-box-outline"
    _attr_native_unit_of_measurement = "points"

    def __init__(self, coordinator, entry, key, name, getter, device_id="my_lock", device_name="Session"):
        super().__init__(coordinator, entry, key, name, device_id, device_name)
        self._getter = getter

    @property
    def native_value(self) -> int | float | None:
        return self._getter(self.coordinator.data)


def _number(value: Any) -> int | float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _task_points_remaining(data: dict[str, Any]) -> int | float | None:
    points = _number(field(data, "taskPoints"))
    required = _number(field(data, "taskPointsRequired"))
    if points is None or required is None:
        return None
    return max(0, required - points)
