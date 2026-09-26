from __future__ import annotations

from typing import Any

import aiohttp

from .const import BASE_URL


class ChastifyApiError(Exception):
    """General Chastify API error."""


class ChastifyAuthError(ChastifyApiError):
    """Authentication failed."""


class ChastifyNoActiveSession(ChastifyApiError):
    """The token is valid, but there is no active lock session."""


def normalize_token(token: str) -> str:
    """Normalize common copy/paste forms of a DEV token."""
    value = token.strip()
    if value.lower().startswith("bearer "):
        value = value[7:].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1].strip()
    return value


class ChastifyApi:
    def __init__(
        self, token: str, session: aiohttp.ClientSession | None = None
    ) -> None:
        self._token = normalize_token(token)
        self._session = session
        self._owns_session = session is None

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if self._session is None:
            self._session = aiohttp.ClientSession()

        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {self._token}"
        headers.setdefault("Accept", "application/json")

        try:
            async with self._session.request(
                method, f"{BASE_URL}{path}", headers=headers, **kwargs
            ) as response:
                try:
                    data = await response.json(content_type=None)
                except (ValueError, aiohttp.ContentTypeError):
                    data = {"message": await response.text()}

                if response.status in (401, 403):
                    error = data.get("error") or data.get("code")
                    message = data.get("message") or error or f"HTTP {response.status}"
                    raise ChastifyAuthError(
                        f"Chastify authentication failed ({error or response.status}): {message}"
                    )

                if response.status >= 400:
                    error = data.get("error") or data.get("code")
                    message = data.get("message") or error or f"HTTP {response.status}"
                    if response.status == 409 and error == "no_active_lock_session":
                        raise ChastifyNoActiveSession(message)
                    raise ChastifyApiError(message)

                return data if isinstance(data, dict) else {"data": data}
        except aiohttp.ClientError as err:
            raise ChastifyApiError(str(err)) from err

    async def async_get_session(self) -> dict[str, Any]:
        data = await self._request("GET", "/session")

        return data

    async def async_action(self, name: str, params: Any = None) -> dict[str, Any]:
        body = {"name": name, "params": {} if params is None else params}
        return await self._request("POST", "/action", json=body)

    async def async_apply_time(self, delta_seconds: int) -> dict[str, Any]:
        return await self._request(
            "POST", "/lock/apply-time", json={"deltaSeconds": delta_seconds}
        )

    async def async_freeze(self, duration_seconds: int | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if duration_seconds is not None:
            params["durationSeconds"] = duration_seconds
        return await self._request("POST", "/lock/freeze", json=params)

    async def async_unfreeze(self) -> dict[str, Any]:
        # Chastify expects a JSON request body for this POST, even though
        # unfreeze does not require any parameters.
        return await self._request("POST", "/lock/unfreeze", json={})

    async def async_hygienic_unlock(self) -> dict[str, Any]:
        """Start Chastify's documented temporary hygienic opening."""
        return await self.async_action("hygienic_unlock.start", {})

    async def async_custom_log(
        self,
        title: str,
        description: str | None = None,
        role: str | None = None,
        icon: str | None = None,
        color: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"title": title}
        for key, value in (
            ("description", description),
            ("role", role),
            ("icon", icon),
            ("color", color),
        ):
            if value is not None:
                body[key] = value
        return await self._request("POST", "/logs/custom", json=body)

    async def async_device_command(
        self, command: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"command": command}
        if params is not None:
            body["params"] = params
        return await self._request("POST", "/device-command", json=body)

    async def async_close(self) -> None:
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None
