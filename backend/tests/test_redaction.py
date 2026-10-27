from ai_finance_assistant.core.redaction import REDACTED, redact_mapping, sanitize_metadata


def test_redaction_removes_protected_values_recursively() -> None:
    redacted = redact_mapping(
        {
            "provider": "fixture",
            "api_key": "secret-value",
            "nested": {"raw_prompt": "private prompt", "record_count": 2},
        }
    )

    assert redacted["provider"] == "fixture"
    assert redacted["api_key"] == REDACTED
    assert redacted["nested"] == {"raw_prompt": REDACTED, "record_count": 2}


def test_trace_metadata_uses_an_allow_list() -> None:
    sanitized = sanitize_metadata(
        {
            "provider": "fixture",
            "record_count": 2,
            "arbitrary_payload": "must not pass",
            "authorization": "Bearer value",
        }
    )

    assert sanitized == {"provider": "fixture", "record_count": 2}
