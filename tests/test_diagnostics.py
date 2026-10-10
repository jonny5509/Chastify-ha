from custom_components.chastify.diagnostics import _account, _history, _is_sensitive_key, _sanitize


def test_sensitive_key_matching_handles_common_spellings() -> None:
    for key in ("token", "apiKey", "api_key", "password", "Authorization", "client-secret", "bearerToken"):
        assert _is_sensitive_key(key), key


def test_sanitize_removes_credentials_recursively_but_preserves_safe_fields() -> None:
    payload = {
        "id": 123,
        "name": "test account",
        "apiKey": "secret-one",
        "nested": {
            "access_token": "secret-two",
            "status": "active",
            "items": [{"password": "secret-three", "label": "safe"}],
        },
    }

    assert _sanitize(payload) == {
        "id": 123,
        "name": "test account",
        "nested": {"status": "active", "items": [{"label": "safe"}]},
    }


def test_account_sanitizes_nested_account_payload() -> None:
    payload = {"data": {"account": {"email": "person@example.test", "refreshToken": "secret"}}}

    assert _account(payload) == {"email": "person@example.test"}


def test_history_sanitizes_credential_fields() -> None:
    payload = {"data": {"history": [{"action": "lock", "authorization": "secret"}]}}

    assert _history(payload) == [{"action": "lock"}]


def test_history_handles_unexpected_payload_shape() -> None:
    assert _history({"data": ["not", "an", "object"]}) == []
