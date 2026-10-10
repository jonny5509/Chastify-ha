from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import BASE_URL


class ChastifyApiError(Exception):
    """General Chastify API error."""


class ChastifyAuthError(ChastifyApiError):
    """Authentication or permission failure."""


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
        self,
        token: str,
        session: aiohttp.ClientSession | None = None,
        lock_id: str | None = None,
    ) -> None:
        self._token = normalize_token(token)
        self._session = session
        self._owns_session = session is None
        self._lock_id = (lock_id or "").strip() or None

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if self._session is None:
            self._session = aiohttp.ClientSession()

        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {self._token}"
        headers.setdefault("Accept", "application/json")
        headers.setdefault("Content-Type", "application/json")
        if self._lock_id:
            headers["x-chastify-lock-id"] = self._lock_id

        # Only safe reads are retried. A timed-out mutation may already have
        # taken effect, so repeating it could add/remove time or repeat a device action.
        retryable_read = method.upper() in {"GET", "HEAD"}
        attempt = 0
        while True:
            try:
                async with self._session.request(
                    method, f"{BASE_URL}{path}", headers=headers, **kwargs
                ) as response:
                    if response.status == 429 and retryable_read and attempt < 3:
                        retry_after = response.headers.get("Retry-After")
                        try:
                            delay = min(8.0, max(0.5, float(retry_after))) if retry_after else 0.5 * (2 ** attempt)
                        except ValueError:
                            delay = 0.5 * (2 ** attempt)
                        await response.read()
                        attempt += 1
                        await asyncio.sleep(delay)
                        continue

                    try:
                        data = await response.json(content_type=None)
                    except (ValueError, aiohttp.ContentTypeError):
                        data = {"message": await response.text()}

                    if response.status in (401, 403):
                        error = data.get("error") or data.get("code")
                        message = data.get("message") or error or f"HTTP {response.status}"
                        raise ChastifyAuthError(
                            f"Chastify authentication/permission failure ({error or response.status}): {message}"
                        )

                    if response.status >= 400:
                        error = data.get("error") or data.get("code")
                        message = data.get("message") or error or f"HTTP {response.status}"
                        if response.status == 409 and error == "no_active_lock_session":
                            raise ChastifyNoActiveSession(message)
                        if response.status == 429:
                            message = f"Chastify rate limit reached (429): {message}"
                        raise ChastifyApiError(message)

                    return data if isinstance(data, dict) else {"data": data}
            except aiohttp.ClientError as err:
                raise ChastifyApiError(str(err)) from err

    async def async_get_session(self) -> dict[str, Any]:
        return await self._request("GET", "/session")

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
            if not 60 <= int(duration_seconds) <= 86400:
                raise ChastifyApiError("Freeze duration must be between 60 and 86400 seconds.")
            params["durationSeconds"] = int(duration_seconds)
        return await self._request("POST", "/lock/freeze", json=params)

    async def async_unfreeze(self) -> dict[str, Any]:
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
        title = title.strip()
        if not 1 <= len(title) <= 180:
            raise ChastifyApiError("Custom log title must contain 1–180 characters.")
        if description is not None and len(description) > 2000:
            raise ChastifyApiError("Custom log description must be 2000 characters or fewer.")
        if role not in (None, "extension", "wearer", "keyholder"):
            raise ChastifyApiError("Custom log role must be extension, wearer, or keyholder.")
        if color is not None:
            import re
            if not re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", color):
                raise ChastifyApiError("Custom log color must be a 3- or 6-digit hex color.")
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

    async def async_custom_notification(
        self,
        title: str,
        message: str,
        target: str = "wearer",
        show_page_overlay: bool = False,
    ) -> dict[str, Any]:
        title = title.strip()
        message = message.strip()
        if not 1 <= len(title) <= 100:
            raise ChastifyApiError("Notification title must contain 1–100 characters.")
        if not 1 <= len(message) <= 500:
            raise ChastifyApiError("Notification message must contain 1–500 characters.")
        if target not in {"wearer", "keyholder", "both"}:
            raise ChastifyApiError("Notification target must be wearer, keyholder, or both.")
        return await self._request(
            "POST",
            "/notifications/custom",
            json={
                "title": title,
                "message": message,
                "target": target,
                "showPageOverlay": bool(show_page_overlay),
            },
        )

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
