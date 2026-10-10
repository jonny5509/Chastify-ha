"""Tests for the Chastify session calendar timing and history."""
from datetime import datetime, timedelta, timezone

from custom_components.chastify.calendar import _session_bounds, _session_uid


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

    # Explicit starts should be used as-is; even a small change can identify
    # a distinct session, so the inferred-start fallback must not be applied.
    assert _matching_active_record(
        [record], original_start + timedelta(seconds=35), "Session"
    ) is record
