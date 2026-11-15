"""Deterministic behavior checks for the in-process reference edge."""

from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from contracts.validation import load_json_document
from fixtures import (
    AUTHENTICATED_AUDIENCE,
    FIXTURE_SESSION_HEADER,
    FIXTURE_IDENTITY_ISSUER,
    RESTRICTED_AUDIENCE,
    VERIFIED_IDENTITY_HEADER,
    FixtureIdentitySigner,
    FixtureIdentityVerifier,
    ReferenceEdge,
    Request,
    Response,
    SyntheticIdentity,
    SyntheticIdentityAdapter,
    VerificationResult,
    build_fixture_applications,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _attachment(
    application_id: str,
    attachment_id: str,
    mount_path: str,
    forwarding_mode: str,
    *,
    audience: str | None = None,
) -> dict[str, Any]:
    return {
        "contract_version": 1,
        "owner_application_id": application_id,
        "attachment_id": attachment_id,
        "adapter_kind": "fixture-in-process-v1",
        "resource_reference": (
            "urn:comfforts:app-platform:fixture:"
            f"{application_id}:{attachment_id}"
        ),
        "mount_path": mount_path,
        "forwarding_mode": forwarding_mode,
        "identity_requirement": "verified" if audience is not None else "none",
        "audience": audience,
        "ingress_mode": "shared_edge_only",
    }


def _registration(
    application_id: str,
    route_prefix: str,
    attachments: list[dict[str, Any]],
    *,
    lifecycle: str,
    revision: int,
    visibility: str = "listed",
    title: str | None = None,
    admission: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "contract_version": 1,
        "application_id": application_id,
        "registration_revision": revision,
        "route_prefix": route_prefix,
        "catalogue": {
            "visibility": visibility,
            "title": title or application_id,
            "summary": f"Synthetic summary for {application_id}",
        },
        "admission": copy.deepcopy(admission or {"mode": "public"}),
        "lifecycle": lifecycle,
        "attachments": attachments,
    }


def _registration_set(
    generation: int,
    previous_digest: str | None,
    registrations: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "contract_version": 1,
        "generation": generation,
        "previous_generation_digest": previous_digest,
        "proposal": {
            "source_revision": f"{generation}" * 7,
            "change_summary": f"Synthetic fixture generation {generation}",
        },
        "registrations": copy.deepcopy(registrations),
    }


class _RecordingAttachment:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.requests: list[Request] = []
        self.failure: Exception | None = None

    def __call__(self, request: Request) -> Response:
        self.requests.append(request)
        if self.failure is not None:
            raise self.failure
        return Response(
            status=200,
            outcome="fixture",
            headers=(("Content-Type", "text/plain; charset=utf-8"),),
            body=self.body,
        )


class _Clock:
    def __init__(self, value: int) -> None:
        self.value = value

    def __call__(self) -> int:
        return self.value


class _CorrelationIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"fixture-request-{self.value}"


class _VerifyingAttachment:
    def __init__(self, verifier: FixtureIdentityVerifier) -> None:
        self.verifier = verifier
        self.requests: list[Request] = []
        self.results: list[VerificationResult] = []

    def __call__(self, request: Request) -> Response:
        self.requests.append(request)
        assertions = [
            value
            for name, value in request.headers
            if name.lower() == VERIFIED_IDENTITY_HEADER.lower()
        ]
        result = self.verifier.verify(assertions[0] if len(assertions) == 1 else None)
        self.results.append(result)
        return Response(
            status=200 if result.accepted else 401,
            outcome="fixture-identity",
            headers=(("Content-Type", "text/plain; charset=utf-8"),),
            body=b"verified" if result.accepted else b"denied",
        )


def _signed_assertion(key: bytes, claims: dict[str, Any]) -> str:
    payload = json.dumps(
        claims,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    payload_segment = base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")
    signed = f"fixture-v1.{payload_segment}".encode("ascii")
    signature = hmac.new(key, signed, hashlib.sha256).digest()
    signature_segment = (
        base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    )
    return f"fixture-v1.{payload_segment}.{signature_segment}"


class _CatalogueParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.text: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag == "a":
            values = dict(attrs)
            if values.get("href") is not None:
                self.links.append(values["href"] or "")

    def handle_data(self, data: str) -> None:
        self.text.append(data)


class ReferenceEdgeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.preserve = _RecordingAttachment(b"preserve")
        self.strip_prefix = _RecordingAttachment(b"strip-prefix")
        self.strip_mount = _RecordingAttachment(b"strip-mount")
        self.beta = _RecordingAttachment(b"beta")
        self.gamma = _RecordingAttachment(b"gamma")
        self.attachments = {
            "urn:comfforts:app-platform:fixture:alpha-app:preserve": self.preserve,
            "urn:comfforts:app-platform:fixture:alpha-app:strip-prefix": self.strip_prefix,
            "urn:comfforts:app-platform:fixture:alpha-app:strip-mount": self.strip_mount,
            "urn:comfforts:app-platform:fixture:beta-app:web": self.beta,
            "urn:comfforts:app-platform:fixture:gamma-app:web": self.gamma,
        }
        self.staged_registrations = self._registrations("staged", 1)
        self.edge = ReferenceEdge(self.attachments)
        staged = self.edge.activate(
            _registration_set(1, None, self.staged_registrations)
        )
        self.assertTrue(staged.accepted)
        self.assertIsNotNone(staged.generation_digest)
        active_registrations = self._registrations("active", 2)
        active_registrations[0]["lifecycle"] = "staged"
        active_registrations[0]["registration_revision"] = 1
        active = self.edge.activate(
            _registration_set(2, staged.generation_digest, active_registrations)
        )
        self.assertTrue(active.accepted)
        self.active_digest = active.generation_digest

    def _registrations(self, lifecycle: str, revision: int) -> list[dict[str, Any]]:
        return [
            _registration(
                "gamma-app",
                "/gamma",
                [_attachment("gamma-app", "web", "/", "preserve")],
                lifecycle=lifecycle,
                revision=revision,
            ),
            _registration(
                "beta-app",
                "/beta",
                [_attachment("beta-app", "web", "/", "strip_application_prefix")],
                lifecycle=lifecycle,
                revision=revision,
                title="Beta & Beyond",
            ),
            _registration(
                "alpha-app",
                "/alpha",
                [
                    _attachment("alpha-app", "preserve", "/", "preserve"),
                    _attachment(
                        "alpha-app", "strip-prefix", "/api", "strip_application_prefix"
                    ),
                    _attachment(
                        "alpha-app", "strip-mount", "/api/v1", "strip_attachment_mount"
                    ),
                ],
                lifecycle=lifecycle,
                revision=revision,
            ),
        ]

    def test_catalogue_is_compiled_ordered_and_escaped(self) -> None:
        response = self.edge.handle(Request("GET", "/"))
        parser = _CatalogueParser()
        parser.feed(response.body.decode("utf-8"))

        self.assertEqual(response.status, 200)
        self.assertEqual(response.outcome, "catalogue")
        self.assertEqual(parser.links, ["/alpha", "/beta"])
        self.assertIn("Beta & Beyond", "".join(parser.text))
        self.assertIn(b"Beta &amp; Beyond", response.body)
        self.assertNotIn(b"gamma-app", response.body)
        self.assertNotIn(b"resource_reference", response.body)

    def test_route_mount_and_forwarding_modes_use_compiled_configuration(self) -> None:
        cases = (
            ("/alpha", "", self.preserve, "/alpha"),
            ("/alpha/", "", self.preserve, "/alpha/"),
            ("/alpha/File.Name", "", self.preserve, "/alpha/File.Name"),
            ("/alpha/é", "", self.preserve, "/alpha/é"),
            ("/alpha/api/item", "page=1", self.strip_prefix, "/api/item"),
            ("/alpha/api/v1/item", "page=2", self.strip_mount, "/item"),
            ("/beta/item", "", self.beta, "/item"),
        )
        for path, query, target, expected_path in cases:
            with self.subTest(path=path):
                response = self.edge.handle(Request("GET", path, query=query))
                self.assertEqual(response.status, 200)
                self.assertEqual(response.outcome, "forwarded")
                self.assertEqual(target.requests[-1].path, expected_path)
                self.assertEqual(target.requests[-1].query, query)

        self.assertEqual(len(self.preserve.requests), 4)
        self.assertEqual(len(self.strip_prefix.requests), 1)
        self.assertEqual(len(self.strip_mount.requests), 1)
        self.assertEqual(len(self.beta.requests), 1)

    def test_closed_and_malformed_paths_never_invoke_an_attachment(self) -> None:
        closed = (
            "/alphabet",
            "/unknown",
            "/Alpha",
            "/_platform/status",
            "/.well-known/test",
            "/gamma",
        )
        malformed = (
            "/alpha//item",
            "/alpha/./item",
            "/alpha/%2fitem",
            "/alpha\\item",
            "/alpha?item",
            "/alpha item",
        )
        for path in closed:
            with self.subTest(path=path):
                response = self.edge.handle(Request("GET", path))
                self.assertEqual((response.status, response.outcome), (404, "route_closed"))
        for path in malformed:
            with self.subTest(path=path):
                response = self.edge.handle(Request("GET", path))
                self.assertEqual((response.status, response.outcome), (400, "request_invalid"))
        self.assertFalse(self.preserve.requests)
        self.assertFalse(self.strip_prefix.requests)
        self.assertFalse(self.strip_mount.requests)
        self.assertFalse(self.beta.requests)
        self.assertFalse(self.gamma.requests)

    def test_activation_rejects_wrong_or_unavailable_fixture_binding_atomically(self) -> None:
        wrong_reference = _registration_set(1, None, self.staged_registrations)
        wrong_reference["registrations"][0]["attachments"][0][
            "resource_reference"
        ] = "urn:comfforts:app-platform:fixture:gamma-app:other"
        empty_edge = ReferenceEdge(self.attachments)
        rejected = empty_edge.activate(wrong_reference)
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.issues[0].code, "ATTACHMENT_INVALID")
        self.assertEqual(empty_edge.handle(Request("GET", "/")).status, 503)

        proposed = self._registrations("active", 2)
        proposed[0]["lifecycle"] = "staged"
        proposed[0]["registration_revision"] = 1
        beta = next(item for item in proposed if item["application_id"] == "beta-app")
        beta["registration_revision"] = 3
        beta["attachments"][0]["attachment_id"] = "replacement"
        beta["attachments"][0]["resource_reference"] = (
            "urn:comfforts:app-platform:fixture:beta-app:replacement"
        )
        failed = self.edge.activate(
            _registration_set(3, self.active_digest, proposed)
        )

        self.assertFalse(failed.accepted)
        self.assertEqual(failed.issues[0].code, "FIXTURE_ATTACHMENT_UNAVAILABLE")
        self.assertEqual(self.edge.handle(Request("GET", "/beta")).body, b"beta")

    def test_request_limits_are_enforced_before_forwarding(self) -> None:
        accepted_path = "/a" * 512
        accepted_headers = tuple(("a", "v") for _ in range(32))
        aggregate_limit = tuple(("a", "v" * 1_023) for _ in range(8))
        cases = (
            (Request("X" * 16, "/alpha"), 405),
            (Request("X" * 17, "/alpha"), 400),
            (Request("GET", accepted_path), 404),
            (Request("GET", f"{accepted_path}a"), 400),
            (Request("GET", "/alpha", query="q" * 1_024), 200),
            (Request("GET", "/alpha", query="q" * 1_025), 400),
            (Request("GET", "/alpha", headers=accepted_headers), 200),
            (Request("GET", "/alpha", headers=accepted_headers + (("b", "v"),)), 400),
            (Request("GET", "/alpha", headers=(("a" * 64, "v"),)), 200),
            (Request("GET", "/alpha", headers=(("a" * 65, "v"),)), 400),
            (Request("GET", "/alpha", headers=(("a", "v" * 1_024),)), 200),
            (Request("GET", "/alpha", headers=(("a", "v" * 1_025),)), 400),
            (Request("GET", "/alpha", headers=aggregate_limit), 200),
            (
                Request(
                    "GET",
                    "/alpha",
                    headers=aggregate_limit[:-1] + (("a", "v" * 1_024),),
                ),
                400,
            ),
            (Request("GET", "/alpha", body=b"x"), 400),
            (
                Request(
                    "GET",
                    "/alpha",
                    headers=(
                        ("X-Comfforts-Verified-Identity", "one"),
                        ("x-comfforts-verified-identity", "two"),
                    ),
                ),
                400,
            ),
            (
                Request(
                    "GET",
                    "/alpha",
                    headers=(
                        (FIXTURE_SESSION_HEADER, "one"),
                        (FIXTURE_SESSION_HEADER.lower(), "two"),
                    ),
                ),
                400,
            ),
        )
        for request, expected_status in cases:
            with self.subTest(request=request):
                self.assertEqual(self.edge.handle(request).status, expected_status)

    def test_attachment_failure_and_invalid_response_are_isolated(self) -> None:
        self.beta.failure = RuntimeError("synthetic failure")
        failed = self.edge.handle(Request("GET", "/beta"))
        healthy = self.edge.handle(Request("GET", "/alpha"))

        self.assertEqual((failed.status, failed.outcome), (502, "attachment_unavailable"))
        self.assertEqual((healthy.status, healthy.body), (200, b"preserve"))

        self.preserve.failure = None
        self.preserve.body = b"x" * 65_536
        boundary = self.edge.handle(Request("GET", "/alpha"))
        self.assertEqual((boundary.status, len(boundary.body)), (200, 65_536))

        self.preserve.body = b"x" * 65_537
        invalid = self.edge.handle(Request("GET", "/alpha"))
        self.assertEqual(
            (invalid.status, invalid.outcome),
            (502, "attachment_response_invalid"),
        )

    def test_activation_and_requests_do_not_mutate_caller_inputs(self) -> None:
        registration_set = _registration_set(1, None, self.staged_registrations)
        before_registration = copy.deepcopy(registration_set)
        request = Request("GET", "/alpha", headers=(("X-Test", "value"),))

        ReferenceEdge(self.attachments).activate(registration_set)
        self.edge.handle(request)

        self.assertEqual(registration_set, before_registration)
        self.assertEqual(request.headers, (("X-Test", "value"),))

    def test_fixture_layer_runs_from_an_extracted_project_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            extracted_root = Path(temporary_directory) / "apps-platform"
            shutil.copytree(PROJECT_ROOT / "contracts", extracted_root / "contracts")
            shutil.copytree(PROJECT_ROOT / "fixtures", extracted_root / "fixtures")
            before = {
                path.relative_to(extracted_root): path.read_bytes()
                for path in extracted_root.rglob("*")
                if path.is_file()
            }
            program = "\n".join(
                (
                    "from fixtures import (",
                    "    FixtureIdentitySigner, FixtureIdentityVerifier,",
                    "    ReferenceEdge, Request, SyntheticIdentity,",
                    ")",
                    "registration_set = {",
                    "    'contract_version': 1,",
                    "    'generation': 1,",
                    "    'previous_generation_digest': None,",
                    "    'proposal': {",
                    "        'source_revision': '1111111',",
                    "        'change_summary': 'Extraction fixture',",
                    "    },",
                    "    'registrations': [],",
                    "}",
                    "edge = ReferenceEdge({})",
                    "result = edge.activate(registration_set)",
                    "assert result.accepted",
                    "assert edge.handle(Request('GET', '/')).status == 200",
                    "clock = lambda: 100",
                    "correlation_ids = iter(('extracted-request',))",
                    "test_key = b'public-extraction-test-material'",
                    "identity = SyntheticIdentity(",
                    "    'urn:comfforts:identity:fixture', 'extracted-user',",
                    ")",
                    "signer = FixtureIdentitySigner(",
                    "    test_key, clock, lambda: next(correlation_ids),",
                    ")",
                    "audience = 'urn:comfforts:app-platform:audience:extracted'",
                    "assertion = signer.issue(identity, audience)",
                    "verifier = FixtureIdentityVerifier(",
                    "    test_key, identity.issuer, audience, clock,",
                    ")",
                    "assert verifier.verify(assertion).accepted",
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


class FixtureIdentityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.key = b"public-fixture-key-material-v1"
        self.issuer = "urn:comfforts:identity:fixture"
        self.authenticated_audience = (
            "urn:comfforts:app-platform:audience:identity-authenticated"
        )
        self.restricted_audience = (
            "urn:comfforts:app-platform:audience:identity-restricted"
        )
        self.clock = _Clock(100)
        self.allowed_identity = SyntheticIdentity(self.issuer, "synthetic-user-a")
        self.other_identity = SyntheticIdentity(self.issuer, "synthetic-user-b")
        identity_adapter = SyntheticIdentityAdapter(
            {
                "allowed-session": self.allowed_identity,
                "other-session": self.other_identity,
            }
        )
        signer = FixtureIdentitySigner(
            self.key, self.clock, _CorrelationIds()
        )
        self.public = _RecordingAttachment(b"public")
        self.authenticated = _VerifyingAttachment(
            FixtureIdentityVerifier(
                self.key,
                self.issuer,
                self.authenticated_audience,
                self.clock,
            )
        )
        self.restricted = _VerifyingAttachment(
            FixtureIdentityVerifier(
                self.key,
                self.issuer,
                self.restricted_audience,
                self.clock,
            )
        )
        self.attachment_map = {
            "urn:comfforts:app-platform:fixture:identity-public:web": self.public,
            "urn:comfforts:app-platform:fixture:identity-authenticated:web": (
                self.authenticated
            ),
            "urn:comfforts:app-platform:fixture:identity-restricted:web": (
                self.restricted
            ),
        }
        self.edge = ReferenceEdge(
            self.attachment_map,
            identity_adapter=identity_adapter,
            identity_signer=signer,
        )
        staged = self.edge.activate(
            _registration_set(1, None, self._registrations("staged", 1))
        )
        self.assertTrue(staged.accepted)
        active = self.edge.activate(
            _registration_set(
                2,
                staged.generation_digest,
                self._registrations("active", 2),
            )
        )
        self.assertTrue(active.accepted)

    def _registrations(self, lifecycle: str, revision: int) -> list[dict[str, Any]]:
        return [
            _registration(
                "identity-restricted",
                "/restricted",
                [
                    _attachment(
                        "identity-restricted",
                        "web",
                        "/",
                        "strip_application_prefix",
                        audience=self.restricted_audience,
                    )
                ],
                lifecycle=lifecycle,
                revision=revision,
                admission={
                    "mode": "restricted",
                    "members": [
                        {
                            "issuer": self.allowed_identity.issuer,
                            "subject": self.allowed_identity.subject,
                        }
                    ],
                },
            ),
            _registration(
                "identity-public",
                "/public",
                [
                    _attachment(
                        "identity-public",
                        "web",
                        "/",
                        "strip_application_prefix",
                    )
                ],
                lifecycle=lifecycle,
                revision=revision,
            ),
            _registration(
                "identity-authenticated",
                "/authenticated",
                [
                    _attachment(
                        "identity-authenticated",
                        "web",
                        "/",
                        "strip_application_prefix",
                        audience=self.authenticated_audience,
                    )
                ],
                lifecycle=lifecycle,
                revision=revision,
                admission={"mode": "authenticated"},
            ),
        ]

    def _claims(self, correlation_id: str = "fixture-claim") -> dict[str, Any]:
        return {
            "contract_version": 1,
            "issuer": self.issuer,
            "subject": "synthetic-user-a",
            "audience": self.authenticated_audience,
            "issued_at": 100,
            "expires_at": 160,
            "correlation_id": correlation_id,
        }

    def test_edge_applies_admission_and_replaces_visitor_identity(self) -> None:
        public_response = self.edge.handle(
            Request(
                "GET",
                "/public",
                headers=(
                    (VERIFIED_IDENTITY_HEADER, "visitor-controlled"),
                    (FIXTURE_SESSION_HEADER, "allowed-session"),
                ),
            )
        )
        self.assertEqual((public_response.status, public_response.body), (200, b"public"))
        self.assertEqual(self.public.requests[-1].headers, ())

        missing = self.edge.handle(Request("GET", "/authenticated"))
        unknown = self.edge.handle(
            Request(
                "GET",
                "/authenticated",
                headers=((FIXTURE_SESSION_HEADER, "unknown-session"),),
            )
        )
        self.assertEqual(
            (missing.status, missing.body),
            (401, b"authentication required\n"),
        )
        self.assertEqual((unknown.status, unknown.body), (missing.status, missing.body))

        authenticated = self.edge.handle(
            Request(
                "GET",
                "/authenticated",
                headers=(
                    (VERIFIED_IDENTITY_HEADER, "visitor-controlled"),
                    (FIXTURE_SESSION_HEADER, "allowed-session"),
                ),
            )
        )
        self.assertEqual((authenticated.status, authenticated.body), (200, b"verified"))
        self.assertTrue(self.authenticated.results[-1].accepted)
        forwarded_headers = self.authenticated.requests[-1].headers
        self.assertNotIn("visitor-controlled", dict(forwarded_headers).values())
        self.assertFalse(
            any(
                name.lower() == FIXTURE_SESSION_HEADER.lower()
                for name, _ in forwarded_headers
            )
        )
        self.assertEqual(
            sum(
                name.lower() == VERIFIED_IDENTITY_HEADER.lower()
                for name, _ in forwarded_headers
            ),
            1,
        )

        denied = self.edge.handle(
            Request(
                "GET",
                "/restricted",
                headers=((FIXTURE_SESSION_HEADER, "other-session"),),
            )
        )
        self.assertEqual((denied.status, denied.body), (403, b"admission denied\n"))
        self.assertFalse(self.restricted.requests)

        allowed = self.edge.handle(
            Request(
                "GET",
                "/restricted",
                headers=((FIXTURE_SESSION_HEADER, "allowed-session"),),
            )
        )
        self.assertEqual((allowed.status, allowed.body), (200, b"verified"))
        self.assertTrue(self.restricted.results[-1].accepted)

    def test_protected_entry_point_verifies_audience_and_replay(self) -> None:
        direct_missing = self.authenticated(Request("GET", "/"))
        self.assertEqual(direct_missing.status, 401)
        self.assertEqual(self.authenticated.results[-1].code, "assertion_missing")

        admitted = self.edge.handle(
            Request(
                "GET",
                "/authenticated",
                headers=((FIXTURE_SESSION_HEADER, "allowed-session"),),
            )
        )
        self.assertEqual(admitted.status, 200)
        forwarded_request = self.authenticated.requests[-1]

        replayed = self.authenticated(forwarded_request)
        self.assertEqual(replayed.status, 401)
        self.assertEqual(self.authenticated.results[-1].code, "identity_replayed")

        cross_application = self.restricted(forwarded_request)
        self.assertEqual(cross_application.status, 401)
        self.assertEqual(
            self.restricted.results[-1].code,
            "identity_audience_invalid",
        )

    def test_protected_route_fails_closed_without_identity_dependencies(self) -> None:
        edge = ReferenceEdge(self.attachment_map)
        staged = edge.activate(
            _registration_set(1, None, self._registrations("staged", 1))
        )
        self.assertTrue(staged.accepted)
        active = edge.activate(
            _registration_set(
                2,
                staged.generation_digest,
                self._registrations("active", 2),
            )
        )
        self.assertTrue(active.accepted)

        response = edge.handle(
            Request(
                "GET",
                "/authenticated",
                headers=((FIXTURE_SESSION_HEADER, "allowed-session"),),
            )
        )
        self.assertEqual((response.status, response.outcome), (503, "identity_unavailable"))
        self.assertFalse(self.authenticated.requests)

    def test_verifier_rejects_forged_and_invalid_claims(self) -> None:
        cases: list[tuple[str, str | None, str]] = [
            ("missing", None, "assertion_missing"),
            ("malformed", "visitor-controlled", "assertion_malformed"),
            ("unsigned", "fixture-v1.e30", "assertion_malformed"),
            (
                "wrong-key",
                _signed_assertion(b"other-public-test-key", self._claims()),
                "assertion_signature_invalid",
            ),
        ]
        changed_claims = (
            ("version", {"contract_version": 2}, "identity_contract_invalid"),
            (
                "issuer",
                {"issuer": "urn:comfforts:identity:other"},
                "identity_issuer_invalid",
            ),
            ("subject", {"subject": "bad subject"}, "identity_contract_invalid"),
            (
                "audience",
                {"audience": self.restricted_audience},
                "identity_audience_invalid",
            ),
            (
                "future",
                {"issued_at": 101, "expires_at": 161},
                "identity_not_yet_valid",
            ),
            (
                "expired",
                {"issued_at": 40, "expires_at": 100},
                "identity_expired",
            ),
            (
                "lifetime",
                {"issued_at": 100, "expires_at": 161},
                "identity_lifetime_invalid",
            ),
        )
        for name, changes, code in changed_claims:
            claims = self._claims(f"fixture-{name}")
            claims.update(changes)
            cases.append((name, _signed_assertion(self.key, claims), code))

        for name, assertion, expected_code in cases:
            with self.subTest(name=name):
                verifier = FixtureIdentityVerifier(
                    self.key,
                    self.issuer,
                    self.authenticated_audience,
                    self.clock,
                )
                result = verifier.verify(assertion)
                self.assertFalse(result.accepted)
                self.assertIsNone(result.identity)
                self.assertEqual(result.code, expected_code)

        valid = FixtureIdentityVerifier(
            self.key,
            self.issuer,
            self.authenticated_audience,
            self.clock,
        ).verify(_signed_assertion(self.key, self._claims("fixture-valid")))
        self.assertTrue(valid.accepted)
        self.assertEqual(valid.identity.subject, "synthetic-user-a")

    def test_replay_store_is_bounded_and_removes_only_expired_entries(self) -> None:
        verifier = FixtureIdentityVerifier(
            self.key,
            self.issuer,
            self.authenticated_audience,
            self.clock,
        )
        for index in range(256):
            assertion = _signed_assertion(
                self.key, self._claims(f"fixture-replay-{index}")
            )
            self.assertTrue(verifier.verify(assertion).accepted)

        full = verifier.verify(
            _signed_assertion(self.key, self._claims("fixture-replay-full"))
        )
        self.assertEqual((full.accepted, full.code), (False, "replay_capacity"))

        self.clock.value = 161
        replacement_claims = self._claims("fixture-replay-after-expiry")
        replacement_claims.update({"issued_at": 161, "expires_at": 221})
        after_expiry = verifier.verify(
            _signed_assertion(self.key, replacement_claims)
        )
        self.assertTrue(after_expiry.accepted)


class ReviewedFixtureApplicationsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registration_root = PROJECT_ROOT / "fixtures" / "registrations"
        manifest_document = load_json_document(
            self.registration_root / "manifest.v1.json"
        )
        self.assertEqual(manifest_document.violations, ())
        self.manifest = manifest_document.value
        self.assertEqual(self.manifest["manifest_version"], 1)
        self.assertEqual(self.manifest["evidence_class"], "F")

        self.clock = _Clock(1_000)
        self.key = b"public-reviewed-fixture-key-material-v1"
        self.correlation_ids = _CorrelationIds()
        self.fixture_set = build_fixture_applications(self.key, self.clock)
        self.allowed_identity = SyntheticIdentity(
            FIXTURE_IDENTITY_ISSUER, "synthetic-user-a"
        )
        identity_adapter = SyntheticIdentityAdapter(
            {
                "allowed-session": self.allowed_identity,
                "other-session": SyntheticIdentity(
                    FIXTURE_IDENTITY_ISSUER, "synthetic-user-b"
                ),
            }
        )
        self.signer = FixtureIdentitySigner(
            self.key, self.clock, self.correlation_ids
        )
        self.edge = ReferenceEdge(
            self.fixture_set.attachments,
            identity_adapter=identity_adapter,
            identity_signer=self.signer,
        )
        self.registration_sets: list[dict[str, Any]] = []
        for entry in self.manifest["generations"]:
            document = load_json_document(self.registration_root / entry["path"])
            self.assertEqual(document.violations, ())
            self.registration_sets.append(document.value)
            result = self.edge.activate(document.value)
            self.assertTrue(result.accepted, result.issues)
            self.assertEqual(result.generation_digest, entry["expected_digest"])

    def _session_headers(self, session: str = "allowed-session") -> tuple[tuple[str, str], ...]:
        return ((FIXTURE_SESSION_HEADER, session),)

    def test_reviewed_registrations_activate_the_exact_fixture_set(self) -> None:
        self.assertEqual(
            [entry["generation"] for entry in self.manifest["generations"]],
            [1, 2],
        )
        self.assertEqual(
            set(self.fixture_set.states),
            {"fixture-public", "fixture-authenticated", "fixture-restricted"},
        )
        self.assertEqual(
            set(self.fixture_set.attachments),
            {
                "urn:comfforts:app-platform:fixture:fixture-public:web",
                "urn:comfforts:app-platform:fixture:fixture-public:api",
                "urn:comfforts:app-platform:fixture:fixture-authenticated:web",
                "urn:comfforts:app-platform:fixture:fixture-restricted:web",
            },
        )

        catalogue = self.edge.handle(Request("GET", "/"))
        parser = _CatalogueParser()
        parser.feed(catalogue.body.decode("utf-8"))
        self.assertEqual(parser.links, ["/public", "/restricted"])
        self.assertNotIn("/authenticated", parser.links)

        public = self.edge.handle(Request("GET", "/public"))
        public_api = self.edge.handle(Request("GET", "/public/api/v1/status"))
        authenticated = self.edge.handle(
            Request("GET", "/authenticated", headers=self._session_headers())
        )
        restricted = self.edge.handle(
            Request("GET", "/restricted", headers=self._session_headers())
        )
        self.assertEqual((public.status, public.body), (200, b"public fixture\n"))
        self.assertEqual(
            (public_api.status, public_api.body),
            (200, b"public fixture api\n"),
        )
        self.assertEqual((authenticated.status, authenticated.body), (200, b"unrestricted fixture\n"))
        self.assertEqual((restricted.status, restricted.body), (200, b"unrestricted fixture\n"))

    def test_application_principals_and_feature_entitlements_remain_app_owned(self) -> None:
        authenticated = self.edge.handle(
            Request("GET", "/authenticated", headers=self._session_headers())
        )
        unrestricted = self.edge.handle(
            Request("GET", "/restricted", headers=self._session_headers())
        )
        premium = self.edge.handle(
            Request("GET", "/restricted/premium", headers=self._session_headers())
        )

        self.assertEqual(authenticated.status, 200)
        self.assertEqual(unrestricted.status, 200)
        self.assertEqual((premium.status, premium.body), (403, b"feature denied\n"))
        self.assertEqual(premium.outcome, "forwarded")

        public_state = self.fixture_set.states["fixture-public"].snapshot()
        authenticated_state = self.fixture_set.states[
            "fixture-authenticated"
        ].snapshot()
        restricted_state = self.fixture_set.states["fixture-restricted"].snapshot()
        self.assertEqual(public_state.principal_count, 0)
        self.assertEqual(authenticated_state.principal_count, 1)
        self.assertEqual(restricted_state.principal_count, 1)
        self.assertEqual(restricted_state.feature_denials, 1)
        self.assertNotEqual(
            authenticated_state.principal_fingerprints,
            restricted_state.principal_fingerprints,
        )

    def test_fixture_state_and_identity_are_isolated_across_applications(self) -> None:
        states = self.fixture_set.states
        self.assertEqual(len({id(state) for state in states.values()}), 3)
        with self.assertRaises(AttributeError):
            setattr(states["fixture-public"], "application_id", "other-application")

        self.edge.handle(Request("GET", "/public"))
        after_public = {name: state.snapshot() for name, state in states.items()}
        self.assertEqual(after_public["fixture-public"].handled_requests, 1)
        self.assertEqual(after_public["fixture-authenticated"].handled_requests, 0)
        self.assertEqual(after_public["fixture-restricted"].handled_requests, 0)

        self.edge.handle(
            Request("GET", "/authenticated", headers=self._session_headers())
        )
        after_authenticated = {
            name: state.snapshot() for name, state in states.items()
        }
        self.assertEqual(after_authenticated["fixture-public"].handled_requests, 1)
        self.assertEqual(
            after_authenticated["fixture-authenticated"].handled_requests, 1
        )
        self.assertEqual(after_authenticated["fixture-restricted"].handled_requests, 0)

        assertion = self.signer.issue(
            self.allowed_identity, AUTHENTICATED_AUDIENCE
        )
        restricted_attachment = self.fixture_set.attachments[
            "urn:comfforts:app-platform:fixture:fixture-restricted:web"
        ]
        cross_application = restricted_attachment(
            Request(
                "GET",
                "/",
                headers=((VERIFIED_IDENTITY_HEADER, assertion),),
            )
        )
        self.assertEqual((cross_application.status, cross_application.body), (401, b"identity denied\n"))
        self.assertEqual(
            states["fixture-restricted"].snapshot().handled_requests,
            0,
        )

        missing = restricted_attachment(Request("GET", "/"))
        self.assertEqual((missing.status, missing.body), (401, b"identity denied\n"))
        self.assertEqual(
            states["fixture-restricted"].snapshot().handled_requests,
            0,
        )

    def test_registration_inputs_are_independent_and_revision_bound(self) -> None:
        application_revision = hashlib.sha256(
            (PROJECT_ROOT / "fixtures" / "applications.py").read_bytes()
        ).hexdigest()
        for registration_set in self.registration_sets:
            self.assertEqual(
                registration_set["proposal"]["source_revision"],
                application_revision,
            )
            self.assertEqual(
                {item["application_id"] for item in registration_set["registrations"]},
                {
                    "fixture-public",
                    "fixture-authenticated",
                    "fixture-restricted",
                },
            )

        committed_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(self.registration_root.glob("*.json"))
        ).lower()
        self.assertNotIn("contract-test-v1", committed_text)
        self.assertNotIn("ai_finance", committed_text)
        self.assertNotIn("finance assistant", committed_text)
        self.assertNotIn("terraform", committed_text)
        self.assertNotIn("credential", committed_text)
        self.assertIn(RESTRICTED_AUDIENCE, committed_text)


if __name__ == "__main__":
    unittest.main()
