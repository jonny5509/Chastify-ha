from __future__ import annotations

from pathlib import Path
import voluptuous as vol

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .api import ChastifyApi
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
)
from .coordinator import ChastifyCoordinator


CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]


def _get_coordinator(hass: HomeAssistant) -> ChastifyCoordinator:
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries or entries[0].runtime_data is None:
        raise ServiceValidationError("Chastify is not loaded")
    return entries[0].runtime_data


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Chastify services and the optional Lovelace card."""
    card_file = Path(__file__).resolve().parent / "www" / "chastify-card.js"
    if card_file.is_file():
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    "/chastify/chastify-card.js",
                    str(card_file),
                    cache_headers=False,
                )
            ]
        )
        frontend.add_extra_js_url(hass, "/chastify/chastify-card.js")

    async def action(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        await coordinator.api.async_action(call.data[ATTR_NAME], call.data.get(ATTR_PARAMS))

    async def apply_time(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        await coordinator.api.async_apply_time(int(call.data[ATTR_SECONDS]))

    async def add_time(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        await coordinator.api.async_apply_time(abs(int(call.data[ATTR_SECONDS])))

    async def remove_time(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        await coordinator.api.async_apply_time(-abs(int(call.data[ATTR_SECONDS])))

    async def freeze(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        await coordinator.api.async_freeze(call.data.get(ATTR_DURATION_SECONDS))

    async def unfreeze(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        await coordinator.api.async_unfreeze()

    async def hygienic_unlock(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        await coordinator.api.async_hygienic_unlock()

    async def custom_log(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        await coordinator.api.async_custom_log(
            call.data[ATTR_TITLE],
            call.data.get(ATTR_DESCRIPTION),
            call.data.get(ATTR_ROLE),
            call.data.get(ATTR_ICON),
            call.data.get(ATTR_COLOR),
        )

    async def device_command(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        await coordinator.api.async_device_command(
            call.data[ATTR_COMMAND], call.data.get(ATTR_PARAMS)
        )

    registrations = {
        SERVICE_ACTION: (
            action,
            vol.Schema(
                {
                    vol.Required(ATTR_NAME): str,
                    vol.Optional(ATTR_PARAMS): object,
                }
            ),
        ),
        SERVICE_APPLY_TIME: (
            apply_time,
            vol.Schema({vol.Required(ATTR_SECONDS): vol.Coerce(int)}),
        ),
        SERVICE_ADD_TIME: (
            add_time,
            vol.Schema(
                {
                    vol.Required(ATTR_SECONDS): vol.All(
                        vol.Coerce(int), vol.Range(min=1)
                    )
                }
            ),
        ),
        SERVICE_REMOVE_TIME: (
            remove_time,
            vol.Schema(
                {
                    vol.Required(ATTR_SECONDS): vol.All(
                        vol.Coerce(int), vol.Range(min=1)
                    )
                }
            ),
        ),
        SERVICE_FREEZE: (
            freeze,
            vol.Schema(
                {
                    vol.Optional(ATTR_DURATION_SECONDS): vol.All(
                        vol.Coerce(int), vol.Range(min=60, max=86400)
                    )
                }
            ),
        ),
        SERVICE_UNFREEZE: (unfreeze, vol.Schema({})),
        SERVICE_HYGIENIC_UNLOCK: (hygienic_unlock, vol.Schema({})),
        SERVICE_LOG: (
            custom_log,
            vol.Schema(
                {
                    vol.Required(ATTR_TITLE): str,
                    vol.Optional(ATTR_DESCRIPTION): str,
                    vol.Optional(ATTR_ROLE): vol.In(
                        ["extension", "wearer", "keyholder"]
                    ),
                    vol.Optional(ATTR_ICON): str,
                    vol.Optional(ATTR_COLOR): str,
                }
            ),
        ),
        SERVICE_DEVICE_COMMAND: (
            device_command,
            vol.Schema(
                {
                    vol.Required(ATTR_COMMAND): str,
                    vol.Optional(ATTR_PARAMS): object,
                }
            ),
        ),
    }

    for name, (handler, schema) in registrations.items():
        hass.services.async_register(DOMAIN, name, handler, schema=schema)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate older installations and remove retired entities."""
    from homeassistant.helpers import entity_registry as er

    entity_registry = er.async_get(hass)

    if entry.version < 14:
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
            if "keyholder" in entity.unique_id:
                entity_registry.async_remove(entity.entity_id)
        hass.config_entries.async_update_entry(entry, version=14)

    if entry.version < 15:
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
            if entity.unique_id.endswith("_keyholder_last_seen"):
                entity_registry.async_remove(entity.entity_id)
        hass.config_entries.async_update_entry(entry, version=15)

    if entry.version < 16:
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
            if entity.unique_id.endswith("_wearer_last_seen"):
                entity_registry.async_remove(entity.entity_id)
        hass.config_entries.async_update_entry(entry, version=16)

    if entry.version < 17:
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
            if entity.unique_id.endswith("_trusted"):
                entity_registry.async_remove(entity.entity_id)
        hass.config_entries.async_update_entry(entry, version=17)

    if entry.version < 18:
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
            if entity.unique_id.endswith("_session_role"):
                entity_registry.async_update_entity(
                    entity.entity_id, name="Session Role"
                )
        hass.config_entries.async_update_entry(entry, version=18)

    if entry.version < 19:
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
            if entity.unique_id.endswith("_ready_to_unlock"):
                entity_registry.async_remove(entity.entity_id)
        hass.config_entries.async_update_entry(entry, version=19)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Chastify config entry."""
    api = ChastifyApi(entry.data[CONF_TOKEN])
    coordinator = ChastifyCoordinator(hass, api, entry)
    entry.runtime_data = coordinator

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await api.async_close()
        entry.runtime_data = None
        raise

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Chastify config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and entry.runtime_data is not None:
        await entry.runtime_data.api.async_close()
        entry.runtime_data = None
    return unloaded
