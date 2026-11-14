"""Deterministic behavior checks for the in-process reference edge."""

from __future__ import annotations

import copy
import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from fixtures import ReferenceEdge, Request, Response


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _attachment(
    application_id: str,
    attachment_id: str,
    mount_path: str,
    forwarding_mode: str,
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
        "identity_requirement": "none",
        "audience": None,
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
        "admission": {"mode": "public"},
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
                    "from fixtures import ReferenceEdge, Request",
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


if __name__ == "__main__":
    unittest.main()
