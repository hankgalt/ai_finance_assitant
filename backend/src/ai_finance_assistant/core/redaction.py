"""Allow-list trace metadata and redact protected keys recursively."""

from collections.abc import Mapping
from typing import Final

from pydantic import JsonValue

REDACTED: Final = "[REDACTED]"
PROTECTED_KEY_PARTS: Final = frozenset(
    {
        "api_key",
        "authorization",
        "cookie",
        "credential",
        "holdings",
        "password",
        "prompt",
        "secret",
        "token",
        "transaction",
    }
)
SAFE_METADATA_KEYS: Final = frozenset(
    {
        "cache_status",
        "collection_version",
        "duration_source",
        "provider",
        "record_count",
        "result_status",
        "source_count",
        "strategy",
    }
)


def _is_protected(key: str) -> bool:
    normalized = key.casefold().replace("-", "_")
    return any(part in normalized for part in PROTECTED_KEY_PARTS)


def redact_mapping(value: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, item in value.items():
        if _is_protected(key):
            result[key] = REDACTED
        elif isinstance(item, dict):
            result[key] = redact_mapping(item)
        elif isinstance(item, list):
            result[key] = [
                redact_mapping(entry) if isinstance(entry, dict) else entry for entry in item
            ]
        else:
            result[key] = item
    return result


def sanitize_metadata(
    value: Mapping[str, JsonValue],
    *,
    allowed_keys: frozenset[str] = SAFE_METADATA_KEYS,
) -> dict[str, JsonValue]:
    return redact_mapping({key: item for key, item in value.items() if key in allowed_keys})
