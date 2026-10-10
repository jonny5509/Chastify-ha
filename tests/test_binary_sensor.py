import pytest

from custom_components.chastify.binary_sensor import _as_bool, _find_value


@pytest.mark.parametrize("value", [True, 1, 1.0, "true", " TRUE ", "1", "yes", "on"])
def test_as_bool_recognizes_true_values(value) -> None:
    assert _as_bool(value) is True


@pytest.mark.parametrize("value", [False, 0, 0.0, "false", " FALSE ", "0", "no", "off"])
def test_as_bool_recognizes_false_values(value) -> None:
    assert _as_bool(value) is False


@pytest.mark.parametrize("value", [None, "", "unknown", "null", [], {}, object()])
def test_as_bool_returns_unknown_for_unrecognized_values(value) -> None:
    assert _as_bool(value) is None


def test_find_value_reads_nested_api_field() -> None:
    payload = {"data": {"lockData": {"readyToUnlock": True}}}

    assert _find_value(payload, {"readyToUnlock", "unlockable"}) is True


def test_find_value_returns_none_when_field_is_missing() -> None:
    assert _find_value({"data": {"lockData": {"status": "active"}}}, {"locked"}) is None
