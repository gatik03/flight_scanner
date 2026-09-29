from app.api.middleware import redact_secrets


def test_structured_logs_redact_secret_keys_and_query_values() -> None:
    event = {
        "api_key": "real-looking-value",
        "url": "https://example.test?token=real-looking-value",
        "message": "safe",
    }
    redacted = redact_secrets(None, "event", event)
    assert redacted == {
        "api_key": "[REDACTED]",
        "url": "https://example.test?token=[REDACTED]",
        "message": "safe",
    }
