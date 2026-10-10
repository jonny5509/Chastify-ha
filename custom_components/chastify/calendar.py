"""Persistent Home Assistant calendar history for Chastify sessions."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ChastifyCoordinator, field


_STORAGE_VERSION = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([ChastifyCalendar(coordinator, entry)])


class ChastifyCalendar(CoordinatorEntity[ChastifyCoordinator], CalendarEntity):
    """Expose active sessions and retain completed sessions in local HA storage."""

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
        self._store: Store[dict[str, Any]] = Store(
            coordinator.hass, _STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}_calendar_history"
        )
        self._history: list[dict[str, Any]] = []

    async def async_added_to_hass(self) -> None:
        """Restore saved history before listening for coordinator updates."""
        await super().async_added_to_hass()
        saved = await self._store.async_load()
        if isinstance(saved, dict) and isinstance(saved.get("events"), list):
            self._history = [
                item for item in saved["events"]
                if isinstance(item, dict)
                and isinstance(item.get("start"), str)
                and isinstance(item.get("end"), str)
                and isinstance(item.get("uid"), str)
            ]
        self._record_current_snapshot()

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current session event, if a valid session is active."""
        data = self.coordinator.data or {}
        if not data:
            return None

        now = datetime.now(timezone.utc)
        updated_at = getattr(self.coordinator, "last_update_success_time", None)
        if not isinstance(updated_at, datetime):
            updated_at = now
        elif updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        else:
            updated_at = updated_at.astimezone(timezone.utc)

        start, end = _session_bounds(data, updated_at)
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
            uid=_session_uid(self.unique_id, start, str(title)),
        )

    def _handle_coordinator_update(self) -> None:
        """Update persisted history whenever the API snapshot changes."""
        self._record_current_snapshot()
        super()._handle_coordinator_update()

    def _record_current_snapshot(self) -> None:
        data = self.coordinator.data
        event = self.event
        changed = False
        active_records = [item for item in self._history if item.get("active")]

        if event is not None:
            start = _as_datetime(event.start)
            end = _as_datetime(event.end)
            if start is None or end is None:
                return
            # If a new session replaces the previous one without an empty
            # snapshot between them, close the previous event at observation time.
            for item in active_records:
                if item.get("uid") != event.uid:
                    item["end"] = datetime.now(timezone.utc).isoformat()
                    item["active"] = False
                    changed = True
            record = next((item for item in self._history if item.get("uid") == event.uid), None)
            serialized = {
                "uid": str(event.uid),
                "summary": event.summary,
                "description": event.description or "",
                "start": start.isoformat(),
                "end": end.isoformat(),
                "active": True,
            }
            if record is None:
                self._history.append(serialized)
                changed = True
            elif record != serialized:
                record.update(serialized)
                changed = True
        elif data == {}:
            # An empty snapshot means Chastify confirmed there is no active
            # session. Preserve the event, with its observed completion time.
            finished_at = datetime.now(timezone.utc).isoformat()
            for item in active_records:
                item["end"] = finished_at
                item["active"] = False
                changed = True

        if changed:
            self.hass.async_create_task(self._store.async_save({"events": self._history}))

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return all saved sessions overlapping the requested date range."""
        range_start = _as_datetime(start_date)
        range_end = _as_datetime(end_date)
        if range_start is None or range_end is None:
            return []

        # Make sure the latest active snapshot is represented even before the
        # coordinator's update listener has had a chance to persist it.
        current = self.event
        records = list(self._history)
        if current is not None:
            current_start = _as_datetime(current.start)
            current_end = _as_datetime(current.end)
            if current_start and current_end:
                active = {
                    "uid": str(current.uid),
                    "summary": current.summary,
                    "description": current.description or "",
                    "start": current_start.isoformat(),
                    "end": current_end.isoformat(),
                    "active": True,
                }
                records = [item for item in records if item.get("uid") != active["uid"]]
                records.append(active)

        events: list[CalendarEvent] = []
        for item in records:
            start = _parse_datetime(item.get("start"))
            end = _parse_datetime(item.get("end"))
            if start is None or end is None or end <= range_start or start >= range_end:
                continue
            events.append(
                CalendarEvent(
                    summary=str(item.get("summary") or "Chastify session"),
                    start=start,
                    end=end,
                    description=str(item.get("description") or ""),
                    uid=str(item["uid"]),
                )
            )
        return sorted(events, key=lambda item: _as_datetime(item.start) or datetime.min.replace(tzinfo=timezone.utc))


def _session_uid(unique_id: str, start: datetime, title: str) -> str:
    """Create a stable identifier for one session's history record."""
    return f"{unique_id}:{start.astimezone(timezone.utc).isoformat()}:{title}"


def _session_bounds(
    data: dict[str, Any], updated_at: datetime
) -> tuple[datetime | None, datetime | None]:
    """Calculate stable event bounds from the latest Chastify session snapshot."""
    start = _session_datetime(
        data, "startDate", ("start_date", "startedAt", "startTimestamp", "startDateTime")
    )
    end = _session_datetime(
        data, "endDate", ("end_date", "endsAt", "endTimestamp", "endDateTime")
    )
    locked = _number(field(data, "timeLockedSeconds"))
    remaining = _number(field(data, "timeRemainingSeconds"))
    if remaining is not None:
        end = updated_at + timedelta(seconds=max(0, remaining))
    if start is None and locked is not None:
        start = updated_at - timedelta(seconds=max(0, locked))
    return start, end


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
