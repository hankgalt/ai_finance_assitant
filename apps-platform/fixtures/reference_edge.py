"""Deterministic in-process reference edge for Fixture qualification."""

from __future__ import annotations

import copy
import html
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, TypeAlias

from contracts.validation import compile_registration_set


FIXTURE_ADAPTER_KIND = "fixture-in-process-v1"
VERIFIED_IDENTITY_HEADER = "x-comfforts-verified-identity"

MAX_METHOD_BYTES = 16
MAX_PATH_BYTES = 1_024
MAX_QUERY_BYTES = 1_024
MAX_HEADER_COUNT = 32
MAX_HEADER_NAME_BYTES = 64
MAX_HEADER_VALUE_BYTES = 1_024
MAX_HEADER_BYTES = 8_192
MAX_RESPONSE_BODY_BYTES = 65_536

_HEADER_NAME = re.compile(r"^[A-Za-z0-9!#$%&'*+.^_`|~-]+$")
_PLATFORM_CONFIGURATION = {
    "contract_version": 1,
    "enabled_attachment_adapter_kinds": [FIXTURE_ADAPTER_KIND],
}

Header: TypeAlias = tuple[str, str]


@dataclass(frozen=True, slots=True)
class Request:
    """One immutable synthetic request presented to the reference edge."""

    method: str
    path: str
    query: str = ""
    headers: tuple[Header, ...] = ()
    body: bytes = b""


@dataclass(frozen=True, slots=True)
class Response:
    """One immutable synthetic response returned by the edge or attachment."""

    status: int
    outcome: str
    headers: tuple[Header, ...] = ()
    body: bytes = b""


Attachment: TypeAlias = Callable[[Request], Response]


@dataclass(frozen=True, slots=True)
class ActivationIssue:
    """One stable reason a proposed generation was not activated."""

    code: str
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class ActivationResult:
    """The complete observable result of one activation attempt."""

    accepted: bool
    generation_digest: str | None
    issues: tuple[ActivationIssue, ...]


class ReferenceEdge:
    """Compile, bind, and serve one deterministic in-memory generation."""

    def __init__(self, attachments: Mapping[str, Attachment]) -> None:
        self._attachments = MappingProxyType(dict(attachments))
        self._current_registration_set: dict[str, Any] | None = None
        self._compiled_configuration: dict[str, Any] | None = None

    def activate(self, proposed_registration_set: dict[str, Any]) -> ActivationResult:
        """Atomically compile and bind a complete proposed generation."""

        compilation = compile_registration_set(
            self._current_registration_set,
            proposed_registration_set,
            _PLATFORM_CONFIGURATION,
        )
        if compilation.violations:
            return ActivationResult(
                accepted=False,
                generation_digest=None,
                issues=tuple(
                    ActivationIssue(item.code, item.path, item.message)
                    for item in compilation.violations
                ),
            )

        binding_issues = self._attachment_binding_issues(proposed_registration_set)
        if binding_issues:
            return ActivationResult(False, None, binding_issues)

        if compilation.compiled_configuration is None:
            raise AssertionError("successful compilation omitted compiled configuration")

        self._current_registration_set = copy.deepcopy(proposed_registration_set)
        self._compiled_configuration = copy.deepcopy(
            compilation.compiled_configuration
        )
        return ActivationResult(True, compilation.generation_digest, ())

    def handle(self, request: Request) -> Response:
        """Return the deterministic result of one bounded synthetic request."""

        invalid = _request_failure(request)
        if invalid is not None:
            return invalid
        if self._compiled_configuration is None:
            return _plain_response(503, "generation_unavailable", "unavailable")
        if request.path == "/":
            return _catalogue_response(self._compiled_configuration["catalogue"])
        if _is_reserved_path(request.path):
            return _plain_response(404, "route_closed", "not found")

        route = _select_route(self._compiled_configuration["routes"], request.path)
        if route is None:
            return _plain_response(404, "route_closed", "not found")

        policy = next(
            item["policy"]
            for item in self._compiled_configuration["admission_policies"]
            if item["application_id"] == route["application_id"]
        )
        if policy["mode"] != "public":
            return _plain_response(401, "authentication_required", "authentication required")

        attachment = _select_attachment(route, request.path)
        if attachment is None:
            return _plain_response(404, "route_closed", "not found")
        target = self._attachments.get(attachment["resource_reference"])
        if target is None:
            return _plain_response(502, "attachment_unavailable", "unavailable")

        forwarded = Request(
            method=request.method,
            path=_forwarded_path(route["route_prefix"], attachment, request.path),
            query=request.query,
            headers=request.headers,
            body=request.body,
        )
        try:
            response = target(forwarded)
        except Exception:
            return _plain_response(502, "attachment_unavailable", "unavailable")
        if not _valid_attachment_response(response):
            return _plain_response(502, "attachment_response_invalid", "unavailable")
        return Response(
            status=response.status,
            outcome="forwarded",
            headers=response.headers,
            body=response.body,
        )

    def _attachment_binding_issues(
        self, registration_set: dict[str, Any]
    ) -> tuple[ActivationIssue, ...]:
        issues: list[ActivationIssue] = []
        for registration_index, registration in enumerate(
            registration_set["registrations"]
        ):
            for attachment_index, attachment in enumerate(
                registration["attachments"]
            ):
                reference = attachment["resource_reference"]
                target = self._attachments.get(reference)
                if target is None or not callable(target):
                    issues.append(
                        ActivationIssue(
                            "FIXTURE_ATTACHMENT_UNAVAILABLE",
                            "/registrations/"
                            f"{registration_index}/attachments/{attachment_index}"
                            "/resource_reference",
                            "fixture attachment is not explicitly supplied",
                        )
                    )
        return tuple(sorted(issues, key=lambda item: (item.path, item.code, item.message)))


