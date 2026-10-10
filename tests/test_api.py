import asyncio

import pytest

from custom_components.chastify.api import ChastifyApi, ChastifyApiError, _extract_lock_id


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
