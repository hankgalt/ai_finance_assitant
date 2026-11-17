"""Deterministic App Platform contract-interface checks."""

from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from contracts.validation import (
    CompilationResult,
    ContractSchemaError,
    compile_registration_set,
    load_contract_schemas,
    load_json_document,
    validate_contract_instance,
)


EXPECTED_SCHEMA_IDS = {
    "urn:comfforts:app-platform:schema:application-attachment:v1",
    "urn:comfforts:app-platform:schema:compiled-shared-edge:v1",
    "urn:comfforts:app-platform:schema:registration-set:v1",
    "urn:comfforts:app-platform:schema:state-ownership-manifest:v1",
    "urn:comfforts:app-platform:schema:verified-identity-context:v1",
}
PROJECT_ROOT = Path(__file__).resolve().parents[1]
VECTOR_ROOT = PROJECT_ROOT / "contracts" / "test-vectors"


def _load_vector(relative_path: str) -> object:
    loaded = load_json_document(VECTOR_ROOT / relative_path)
    if loaded.violations:
        raise AssertionError(loaded.violations)
    return loaded.value


def _reverse_object_order(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _reverse_object_order(item)
            for key, item in reversed(list(value.items()))
        }
    if isinstance(value, list):
        return [_reverse_object_order(item) for item in value]
    return value


def _valid_identity_context() -> dict[str, object]:
    return {
        "contract_version": 1,
        "issuer": "urn:comfforts:identity:synthetic",
        "subject": "synthetic-user-1",
        "audience": "urn:comfforts:app-platform:audience:alpha-app",
        "issued_at": 100,
        "expires_at": 200,
        "correlation_id": "request-1",
    }