def _request_failure(request: Request) -> Response | None:
    if not isinstance(request, Request):
        return _plain_response(400, "request_invalid", "invalid request")
    method_bytes = _utf8_bytes(request.method)
    if (
        method_bytes is None
        or len(method_bytes) > MAX_METHOD_BYTES
        or not request.method.isascii()
    ):
        return _plain_response(400, "request_invalid", "invalid request")

    path_bytes = _utf8_bytes(request.path)
    if (
        path_bytes is None
        or len(path_bytes) > MAX_PATH_BYTES
        or not _canonical_request_path(request.path)
    ):
        return _plain_response(400, "request_invalid", "invalid request")

    query_bytes = _utf8_bytes(request.query)
    if (
        query_bytes is None
        or len(query_bytes) > MAX_QUERY_BYTES
        or _has_control_character(request.query)
    ):
        return _plain_response(400, "request_invalid", "invalid request")

    if not _valid_headers(request.headers, reject_duplicate_identity=True):
        return _plain_response(400, "request_invalid", "invalid request")
    if not isinstance(request.body, bytes) or request.body:
        return _plain_response(400, "request_invalid", "invalid request")
    if request.method != "GET":
        return Response(
            status=405,
            outcome="method_not_allowed",
            headers=(
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Allow", "GET"),
            ),
            body=b"method not allowed\n",
        )
    return None


def _utf8_bytes(value: Any) -> bytes | None:
    if not isinstance(value, str):
        return None
    try:
        return value.encode("utf-8")
    except UnicodeEncodeError:
        return None


def _has_control_character(value: str) -> bool:
    return any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)


def _canonical_request_path(path: str) -> bool:
    if path == "/":
        return True
    if (
        not path.startswith("/")
        or _has_control_character(path)
        or any(character in path for character in ("%", "?", "#", "\\"))
        or any(character.isspace() for character in path)
    ):
        return False
    segments = path[1:].split("/")
    if segments[-1] == "":
        segments.pop()
    return all(segment and segment not in {".", ".."} for segment in segments)


