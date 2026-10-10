from __future__ import annotations

import re
import voluptuous as vol

from homeassistant import config_entries
from .api import ChastifyApi, ChastifyAuthError, ChastifyApiError, ChastifyNoActiveSession
from .const import CONF_LOCK_ID, CONF_TOKEN, DOMAIN


async def _validate_token(token: str, lock_id: str | None = None) -> None:
    api = ChastifyApi(token, lock_id=lock_id)
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
            lock_id = user_input.get(CONF_LOCK_ID, "").strip()
            if lock_id and not re.fullmatch(r"[0-9a-fA-F]{24}", lock_id):
                errors["base"] = "invalid_lock_id"
            elif not token:
                errors["base"] = "invalid_auth"
            else:
                try:
                    await _validate_token(token, lock_id or None)
                except ChastifyAuthError:
                    errors["base"] = "invalid_auth"
                except ChastifyApiError:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id("chastify")
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title="Chastify",
                        data={CONF_TOKEN: token, CONF_LOCK_ID: lock_id},
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_TOKEN): str,
                vol.Optional(CONF_LOCK_ID, default=""): str,
            }),
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
                await _validate_token(token, self._reauth_entry.data.get(CONF_LOCK_ID) or None)
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
