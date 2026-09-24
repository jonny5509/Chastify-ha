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
    # The API may wrap the session payload in a top-level "data" object.
    payload = data.get("data", data)
    if not isinstance(payload, dict):
        return {}

    value = payload.get("lockData", payload)
    return value if isinstance(value, dict) else {}


def field(data: dict[str, Any], key: str) -> Any:
    payload = data.get("data", data)
    if not isinstance(payload, dict):
        return None

    return lock_data(data).get(key, payload.get(key))
