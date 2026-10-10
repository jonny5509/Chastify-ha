"""Read-only Home Assistant calendar for the active Chastify session."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
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
    async_add_entities([ChastifyCalendar(coordinator, entry)])


class ChastifyCalendar(CoordinatorEntity[ChastifyCoordinator], CalendarEntity):
    """Expose the current Chastify session as an automatically updated calendar event."""

    _attr_has_entity_name = True
    _attr_name = "Session Calendar"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: ChastifyCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_session_calendar"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_my_lock")},
            name="Session",
            manufacturer="Chastify",
            model="Chastify Lock",
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current session event, if a valid session is active."""
        data = self.coordinator.data or {}
        if not data:
            return None

        start = _session_datetime(data, "startDate", ("start_date", "startedAt", "startTimestamp", "startDateTime"))
        end = _session_datetime(data, "endDate", ("end_date", "endsAt", "endTimestamp", "endDateTime"))

        locked = _number(field(data, "timeLockedSeconds"))
        remaining = _number(field(data, "timeRemainingSeconds"))
        now = datetime.now(timezone.utc)

        if start is None and locked is not None and remaining is not None:
            start = now - timedelta(seconds=max(0, locked - remaining))
        if end is None and remaining is not None:
            end = now + timedelta(seconds=max(0, remaining))

        if start is None or end is None or end <= start:
            return None

        title = field(data, "lockTitle") or field(data, "title") or "Chastify session"
        lock_type = field(data, "lockType") or field(data, "deviceType")
        description = "Chastify session"
        if lock_type:
            description += f" — {lock_type}"
        return CalendarEvent(
            summary=str(title),
            start=start,
            end=end,
            description=description,
            uid=f"{self.unique_id}:active-session",
        )

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return the active session if it overlaps the requested calendar range."""
        event = self.event
        if event is None:
            return []
        event_start = _as_datetime(event.start)
        event_end = _as_datetime(event.end)
        range_start = _as_datetime(start_date)
        range_end = _as_datetime(end_date)
        if event_start is None or event_end is None or range_start is None or range_end is None:
            return []
        if event_end <= range_start or event_start >= range_end:
            return []
        return [event]


def _session_datetime(
    data: dict[str, Any], primary: str, aliases: tuple[str, ...]
) -> datetime | None:
    value = field(data, primary)
    if value is None:
        for alias in aliases:
            value = field(data, alias)
            if value is not None:
                break
    return _parse_datetime(value)


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
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _number(value: Any) -> int | float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _as_datetime(value: datetime | date) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
    return None
