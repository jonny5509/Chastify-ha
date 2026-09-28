from __future__ import annotations

from datetime import timedelta
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
        super().__init__(
            hass,
            _LOGGER,
            name="Chastify",
            config_entry=entry,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            always_update=False,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.api.async_get_session()
        except ChastifyNoActiveSession:
            # A valid DEV token can exist when there is no active lock.
            return {}
        except ChastifyAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except ChastifyApiError as err:
            raise UpdateFailed(str(err)) from err


def lock_data(data: dict[str, Any]) -> dict[str, Any]:
    """Return Chastify's documented lockData object from /session."""
    if not isinstance(data, dict):
        return {}

    # The External API documents /session as returning lockData directly.
    value = data.get("lockData")
    if isinstance(value, dict):
        return value

    # Be tolerant of response envelopes used by older API versions.
    for key in ("data", "session", "lock"):
        value = data.get(key)
        if isinstance(value, dict):
            nested = value.get("lockData")
            if isinstance(nested, dict):
                return nested

    # Some API responses expose the lock fields directly.
    return data

def field(data: dict[str, Any], key: str) -> Any:
    """Read a session field from lockData or any documented response envelope."""
    if not isinstance(data, dict):
        return None

    # Prefer the documented lockData object.
    value = lock_data(data)
    if isinstance(value, dict) and key in value:
        return value[key]

    # Some API responses keep session-level values beside lockData.
    # Search the common envelopes as well instead of letting lockData mask them.
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
