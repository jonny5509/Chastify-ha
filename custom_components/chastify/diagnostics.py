from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_TOKEN, DOMAIN

_SENSITIVE_KEYS = {"token", "apikey", "api_key", "password", "authorization", "secret"}


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _sanitize(item)
            for key, item in value.items()
            if str(key).lower() not in _SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _account(data: Any) -> Any:
    if not isinstance(data, dict):
        return None
    for source in (data, data.get("data")):
        if isinstance(source, dict):
            for key in ("account", "user", "profile", "me"):
                value = source.get(key)
                if isinstance(value, dict):
                    return _sanitize(value)
    return None


def _history(data: dict[str, Any]) -> Any:
    payload = data.get("data", data)
    if not isinstance(payload, dict):
        return []
    for key in ("history", "lockHistory", "logs", "events"):
        value = payload.get(key)
        if isinstance(value, (list, dict)):
            return _sanitize(value)
    lock_data = payload.get("lockData")
    if isinstance(lock_data, dict):
        for key in ("history", "lockHistory", "logs", "events"):
            value = lock_data.get(key)
            if isinstance(value, (list, dict)):
                return _sanitize(value)
    return []


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    data = hass.data.get(DOMAIN, {})
    entry_data = data.get(entry.entry_id, {})
    coordinator = entry_data.get("coordinator") if isinstance(entry_data, dict) else None
    payload = coordinator.data if coordinator and isinstance(coordinator.data, dict) else {}
    return {
        "account": _account(payload),
        "current_lock": _sanitize(payload.get("data", payload).get("lockData") if isinstance(payload.get("data", payload), dict) else None),
        "current_lock_history": _history(payload),
        "configured": bool(entry.data.get(CONF_TOKEN)),
        "entry_id": entry.entry_id,
    }
