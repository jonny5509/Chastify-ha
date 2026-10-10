"""Regression tests for Chastify session response parsing and token normalization."""

from custom_components.chastify.api import normalize_token
from custom_components.chastify.coordinator import field, lock_data


def test_normalize_token_strips_bearer_prefix_and_whitespace():
    assert normalize_token("  Bearer abc123  ") == "abc123"


def test_normalize_token_strips_matching_quotes():
    assert normalize_token('"abc123"') == "abc123"
    assert normalize_token("'abc123'") == "abc123"


def test_lock_data_prefers_documented_lock_data_object():
    payload = {"lockData": {"locked": True}, "locked": False}
    assert lock_data(payload) == {"locked": True}


def test_field_reads_direct_lock_data():
    assert field({"lockData": {"timeRemainingSeconds": 900}}, "timeRemainingSeconds") == 900


def test_field_reads_nested_response_envelope():
    payload = {"data": {"lockData": {"taskPoints": 4}}}
    assert field(payload, "taskPoints") == 4


def test_field_returns_none_for_missing_values():
    assert field({"lockData": {"locked": True}}, "unknownField") is None


def test_lock_data_falls_back_to_top_level_payload():
    payload = {"locked": True, "timeRemainingSeconds": 120}
    assert lock_data(payload) == payload