def _valid_headers(
    headers: Any, *, reject_duplicate_identity: bool = False
) -> bool:
    if not isinstance(headers, tuple) or len(headers) > MAX_HEADER_COUNT:
        return False
    aggregate = 0
    identity_count = 0
    for header in headers:
        if not isinstance(header, tuple) or len(header) != 2:
            return False
        name, value = header
        name_bytes = _utf8_bytes(name)
        value_bytes = _utf8_bytes(value)
        if (
            name_bytes is None
            or value_bytes is None
            or not name.isascii()
            or not _HEADER_NAME.fullmatch(name)
            or len(name_bytes) > MAX_HEADER_NAME_BYTES
            or len(value_bytes) > MAX_HEADER_VALUE_BYTES
            or _has_control_character(value)
        ):
            return False
        aggregate += len(name_bytes) + len(value_bytes)
        if name.lower() == VERIFIED_IDENTITY_HEADER:
            identity_count += 1
    if aggregate > MAX_HEADER_BYTES:
        return False
    return not reject_duplicate_identity or identity_count <= 1


def _is_reserved_path(path: str) -> bool:
    return any(
        path == reserved or path.startswith(f"{reserved}/")
        for reserved in ("/.well-known", "/_platform")
    )


def _select_route(routes: list[dict[str, Any]], path: str) -> dict[str, Any] | None:
    for route in routes:
        prefix = route["route_prefix"]
        if path == prefix or path.startswith(f"{prefix}/"):
            return route
    return None


def _select_attachment(
    route: dict[str, Any], path: str
) -> dict[str, Any] | None:
    prefix = route["route_prefix"]
    relative_path = path[len(prefix) :] or "/"
    for attachment in route["attachments"]:
        mount = attachment["mount_path"]
        if (
            mount == "/"
            or relative_path == mount
            or relative_path.startswith(f"{mount}/")
        ):
            return attachment
    return None


def _forwarded_path(
    route_prefix: str, attachment: dict[str, Any], external_path: str
) -> str:
    mode = attachment["forwarding_mode"]
    if mode == "preserve":
        return external_path
    relative_path = external_path[len(route_prefix) :] or "/"
    if mode == "strip_application_prefix":
        return relative_path
    mount = attachment["mount_path"]
    if mount == "/":
        return relative_path
    return relative_path[len(mount) :] or "/"


def _catalogue_response(catalogue: list[dict[str, Any]]) -> Response:
    entries = []
    for item in catalogue:
        route = html.escape(item["route_prefix"], quote=True)
        title = html.escape(item["title"], quote=True)
        summary = html.escape(item["summary"], quote=True)
        admission = html.escape(item["admission_mode"], quote=True)
        entries.append(
            f'<li><a href="{route}">{title}</a><p>{summary}</p>'
            f'<span data-admission="{admission}">{admission}</span></li>'
        )
    document = (
        '<!doctype html><html><head><meta charset="utf-8">'
        "<title>Comfforts Apps</title></head><body><main>"
        f"<h1>Applications</h1><ul>{''.join(entries)}</ul>"
        "</main></body></html>\n"
    ).encode("utf-8")
    if len(document) > MAX_RESPONSE_BODY_BYTES:
        return _plain_response(502, "catalogue_response_invalid", "unavailable")
    return Response(
        status=200,
        outcome="catalogue",
        headers=(("Content-Type", "text/html; charset=utf-8"),),
        body=document,
    )


def _valid_attachment_response(response: Any) -> bool:
    if not isinstance(response, Response):
        return False
    if (
        not isinstance(response.status, int)
        or isinstance(response.status, bool)
        or not 100 <= response.status <= 599
        or not isinstance(response.outcome, str)
        or not response.outcome
        or not _valid_headers(response.headers)
        or not isinstance(response.body, bytes)
        or len(response.body) > MAX_RESPONSE_BODY_BYTES
    ):
        return False
    try:
        response.body.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _plain_response(status: int, outcome: str, message: str) -> Response:
    return Response(
        status=status,
        outcome=outcome,
        headers=(("Content-Type", "text/plain; charset=utf-8"),),
        body=f"{message}\n".encode("utf-8"),
    )
