from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ChastifyCoordinator, field


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    # Remove sensor entities from older versions that are not in the requested list.
    async_add_entities([
        ChastifySensor(coordinator, entry, "keyholder_username", "Keyholder Username", "keyholderUsername"),
        ChastifySensor(coordinator, entry, "lock_title", "Lock Title", "lockTitle"),
        ChastifySensor(coordinator, entry, "lock_type", "Lock Type", "lockType"),
        ChastifySensor(coordinator, entry, "start_date", "Start Date", "startDate"),
        ChastifySensor(coordinator, entry, "end_date", "End Date", "endDate"),
        ChastifySensor(coordinator, entry, "timer_visible", "Timer Visible", "displayRemainingTime"),
        ChastifySensor(coordinator, entry, "session_role", "Session Role", "role"),
        ChastifyNumberSensor(coordinator, entry, "task_points", "Task Points", "taskPoints"),
        ChastifyDerivedNumberSensor(coordinator, entry, "task_points_remaining", "Task Points Remaining", _task_points_remaining),
        ChastifyNumberSensor(coordinator, entry, "task_points_required", "Task Points Required", "taskPointsRequired"),
        ChastifyDurationSensor(coordinator, entry, "time_locked", "Time Locked", "timeLockedSeconds"),
        ChastifyDurationSensor(coordinator, entry, "time_remaining", "Time Remaining", "timeRemainingSeconds"),
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
        if value is None and self._data_key == "lockType":
            # Chastify documents lockData.lockType inconsistently across API
            # versions. Some session responses expose the connected lock as
            # deviceType instead, so accept both forms.
            value = field(self.coordinator.data, "deviceType")
            if value is None:
                value = field(self.coordinator.data, "lock_type")
        if value is None and self._data_key == "displayRemainingTime":
            for key in ("timerVisible", "timer_visible", "showTimer", "showRemainingTime"):
                value = field(self.coordinator.data, key)
                if value is not None:
                    break
            if value is None:
                # If the API does not expose a dedicated visibility flag,
                # infer visibility from whether a remaining-time value exists.
                remaining = field(self.coordinator.data, "timeRemainingSeconds")
                if remaining is not None:
                    value = True

        if value is None and self._data_key == "startDate":
            for key in ("start_date", "startedAt", "startTimestamp", "startDateTime"):
                value = field(self.coordinator.data, key)
                if value is not None:
                    break
            # The current External API documents timeLockedSeconds and
            # timeRemainingSeconds, but not a startDate field. Derive the
            # session start from those authoritative counters.
            if value is None:
                locked = _number(field(self.coordinator.data, "timeLockedSeconds"))
                remaining = _number(field(self.coordinator.data, "timeRemainingSeconds"))
                if locked is not None and remaining is not None:
                    value = (datetime.now(timezone.utc) - timedelta(
                        seconds=max(0, locked - remaining)
                    )).isoformat()
        if value is None and self._data_key == "endDate":
            # API versions may omit endDate. Prefer explicit aliases, then
            # derive it from the session start and locked duration.
            for key in ("end_date", "endsAt", "endTimestamp", "endDateTime"):
                value = field(self.coordinator.data, key)
                if value is not None:
                    break
            if value is None:
                remaining = _number(field(self.coordinator.data, "timeRemainingSeconds"))
                if remaining is not None:
                    value = (datetime.now(timezone.utc) + timedelta(
                        seconds=max(0, remaining)
                    )).isoformat()

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
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "s"


    def __init__(self, coordinator, entry, key, name, data_key, device_id="my_lock", device_name="Session"):
        super().__init__(coordinator, entry, key, name, device_id, device_name)
        self._data_key = data_key

    @property
    def native_value(self) -> int | float | None:
        value = _number(field(self.coordinator.data, self._data_key))
        return None if value is None else max(0, value)


class ChastifyDerivedNumberSensor(ChastifyBaseSensor):
    _attr_icon = "mdi:chart-box-outline"
    _attr_native_unit_of_measurement = "points"

    def __init__(self, coordinator, entry, key, name, getter, device_id="my_lock", device_name="Session"):
        super().__init__(coordinator, entry, key, name, device_id, device_name)
        self._getter = getter

    @property
    def native_value(self) -> int | float | None:
        return self._getter(self.coordinator.data)


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        try:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


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
