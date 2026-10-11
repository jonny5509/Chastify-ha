from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .api import (
    ChastifyApi,
    ChastifyApiError,
    ChastifyAuthError,
    ChastifyNoActiveSession,
)
from .const import (
    ATTR_COLOR,
    ATTR_COMMAND,
    ATTR_DESCRIPTION,
    ATTR_DURATION_SECONDS,
    ATTR_ICON,
    ATTR_NAME,
    ATTR_PARAMS,
    ATTR_ROLE,
    ATTR_SECONDS,
    ATTR_TITLE,
    CONF_TOKEN,
    DOMAIN,
    SERVICE_ACTION,
    SERVICE_ADD_TIME,
    SERVICE_APPLY_TIME,
    SERVICE_DEVICE_COMMAND,
    SERVICE_FREEZE,
    SERVICE_HYGIENIC_UNLOCK,
    SERVICE_LOG,
    SERVICE_REMOVE_TIME,
    SERVICE_UNFREEZE,
    SERVICE_TEST_NOTIFICATION,
)
from .coordinator import ChastifyCoordinator
from .notifications import ChastifyNotifications

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CALENDAR,
]

SERVICE_NAMES = (
    SERVICE_ACTION,
    SERVICE_APPLY_TIME,
    SERVICE_ADD_TIME,
    SERVICE_REMOVE_TIME,
    SERVICE_FREEZE,
    SERVICE_UNFREEZE,
    SERVICE_HYGIENIC_UNLOCK,
    SERVICE_LOG,
    SERVICE_DEVICE_COMMAND,
    SERVICE_TEST_NOTIFICATION,
)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    card_file = Path(__file__).resolve().parent / "www" / "chastify-card.js"
    if card_file.is_file():
        await hass.http.async_register_static_paths([StaticPathConfig("/chastify/chastify-card.js", str(card_file), cache_headers=False)])
        frontend.add_extra_js_url(hass, "/chastify/chastify-card.js")
    return True

