from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from .api import ChastifyApi, ChastifyAuthError, ChastifyApiError, ChastifyNoActiveSession
from .const import CONF_TOKEN, DOMAIN


async def _validate_token(token: str) -> None:
    api = ChastifyApi(token)
    try:
        await api.async_get_session()
    except ChastifyNoActiveSession:
        return
    finally:
        await api.async_close()


class ChastifyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 13

    async def async_step_user(self, user_input=None):
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
                    return self.async_create_entry(
                        title="Chastify",
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
