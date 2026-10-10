"""Configurable session congratulations notifications."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .calendar import _first_datetime, _session_bounds
from .const import CONF_DAILY_NOTIFICATIONS, CONF_END_NOTIFICATIONS, DOMAIN
from .coordinator import ChastifyCoordinator

_LOGGER = logging.getLogger(__name__)
_STORAGE_VERSION = 1
_START_KEYS = (
    "startDate", "startAt", "startedAt", "start_date", "startTimestamp", "startDateTime"
)


class ChastifyNotifications:
    """Send daily and session-end notifications, with persisted de-duplication."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, coordinator: ChastifyCoordinator):
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self.store: Store[dict[str, Any]] = Store(
            hass, _STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}_notification_state"
        )
        self.state: dict[str, Any] = {}
        self._unsub = None
        self._task = None
        self._save_task = None

    async def async_start(self) -> None:
        saved = await self.store.async_load()
        if isinstance(saved, dict):
            self.state = saved
        self._unsub = self.coordinator.async_add_listener(self._handle_update)
        await self._process()

    async def async_stop(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None
        if self._task:
            await self._task
        if self._save_task:
            await self._save_task

    @callback
    def _handle_update(self) -> None:
        if self._task is None or self._task.done():
            self._task = self.hass.async_create_task(self._process())

    async def _process(self) -> None:
        data = self.coordinator.data
        if not isinstance(data, dict):
            return
        now = datetime.now(timezone.utc)
        active_start = self.state.get("active_start")
        if data:
            explicit_start = _first_datetime(data, _START_KEYS)
            start, _ = _session_bounds(data, now)
            if explicit_start is not None:
                start = explicit_start
            if start is None:
                return
            start_iso = start.astimezone(timezone.utc).isoformat()
            if not active_start or (
                explicit_start is not None
                and abs((explicit_start - _parse(active_start)).total_seconds()) > 90
            ):
                self.state = {"active_start": start_iso, "last_daily_day": 0}
                active_start = start_iso
            # If no explicit timestamp exists, retain the first observed inferred
            # start so the timer does not drift between coordinator polls.
            start = _parse(active_start) or start
            elapsed_days = max(0, int((now - start).total_seconds() // 86400))
            if self.entry.options.get(CONF_DAILY_NOTIFICATIONS, True) and elapsed_days > int(self.state.get("last_daily_day", 0)):
                await self.hass.services.async_call(
                    "persistent_notification", "create",
                    {
                        "title": "🎉 Chastify congratulations!",
                        "message": f"Congratulations! You've reached Day {elapsed_days} of your Chastify session.",
                        "notification_id": f"chastify_{self.entry.entry_id}_day_{elapsed_days}",
                    },
                    blocking=True,
                )
                self.state["last_daily_day"] = elapsed_days
                await self._save()
            elif not self.state.get("active_start"):
                self.state["active_start"] = start_iso
                await self._save()
        elif data == {} and active_start:
            start = _parse(active_start)
            if start is not None and self.entry.options.get(CONF_END_NOTIFICATIONS, True):
                days = max(0, int((now - start).total_seconds() // 86400))
                await self.hass.services.async_call(
                    "persistent_notification", "create",
                    {
                        "title": "🎉 Chastify session complete!",
                        "message": f"Congratulations on completing your Chastify session after {days} full day(s)!",
                        "notification_id": f"chastify_{self.entry.entry_id}_session_end",
                    },
                    blocking=True,
                )
            self.state = {}
            await self._save()

    async def _save(self) -> None:
        snapshot = dict(self.state)
        previous = self._save_task
        self._save_task = self.hass.async_create_task(_save_snapshot(self.store, snapshot, previous))
        await self._save_task


async def _save_snapshot(store: Store, snapshot: dict[str, Any], previous: Any) -> None:
    if previous:
        try:
            await previous
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Previous Chastify notification state save failed")
    try:
        await store.async_save(snapshot)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Unable to save Chastify notification state")


def _parse(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
