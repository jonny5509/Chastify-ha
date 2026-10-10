"""Tests for the Chastify session calendar timing and history."""
import asyncio
from datetime import datetime, timedelta, timezone

from custom_components.chastify.calendar import _parse_datetime, _session_bounds, _session_uid


def test_calendar_end_tracks_latest_remaining_time_snapshot() -> None:
    fetched_at = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    data = {
        "lockData": {
            "timeLockedSeconds": 600,
            "timeRemainingSeconds": 1800,
        }
    }

    start, end = _session_bounds(data, fetched_at)

    assert start == fetched_at - timedelta(seconds=600)
    assert end == fetched_at + timedelta(seconds=1800)


def test_calendar_uses_updated_remaining_time_after_extension() -> None:
    fetched_at = datetime(2026, 10, 10, 12, 5, tzinfo=timezone.utc)
    data = {
        "lockData": {
            "startDate": "2026-10-10T12:00:00Z",
            "endDate": "2026-10-10T12:30:00Z",
            "timeRemainingSeconds": 3600,
        }
    }

    start, end = _session_bounds(data, fetched_at)

    assert start == datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 10, 10, 13, 5, tzinfo=timezone.utc)


def test_calendar_falls_back_to_explicit_end_when_remaining_is_hidden() -> None:
    fetched_at = datetime(2026, 10, 10, 12, 5, tzinfo=timezone.utc)
    data = {"lockData": {"endDate": "2026-10-10T13:00:00Z"}}

    start, end = _session_bounds(data, fetched_at)

    assert start is None
    assert end == datetime(2026, 10, 10, 13, 0, tzinfo=timezone.utc)


def test_calendar_keeps_active_session_visible_after_timer_expiry() -> None:
    fetched_at = datetime(2026, 10, 10, 12, 5, tzinfo=timezone.utc)
    data = {
        "lockData": {
            "startDate": "2026-10-10T12:00:00Z",
            "endDate": "2026-10-10T12:04:00Z",
            "timeRemainingSeconds": 0,
        }
    }

    start, end = _session_bounds(data, fetched_at)

    assert start == datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    assert end == fetched_at + timedelta(seconds=60)


def test_calendar_reuses_active_history_identity_when_derived_start_drifts() -> None:
    from custom_components.chastify.calendar import _matching_active_record

    original_start = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    record = {
        "uid": "existing-session",
        "summary": "Session",
        "start": original_start.isoformat(),
        "active": True,
    }

    match = _matching_active_record(
        [record], original_start + timedelta(seconds=35), "Session"
    )

    assert match is record


def test_calendar_does_not_match_different_title_or_large_start_drift() -> None:
    from custom_components.chastify.calendar import _matching_active_record

    original_start = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    record = {
        "uid": "existing-session",
        "summary": "Session",
        "start": original_start.isoformat(),
        "active": True,
    }

    assert _matching_active_record(
        [record], original_start + timedelta(seconds=35), "Other"
    ) is None
    assert _matching_active_record(
        [record], original_start + timedelta(seconds=120), "Session"
    ) is None


def test_session_history_uid_is_stable_for_same_session() -> None:
    start = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)

    first = _session_uid("entry_session_calendar", start, "Session")
    second = _session_uid("entry_session_calendar", start, "Session")

    assert first == second
    assert first != _session_uid(
        "entry_session_calendar", start + timedelta(seconds=1), "Session"
    )


def test_calendar_does_not_drift_match_when_start_is_explicit() -> None:
    from custom_components.chastify.calendar import _matching_active_record

    original_start = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    record = {
        "uid": "existing-session",
        "summary": "Session",
        "start": original_start.isoformat(),
        "active": True,
    }

    # Explicit starts must not use the fallback that tolerates inferred drift.
    assert _matching_active_record(
        [record],
        original_start + timedelta(seconds=35),
        "Session",
        allow_start_drift=False,
    ) is None


def test_calendar_ignores_lock_created_at_when_deriving_session_start() -> None:
    fetched_at = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    data = {
        "lock": {"createdAt": "2024-01-01T00:00:00Z"},
        "lockData": {
            "timeLockedSeconds": 600,
            "timeRemainingSeconds": 1800,
        },
    }

    start, end = _session_bounds(data, fetched_at)

    assert start == fetched_at - timedelta(seconds=600)
    assert end == fetched_at + timedelta(seconds=1800)



def test_calendar_history_saves_are_serialized_and_use_snapshots() -> None:
    from custom_components.chastify.calendar import _save_history_snapshot

    class BlockingStore:
        def __init__(self) -> None:
            self.calls = []
            self.first_started = asyncio.Event()
            self.release_first = asyncio.Event()

        async def async_save(self, snapshot) -> None:
            self.calls.append(snapshot)
            if snapshot["version"] == 1:
                self.first_started.set()
                await self.release_first.wait()

    async def run_test() -> None:
        store = BlockingStore()
        first_snapshot = {"version": 1, "events": [{"uid": "old"}]}
        first = asyncio.create_task(_save_history_snapshot(store, first_snapshot, None))
        await store.first_started.wait()

        # Later changes must not start saving until the earlier write completes.
        # The entity queues a shallow copy of each event dictionary, not its live list.
        live_history = [{"uid": "new"}]
        second_snapshot = {"version": 2, "events": [dict(item) for item in live_history]}
        second = asyncio.create_task(_save_history_snapshot(store, second_snapshot, first))
        await asyncio.sleep(0)
        assert [item["version"] for item in store.calls] == [1]

        # Mutating the live history after queueing must not alter the queued data.
        live_history[0]["uid"] = "mutated"
        store.release_first.set()
        await asyncio.gather(first, second)

        assert [item["version"] for item in store.calls] == [1, 2]
        assert store.calls[1]["events"][0]["uid"] == "new"

    asyncio.run(run_test())


def test_calendar_normalizes_naive_and_millisecond_timestamps_to_utc() -> None:
    naive = _parse_datetime("2026-10-10T12:00:00")
    milliseconds = _parse_datetime(1791633600000)

    assert naive == datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    assert milliseconds == datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


def test_calendar_rejects_invalid_or_reversed_event_bounds() -> None:
    fetched_at = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    start, end = _session_bounds(
        {"lockData": {"startDate": "2026-10-10T13:00:00Z", "endDate": "2026-10-10T12:30:00Z"}},
        fetched_at,
    )

    assert start == datetime(2026, 10, 10, 13, 0, tzinfo=timezone.utc)
    assert end == fetched_at + timedelta(seconds=60)
    assert end <= start
