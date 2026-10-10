from __future__ import annotations

import re
from typing import Any

import aiohttp

from .const import BASE_URL

# Keep API calls from hanging Home Assistant setup, service calls, or refreshes.
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15, connect=5, sock_read=10)
_MAX_ERROR_BODY_LENGTH = 500
_LOCK_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{24}$")


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


def _extract_lock_id(payload: dict[str, Any]) -> str | None:
    """Extract the selected lock ID from the documented session response."""
    sources = [payload]
    for key in ("data", "session", "result"):
        value = payload.get(key)
        if isinstance(value, dict):
            sources.append(value)

    for source in sources:
        lock = source.get("lock")
        if isinstance(lock, dict):
            lock_id = lock.get("_id")
            if isinstance(lock_id, str) and _LOCK_ID_PATTERN.fullmatch(lock_id):
                return lock_id
    return None


class ChastifyApi:
    def __init__(
        self, token: str, session: aiohttp.ClientSession | None = None
    ) -> None:
        self._token = normalize_token(token)
        self._session = session
        self._owns_session = session is None
        self._lock_id: str | None = None

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        # The API can automatically select a different active lock over time.
        # Never send a state-changing request until a valid lock ID has been
        # discovered from /session and pinned for this API instance.
        if method.upper() != "GET" and self._lock_id is None:
            raise ChastifyApiError(
                "Cannot safely send a Chastify lock action before /session "
                "returns a valid lock ID"
            )

        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=_REQUEST_TIMEOUT)

        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {self._token}"
        headers.setdefault("Accept", "application/json")
        if self._lock_id is not None:
            headers["x-chastify-lock-id"] = self._lock_id
        # Also apply a bounded timeout when Home Assistant supplies the session.
        kwargs.setdefault("timeout", _REQUEST_TIMEOUT)

        try:
            async with self._session.request(
                method, f"{BASE_URL}{path}", headers=headers, **kwargs
            ) as response:
                try:
                    payload = await response.json(content_type=None)
                except (ValueError, aiohttp.ContentTypeError):
                    body = await response.text()
                    payload = {"message": body.strip()[:_MAX_ERROR_BODY_LENGTH]}

                # The API may return a list, string, or empty body. Normalize it
                # before reading error fields so malformed responses don't crash
                # the integration with an AttributeError.
                data = payload if isinstance(payload, dict) else {"data": payload}

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
                        # The pinned session has ended or is no longer available.
                        # Clear the stale selector so the next read can discover
                        # the current session. Writes remain blocked until that
                        # read pins a new valid lock ID.
                        self._lock_id = None
                        raise ChastifyNoActiveSession(str(message))
                    if response.status == 429:
                        message = f"Chastify API rate limit reached (HTTP 429): {message}"
                    elif response.status >= 500:
                        message = f"Chastify API server error (HTTP {response.status}): {message}"
                    else:
                        message = f"Chastify API request failed (HTTP {response.status}): {message}"
                    raise ChastifyApiError(str(message))

                return data
        except TimeoutError as err:
            if method.upper() != "GET":
                # A write may have reached Chastify even when its response was
                # lost. Retrying time changes or device commands can duplicate
                # the effect, so make the uncertainty explicit to the caller.
                message = (
                    "Chastify API write timed out; the action outcome is unknown. "
                    "Check the lock state/history or device delivery status before "
                    "retrying."
                )
            else:
                message = (
                    f"Chastify API request timed out after "
                    f"{_REQUEST_TIMEOUT.total} seconds"
                )
            raise ChastifyApiError(message) from err
        except aiohttp.ClientError as err:
            # Avoid leaking request details or credentials in low-level errors.
            raise ChastifyApiError(
                f"Unable to connect to the Chastify API ({type(err).__name__})"
            ) from err

    async def async_get_session(self) -> dict[str, Any]:
        data = await self._request("GET", "/session")
        # Pin the first valid target for the lifetime of this config entry.
        # Subsequent session refreshes and all writes then use the same lock.
        if self._lock_id is None:
            self._lock_id = _extract_lock_id(data)
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
        # Chastify accepts an empty JSON request body for unfreeze.
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
