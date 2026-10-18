from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .api import ChastifyApi, ChastifyAuthError, ChastifyApiError, ChastifyNoActiveSession
from .const import (
    CONF_TOKEN, DOMAIN, CONF_ENABLE_NOTIFICATIONS, CONF_ENABLE_PHONE_NOTIFICATIONS, CONF_ENABLE_HA_NOTIFICATIONS, CONF_NOTIFICATION_SERVICE,
    CONF_NOTIFICATION_TARGETS, CONF_NOTIFICATION_DESTINATION, DEFAULT_NOTIFICATION_SERVICE,
    CONF_NOTIFY_DAILY, CONF_NOTIFY_COMPLETION,
)


async def _validate_token(token: str) -> None:
    api = ChastifyApi(token)
    try:
        await api.async_get_session()
    except ChastifyNoActiveSession:
        return
    finally:
        await api.async_close()


class ChastifyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 19

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return ChastifyOptionsFlow()

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        errors: dict[str, str] = {}

        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            if not token:
                errors["base"] = "invalid_auth"
            else:
                try:
                    await _validate_token(token)
                except ChastifyAuthError:
                    errors["base"] = "invalid_auth"
                except ChastifyApiError:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id("chastify")
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title="Chastify - jonny5509",
                        data={CONF_TOKEN: token},
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data):
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            try:
                await _validate_token(token)
            except ChastifyAuthError:
                errors["base"] = "invalid_auth"
            except ChastifyApiError:
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={**self._reauth_entry.data, CONF_TOKEN: token},
                )
                self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            errors=errors,
        )


class ChastifyOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            # Keep the old single-service option in sync for existing automations
            # and older versions while using the multi-target picker going forward.
            targets = user_input.get(CONF_NOTIFICATION_TARGETS, [])
            if targets:
                user_input[CONF_NOTIFICATION_SERVICE] = targets[0]
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        # Infer the previous destination from legacy toggles when opening options after upgrade.
        destination = options.get(CONF_NOTIFICATION_DESTINATION)
        if destination == "ha":
            destination = "home_assistant"
        if destination not in {"none", "home_assistant", "phone", "both"}:
            phone = options.get(CONF_ENABLE_PHONE_NOTIFICATIONS, False)
            ha = options.get(CONF_ENABLE_HA_NOTIFICATIONS, False)
            destination = "both" if phone and ha else "phone" if phone else "home_assistant" if ha else "none"

        notify_services = sorted(
            name for name in self.hass.services.async_services().get("notify", {})
            if name.startswith("mobile_app_")
        )
        service_options = [
            {"value": f"notify.{name}", "label": name.removeprefix("mobile_app_").replace("_", " ")}
            for name in notify_services
        ]
        saved_targets = options.get(CONF_NOTIFICATION_TARGETS)
        if saved_targets is None:
            legacy_service = str(options.get(CONF_NOTIFICATION_SERVICE, DEFAULT_NOTIFICATION_SERVICE))
            saved_targets = [legacy_service] if legacy_service.startswith("notify.mobile_app_") else []
        for target in saved_targets:
            service_name = str(target).removeprefix("notify.")
            if service_name.startswith("mobile_app_") and all(item["value"] != f"notify.{service_name}" for item in service_options):
                service_options.append({
                    "value": f"notify.{service_name}",
                    "label": service_name.removeprefix("mobile_app_").replace("_", " "),
                })

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(CONF_NOTIFY_DAILY, default=options.get(CONF_NOTIFY_DAILY, True)): bool,
                vol.Optional(CONF_NOTIFY_COMPLETION, default=options.get(CONF_NOTIFY_COMPLETION, True)): bool,
                vol.Optional(CONF_NOTIFICATION_DESTINATION, default=destination): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"label": "None", "value": "none"},
                            {"label": "Home Assistant notifications", "value": "home_assistant"},
                            {"label": "Phone notifications", "value": "phone"},
                            {"label": "Home Assistant and phone", "value": "both"},
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_NOTIFICATION_TARGETS, default=saved_targets): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=service_options, multiple=True, mode=selector.SelectSelectorMode.DROPDOWN)
                ),
            }),
        )
