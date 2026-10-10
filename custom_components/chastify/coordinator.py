from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ChastifyApi, ChastifyApiError, ChastifyAuthError, ChastifyNoActiveSession
from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class ChastifyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, api: ChastifyApi, entry: ConfigEntry) -> None:
        self.api = api
        self.entry = entry
        self.last_success: datetime | None = None
        self.last_error: str | None = None
        super().__init__(
            hass, _LOGGER, name="Chastify", config_entry=entry,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            always_update=False,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        previous = self.data
        try:
            data = await self.api.async_get_session()
            self.last_success = datetime.now(timezone.utc)
            self.last_error = None
            old_active = bool(previous)
            new_active = bool(data)
            if previous is not None and old_active != new_active:
                self.hass.bus.async_fire(
                    "chastify_session_started" if new_active else "chastify_session_ended",
                    {"entry_id": self.entry.entry_id, "active": new_active},
                )
            if previous is not None and previous != data:
                self.hass.bus.async_fire(
                    "chastify_session_state_changed",
                    {"entry_id": self.entry.entry_id, "active": new_active},
                )
            return data
        except ChastifyNoActiveSession:
            self.last_success = datetime.now(timezone.utc)
            self.last_error = None
            if previous:
                self.hass.bus.async_fire(
                    "chastify_session_ended",
                    {"entry_id": self.entry.entry_id, "active": False},
                )
            return {}
        except ChastifyAuthError as err:
            self.last_error = str(err)
            raise ConfigEntryAuthFailed(str(err)) from err
        except ChastifyApiError as err:
            self.last_error = str(err)
            raise UpdateFailed(str(err)) from err


def lock_data(data: dict[str, Any]) -> dict[str, Any]:
    """Return Chastify's documented lockData object from /session."""
    if not isinstance(data, dict):
        return {}
    value = data.get("lockData")
    if isinstance(value, dict):
        return value
    for key in ("data", "session", "lock", "result"):
        value = data.get(key)
        if isinstance(value, dict):
            nested = value.get("lockData")
            if isinstance(nested, dict):
                return nested
    return data


def field(data: dict[str, Any], key: str) -> Any:
    """Read a session field from lockData or a response envelope."""
    if not isinstance(data, dict):
        return None
    value = lock_data(data)
    if isinstance(value, dict) and key in value:
        return value[key]
    candidates = [data]
    for name in ("data", "session", "lock", "result"):
        nested = data.get(name)
        if isinstance(nested, dict):
            candidates.append(nested)
            nested_lock = nested.get("lockData")
            if isinstance(nested_lock, dict):
                candidates.append(nested_lock)
    for candidate in candidates:
        if key in candidate:
            return candidate[key]
    return None
