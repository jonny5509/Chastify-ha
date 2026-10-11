from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from .api import ChastifyApi, ChastifyAuthError, ChastifyApiError, ChastifyNoActiveSession
from .const import (
    CONF_DAILY_NOTIFICATIONS,
    CONF_END_NOTIFICATIONS,
    CONF_TOKEN,
    DOMAIN,
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

    @staticmethod
    def async_get_options_flow(config_entry):
        return ChastifyOptionsFlow()

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
    """Configure Chastify session congratulations and notification delivery."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            # Legacy installations may still have this old option saved; it is no longer used.
            user_input.pop("notification_service", None)
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DAILY_NOTIFICATIONS,
                        default=options.get(CONF_DAILY_NOTIFICATIONS, True),
                    ): bool,
                    vol.Required(
                        CONF_END_NOTIFICATIONS,
                        default=options.get(CONF_END_NOTIFICATIONS, True),
                    ): bool,
                }
            ),
        )