async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate older installations and remove the retired last-seen sensor."""
    if entry.version < 14:
        entity_registry = er.async_get(hass)
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
            if "keyholder" in entity.unique_id:
                entity_registry.async_remove(entity.entity_id)
        hass.config_entries.async_update_entry(entry, version=14)

    if entry.version < 15:
        entity_registry = er.async_get(hass)
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
            if entity.unique_id.endswith("_keyholder_last_seen"):
                entity_registry.async_remove(entity.entity_id)
        hass.config_entries.async_update_entry(entry, version=15)

    if entry.version < 16:
        entity_registry = er.async_get(hass)
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
            if entity.unique_id.endswith("_wearer_last_seen"):
                entity_registry.async_remove(entity.entity_id)
        hass.config_entries.async_update_entry(entry, version=16)

    if entry.version < 17:
        entity_registry = er.async_get(hass)
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
            if entity.unique_id.endswith("_trusted"):
                entity_registry.async_remove(entity.entity_id)
        hass.config_entries.async_update_entry(entry, version=17)

    if entry.version < 18:
        entity_registry = er.async_get(hass)
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
            if entity.unique_id.endswith("_session_role"):
                entity_registry.async_update_entity(
                    entity.entity_id, name="Session Role"
                )
        hass.config_entries.async_update_entry(entry, version=18)

    if entry.version < 19:
        # Recreate Ready to unlock so installations with a stale/disabled
        # entity-registry entry get the current binary sensor.
        entity_registry = er.async_get(hass)
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
            if entity.unique_id.endswith("_ready_to_unlock"):
                entity_registry.async_remove(entity.entity_id)
        hass.config_entries.async_update_entry(entry, version=19)

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = ChastifyApi(entry.data[CONF_TOKEN], async_get_clientsession(hass))
    coordinator = ChastifyCoordinator(hass, api, entry)

    # Let the coordinator own the initial API refresh. This keeps a temporary
    # API outage from preventing the config entry from being loaded and lets
    # Home Assistant report auth failures as reauth requests.
    hass.data[DOMAIN][entry.entry_id] = {"api": api, "coordinator": coordinator}
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        await api.async_close()
        raise
    except Exception:
        # The coordinator records transient API failures as UpdateFailed.
        # Keep the entry available so the normal coordinator retry can recover.
        _LOGGER.exception("Initial Chastify refresh failed")

    notifications = ChastifyNotifications(hass, entry, coordinator)
    hass.data[DOMAIN][entry.entry_id]["notifications"] = notifications
    await notifications.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    my_lock = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_my_lock")},
        name="Session",
        manufacturer="Chastify",
        model="Chastify Lock",
    )
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if entity.device_id != my_lock.id:
            er.async_update_entity(entity.entity_id, device_id=my_lock.id)

    async def _call_api(func, *args):
        try:
            return await func(*args)
        except (ChastifyApiError, ChastifyNoActiveSession) as err:
            raise HomeAssistantError(f"Chastify API error: {err}") from err

    async def action(call: ServiceCall):
        await _call_api(api.async_action, call.data[ATTR_NAME], call.data.get(ATTR_PARAMS))

    async def apply_time(call: ServiceCall):
        await _call_api(api.async_apply_time, int(call.data[ATTR_SECONDS]))

    async def add_time(call: ServiceCall):
        await _call_api(api.async_apply_time, abs(int(call.data[ATTR_SECONDS])))

    async def remove_time(call: ServiceCall):
        await _call_api(api.async_apply_time, -abs(int(call.data[ATTR_SECONDS])))

    async def freeze(call: ServiceCall):
        await _call_api(api.async_freeze, call.data.get(ATTR_DURATION_SECONDS))

    async def unfreeze(call: ServiceCall):
        await _call_api(api.async_unfreeze)

    async def hygienic_unlock(call: ServiceCall):
        await _call_api(api.async_hygienic_unlock)

    async def custom_log(call: ServiceCall):
        await _call_api(
            api.async_custom_log,
            call.data[ATTR_TITLE], call.data.get(ATTR_DESCRIPTION),
            call.data.get(ATTR_ROLE), call.data.get(ATTR_ICON), call.data.get(ATTR_COLOR)
        )

    async def device_command(call: ServiceCall):
        await _call_api(api.async_device_command, call.data[ATTR_COMMAND], call.data.get(ATTR_PARAMS))

    registrations = {
        SERVICE_ACTION: (action, vol.Schema({vol.Required(ATTR_NAME): str, vol.Optional(ATTR_PARAMS): object})),
        SERVICE_APPLY_TIME: (apply_time, vol.Schema({vol.Required(ATTR_SECONDS): vol.Coerce(int)})),
        SERVICE_ADD_TIME: (add_time, vol.Schema({vol.Required(ATTR_SECONDS): vol.All(vol.Coerce(int), vol.Range(min=1))})),
        SERVICE_REMOVE_TIME: (remove_time, vol.Schema({vol.Required(ATTR_SECONDS): vol.All(vol.Coerce(int), vol.Range(min=1))})),
        SERVICE_FREEZE: (freeze, vol.Schema({vol.Optional(ATTR_DURATION_SECONDS): vol.All(vol.Coerce(int), vol.Range(min=60, max=86400))})),
        SERVICE_UNFREEZE: (unfreeze, vol.Schema({})),
        SERVICE_HYGIENIC_UNLOCK: (hygienic_unlock, vol.Schema({})),
        SERVICE_LOG: (custom_log, vol.Schema({vol.Required(ATTR_TITLE): str, vol.Optional(ATTR_DESCRIPTION): str, vol.Optional(ATTR_ROLE): vol.In(["extension", "wearer", "keyholder"]), vol.Optional(ATTR_ICON): str, vol.Optional(ATTR_COLOR): str})),
        SERVICE_DEVICE_COMMAND: (device_command, vol.Schema({vol.Required(ATTR_COMMAND): str, vol.Optional(ATTR_PARAMS): object})),
    }
    for name, (handler, schema) in registrations.items():
        if not hass.services.has_service(DOMAIN, name):
            hass.services.async_register(DOMAIN, name, handler, schema=schema)

    async def test_notification(call: ServiceCall) -> None:
        """Create a test persistent notification in Home Assistant only."""
        notification_manager = next(
            (item.get("notifications") for item in hass.data[DOMAIN].values()
             if isinstance(item, dict) and item.get("notifications") is not None),
            None,
        )
        if notification_manager is None:
            raise HomeAssistantError("Chastify notifications are not initialized")
        delivered = await notification_manager._notify(
            "Chastify test notification",
            call.data.get("message", "This is a test notification from Chastify."),
        )
        if not delivered:
            raise HomeAssistantError(
                "Unable to create a Home Assistant persistent notification. Check Home Assistant logs for details."
            )

    if not hass.services.has_service(DOMAIN, SERVICE_TEST_NOTIFICATION):
        hass.services.async_register(
            DOMAIN, SERVICE_TEST_NOTIFICATION, test_notification,
            schema=vol.Schema({vol.Optional("message"): str}),
        )
    return True

async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = hass.data[DOMAIN].get(entry.entry_id)
    if not data:
        return True

    if data.get("notifications"):
        await data["notifications"].async_stop()

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        for name in SERVICE_NAMES:
            if hass.services.has_service(DOMAIN, name):
                hass.services.async_remove(DOMAIN, name)
        await data["api"].async_close()
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unloaded
