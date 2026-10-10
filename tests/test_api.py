import asyncio

import pytest

from custom_components.chastify.api import (
    ChastifyApi,
    ChastifyApiError,
    ChastifyNoActiveSession,
    _extract_lock_id,
)


LOCK_ID = "0123456789abcdef01234567"


def test_extract_lock_id_from_documented_session_payload() -> None:
    assert _extract_lock_id({"lock": {"_id": LOCK_ID}, "lockData": {}}) == LOCK_ID


def test_extract_lock_id_accepts_response_envelope() -> None:
    assert _extract_lock_id({"data": {"lock": {"_id": LOCK_ID}}}) == LOCK_ID


@pytest.mark.parametrize("lock_id", ["", "not-an-id", "0123456789abcdef"])
def test_extract_lock_id_rejects_invalid_ids(lock_id: str) -> None:
    assert _extract_lock_id({"lock": {"_id": lock_id}}) is None


def test_mutation_fails_closed_without_selected_lock_id() -> None:
    async def run() -> None:
        api = ChastifyApi("test-token", session=object())
        with pytest.raises(ChastifyApiError, match="valid lock ID"):
            await api.async_apply_time(60)

    asyncio.run(run())


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    async def json(self, content_type=None):
        return self.payload


class FakeRequest:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeSession:
    def __init__(self):
        self.calls = []
        self.responses = [
            {"lock": {"_id": LOCK_ID}, "lockData": {"timeRemainingSeconds": 60}},
            {"ok": True},
            # Even if a later response reports another selected lock, the
            # original target must remain pinned for this config entry.
            {"lock": {"_id": "abcdef0123456789abcdef01"}, "lockData": {}},
        ]

    def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        return FakeRequest(FakeResponse(self.responses.pop(0)))


def test_requests_pin_selected_lock_and_keep_it_across_refreshes() -> None:
    async def run() -> None:
        session = FakeSession()
        api = ChastifyApi("test-token", session=session)

        await api.async_get_session()
        await api.async_apply_time(60)
        await api.async_get_session()

        assert "x-chastify-lock-id" not in session.calls[0]["headers"]
        assert session.calls[1]["headers"]["x-chastify-lock-id"] == LOCK_ID
        assert session.calls[2]["headers"]["x-chastify-lock-id"] == LOCK_ID

    asyncio.run(run())


class TimeoutRequest:
    async def __aenter__(self):
        raise TimeoutError()

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class TimeoutSession:
    def request(self, method, url, **kwargs):
        return TimeoutRequest()


def test_write_timeout_warns_that_outcome_is_unknown() -> None:
    async def run() -> None:
        api = ChastifyApi("test-token", session=TimeoutSession())
        api._lock_id = LOCK_ID

        with pytest.raises(ChastifyApiError, match="outcome is unknown") as exc:
            await api.async_apply_time(60)

        assert "before retrying" in str(exc.value)

    asyncio.run(run())


def test_read_timeout_keeps_standard_timeout_message() -> None:
    async def run() -> None:
        api = ChastifyApi("test-token", session=TimeoutSession())

        with pytest.raises(ChastifyApiError, match="request timed out after"):
            await api.async_get_session()

    asyncio.run(run())


def test_stale_lock_selector_clears_and_next_session_can_be_selected() -> None:
    async def run() -> None:
        new_lock_id = "abcdef0123456789abcdef01"
        session = SessionWithResponses([
            (200, {"lock": {"_id": LOCK_ID}, "lockData": {}}),
            (409, {"error": "no_active_lock_session", "message": "Session ended"}),
            (200, {"lock": {"_id": new_lock_id}, "lockData": {}}),
            (200, {"ok": True}),
        ])
        api = ChastifyApi("test-token", session=session)

        await api.async_get_session()
        with pytest.raises(ChastifyNoActiveSession, match="Session ended"):
            await api.async_get_session()

        # After the stale target is rejected, the next read discovers the
        # current session without a selector; subsequent writes use that ID.
        await api.async_get_session()
        await api.async_apply_time(60)

        assert session.calls[1]["headers"]["x-chastify-lock-id"] == LOCK_ID
        assert "x-chastify-lock-id" not in session.calls[2]["headers"]
        assert session.calls[3]["headers"]["x-chastify-lock-id"] == new_lock_id

    asyncio.run(run())


class StatusResponse(FakeResponse):
    def __init__(self, status, payload):
        super().__init__(payload)
        self.status = status


class StatusRequest(FakeRequest):
    pass


class SessionWithResponses:
    def __init__(self, responses):
        self.calls = []
        self.responses = list(responses)

    def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        status, payload = self.responses.pop(0)
        return StatusRequest(StatusResponse(status, payload))
