"""Opt-in 24-hour session reminders and session-ended notifications."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.event import async_track_time_interval

from .coordinator import field
from .const import (
    CONF_ENABLE_PHONE_NOTIFICATIONS,
    CONF_ENABLE_HA_NOTIFICATIONS,
    CONF_NOTIFICATION_DESTINATION,
    CONF_NOTIFICATION_SERVICE,
    CONF_NOTIFICATION_TARGETS,
    CONF_NOTIFY_DAILY,
    CONF_NOTIFY_COMPLETION,
    CONF_NOTIFY_HA_DAILY,
    CONF_NOTIFY_HA_COMPLETION,
    DEFAULT_NOTIFICATION_SERVICE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
_CHECK_INTERVAL = timedelta(minutes=1)


def _timestamp(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        if isinstance(value, (int, float)):
            result = float(value)
            if result > 10_000_000_000:
                result /= 1000
            return result
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


class ChastifySessionNotifications:
    """Track session milestones and persist notification delivery state."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, coordinator) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self.store = Store(hass, 1, f"{DOMAIN}_session_notifications_{entry.entry_id}")

    def _destination(self) -> str:
        destination = self.entry.options.get(CONF_NOTIFICATION_DESTINATION)
        if destination in {"none", "ha", "phone", "both"}:
            return destination
        phone = self.entry.options.get(CONF_ENABLE_PHONE_NOTIFICATIONS, False)
        ha = self.entry.options.get(CONF_ENABLE_HA_NOTIFICATIONS, False)
        return "both" if phone and ha else "phone" if phone else "ha" if ha else "none"

    def _notification_targets(self) -> list[str]:
        """Return selected phone targets, supporting the legacy single target."""
        options = self.entry.options
        targets = options.get(CONF_NOTIFICATION_TARGETS)
        if targets is None:
            targets = [options.get(CONF_NOTIFICATION_SERVICE, DEFAULT_NOTIFICATION_SERVICE)]
        if isinstance(targets, str):
            targets = [targets]
        return [
            target.split(".", 1)[1]
            for target in targets
            if isinstance(target, str) and re.fullmatch(r"notify\.mobile_app_[a-z0-9_]+", target)
        ]

    async def async_start(self) -> None:
        saved = await self.store.async_load()
        if isinstance(saved, dict):
            self.state = saved
        else:
            self.state = {}
        self.entry.async_on_unload(
            async_track_time_interval(self.hass, self._tick, _CHECK_INTERVAL)
        )
        await self.async_check()

    async def _tick(self, _now: datetime) -> None:
        await self.async_check()

    async def _notify(self, title: str, message: str, event: str) -> bool:
        """Send to the selected phone targets and/or Home Assistant."""
        destination = self._destination()
        delivered = False
        if destination in {"phone", "both"}:
            for service in self._notification_targets():
                try:
                    await self.hass.services.async_call(
                        "notify", service, {"title": title, "message": message}, blocking=True
                    )
                    delivered = True
                except Exception:
                    _LOGGER.exception("Unable to send Chastify phone notification through notify.%s", service)
        if destination in {"ha", "both"}:
            try:
                await self.hass.services.async_call(
                    "persistent_notification", "create",
                    {"title": title, "message": message, "notification_id": f"{DOMAIN}_{self.entry.entry_id}_{event}"},
                    blocking=True,
                )
                delivered = True
            except Exception:
                _LOGGER.exception("Unable to create Chastify Home Assistant notification")
        return delivered

    async def async_check(self) -> None:
        data = self.coordinator.data
        if not isinstance(data, dict):
            return
        session = field(data, "lockData") if isinstance(data.get("lockData"), dict) else data
        if not isinstance(session, dict):
            session = {}
        active = bool(data)
        now = datetime.now(timezone.utc).timestamp()
        start_value = field(data, "startDate") or field(data, "start_date") or field(data, "startedAt") or field(data, "startTimestamp")
        # Only an API-provided start timestamp is authoritative. The fallback
        # derived from timeLockedSeconds can move slightly on every poll, so
        # never use it to decide that an existing session is a new session.
        authoritative_start = _timestamp(start_value)
        start = authoritative_start
        if start is None:
            locked = field(data, "timeLockedSeconds")
            try:
                locked_seconds = max(0.0, float(locked)) if locked is not None else None
            except (TypeError, ValueError):
                locked_seconds = None
            if locked_seconds is not None:
                start = now - locked_seconds
        name = str(field(data, "lockTitle") or field(data, "title") or "chastify session")
        changed = False

        if active and start is not None and start <= now:
            if not self.state.get("active_seen"):
                self.state["active_seen"] = True
                self.state["start"] = start
                changed = True
            elif authoritative_start is not None:
                saved_start = _timestamp(self.state.get("start"))
                # Reset the daily milestone only when the API confirms a
                # genuinely different session start (allowing minor rounding).
                if saved_start is None or abs(saved_start - authoritative_start) > 60:
                    self.state.update({
                        "start": authoritative_start,
                        "last_daily_day": 0,
                        "completion_notified": False,
                    })
                    changed = True
            elif self.state.get("start") is None:
                # Seed old/missing state once; keep it stable on later polls.
                self.state["start"] = start
                changed = True

            session_start = _timestamp(self.state.get("start"))
            if session_start is None:
                return
            elapsed_days = int(max(0, now - session_start) // 86400)
            if self._destination() != "none" and elapsed_days >= 1 and elapsed_days > int(self.state.get("last_daily_day", 0)):
                if await self._notify("Chastify daily congratulations", f"🎉 Congratulations! You've completed day number {elapsed_days} of your Chastify session. Keep it going!", "daily"):
                    self.state["last_daily_day"] = elapsed_days
                    changed = True
        elif not active and self.state.get("active_seen") and not self.state.get("completion_notified"):
            if self._destination() != "none":
                if await self._notify("Chastify session completed", f"🎉 Congratulations! Your {name} has been completed.", "completion"):
                    self.state["completion_notified"] = True
                    changed = True
            else:
                self.state["completion_notified"] = True
                changed = True
            self.state["active_seen"] = False
            changed = True

        if changed:
            await self.store.async_save(self.state)


async def async_setup_notifications(hass: HomeAssistant, entry: ConfigEntry, coordinator) -> None:
    """Start notifications only after a notification destination is enabled."""
    destination = entry.options.get(CONF_NOTIFICATION_DESTINATION)
    if destination not in {"none", "ha", "phone", "both"}:
        phone = entry.options.get(CONF_ENABLE_PHONE_NOTIFICATIONS, False)
        ha = entry.options.get(CONF_ENABLE_HA_NOTIFICATIONS, False)
        destination = "both" if phone and ha else "phone" if phone else "ha" if ha else "none"
    if destination == "none":
        return
    await ChastifySessionNotifications(hass, entry, coordinator).async_start()
