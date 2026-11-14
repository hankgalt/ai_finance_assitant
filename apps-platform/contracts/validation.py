"""Deterministic validation for versioned App Platform contracts."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_DIRECTORY = Path(__file__).with_name("schemas")
SCHEMA_FILES = (
    "application-attachment.v1.schema.json",
    "compiled-shared-edge.v1.schema.json",
    "registration-set.v1.schema.json",
    "state-ownership-manifest.v1.schema.json",
    "verified-identity-context.v1.schema.json",
)
SCHEMA_KEYWORDS = {
    "$defs",
    "$id",
    "$ref",
    "$schema",
    "additionalProperties",
    "const",
    "enum",
    "items",
    "maxItems",
    "maxLength",
    "maximum",
    "minItems",
    "minLength",
    "minimum",
    "oneOf",
    "pattern",
    "properties",
    "required",
    "type",
    "uniqueItems",
}
SCHEMA_ANNOTATIONS = {"description", "title"}


class ContractSchemaError(ValueError):
    """The reviewed local schema registry is invalid or unsupported."""


@dataclass(frozen=True)
class Violation:
    """One stable contract-validation failure."""

    code: str
    path: str
    message: str


@dataclass(frozen=True)
class LoadedDocument:
    """A parsed JSON value or ordered load violations."""

    value: Any | None
    violations: tuple[Violation, ...]


@dataclass(frozen=True)
class CompilationResult:
    """Complete compiler output or ordered violations."""

    compiled_configuration: dict[str, Any] | None
    ownership_manifest: dict[str, Any] | None
    generation_digest: str | None
    violations: tuple[Violation, ...]


class _DuplicateKeyError(ValueError):
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


class _NonIntegerNumberError(ValueError):
    pass


def _json_pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(key)
        result[key] = value
    return result


def _reject_non_integer_number(value: str) -> None:
    raise _NonIntegerNumberError(value)


def _contains_unpaired_surrogate(value: Any) -> bool:
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            return True
        return False
    if isinstance(value, list):
        return any(_contains_unpaired_surrogate(item) for item in value)
    if isinstance(value, dict):
        return any(
            _contains_unpaired_surrogate(key)
            or _contains_unpaired_surrogate(item)
            for key, item in value.items()
        )
    return False


def load_json_document(path: Path, *, max_bytes: int = 1_048_576) -> LoadedDocument:
    """Load one bounded JSON document without accepting duplicate keys."""

    if path.stat().st_size > max_bytes:
        return LoadedDocument(
            value=None,
            violations=(Violation("JSON_INVALID", "", "document exceeds size limit"),),
        )
    payload = path.read_bytes()
    if len(payload) > max_bytes:
        return LoadedDocument(
            value=None,
            violations=(Violation("JSON_INVALID", "", "document exceeds size limit"),),
        )
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_non_integer_number,
            parse_float=_reject_non_integer_number,
        )
    except _DuplicateKeyError as error:
        return LoadedDocument(
            value=None,
            violations=(
                Violation(
                    "JSON_DUPLICATE_KEY",
                    f"/{_json_pointer_token(error.key)}",
                    f"duplicate object key: {error.key}",
                ),
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, _NonIntegerNumberError) as error:
        return LoadedDocument(
            value=None,
            violations=(Violation("JSON_INVALID", "", str(error)),),
        )
    if _contains_unpaired_surrogate(value):
        return LoadedDocument(
            value=None,
            violations=(
                Violation(
                    "JSON_INVALID",
                    "",
                    "document contains an invalid Unicode scalar value",
                ),
            ),
        )
    return LoadedDocument(value=value, violations=())


def _normalized_registration_set(registration_set: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(registration_set)
    normalized_registrations: list[dict[str, Any]] = []
    for registration in normalized["registrations"]:
        registration["attachments"] = sorted(
            registration["attachments"], key=lambda value: value["attachment_id"]
        )
        admission = registration["admission"]
        if admission["mode"] == "restricted":
            admission["members"] = sorted(
                admission["members"],
                key=lambda value: (value["issuer"], value["subject"]),
            )
        normalized_registrations.append(registration)
    normalized["registrations"] = sorted(
        normalized_registrations, key=lambda value: value["application_id"]
    )
    return normalized


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _generation_digest(registration_set: dict[str, Any]) -> str:
    canonical = _canonical_bytes(_normalized_registration_set(registration_set))
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _mount_specificity(attachment: dict[str, Any]) -> tuple[int, str]:
    mount_path = attachment["mount_path"]
    segment_count = 0 if mount_path == "/" else mount_path.count("/")
    return (-segment_count, attachment["attachment_id"])


def _platform_resource(resource_reference: str, resource_kind: str) -> dict[str, Any]:
    return {
        "resource_reference": resource_reference,
        "resource_kind": resource_kind,
        "management_mode": "managed",
        "owner": {"state": "platform", "owner_id": "app-platform"},
    }


def _application_resource(attachment: dict[str, Any]) -> dict[str, Any]:
    return {
        "resource_reference": attachment["resource_reference"],
        "resource_kind": "application-attachment",
        "management_mode": "referenced",
        "owner": {
            "state": "application",
            "owner_id": attachment["owner_application_id"],
        },
    }


def compile_registration_set(
    previous_generation: dict[str, Any] | None,
    proposed_registration_set: dict[str, Any],
    platform_configuration: dict[str, Any],
) -> CompilationResult:
    """Compile one complete Registration Set without side effects."""

    registry = load_contract_schemas()
    violations = list(
        validate_contract_instance(
            proposed_registration_set,
            "urn:comfforts:app-platform:schema:registration-set:v1",
            registry,
        )
    )
    violations.extend(
        validate_contract_instance(
            platform_configuration,
            "urn:comfforts:app-platform:schema:registration-set:v1"
            "#/$defs/platformConfiguration",
            registry,
        )
    )
    if previous_generation is not None:
        violations.extend(
            validate_contract_instance(
                previous_generation,
                "urn:comfforts:app-platform:schema:registration-set:v1",
                registry,
            )
        )
    reserved_route_violations = _reserved_route_violations(proposed_registration_set)
    if reserved_route_violations:
        reserved_paths = {violation.path for violation in reserved_route_violations}
        violations = [
            violation
            for violation in violations
            if not (
                violation.code == "FIELD_PATTERN" and violation.path in reserved_paths
            )
        ]
        violations.extend(reserved_route_violations)
    if not violations:
        violations.extend(
            _registration_key_conflict_violations(proposed_registration_set)
        )
    if not violations:
        violations.extend(
            _attachment_binding_violations(
                proposed_registration_set, platform_configuration
            )
        )
    if not violations and previous_generation is None:
        violations.extend(_initial_generation_violations(proposed_registration_set))
        violations.extend(_new_application_violations(proposed_registration_set))
    if not violations and previous_generation is not None:
        violations.extend(
            _update_generation_violations(
                previous_generation, proposed_registration_set
            )
        )
    if not violations and previous_generation is not None:
        violations.extend(
            _registration_update_violations(
                previous_generation, proposed_registration_set
            )
        )
    if not violations and previous_generation is not None:
        violations.extend(
            _lifecycle_transition_violations(
                previous_generation, proposed_registration_set
            )
        )
    if violations:
        return CompilationResult(None, None, None, _ordered_violations(violations))

    normalized = _normalized_registration_set(proposed_registration_set)
    digest = _generation_digest(normalized)
    active_registrations = [
        registration
        for registration in normalized["registrations"]
        if registration["lifecycle"] == "active"
    ]

    compiled = {
        "contract_version": 1,
        "compiler_version": 1,
        "generation": normalized["generation"],
        "generation_digest": digest,
        "previous_generation_digest": normalized["previous_generation_digest"],
        "reserved_paths": ["/", "/.well-known", "/_platform"],
        "identity_delivery": {
            "header_name": "X-Comfforts-Verified-Identity",
            "context_contract_version": 1,
        },
        "application_states": [
            {
                "application_id": registration["application_id"],
                "registration_revision": registration["registration_revision"],
                "route_prefix": registration["route_prefix"],
                "lifecycle": registration["lifecycle"],
            }
            for registration in normalized["registrations"]
        ],
        "catalogue": [
            {
                "application_id": registration["application_id"],
                "title": registration["catalogue"]["title"],
                "summary": registration["catalogue"]["summary"],
                "route_prefix": registration["route_prefix"],
                "admission_mode": registration["admission"]["mode"],
            }
            for registration in active_registrations
            if registration["catalogue"]["visibility"] == "listed"
        ],
        "routes": [
            {
                "application_id": registration["application_id"],
                "route_prefix": registration["route_prefix"],
                "attachments": sorted(
                    copy.deepcopy(registration["attachments"]),
                    key=_mount_specificity,
                ),
            }
            for registration in sorted(
                active_registrations, key=lambda value: value["route_prefix"]
            )
        ],
        "admission_policies": [
            {
                "application_id": registration["application_id"],
                "policy": copy.deepcopy(registration["admission"]),
            }
            for registration in active_registrations
        ],
    }

    resources = [
        _platform_resource(
            "urn:comfforts:app-platform:catalogue:root", "catalogue"
        ),
        _platform_resource(
            "urn:comfforts:app-platform:shared-edge:root", "shared-edge"
        ),
    ]
    for registration in normalized["registrations"]:
        if registration["lifecycle"] != "retired":
            resources.extend(
                _application_resource(attachment)
                for attachment in registration["attachments"]
            )
        if registration["lifecycle"] == "active":
            resources.append(
                _platform_resource(
                    "urn:comfforts:app-platform:route:"
                    f"{registration['application_id']}",
                    "route",
                )
            )
            resources.extend(
                _platform_resource(
                    "urn:comfforts:app-platform:edge-connector:"
                    f"{registration['application_id']}:{attachment['attachment_id']}",
                    "edge-connector",
                )
                for attachment in registration["attachments"]
            )

    ownership = {
        "contract_version": 1,
        "generation": normalized["generation"],
        "generation_digest": digest,
        "resources": sorted(resources, key=lambda value: value["resource_reference"]),
    }
    return CompilationResult(compiled, ownership, digest, ())


def _validate_schema_profile(schema: Any, path: str) -> None:
    if not isinstance(schema, dict):
        raise ContractSchemaError(f"schema at {path} must be an object")

    for keyword in schema:
        if keyword not in SCHEMA_KEYWORDS | SCHEMA_ANNOTATIONS:
            raise ContractSchemaError(f"unsupported schema keyword: {keyword} at {path}")

    for name, definition in schema.get("$defs", {}).items():
        _validate_schema_profile(definition, f"{path}/$defs/{name}")
    for name, property_schema in schema.get("properties", {}).items():
        _validate_schema_profile(property_schema, f"{path}/properties/{name}")
    if "items" in schema:
        _validate_schema_profile(schema["items"], f"{path}/items")
    for index, option in enumerate(schema.get("oneOf", [])):
        _validate_schema_profile(option, f"{path}/oneOf/{index}")


def _resolve_pointer(document: Any, pointer: str) -> Any:
    if not pointer:
        return document
    if not pointer.startswith("/"):
        raise ContractSchemaError(f"invalid schema fragment: {pointer}")
    current = document
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            raise ContractSchemaError(f"unresolved schema fragment: {pointer}")
        current = current[token]
    return current


def _resolve_schema_reference(
    reference: str,
    current_schema_id: str,
    registry: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    base, separator, fragment = reference.partition("#")
    target_schema_id = base or current_schema_id
    if target_schema_id not in registry:
        raise ContractSchemaError(f"unresolved or remote schema reference: {reference}")
    target = registry[target_schema_id]
    if separator:
        target = _resolve_pointer(target, fragment)
    if not isinstance(target, dict):
        raise ContractSchemaError(f"schema reference is not an object: {reference}")
    return target, target_schema_id


def _walk_schema_references(
    schema: dict[str, Any],
    current_schema_id: str,
    registry: dict[str, dict[str, Any]],
) -> None:
    if "$ref" in schema:
        _resolve_schema_reference(schema["$ref"], current_schema_id, registry)
    for definition in schema.get("$defs", {}).values():
        _walk_schema_references(definition, current_schema_id, registry)
    for property_schema in schema.get("properties", {}).values():
        _walk_schema_references(property_schema, current_schema_id, registry)
    if "items" in schema:
        _walk_schema_references(schema["items"], current_schema_id, registry)
    for option in schema.get("oneOf", []):
        _walk_schema_references(option, current_schema_id, registry)


def load_contract_schemas(
    schema_directory: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Load the reviewed local schema registry without remote resolution."""

    directory = schema_directory or SCHEMA_DIRECTORY
    registry: dict[str, dict[str, Any]] = {}

    for filename in SCHEMA_FILES:
        schema = json.loads((directory / filename).read_text(encoding="utf-8"))
        schema_id = schema["$id"]
        if schema_id in registry:
            raise ContractSchemaError(f"duplicate schema identifier: {schema_id}")
        _validate_schema_profile(schema, schema_id)
        registry[schema_id] = schema

    for schema_id, schema in registry.items():
        _walk_schema_references(schema, schema_id, registry)
    return registry


