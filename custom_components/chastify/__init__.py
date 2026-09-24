from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
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
)
from .coordinator import ChastifyCoordinator

from . import binary_sensor, button, sensor  # noqa: F401,E402


_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.version < 4:
        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)

        my_lock = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_my_lock")},
            name="My Lock",
            manufacturer="Chastify",
            model="Chastify Lock",
        )
        keyholder = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_keyholder")},
            name="Keyholder",
            manufacturer="Chastify",
            model="Chastify Keyholder",
        )

        keyholder_unique_ids = {
            f"{entry.entry_id}_keyholder_username",
            f"{entry.entry_id}_keyholder_keyholder_username",
            f"{entry.entry_id}_keyholder_freeze",
            f"{entry.entry_id}_keyholder_unfreeze",
            f"{entry.entry_id}_keyholder_lock_title",
            f"{entry.entry_id}_keyholder_max_time_remaining",
            f"{entry.entry_id}_keyholder_time_locked",
            f"{entry.entry_id}_keyholder_time_remaining",
            f"{entry.entry_id}_keyholder_wearer_username",
            f"{entry.entry_id}_keyholder_task_points",
            f"{entry.entry_id}_keyholder_task_points_remaining",
            f"{entry.entry_id}_keyholder_task_points_required",
        }

        for entity in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            target = keyholder if entity.unique_id in keyholder_unique_ids else my_lock
            entity_registry.async_update_entity(entity.entity_id, device_id=target.id)

        hass.config_entries.async_update_entry(entry, version=4)

    if entry.version < 5:
        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)

        keyholder = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_keyholder")},
            name="Keyholder",
            manufacturer="Chastify",
            model="Chastify Keyholder",
        )

        keyholder_refresh_unique_id = f"{entry.entry_id}_keyholder_refresh"
        for entity in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            if entity.unique_id == keyholder_refresh_unique_id:
                entity_registry.async_update_entity(entity.entity_id, device_id=keyholder.id)

        hass.config_entries.async_update_entry(entry, version=5)

    if entry.version < 6:
        entity_registry = er.async_get(hass)

        keyholder_username_unique_id = f"{entry.entry_id}_keyholder_username"
        for entity in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            if entity.unique_id == keyholder_username_unique_id:
                entity_registry.async_update_entity(
                    entity.entity_id,
                    name="Keyholder Username",
                )

        hass.config_entries.async_update_entry(entry, version=6)

    if entry.version < 7:
        entity_registry = er.async_get(hass)

        keyholder_username_unique_id = f"{entry.entry_id}_keyholder_username"
        for entity in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            if entity.unique_id == keyholder_username_unique_id:
                entity_registry.async_update_entity(
                    entity.entity_id,
                    name="Keyholder Username",
                )

        hass.config_entries.async_update_entry(entry, version=7)

    if entry.version < 8:
        entity_registry = er.async_get(hass)

        username_unique_ids = {
            f"{entry.entry_id}_keyholder_username",
            f"{entry.entry_id}_wearer_username",
            f"{entry.entry_id}_keyholder_wearer_username",
        }
        for entity in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            if entity.unique_id in username_unique_ids:
                entity_registry.async_remove(entity.entity_id)

        hass.config_entries.async_update_entry(entry, version=8)

    if entry.version < 9:
        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)
        keyholder = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_keyholder")},
            name="Keyholder",
            manufacturer="Chastify",
            model="Chastify Keyholder",
        )
        keyholder_unique_ids = {
            f"{entry.entry_id}_keyholder_frozen",
            f"{entry.entry_id}_keyholder_ready_to_unlock",
            f"{entry.entry_id}_keyholder_trusted",
            f"{entry.entry_id}_keyholder_task_assigned",
        }
        for entity in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            if entity.unique_id in keyholder_unique_ids:
                entity_registry.async_update_entity(
                    entity.entity_id,
                    device_id=keyholder.id,
                )

        hass.config_entries.async_update_entry(entry, version=9)

    if entry.version < 13:
        entity_registry = er.async_get(hass)
        old_unique_id = f"{entry.entry_id}_keyholder_username"
        for entity in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            if entity.unique_id == old_unique_id:
                entity_registry.async_remove(entity.entity_id)

        hass.config_entries.async_update_entry(entry, version=13)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = ChastifyApi(entry.data[CONF_TOKEN])
    try:
        await api.async_get_session()
    except ChastifyNoActiveSession:
        pass
    except ChastifyAuthError as err:
        await api.async_close()
        raise ConfigEntryAuthFailed(str(err)) from err
    except ChastifyApiError as err:
        await api.async_close()
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = ChastifyCoordinator(hass, api, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = {"api": api, "coordinator": coordinator}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    my_lock = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_my_lock")},
        name="My Lock",
        manufacturer="Chastify",
        model="Chastify Lock",
    )
    keyholder = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_keyholder")},
        name="Keyholder",
        manufacturer="Chastify",
        model="Chastify Keyholder",
    )
    keyholder_unique_ids = {
        f"{entry.entry_id}_keyholder_refresh",
        f"{entry.entry_id}_keyholder_frozen",
        f"{entry.entry_id}_keyholder_ready_to_unlock",
        f"{entry.entry_id}_keyholder_trusted",
        f"{entry.entry_id}_keyholder_task_assigned",
        f"{entry.entry_id}_keyholder_last_seen",
        f"{entry.entry_id}_keyholder_keyholder_username",
        f"{entry.entry_id}_keyholder_freeze",
        f"{entry.entry_id}_keyholder_unfreeze",
        f"{entry.entry_id}_keyholder_lock_title",
        f"{entry.entry_id}_keyholder_max_time_remaining",
        f"{entry.entry_id}_keyholder_time_locked",
        f"{entry.entry_id}_keyholder_time_remaining",
        f"{entry.entry_id}_keyholder_wearer_username",
        f"{entry.entry_id}_keyholder_task_points",
        f"{entry.entry_id}_keyholder_task_points_remaining",
        f"{entry.entry_id}_keyholder_task_points_required",
    }
    for entity in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        target = keyholder if entity.unique_id in keyholder_unique_ids else my_lock
        if entity.device_id != target.id:
            entity_registry.async_update_entity(entity.entity_id, device_id=target.id)

    async def action(call: ServiceCall):
        await api.async_action(call.data[ATTR_NAME], call.data.get(ATTR_PARAMS))

    async def apply_time(call: ServiceCall):
        await api.async_apply_time(int(call.data[ATTR_SECONDS]))

    async def add_time(call: ServiceCall):
        await api.async_apply_time(abs(int(call.data[ATTR_SECONDS])))

    async def remove_time(call: ServiceCall):
        await api.async_apply_time(-abs(int(call.data[ATTR_SECONDS])))

    async def freeze(call: ServiceCall):
        await api.async_freeze(call.data.get(ATTR_DURATION_SECONDS))

    async def unfreeze(call: ServiceCall):
        await api.async_unfreeze()

    async def hygienic_unlock(call: ServiceCall):
        await api.async_hygienic_unlock()

    async def custom_log(call: ServiceCall):
        await api.async_custom_log(
            call.data[ATTR_TITLE],
            call.data.get(ATTR_DESCRIPTION),
            call.data.get(ATTR_ROLE),
            call.data.get(ATTR_ICON),
            call.data.get(ATTR_COLOR),
        )

    async def device_command(call: ServiceCall):
        await api.async_device_command(
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
        if not hass.services.has_service(DOMAIN, name):
            hass.services.async_register(
                DOMAIN, name, handler, schema=schema
            )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = hass.data[DOMAIN].get(entry.entry_id)
    if not data:
        return True

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await data["api"].async_close()
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unloaded
