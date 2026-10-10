from __future__ import annotations

import logging
from pathlib import Path
from datetime import datetime, timezone
import voluptuous as vol
from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import device_registry as dr, entity_registry as er
from .api import ChastifyApi, ChastifyApiError, ChastifyAuthError, ChastifyNoActiveSession
from .const import *
from .coordinator import ChastifyCoordinator, field

_LOGGER = logging.getLogger(__name__)


def _read_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return None


CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]
SERVICE_NAMES = (SERVICE_ACTION, SERVICE_APPLY_TIME, SERVICE_ADD_TIME, SERVICE_REMOVE_TIME, SERVICE_FREEZE, SERVICE_UNFREEZE, SERVICE_HYGIENIC_UNLOCK, SERVICE_LOG, SERVICE_DEVICE_COMMAND, SERVICE_NOTIFICATION, SERVICE_TOGGLE_FREEZE)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    card = Path(__file__).resolve().parent / "www" / "chastify-card.js"
    if card.is_file():
        await hass.http.async_register_static_paths([StaticPathConfig("/chastify/chastify-card.js", str(card), cache_headers=False)])
        frontend.add_extra_js_url(hass, "/chastify/chastify-card.js")
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    registry = er.async_get(hass)
    migrations = {
        14: lambda entity: "keyholder" in entity.unique_id,
        15: lambda entity: entity.unique_id.endswith("_keyholder_last_seen"),
        16: lambda entity: entity.unique_id.endswith("_wearer_last_seen"),
        17: lambda entity: entity.unique_id.endswith("_trusted"),
    }
    for version, should_remove in migrations.items():
        if entry.version < version:
            for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
                if should_remove(entity):
                    registry.async_remove(entity.entity_id)
            hass.config_entries.async_update_entry(entry, version=version)
    if entry.version < 18:
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
            if entity.unique_id.endswith("_session_role"):
                registry.async_update_entity(entity.entity_id, name="Session Role")
        hass.config_entries.async_update_entry(entry, version=18)
    if entry.version < 19:
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
            if entity.unique_id.endswith("_ready_to_unlock"):
                registry.async_remove(entity.entity_id)
        hass.config_entries.async_update_entry(entry, version=19)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = ChastifyApi(entry.data[CONF_TOKEN], async_get_clientsession(hass), lock_id=entry.data.get(CONF_LOCK_ID) or None)
    coordinator = ChastifyCoordinator(hass, api, entry)
    hass.data[DOMAIN][entry.entry_id] = {"api": api, "coordinator": coordinator}
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        await api.async_close()
        raise
    except Exception:
        _LOGGER.exception("Initial Chastify refresh failed")
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    device = device_registry.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, f"{entry.entry_id}_my_lock")}, name="Session", manufacturer="Chastify", model="Chastify Lock")
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if entity.device_id != device.id:
            er.async_update_entity(entity.entity_id, device_id=device.id)

    async def call_api(func, *args, label: str | None = None):
        action_label = label or func.__name__.replace("async_", "").replace("_", " ").capitalize()
        try:
            result = await func(*args)
            coordinator.last_action_result = f"{action_label}: succeeded"
            coordinator.last_action_time = datetime.now(timezone.utc)
            coordinator.async_update_listeners()
            return result
        except (ChastifyApiError, ChastifyNoActiveSession) as err:
            coordinator.last_action_result = f"{action_label}: failed — {err}"
            coordinator.last_action_time = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            coordinator.async_update_listeners()
            raise HomeAssistantError(f"Chastify API error: {err}") from err

    async def action(call: ServiceCall):
        await call_api(api.async_action, call.data[ATTR_NAME], call.data.get(ATTR_PARAMS))
    async def apply_time(call: ServiceCall):
        await call_api(api.async_apply_time, int(call.data[ATTR_SECONDS]))
    async def add_time(call: ServiceCall):
        await call_api(api.async_apply_time, abs(int(call.data[ATTR_SECONDS])))
    async def remove_time(call: ServiceCall):
        await call_api(api.async_apply_time, -abs(int(call.data[ATTR_SECONDS])))
    async def freeze(call: ServiceCall):
        await call_api(api.async_freeze, call.data.get(ATTR_DURATION_SECONDS))
    async def unfreeze(call: ServiceCall):
        await call_api(api.async_unfreeze)
    async def hygienic_unlock(call: ServiceCall):
        await call_api(api.async_hygienic_unlock)
    async def custom_log(call: ServiceCall):
        await call_api(api.async_custom_log, call.data[ATTR_TITLE], call.data.get(ATTR_DESCRIPTION), call.data.get(ATTR_ROLE), call.data.get(ATTR_ICON), call.data.get(ATTR_COLOR))
    async def device_command(call: ServiceCall):
        await call_api(api.async_device_command, call.data[ATTR_COMMAND], call.data.get(ATTR_PARAMS))
    async def notification(call: ServiceCall):
        await call_api(api.async_custom_notification, call.data[ATTR_TITLE], call.data[ATTR_MESSAGE], call.data.get(ATTR_TARGET, "wearer"), call.data.get(ATTR_SHOW_PAGE_OVERLAY, False))
    async def toggle_freeze(call: ServiceCall):
        if not coordinator.data:
            raise HomeAssistantError("Cannot toggle freeze without an active Chastify session.")
        frozen = _read_bool(field(coordinator.data, "frozen"))
        if frozen is None:
            raise HomeAssistantError("Cannot determine whether the Chastify session is frozen; use freeze or unfreeze explicitly.")
        if frozen:
            await call_api(api.async_unfreeze, label="Toggle freeze (unfreeze)")
        else:
            await call_api(api.async_freeze, call.data.get(ATTR_DURATION_SECONDS), label="Toggle freeze (freeze)")

    schemas = {
        SERVICE_TOGGLE_FREEZE: (toggle_freeze, vol.Schema({vol.Optional(ATTR_DURATION_SECONDS): vol.All(vol.Coerce(int), vol.Range(min=60, max=86400))})),
        SERVICE_ACTION: (action, vol.Schema({vol.Required(ATTR_NAME): str, vol.Optional(ATTR_PARAMS): object})),
        SERVICE_APPLY_TIME: (apply_time, vol.Schema({vol.Required(ATTR_SECONDS): vol.Coerce(int)})),
        SERVICE_ADD_TIME: (add_time, vol.Schema({vol.Required(ATTR_SECONDS): vol.All(vol.Coerce(int), vol.Range(min=1))})),
        SERVICE_REMOVE_TIME: (remove_time, vol.Schema({vol.Required(ATTR_SECONDS): vol.All(vol.Coerce(int), vol.Range(min=1))})),
        SERVICE_FREEZE: (freeze, vol.Schema({vol.Optional(ATTR_DURATION_SECONDS): vol.All(vol.Coerce(int), vol.Range(min=60, max=86400))})),
        SERVICE_UNFREEZE: (unfreeze, vol.Schema({})),
        SERVICE_HYGIENIC_UNLOCK: (hygienic_unlock, vol.Schema({})),
        SERVICE_LOG: (custom_log, vol.Schema({vol.Required(ATTR_TITLE): str, vol.Optional(ATTR_DESCRIPTION): str, vol.Optional(ATTR_ROLE): vol.In(["extension", "wearer", "keyholder"]), vol.Optional(ATTR_ICON): str, vol.Optional(ATTR_COLOR): str})),
        SERVICE_DEVICE_COMMAND: (device_command, vol.Schema({vol.Required(ATTR_COMMAND): str, vol.Optional(ATTR_PARAMS): object})),
        SERVICE_NOTIFICATION: (notification, vol.Schema({vol.Required(ATTR_TITLE): str, vol.Required(ATTR_MESSAGE): str, vol.Optional(ATTR_TARGET, default="wearer"): vol.In(["wearer", "keyholder", "both"]), vol.Optional(ATTR_SHOW_PAGE_OVERLAY, default=False): bool})),
    }
    for name, (handler, schema) in schemas.items():
        if not hass.services.has_service(DOMAIN, name):
            hass.services.async_register(DOMAIN, name, handler, schema=schema)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = hass.data[DOMAIN].get(entry.entry_id)
    if not data:
        return True
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        for name in SERVICE_NAMES:
            if hass.services.has_service(DOMAIN, name):
                hass.services.async_remove(DOMAIN, name)
        await data["api"].async_close()
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
