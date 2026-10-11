"""Configurable session milestone and completion notifications."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .calendar import _first_datetime, _session_bounds
from .const import (
    CONF_DAILY_NOTIFICATIONS,
    CONF_END_NOTIFICATIONS,
    CONF_NOTIFICATION_SERVICE,
    DEFAULT_NOTIFICATION_SERVICE,
    DOMAIN,
)
from .coordinator import ChastifyCoordinator

_LOGGER = logging.getLogger(__name__)
_STORAGE_VERSION = 1
_START_KEYS = (
    "startDate", "startAt", "startedAt", "start_date", "startTimestamp", "startDateTime"
)


class ChastifyNotifications:
    """Send daily and session-end notifications with persistent de-duplication."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, coordinator: ChastifyCoordinator):
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        configured_service = str(
            entry.options.get(CONF_NOTIFICATION_SERVICE, DEFAULT_NOTIFICATION_SERVICE)
        ).strip()
        self.service = (
            configured_service.split(".", 1)[1]
            if re.fullmatch(r"notify\.[a-z0-9_]+", configured_service)
            else DEFAULT_NOTIFICATION_SERVICE.split(".", 1)[1]
        )
        self.store: Store[dict[str, Any]] = Store(
            hass, _STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}_notification_state"
        )
        self.state: dict[str, Any] = {}
        self._unsub = None
        self._task = None
        self._save_task = None

    async def async_start(self) -> None:
        """Restore state and subscribe to coordinator updates."""
        saved = await self.store.async_load()
        if isinstance(saved, dict):
            self.state = saved
        self._unsub = self.coordinator.async_add_listener(self._handle_update)
        await self._process()

    async def async_stop(self) -> None:
        """Unsubscribe and wait for outstanding work."""
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

    async def _notify(self, title: str, message: str) -> bool:
        """Create a Home Assistant persistent notification only."""
        notification_id = (
            f"{DOMAIN}_{self.entry.entry_id}_"
            f"{hashlib.sha256((title + '|' + message).encode()).hexdigest()[:16]}"
        )
        try:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": title,
                    "message": message,
                    "notification_id": notification_id,
                },
                blocking=True,
            )
            return True
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unable to create Home Assistant persistent notification")
            return False

    async def _process(self) -> None:
        """Check daily milestones and session completion."""
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
            parsed_active_start = _parse(active_start)
            state_changed = False
            if not active_start or (
                explicit_start is not None
                and (
                    parsed_active_start is None
                    or abs((explicit_start - parsed_active_start).total_seconds()) > 90
                )
            ):
                self.state = {"active_start": start_iso, "last_daily_day": 0}
                active_start = start_iso
                state_changed = True

            # Keep inferred starts stable across coordinator polls.
            start = _parse(active_start) or start
            elapsed_days = max(0, int((now - start).total_seconds() // 86400))

            if (
                self.entry.options.get(CONF_DAILY_NOTIFICATIONS, True)
                and elapsed_days >= 1
                and elapsed_days > int(self.state.get("last_daily_day", 0))
            ):
                message = (
                    f"🎉 Congratulations! You've completed {elapsed_days} "
                    f"{'day' if elapsed_days == 1 else 'days'} of your Chastify session. "
                    "Keep it going!"
                )
                if await self._notify("Daily congratulations", message):
                    self.state["last_daily_day"] = elapsed_days
                    state_changed = True

            if state_changed:
                await self._save()

        elif active_start:
            start = _parse(active_start)
            if start is None:
                self.state = {}
                await self._save()
                return

            if self.entry.options.get(CONF_END_NOTIFICATIONS, True):
                days = max(0, int((now - start).total_seconds() // 86400))
                message = (
                    f"🏆 Congratulations! Your Chastify session has ended after {days} "
                    f"{'day' if days == 1 else 'days'}. Well done!"
                )
                # Retain state if delivery fails so the next coordinator update retries.
                if not await self._notify("Session completed", message):
                    return

            self.state = {}
            await self._save()

    async def _save(self) -> None:
        """Serialize storage writes so an older snapshot cannot overwrite a newer one."""
        snapshot = dict(self.state)
        previous = self._save_task
        self._save_task = self.hass.async_create_task(
            _save_snapshot(self.store, snapshot, previous)
        )
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
    """Parse a persisted timestamp as a UTC-aware datetime."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