class ContractSchemaTest(unittest.TestCase):
    def test_reviewed_schema_registry_loads_offline(self) -> None:
        registry = load_contract_schemas()

        self.assertEqual(set(registry), EXPECTED_SCHEMA_IDS)

    def test_unapproved_schema_keyword_fails_registry_loading(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            copied_schemas = Path(temporary_directory) / "schemas"
            shutil.copytree(PROJECT_ROOT / "contracts" / "schemas", copied_schemas)
            target = copied_schemas / "verified-identity-context.v1.schema.json"
            schema = json.loads(target.read_text(encoding="utf-8"))
            schema["properties"]["issuer"]["format"] = "uri"
            target.write_text(json.dumps(schema), encoding="utf-8")

            with self.assertRaisesRegex(
                ContractSchemaError, "unsupported schema keyword: format"
            ):
                load_contract_schemas(copied_schemas)

    def test_remote_schema_reference_fails_registry_loading(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            copied_schemas = Path(temporary_directory) / "schemas"
            shutil.copytree(PROJECT_ROOT / "contracts" / "schemas", copied_schemas)
            target = copied_schemas / "verified-identity-context.v1.schema.json"
            schema = json.loads(target.read_text(encoding="utf-8"))
            schema["properties"]["issuer"] = {
                "$ref": "https://schemas.example.test/issuer.json"
            }
            target.write_text(json.dumps(schema), encoding="utf-8")

            with self.assertRaisesRegex(
                ContractSchemaError, "unresolved or remote schema reference"
            ):
                load_contract_schemas(copied_schemas)

    def test_duplicate_json_key_is_rejected_before_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            document_path = Path(temporary_directory) / "duplicate.json"
            document_path.write_text('{"contract_version":1,"contract_version":1}')

            loaded = load_json_document(document_path)

            self.assertIsNone(loaded.value)
            self.assertEqual(
                [(violation.code, violation.path) for violation in loaded.violations],
                [("JSON_DUPLICATE_KEY", "/contract_version")],
            )

    def test_floating_point_json_is_rejected_before_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            document_path = Path(temporary_directory) / "float.json"
            document_path.write_text('{"value":1.5}')

            loaded = load_json_document(document_path)

            self.assertIsNone(loaded.value)
            self.assertEqual(
                [violation.code for violation in loaded.violations],
                ["JSON_INVALID"],
            )

    def test_non_json_numeric_constants_are_rejected_before_validation(self) -> None:
        for constant in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(constant=constant), tempfile.TemporaryDirectory() as directory:
                document_path = Path(directory) / "constant.json"
                document_path.write_text(f'{{"value":{constant}}}')

                loaded = load_json_document(document_path)

                self.assertIsNone(loaded.value)
                self.assertEqual(
                    [violation.code for violation in loaded.violations],
                    ["JSON_INVALID"],
                )

    def test_unpaired_unicode_surrogates_are_rejected_before_validation(self) -> None:
        payloads = (
            '{"value":"\\ud800"}',
            '{"\\udfff":"value"}',
        )
        for payload in payloads:
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as directory:
                document_path = Path(directory) / "surrogate.json"
                document_path.write_text(payload, encoding="utf-8")

                loaded = load_json_document(document_path)

                self.assertIsNone(loaded.value)
                self.assertEqual(
                    [violation.code for violation in loaded.violations],
                    ["JSON_INVALID"],
                )

    def test_json_document_size_is_bounded_before_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            document_path = Path(temporary_directory) / "oversized.json"
            document_path.write_text('{"value":"too large"}')

            loaded = load_json_document(document_path, max_bytes=10)

            self.assertIsNone(loaded.value)
            self.assertEqual(
                [violation.code for violation in loaded.violations],
                ["JSON_INVALID"],
            )

    def test_default_check_includes_contract_fixture_and_runtime_gates(self) -> None:
        makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn(
            "check: governance-check contract-check fixture-check", makefile
        )
        self.assertIn("contract-check:", makefile)
        self.assertIn("fixture-check:", makefile)
        self.assertIn("runtime-check:", makefile)
        self.assertEqual(makefile.count("PYTHONDONTWRITEBYTECODE=1"), 4)

    def test_contract_layer_runs_from_an_extracted_project_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            extracted_root = Path(temporary_directory) / "apps-platform"
            copied_contracts = extracted_root / "contracts"
            shutil.copytree(PROJECT_ROOT / "contracts", copied_contracts)
            proposed_path = (
                copied_contracts
                / "test-vectors"
                / "valid"
                / "initial-registration-set.v1.json"
            )
            configuration_path = (
                copied_contracts
                / "test-vectors"
                / "valid"
                / "platform-configuration.v1.json"
            )
            before = {
                path.relative_to(extracted_root): path.read_bytes()
                for path in extracted_root.rglob("*")
                if path.is_file()
            }
            program = "\n".join(
                (
                    "from pathlib import Path",
                    "from contracts.validation import (",
                    "    compile_registration_set, load_json_document,",
                    ")",
                    "root = Path('contracts/test-vectors/valid')",
                    "proposed_path = root / 'initial-registration-set.v1.json'",
                    "config_path = root / 'platform-configuration.v1.json'",
                    "proposed = load_json_document(proposed_path).value",
                    "config = load_json_document(config_path).value",
                    "result = compile_registration_set(None, proposed, config)",
                    "assert result.violations == ()",
                    "expected = 'sha256:' + 'bdf0608ec2111ad74e6042edb2be550'",
                    "expected += 'f47a8f4a15ca5ac7b3a6d09951df75008'",
                    "assert result.generation_digest == expected",
                )
            )

            completed = subprocess.run(
                [sys.executable, "-c", program],
                cwd=extracted_root,
                env={
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": str(extracted_root),
                },
                check=False,
                capture_output=True,
                text=True,
            )
            after = {
                path.relative_to(extracted_root): path.read_bytes()
                for path in extracted_root.rglob("*")
                if path.is_file()
            }

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(before, after)
            self.assertEqual(
                proposed_path.read_bytes(),
                before[proposed_path.relative_to(extracted_root)],
            )
            self.assertEqual(
                configuration_path.read_bytes(),
                before[configuration_path.relative_to(extracted_root)],
            )


class ContractVectorManifestTest(unittest.TestCase):
    def test_manifest_indexes_reviewed_acceptance_and_rejection_vectors(self) -> None:
        manifest = _load_vector("manifest.v1.json")

        self.assertEqual(manifest["contract_version"], 1)
        self.assertEqual(
            [
                case["case_id"]
                for case in manifest["cases"]
                if case["expected"] == "accept"
            ],
            [
                "initial-staged",
                "activate-application",
                "activate-multiple-admission-modes",
                "retire-application",
                "replace-attachment-reference",
                "restore-reviewed-attachment-reference",
                "content-release-with-unchanged-registration",
            ],
        )
        case_ids = [case["case_id"] for case in manifest["cases"]]
        self.assertEqual(len(case_ids), len(set(case_ids)))
        self.assertEqual(len(case_ids), 34)
        for case in manifest["cases"]:
            self.assertEqual(case["evidence_class"], "C")
            self.assertIn(case["expected"], {"accept", "reject"})
            self.assertTrue(case["requirements"])
            self.assertTrue(case["decisions"])
            self.assertTrue(case["threats"])
            for field in ("platform_configuration", "proposed"):
                self.assertTrue((VECTOR_ROOT / case[field]).is_file())
            if case["previous"] is not None:
                self.assertTrue((VECTOR_ROOT / case["previous"]).is_file())
            if case["expected"] == "accept":
                for field in ("expected_compiled", "expected_ownership"):
                    self.assertTrue((VECTOR_ROOT / case[field]).is_file())
            else:
                self.assertTrue(case["expected_violations"])

    def test_reviewed_manifest_cases_match_literal_results(self) -> None:
        manifest = _load_vector("manifest.v1.json")
        vector_bytes_before = {
            path.relative_to(VECTOR_ROOT): path.read_bytes()
            for path in VECTOR_ROOT.rglob("*.json")
        }

        for case in manifest["cases"]:
            with self.subTest(case_id=case["case_id"]):
                previous = (
                    None
                    if case["previous"] is None
                    else _load_vector(case["previous"])
                )
                result = compile_registration_set(
                    previous,
                    _load_vector(case["proposed"]),
                    _load_vector(case["platform_configuration"]),
                )

                if case["expected"] == "accept":
                    self.assertEqual(result.violations, ())
                    self.assertEqual(
                        result.compiled_configuration,
                        _load_vector(case["expected_compiled"]),
                    )
                    self.assertEqual(
                        result.ownership_manifest,
                        _load_vector(case["expected_ownership"]),
                    )
                    self.assertEqual(
                        validate_contract_instance(
                            result.compiled_configuration,
                            "urn:comfforts:app-platform:schema:compiled-shared-edge:v1",
                        ),
                        (),
                    )
                    self.assertEqual(
                        validate_contract_instance(
                            result.ownership_manifest,
                            "urn:comfforts:app-platform:schema:state-ownership-manifest:v1",
                        ),
                        (),
                    )
                else:
                    self.assertIsNone(result.compiled_configuration)
                    self.assertIsNone(result.ownership_manifest)
                    self.assertIsNone(result.generation_digest)
                    self.assertEqual(
                        [
                            {"code": violation.code, "path": violation.path}
                            for violation in result.violations
                        ],
                        case["expected_violations"],
                    )
        vector_bytes_after = {
            path.relative_to(VECTOR_ROOT): path.read_bytes()
            for path in VECTOR_ROOT.rglob("*.json")
        }
        self.assertEqual(vector_bytes_before, vector_bytes_after)

    def test_release_and_replacement_vectors_preserve_declared_boundaries(self) -> None:
        active = _load_vector("valid/active-registration-set.v1.json")
        content_release = _load_vector(
            "valid/content-release-unchanged-registration-set.v1.json"
        )
        replacement = _load_vector(
            "valid/replaced-attachment-registration-set.v1.json"
        )
        rollback = _load_vector(
            "valid/rollback-attachment-registration-set.v1.json"
        )

        self.assertEqual(active["registrations"], content_release["registrations"])
        self.assertEqual(
            active["registrations"][0]["attachments"][0]["resource_reference"],
            rollback["registrations"][0]["attachments"][0]["resource_reference"],
        )
        self.assertNotEqual(
            active["registrations"][0]["attachments"][0]["resource_reference"],
            replacement["registrations"][0]["attachments"][0][
                "resource_reference"
            ],
        )


class RegistrationCompilerTest(unittest.TestCase):
    def test_compilation_is_repeatable_and_does_not_mutate_inputs(self) -> None:
        previous = _load_vector("valid/initial-registration-set.v1.json")
        proposed = _load_vector("valid/active-registration-set.v1.json")
        platform_configuration = _load_vector("valid/platform-configuration.v1.json")
        inputs_before = copy.deepcopy((previous, proposed, platform_configuration))

        first = compile_registration_set(previous, proposed, platform_configuration)
        second = compile_registration_set(previous, proposed, platform_configuration)

        self.assertEqual(first, second)
        self.assertEqual((previous, proposed, platform_configuration), inputs_before)

    def test_compilation_ignores_nonsemantic_object_key_order(self) -> None:
        previous = _load_vector("valid/multi-staged-registration-set.v1.json")
        proposed = _load_vector("valid/multi-active-registration-set.v1.json")
        platform_configuration = _load_vector("valid/platform-configuration.v1.json")

        canonical = compile_registration_set(
            previous, proposed, platform_configuration
        )
        permuted = compile_registration_set(
            _reverse_object_order(previous),
            _reverse_object_order(proposed),
            _reverse_object_order(platform_configuration),
        )

        self.assertEqual(canonical, permuted)

    def test_initial_staged_registration_compiles_without_exposure(self) -> None:
        proposed = _load_vector("valid/initial-registration-set.v1.json")
        platform_configuration = _load_vector("valid/platform-configuration.v1.json")

        result = compile_registration_set(None, proposed, platform_configuration)

        self.assertIsInstance(result, CompilationResult)
        self.assertEqual(result.violations, ())
        self.assertEqual(
            result.compiled_configuration,
            _load_vector("valid/compiled-initial.v1.json"),
        )
        self.assertEqual(
            result.ownership_manifest,
            _load_vector("valid/ownership-initial.v1.json"),
        )
        self.assertEqual(
            result.generation_digest,
            "sha256:bdf0608ec2111ad74e6042edb2be550f47a8f4a15ca5ac7b3a6d09951df75008",
        )

    def test_application_feature_entitlement_field_fails_closed(self) -> None:
        proposed = copy.deepcopy(
            _load_vector("valid/initial-registration-set.v1.json")
        )
        proposed["registrations"][0]["feature_entitlements"] = ["market-data"]

        result = compile_registration_set(
            None,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertIsNone(result.ownership_manifest)
        self.assertIsNone(result.generation_digest)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [("FIELD_UNKNOWN", "/registrations/0/feature_entitlements")],
        )

    def test_platform_reserved_route_is_rejected_semantically(self) -> None:
        proposed = copy.deepcopy(
            _load_vector("valid/initial-registration-set.v1.json")
        )
        proposed["registrations"][0]["route_prefix"] = "/_platform"

        result = compile_registration_set(
            None,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [("ROUTE_RESERVED", "/registrations/0/route_prefix")],
        )

    def test_route_prefix_rejects_terminal_control_characters(self) -> None:
        proposed = copy.deepcopy(
            _load_vector("valid/initial-registration-set.v1.json")
        )
        proposed["registrations"][0]["route_prefix"] = "/alpha\n"

        result = compile_registration_set(
            None,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [("FIELD_PATTERN", "/registrations/0/route_prefix")],
        )

    def test_complete_set_rejects_duplicate_route_prefixes(self) -> None:
        proposed = copy.deepcopy(
            _load_vector("valid/initial-registration-set.v1.json")
        )
        second = copy.deepcopy(proposed["registrations"][0])
        second["application_id"] = "beta-app"
        second["catalogue"]["title"] = "Beta"
        second["attachments"][0]["owner_application_id"] = "beta-app"
        second["attachments"][0]["resource_reference"] = (
            "urn:comfforts:app-platform:contract-test:beta-app:web"
        )
        proposed["registrations"].append(second)

        result = compile_registration_set(
            None,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [("ROUTE_CONFLICT", "/registrations/1/route_prefix")],
        )

    def test_complete_set_rejects_duplicate_application_identifiers(self) -> None:
        proposed = copy.deepcopy(
            _load_vector("valid/initial-registration-set.v1.json")
        )
        second = copy.deepcopy(proposed["registrations"][0])
        second["route_prefix"] = "/beta"
        second["catalogue"]["title"] = "Duplicate Alpha"
        second["attachments"][0]["attachment_id"] = "api"
        second["attachments"][0]["resource_reference"] = (
            "urn:comfforts:app-platform:contract-test:alpha-app:api"
        )
        proposed["registrations"].append(second)

        result = compile_registration_set(
            None,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [("APPLICATION_ID_CONFLICT", "/registrations/1/application_id")],
        )

    def test_attachment_resource_has_one_application_owner(self) -> None:
        proposed = copy.deepcopy(
            _load_vector("valid/initial-registration-set.v1.json")
        )
        first = proposed["registrations"][0]
        first["attachments"][0]["adapter_kind"] = "generic-v1"
        first["attachments"][0]["resource_reference"] = "urn:test:shared"
        second = copy.deepcopy(first)
        second["application_id"] = "beta-app"
        second["route_prefix"] = "/beta"
        second["catalogue"]["title"] = "Beta"
        second["attachments"][0]["owner_application_id"] = "beta-app"
        proposed["registrations"].append(second)
        platform_configuration = copy.deepcopy(
            _load_vector("valid/platform-configuration.v1.json")
        )
        platform_configuration["enabled_attachment_adapter_kinds"].append(
            "generic-v1"
        )

        result = compile_registration_set(None, proposed, platform_configuration)

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [("OWNER_CONFLICT", "/registrations/1/attachments/0/resource_reference")],
        )

    def test_application_resource_reference_cannot_be_repeated_by_same_owner(self) -> None:
        proposed = copy.deepcopy(
            _load_vector("valid/initial-registration-set.v1.json")
        )
        first = proposed["registrations"][0]["attachments"][0]
        first["adapter_kind"] = "generic-v1"
        first["resource_reference"] = "urn:test:alpha-runtime"
        second = copy.deepcopy(first)
        second["attachment_id"] = "api"
        second["mount_path"] = "/api"
        proposed["registrations"][0]["attachments"].append(second)
        platform_configuration = copy.deepcopy(
            _load_vector("valid/platform-configuration.v1.json")
        )
        platform_configuration["enabled_attachment_adapter_kinds"].append(
            "generic-v1"
        )

        result = compile_registration_set(None, proposed, platform_configuration)

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [
                (
                    "ATTACHMENT_CONFLICT",
                    "/registrations/0/attachments/1/resource_reference",
                )
            ],
        )

    def test_application_resource_cannot_claim_platform_resource_reference(self) -> None:
        proposed = copy.deepcopy(
            _load_vector("valid/initial-registration-set.v1.json")
        )
        attachment = proposed["registrations"][0]["attachments"][0]
        attachment["adapter_kind"] = "generic-v1"
        attachment["resource_reference"] = (
            "urn:comfforts:app-platform:catalogue:root"
        )
        platform_configuration = copy.deepcopy(
            _load_vector("valid/platform-configuration.v1.json")
        )
        platform_configuration["enabled_attachment_adapter_kinds"].append(
            "generic-v1"
        )

        result = compile_registration_set(None, proposed, platform_configuration)

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [("OWNER_CONFLICT", "/registrations/0/attachments/0/resource_reference")],
        )

    def test_new_application_cannot_enter_directly_as_active(self) -> None:
        proposed = copy.deepcopy(
            _load_vector("valid/initial-registration-set.v1.json")
        )
        proposed["registrations"][0]["lifecycle"] = "active"

        result = compile_registration_set(
            None,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [("LIFECYCLE_TRANSITION_INVALID", "/registrations/0/lifecycle")],
        )

    def test_initial_application_begins_at_registration_revision_one(self) -> None:
        proposed = copy.deepcopy(
            _load_vector("valid/initial-registration-set.v1.json")
        )
        proposed["registrations"][0]["registration_revision"] = 2

        result = compile_registration_set(
            None,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [("GENERATION_INVALID", "/registrations/0/registration_revision")],
        )

    def test_initial_generation_cannot_invent_lineage(self) -> None:
        proposed = copy.deepcopy(
            _load_vector("valid/initial-registration-set.v1.json")
        )
        proposed["generation"] = 2

        result = compile_registration_set(
            None,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [("GENERATION_INVALID", "/generation")],
        )

    def test_suspension_and_reactivation_are_whole_generation_transitions(self) -> None:
        active = _load_vector("valid/active-registration-set.v1.json")
        suspended = copy.deepcopy(active)
        suspended["generation"] = 3
        suspended["previous_generation_digest"] = (
            "sha256:dbbf3a48ddfa7457bb5260bf4060958f31c2485317a255d51b7adca86c9f9224"
        )
        suspended["proposal"] = {
            "source_revision": "3333333",
            "change_summary": "Suspend alpha",
        }
        suspended["registrations"][0]["registration_revision"] = 3
        suspended["registrations"][0]["lifecycle"] = "suspended"

        suspended_result = compile_registration_set(
            active,
            suspended,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertEqual(suspended_result.violations, ())
        self.assertEqual(suspended_result.compiled_configuration["catalogue"], [])
        self.assertEqual(suspended_result.compiled_configuration["routes"], [])
        self.assertEqual(
            suspended_result.compiled_configuration["admission_policies"], []
        )
        reactivated = copy.deepcopy(suspended)
        reactivated["generation"] = 4
        reactivated["previous_generation_digest"] = (
            suspended_result.generation_digest
        )
        reactivated["proposal"] = {
            "source_revision": "4444444",
            "change_summary": "Reactivate alpha",
        }
        reactivated["registrations"][0]["registration_revision"] = 4
        reactivated["registrations"][0]["lifecycle"] = "active"

        reactivated_result = compile_registration_set(
            suspended,
            reactivated,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertEqual(reactivated_result.violations, ())
        self.assertEqual(len(reactivated_result.compiled_configuration["routes"]), 1)

    def test_active_registration_cannot_transition_backward_to_staged(self) -> None:
        active = _load_vector("valid/active-registration-set.v1.json")
        proposed = copy.deepcopy(active)
        proposed["generation"] = 3
        proposed["previous_generation_digest"] = (
            "sha256:dbbf3a48ddfa7457bb5260bf4060958f31c2485317a255d51b7adca86c9f9224"
        )
        proposed["proposal"] = {
            "source_revision": "3333333",
            "change_summary": "Attempt backward lifecycle transition",
        }
        proposed["registrations"][0]["registration_revision"] = 3
        proposed["registrations"][0]["lifecycle"] = "staged"

        result = compile_registration_set(
            active,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [("LIFECYCLE_TRANSITION_INVALID", "/registrations/0/lifecycle")],
        )

    def test_attachment_adapter_must_be_enabled_by_platform_configuration(self) -> None:
        proposed = copy.deepcopy(
            _load_vector("valid/initial-registration-set.v1.json")
        )
        proposed["registrations"][0]["attachments"][0]["adapter_kind"] = (
            "future-provider-v1"
        )

        result = compile_registration_set(
            None,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [("ATTACHMENT_INVALID", "/registrations/0/attachments/0/adapter_kind")],
        )

    def test_attachment_mounts_are_unique_within_registration(self) -> None:
        proposed = copy.deepcopy(
            _load_vector("valid/initial-registration-set.v1.json")
        )
        second = copy.deepcopy(proposed["registrations"][0]["attachments"][0])
        second["attachment_id"] = "api"
        second["resource_reference"] = (
            "urn:comfforts:app-platform:contract-test:alpha-app:api"
        )
        proposed["registrations"][0]["attachments"].append(second)

        result = compile_registration_set(
            None,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [("ATTACHMENT_CONFLICT", "/registrations/0/attachments/1/mount_path")],
        )

    def test_attachment_identifiers_are_unique_within_registration(self) -> None:
        proposed = copy.deepcopy(
            _load_vector("valid/initial-registration-set.v1.json")
        )
        second = copy.deepcopy(proposed["registrations"][0]["attachments"][0])
        second["mount_path"] = "/api"
        proposed["registrations"][0]["attachments"].append(second)

        result = compile_registration_set(
            None,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [
                (
                    "ATTACHMENT_CONFLICT",
                    "/registrations/0/attachments/1/attachment_id",
                )
            ],
        )

    def test_attachment_owner_must_match_registered_application(self) -> None:
        proposed = copy.deepcopy(
            _load_vector("valid/initial-registration-set.v1.json")
        )
        proposed["registrations"][0]["attachments"][0][
            "owner_application_id"
        ] = "other-app"

        result = compile_registration_set(
            None,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [
                (
                    "ATTACHMENT_INVALID",
                    "/registrations/0/attachments/0/owner_application_id",
                )
            ],
        )

    def test_contract_test_attachment_reference_is_owner_scoped(self) -> None:
        proposed = copy.deepcopy(
            _load_vector("valid/initial-registration-set.v1.json")
        )
        proposed["registrations"][0]["attachments"][0]["resource_reference"] = (
            "urn:comfforts:app-platform:contract-test:other-app:web"
        )

        result = compile_registration_set(
            None,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [
                (
                    "ATTACHMENT_INVALID",
                    "/registrations/0/attachments/0/resource_reference",
                )
            ],
        )

    def test_authenticated_admission_requires_verified_attachment_identity(self) -> None:
        proposed = copy.deepcopy(
            _load_vector("valid/initial-registration-set.v1.json")
        )
        proposed["registrations"][0]["admission"] = {"mode": "authenticated"}

        result = compile_registration_set(
            None,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [
                (
                    "IDENTITY_INVALID",
                    "/registrations/0/attachments/0/identity_requirement",
                )
            ],
        )

    def test_protected_audience_cannot_be_shared_between_applications(self) -> None:
        proposed = copy.deepcopy(
            _load_vector("valid/initial-registration-set.v1.json")
        )
        first = proposed["registrations"][0]
        first["admission"] = {"mode": "authenticated"}
        first["attachments"][0]["identity_requirement"] = "verified"
        first["attachments"][0]["audience"] = "shared-audience"
        second = copy.deepcopy(first)
        second["application_id"] = "beta-app"
        second["route_prefix"] = "/beta"
        second["catalogue"]["title"] = "Beta"
        second["attachments"][0]["owner_application_id"] = "beta-app"
        second["attachments"][0]["resource_reference"] = (
            "urn:comfforts:app-platform:contract-test:beta-app:web"
        )
        proposed["registrations"].append(second)

        result = compile_registration_set(
            None,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [("IDENTITY_INVALID", "/registrations/1/attachments/0/audience")],
        )

    def test_update_must_name_reviewed_predecessor_digest(self) -> None:
        previous = _load_vector("valid/initial-registration-set.v1.json")
        proposed = copy.deepcopy(previous)
        proposed["generation"] = 2
        proposed["previous_generation_digest"] = "sha256:" + ("0" * 64)
        proposed["proposal"] = {
            "source_revision": "2222222",
            "change_summary": "Activate alpha",
        }
        proposed["registrations"][0]["registration_revision"] = 2
        proposed["registrations"][0]["lifecycle"] = "active"

        result = compile_registration_set(
            previous,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [("GENERATION_INVALID", "/previous_generation_digest")],
        )

    def test_update_cannot_drop_registration_instead_of_retiring_it(self) -> None:
        previous = _load_vector("valid/initial-registration-set.v1.json")
        proposed = copy.deepcopy(previous)
        proposed["generation"] = 2
        proposed["previous_generation_digest"] = (
            "sha256:bdf0608ec2111ad74e6042edb2be550f47a8f4a15ca5ac7b3a6d09951df75008"
        )
        proposed["proposal"] = {
            "source_revision": "2222222",
            "change_summary": "Incorrectly remove alpha",
        }
        proposed["registrations"] = []

        result = compile_registration_set(
            previous,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [("LIFECYCLE_TRANSITION_INVALID", "/registrations")],
        )

    def test_later_generation_adds_new_application_as_staged(self) -> None:
        previous = _load_vector("valid/initial-registration-set.v1.json")
        proposed = copy.deepcopy(previous)
        proposed["generation"] = 2
        proposed["previous_generation_digest"] = (
            "sha256:bdf0608ec2111ad74e6042edb2be550f47a8f4a15ca5ac7b3a6d09951df75008"
        )
        proposed["proposal"] = {
            "source_revision": "2222222",
            "change_summary": "Incorrectly activate beta on entry",
        }
        second = copy.deepcopy(proposed["registrations"][0])
        second["application_id"] = "beta-app"
        second["route_prefix"] = "/beta"
        second["lifecycle"] = "active"
        second["catalogue"]["title"] = "Beta"
        second["attachments"][0]["owner_application_id"] = "beta-app"
        second["attachments"][0]["resource_reference"] = (
            "urn:comfforts:app-platform:contract-test:beta-app:web"
        )
        proposed["registrations"].append(second)

        result = compile_registration_set(
            previous,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [("LIFECYCLE_TRANSITION_INVALID", "/registrations/1/lifecycle")],
        )

    def test_later_generation_adds_new_application_at_revision_one(self) -> None:
        previous = _load_vector("valid/initial-registration-set.v1.json")
        proposed = copy.deepcopy(previous)
        proposed["generation"] = 2
        proposed["previous_generation_digest"] = (
            "sha256:bdf0608ec2111ad74e6042edb2be550f47a8f4a15ca5ac7b3a6d09951df75008"
        )
        proposed["proposal"] = {
            "source_revision": "2222222",
            "change_summary": "Incorrectly add beta at revision two",
        }
        second = copy.deepcopy(proposed["registrations"][0])
        second["application_id"] = "beta-app"
        second["registration_revision"] = 2
        second["route_prefix"] = "/beta"
        second["catalogue"]["title"] = "Beta"
        second["attachments"][0]["owner_application_id"] = "beta-app"
        second["attachments"][0]["resource_reference"] = (
            "urn:comfforts:app-platform:contract-test:beta-app:web"
        )
        proposed["registrations"].append(second)

        result = compile_registration_set(
            previous,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [("GENERATION_INVALID", "/registrations/1/registration_revision")],
        )

    def test_registered_value_change_must_advance_application_revision(self) -> None:
        previous = _load_vector("valid/initial-registration-set.v1.json")
        proposed = copy.deepcopy(previous)
        proposed["generation"] = 2
        proposed["previous_generation_digest"] = (
            "sha256:bdf0608ec2111ad74e6042edb2be550f47a8f4a15ca5ac7b3a6d09951df75008"
        )
        proposed["proposal"] = {
            "source_revision": "2222222",
            "change_summary": "Activate alpha",
        }
        proposed["registrations"][0]["lifecycle"] = "active"

        result = compile_registration_set(
            previous,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [("GENERATION_INVALID", "/registrations/0/registration_revision")],
        )

    def test_retired_registration_is_a_terminal_tombstone(self) -> None:
        previous = _load_vector("valid/retired-registration-set.v1.json")
        proposed = copy.deepcopy(previous)
        proposed["generation"] = 4
        proposed["previous_generation_digest"] = (
            "sha256:1f0c716cb37cba205260f90913c68aea29c7ed4d86a79b9e9b934da772547eb2"
        )
        proposed["proposal"] = {
            "source_revision": "4444444",
            "change_summary": "Attempt to reactivate alpha",
        }
        proposed["registrations"][0]["registration_revision"] = 4
        proposed["registrations"][0]["lifecycle"] = "active"

        result = compile_registration_set(
            previous,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [("LIFECYCLE_TRANSITION_INVALID", "/registrations/0/lifecycle")],
        )

    def test_retired_tombstone_values_are_immutable(self) -> None:
        previous = _load_vector("valid/retired-registration-set.v1.json")
        proposed = copy.deepcopy(previous)
        proposed["generation"] = 4
        proposed["previous_generation_digest"] = (
            "sha256:1f0c716cb37cba205260f90913c68aea29c7ed4d86a79b9e9b934da772547eb2"
        )
        proposed["proposal"] = {
            "source_revision": "4444444",
            "change_summary": "Attempt to rewrite retired metadata",
        }
        proposed["registrations"][0]["registration_revision"] = 4
        proposed["registrations"][0]["catalogue"]["title"] = "Rewritten"

        result = compile_registration_set(
            previous,
            proposed,
            _load_vector("valid/platform-configuration.v1.json"),
        )

        self.assertIsNone(result.compiled_configuration)
        self.assertEqual(
            [(violation.code, violation.path) for violation in result.violations],
            [("LIFECYCLE_TRANSITION_INVALID", "/registrations/0")],
        )


class IdentityContractTest(unittest.TestCase):
    def test_complete_identity_context_matches_versioned_schema(self) -> None:
        violations = validate_contract_instance(
            _valid_identity_context(),
            "urn:comfforts:app-platform:schema:verified-identity-context:v1",
        )

        self.assertEqual(violations, ())

    def test_identity_context_rejects_missing_and_application_owned_fields(self) -> None:
        identity_context = _valid_identity_context()
        del identity_context["issuer"]
        identity_context["email"] = "mutable@example.test"
        identity_context["application_principal"] = "principal-1"
        identity_context["feature_entitlements"] = ["synthetic-feature"]
        identity_context["product_role"] = "administrator"

        violations = validate_contract_instance(
            identity_context,
            "urn:comfforts:app-platform:schema:verified-identity-context:v1",
        )

        self.assertEqual(
            [(violation.code, violation.path) for violation in violations],
            [
                ("FIELD_UNKNOWN", "/application_principal"),
                ("FIELD_UNKNOWN", "/email"),
                ("FIELD_UNKNOWN", "/feature_entitlements"),
                ("FIELD_REQUIRED", "/issuer"),
                ("FIELD_UNKNOWN", "/product_role"),
            ],
        )

    def test_identity_context_rejects_wrong_types_and_contract_version(self) -> None:
        identity_context = _valid_identity_context()
        identity_context["contract_version"] = 2
        identity_context["issued_at"] = "100"

        violations = validate_contract_instance(
            identity_context,
            "urn:comfforts:app-platform:schema:verified-identity-context:v1",
        )

        self.assertEqual(
            [(violation.code, violation.path) for violation in violations],
            [
                ("CONTRACT_VERSION_UNSUPPORTED", "/contract_version"),
                ("FIELD_TYPE", "/issued_at"),
            ],
        )

    def test_identity_expiry_must_follow_issue_time(self) -> None:
        identity_context = _valid_identity_context()
        identity_context["expires_at"] = identity_context["issued_at"]

        violations = validate_contract_instance(
            identity_context,
            "urn:comfforts:app-platform:schema:verified-identity-context:v1",
        )

        self.assertEqual(
            [(violation.code, violation.path) for violation in violations],
            [("IDENTITY_INVALID", "/expires_at")],
        )


class ContractArtifactSafetyTest(unittest.TestCase):
    def test_committed_contract_json_has_no_high_signal_secret_material(self) -> None:
        patterns = {
            "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
            "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
            "jwt": re.compile(
                r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
            ),
            "assigned_secret": re.compile(
                r"(?i)(?:api[_-]?key|client[_-]?secret|password)\s*[:=]\s*[^\s]+"
            ),
        }

        for path in (PROJECT_ROOT / "contracts").rglob("*.json"):
            payload = path.read_text(encoding="utf-8")
            for name, pattern in patterns.items():
                with self.subTest(path=path.relative_to(PROJECT_ROOT), pattern=name):
                    self.assertIsNone(pattern.search(payload))


if __name__ == "__main__":
    unittest.main()