def _pointer(path: str, token: str | int) -> str:
    encoded = _json_pointer_token(str(token))
    return f"{path}/{encoded}" if path else f"/{encoded}"


def _is_type(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    raise ContractSchemaError(f"unsupported schema type: {expected}")


def _field_violation(code: str, path: str, message: str) -> list[Violation]:
    return [Violation(code, path, message)]


def _validate_value(
    value: Any,
    schema: dict[str, Any],
    current_schema_id: str,
    registry: dict[str, dict[str, Any]],
    path: str,
) -> list[Violation]:
    if "$ref" in schema:
        target, target_schema_id = _resolve_schema_reference(
            schema["$ref"], current_schema_id, registry
        )
        return _validate_value(value, target, target_schema_id, registry, path)

    violations: list[Violation] = []
    expected_type = schema.get("type")
    if expected_type is not None and not _is_type(value, expected_type):
        return _field_violation(
            "FIELD_TYPE", path, f"expected {expected_type}, received {type(value).__name__}"
        )

    if "const" in schema and value != schema["const"]:
        code = (
            "CONTRACT_VERSION_UNSUPPORTED"
            if path.endswith("/contract_version")
            else "FIELD_PATTERN"
        )
        violations.extend(_field_violation(code, path, "value does not match const"))
    if "enum" in schema and value not in schema["enum"]:
        violations.extend(
            _field_violation("FIELD_PATTERN", path, "value is not in the allowed set")
        )

    if "oneOf" in schema:
        branch_results = [
            _validate_value(value, option, current_schema_id, registry, path)
            for option in schema["oneOf"]
        ]
        successful = [result for result in branch_results if not result]
        if len(successful) == 0:
            best_result = min(
                branch_results,
                key=lambda result: (
                    len(result),
                    [(item.path, item.code) for item in result],
                ),
            )
            violations.extend(best_result)
        elif len(successful) > 1:
            violations.extend(
                _field_violation(
                    "FIELD_TYPE", path, "value matches more than one allowed shape"
                )
            )

    if isinstance(value, dict):
        required = schema.get("required", [])
        for name in required:
            if name not in value:
                violations.extend(
                    _field_violation(
                        "FIELD_REQUIRED", _pointer(path, name), "required field is absent"
                    )
                )
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for name in value:
                if name not in properties:
                    violations.extend(
                        _field_violation(
                            "FIELD_UNKNOWN",
                            _pointer(path, name),
                            "field is not allowed",
                        )
                    )
        for name, property_schema in properties.items():
            if name in value:
                violations.extend(
                    _validate_value(
                        value[name],
                        property_schema,
                        current_schema_id,
                        registry,
                        _pointer(path, name),
                    )
                )

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get(
            "maxItems", len(value)
        ):
            violations.extend(
                _field_violation("FIELD_BOUNDS", path, "array length is out of bounds")
            )
        if schema.get("uniqueItems"):
            try:
                canonical_items = [_canonical_bytes(item) for item in value]
            except (TypeError, ValueError):
                canonical_items = []
            if canonical_items and len(canonical_items) != len(set(canonical_items)):
                violations.extend(
                    _field_violation("FIELD_BOUNDS", path, "array items are not unique")
                )
        if "items" in schema:
            for index, item in enumerate(value):
                violations.extend(
                    _validate_value(
                        item,
                        schema["items"],
                        current_schema_id,
                        registry,
                        _pointer(path, index),
                    )
                )

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get(
            "maxLength", len(value)
        ):
            violations.extend(
                _field_violation("FIELD_BOUNDS", path, "string length is out of bounds")
            )
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            violations.extend(
                _field_violation("FIELD_PATTERN", path, "string is not canonical")
            )

    if isinstance(value, int) and not isinstance(value, bool):
        if value < schema.get("minimum", value) or value > schema.get("maximum", value):
            violations.extend(
                _field_violation("FIELD_BOUNDS", path, "integer is out of bounds")
            )

    return violations


def _ordered_violations(violations: list[Violation]) -> tuple[Violation, ...]:
    return tuple(sorted(violations, key=lambda item: (item.path, item.code, item.message)))


def validate_contract_instance(
    value: Any,
    schema_reference: str,
    registry: dict[str, dict[str, Any]] | None = None,
) -> tuple[Violation, ...]:
    """Validate one value against a reviewed schema or definition URN."""

    active_registry = registry or load_contract_schemas()
    target, target_schema_id = _resolve_schema_reference(
        schema_reference, schema_reference.partition("#")[0], active_registry
    )
    violations = _validate_value(value, target, target_schema_id, active_registry, "")
    if (
        not violations
        and target_schema_id
        == "urn:comfforts:app-platform:schema:verified-identity-context:v1"
        and isinstance(value, dict)
        and value["expires_at"] <= value["issued_at"]
    ):
        violations.append(
            Violation(
                "IDENTITY_INVALID",
                "/expires_at",
                "identity expiry must be later than issue time",
            )
        )
    return _ordered_violations(violations)


def _reserved_route_violations(value: Any) -> list[Violation]:
    if not isinstance(value, dict) or not isinstance(value.get("registrations"), list):
        return []
    violations: list[Violation] = []
    for index, registration in enumerate(value["registrations"]):
        if not isinstance(registration, dict):
            continue
        route_prefix = registration.get("route_prefix")
        if route_prefix in {"/", "/.well-known", "/_platform"}:
            violations.append(
                Violation(
                    "ROUTE_RESERVED",
                    f"/registrations/{index}/route_prefix",
                    "route prefix is reserved by the platform",
                )
            )
    return violations


def _registration_key_conflict_violations(
    value: dict[str, Any],
) -> list[Violation]:
    seen_routes: set[str] = set()
    seen_application_ids: set[str] = set()
    violations: list[Violation] = []
    for index, registration in enumerate(value["registrations"]):
        application_id = registration["application_id"]
        if application_id in seen_application_ids:
            violations.append(
                Violation(
                    "APPLICATION_ID_CONFLICT",
                    f"/registrations/{index}/application_id",
                    "application identifier is already registered",
                )
            )
        seen_application_ids.add(application_id)
        route_prefix = registration["route_prefix"]
        if route_prefix in seen_routes:
            violations.append(
                Violation(
                    "ROUTE_CONFLICT",
                    f"/registrations/{index}/route_prefix",
                    "route prefix is already held by another registration",
                )
            )
        seen_routes.add(route_prefix)
    return violations


def _new_application_violations(value: dict[str, Any]) -> list[Violation]:
    violations: list[Violation] = []
    for index, registration in enumerate(value["registrations"]):
        if registration["registration_revision"] != 1:
            violations.append(
                Violation(
                    "GENERATION_INVALID",
                    f"/registrations/{index}/registration_revision",
                    "a new application must begin at registration revision 1",
                )
            )
        if registration["lifecycle"] != "staged":
            violations.append(
                Violation(
                    "LIFECYCLE_TRANSITION_INVALID",
                    f"/registrations/{index}/lifecycle",
                    "a new application must enter staged",
                )
            )
    return violations


def _initial_generation_violations(value: dict[str, Any]) -> list[Violation]:
    violations: list[Violation] = []
    if value["generation"] != 1:
        violations.append(
            Violation(
                "GENERATION_INVALID",
                "/generation",
                "the first Registration Set must be generation 1",
            )
        )
    if value["previous_generation_digest"] is not None:
        violations.append(
            Violation(
                "GENERATION_INVALID",
                "/previous_generation_digest",
                "the first Registration Set cannot name a predecessor",
            )
        )
    return violations


def _attachment_binding_violations(
    registration_set: dict[str, Any], platform_configuration: dict[str, Any]
) -> list[Violation]:
    enabled = set(platform_configuration["enabled_attachment_adapter_kinds"])
    violations: list[Violation] = []
    platform_resource_references = {
        "urn:comfforts:app-platform:catalogue:root",
        "urn:comfforts:app-platform:shared-edge:root",
    }
    for registration in registration_set["registrations"]:
        platform_resource_references.add(
            "urn:comfforts:app-platform:route:"
            f"{registration['application_id']}"
        )
        platform_resource_references.update(
            "urn:comfforts:app-platform:edge-connector:"
            f"{registration['application_id']}:{attachment['attachment_id']}"
            for attachment in registration["attachments"]
        )
    resource_owners: dict[str, str] = {}
    audience_owners: dict[str, str] = {}
    for registration_index, registration in enumerate(
        registration_set["registrations"]
    ):
        seen_attachment_ids: set[str] = set()
        seen_mounts: set[str] = set()
        for attachment_index, attachment in enumerate(registration["attachments"]):
            path = f"/registrations/{registration_index}/attachments/{attachment_index}"
            duplicate_attachment_id = (
                attachment["attachment_id"] in seen_attachment_ids
            )
            if duplicate_attachment_id:
                violations.append(
                    Violation(
                        "ATTACHMENT_CONFLICT",
                        f"{path}/attachment_id",
                        "attachment identifier is already used in this registration",
                    )
                )
            seen_attachment_ids.add(attachment["attachment_id"])
            prior_owner = resource_owners.get(attachment["resource_reference"])
            if attachment["resource_reference"] in platform_resource_references:
                violations.append(
                    Violation(
                        "OWNER_CONFLICT",
                        f"{path}/resource_reference",
                        "attachment resource is reserved for platform ownership",
                    )
                )
            elif prior_owner is not None and not (
                duplicate_attachment_id
                and prior_owner == registration["application_id"]
            ):
                code = (
                    "OWNER_CONFLICT"
                    if prior_owner != registration["application_id"]
                    else "ATTACHMENT_CONFLICT"
                )
                message = (
                    "attachment resource is declared by another application owner"
                    if code == "OWNER_CONFLICT"
                    else "attachment resource is repeated in this application"
                )
                violations.append(
                    Violation(code, f"{path}/resource_reference", message)
                )
            else:
                resource_owners[attachment["resource_reference"]] = registration[
                    "application_id"
                ]
            if attachment["mount_path"] in seen_mounts:
                violations.append(
                    Violation(
                        "ATTACHMENT_CONFLICT",
                        f"{path}/mount_path",
                        "attachment mount is already used in this registration",
                    )
                )
            seen_mounts.add(attachment["mount_path"])
            if attachment["adapter_kind"] not in enabled:
                violations.append(
                    Violation(
                        "ATTACHMENT_INVALID",
                        f"{path}/adapter_kind",
                        "attachment adapter kind is not enabled",
                    )
                )
            if attachment["owner_application_id"] != registration["application_id"]:
                violations.append(
                    Violation(
                        "ATTACHMENT_INVALID",
                        f"{path}/owner_application_id",
                        "attachment owner does not match the registered application",
                    )
                )
            if attachment["adapter_kind"] == "contract-test-v1":
                expected_reference = (
                    "urn:comfforts:app-platform:contract-test:"
                    f"{registration['application_id']}:{attachment['attachment_id']}"
                )
                if attachment["resource_reference"] != expected_reference:
                    violations.append(
                        Violation(
                            "ATTACHMENT_INVALID",
                            f"{path}/resource_reference",
                            "contract-test reference does not match its owner and identifier",
                        )
                    )
            elif attachment["adapter_kind"] == "fixture-in-process-v1":
                expected_reference = (
                    "urn:comfforts:app-platform:fixture:"
                    f"{registration['application_id']}:{attachment['attachment_id']}"
                )
                if attachment["resource_reference"] != expected_reference:
                    violations.append(
                        Violation(
                            "ATTACHMENT_INVALID",
                            f"{path}/resource_reference",
                            "fixture reference does not match its owner and identifier",
                        )
                    )
            if (
                registration["admission"]["mode"] != "public"
                and attachment["identity_requirement"] != "verified"
            ):
                violations.append(
                    Violation(
                        "IDENTITY_INVALID",
                        f"{path}/identity_requirement",
                        "protected admission requires verified attachment identity",
                    )
                )
            audience = attachment["audience"]
            if audience is not None:
                prior_audience_owner = audience_owners.get(audience)
                if (
                    prior_audience_owner is not None
                    and prior_audience_owner != registration["application_id"]
                ):
                    violations.append(
                        Violation(
                            "IDENTITY_INVALID",
                            f"{path}/audience",
                            "identity audience is already bound to another application",
                        )
                    )
                audience_owners[audience] = registration["application_id"]
    return violations


def _update_generation_violations(
    previous: dict[str, Any], proposed: dict[str, Any]
) -> list[Violation]:
    violations: list[Violation] = []
    if proposed["generation"] != previous["generation"] + 1:
        violations.append(
            Violation(
                "GENERATION_INVALID",
                "/generation",
                "generation must advance exactly once",
            )
        )
    if proposed["previous_generation_digest"] != _generation_digest(previous):
        violations.append(
            Violation(
                "GENERATION_INVALID",
                "/previous_generation_digest",
                "predecessor digest does not match the reviewed generation",
            )
        )
    return violations


def _registration_update_violations(
    previous: dict[str, Any], proposed: dict[str, Any]
) -> list[Violation]:
    previous_by_id = {
        registration["application_id"]: registration
        for registration in previous["registrations"]
    }
    violations: list[Violation] = []
    proposed_ids = {
        registration["application_id"] for registration in proposed["registrations"]
    }
    if set(previous_by_id) - proposed_ids:
        violations.append(
            Violation(
                "LIFECYCLE_TRANSITION_INVALID",
                "/registrations",
                "an existing registration must be retained as a tombstone",
            )
        )
    for index, registration in enumerate(proposed["registrations"]):
        earlier = previous_by_id.get(registration["application_id"])
        if earlier is None:
            if registration["registration_revision"] != 1:
                violations.append(
                    Violation(
                        "GENERATION_INVALID",
                        f"/registrations/{index}/registration_revision",
                        "a new application must begin at registration revision 1",
                    )
                )
            if registration["lifecycle"] != "staged":
                violations.append(
                    Violation(
                        "LIFECYCLE_TRANSITION_INVALID",
                        f"/registrations/{index}/lifecycle",
                        "a new application must enter staged",
                    )
                )
            continue
        earlier_values = {
            key: value
            for key, value in earlier.items()
            if key != "registration_revision"
        }
        proposed_values = {
            key: value
            for key, value in registration.items()
            if key != "registration_revision"
        }
        expected_revision = earlier["registration_revision"] + (
            1 if proposed_values != earlier_values else 0
        )
        if registration["registration_revision"] != expected_revision:
            violations.append(
                Violation(
                    "GENERATION_INVALID",
                    f"/registrations/{index}/registration_revision",
                    "registration revision does not match its registered value change",
                )
            )
    return violations


def _lifecycle_transition_violations(
    previous: dict[str, Any], proposed: dict[str, Any]
) -> list[Violation]:
    allowed = {
        "staged": {"staged", "active", "retired"},
        "active": {"active", "suspended", "retired"},
        "suspended": {"suspended", "active", "retired"},
        "retired": {"retired"},
    }
    previous_by_id = {
        registration["application_id"]: registration
        for registration in previous["registrations"]
    }
    violations: list[Violation] = []
    for index, registration in enumerate(proposed["registrations"]):
        earlier = previous_by_id.get(registration["application_id"])
        if earlier is None:
            continue
        if earlier["lifecycle"] == "retired":
            if registration["lifecycle"] != "retired":
                violations.append(
                    Violation(
                        "LIFECYCLE_TRANSITION_INVALID",
                        f"/registrations/{index}/lifecycle",
                        "a retired registration cannot reactivate",
                    )
                )
            elif registration != earlier:
                violations.append(
                    Violation(
                        "LIFECYCLE_TRANSITION_INVALID",
                        f"/registrations/{index}",
                        "a retired registration is an immutable tombstone",
                    )
                )
            continue
        if registration["lifecycle"] not in allowed[earlier["lifecycle"]]:
            violations.append(
                Violation(
                    "LIFECYCLE_TRANSITION_INVALID",
                    f"/registrations/{index}/lifecycle",
                    "registration lifecycle transition is not permitted",
                )
            )
    return violations
