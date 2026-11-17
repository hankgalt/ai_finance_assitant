"""Catalogue projection and registered routing for one compiled generation."""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any, Protocol

from ._attachments import ResolvedAttachment

MAX_PATH_BYTES = 4_096


@dataclass(frozen=True, slots=True)
class RoutedApplicationRequest:
    """One registered application handoff selected from the bound generation."""

    application_id: str
    attachment_id: str
    attachment_owner_application_id: str
    adapter_kind: str
    resource_reference: str
    path: str
    query_string: bytes
    identity_audience: str | None
    verified_identity_assertion: str | None = None
    resolved_attachment: ResolvedAttachment | None = None


class RouteHandoff(Protocol):
    async def dispatch(self, request: RoutedApplicationRequest) -> None: ...


def _active_application_routes(configuration: dict[str, Any]) -> dict[str, str]:
    routes: dict[str, str] = {}
    duplicates: set[str] = set()
    for item in configuration["application_states"]:
        if item["lifecycle"] != "active":
            continue
        application_id = item["application_id"]
        if application_id in routes:
            duplicates.add(application_id)
        routes[application_id] = item["route_prefix"]
    return {
        application_id: route_prefix
        for application_id, route_prefix in routes.items()
        if application_id not in duplicates
    }


def request_path(scope: dict[str, Any]) -> str | None:
    """Return one canonical request path without normalizing visitor input."""

    raw_path = scope.get("raw_path")
    decoded_path = scope.get("path")
    if (
        not isinstance(raw_path, bytes)
        or not raw_path
        or len(raw_path) > MAX_PATH_BYTES
        or not isinstance(decoded_path, str)
    ):
        return None
    try:
        path = raw_path.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if path != decoded_path or path == "":
        return None
    if path == "/":
        return path
    if (
        not path.startswith("/")
        or any(character in path for character in ("%", "?", "#", "\\"))
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in path)
        or any(character.isspace() for character in path)
    ):
        return None
    segments = path[1:].split("/")
    if segments[-1] == "":
        segments.pop()
    if not segments or any(segment in {"", ".", ".."} for segment in segments):
        return None
    return path


def is_reserved_path(configuration: dict[str, Any], path: str) -> bool:
    """Return whether the canonical path belongs to a platform reservation."""

    return any(
        reserved != "/"
        and (path == reserved or path.startswith(f"{reserved}/"))
        for reserved in configuration["reserved_paths"]
    )


def select_application_route(
    configuration: dict[str, Any],
    path: str,
) -> dict[str, Any] | None:
    """Select the longest active, segment-bounded application route."""

    active_routes = _active_application_routes(configuration)
    candidates = [
        route
        for route in configuration["routes"]
        if active_routes.get(route["application_id"]) == route["route_prefix"]
        and (
            path == route["route_prefix"]
            or path.startswith(f'{route["route_prefix"]}/')
        )
    ]
    if not candidates:
        return None
    longest_prefix = max(len(route["route_prefix"]) for route in candidates)
    selected = [
        route for route in candidates if len(route["route_prefix"]) == longest_prefix
    ]
    return selected[0] if len(selected) == 1 else None


def routed_application_request(
    route: dict[str, Any],
    path: str,
    query_string: bytes,
) -> RoutedApplicationRequest | None:
    """Select the longest mount and apply its declared path rewrite."""

    route_prefix = route["route_prefix"]
    relative_path = path[len(route_prefix) :] or "/"
    candidates = [
        attachment
        for attachment in route["attachments"]
        if attachment["mount_path"] == "/"
        or relative_path == attachment["mount_path"]
        or relative_path.startswith(f'{attachment["mount_path"]}/')
    ]
    if not candidates:
        return None
    longest_mount = max(len(item["mount_path"]) for item in candidates)
    selected = [
        item for item in candidates if len(item["mount_path"]) == longest_mount
    ]
    if len(selected) != 1:
        return None
    attachment = selected[0]
    forwarding_mode = attachment["forwarding_mode"]
    if forwarding_mode == "preserve":
        forwarded_path = path
    elif forwarding_mode == "strip_application_prefix":
        forwarded_path = relative_path
    else:
        mount_path = attachment["mount_path"]
        forwarded_path = (
            relative_path
            if mount_path == "/"
            else relative_path[len(mount_path) :] or "/"
        )
    return RoutedApplicationRequest(
        application_id=route["application_id"],
        attachment_id=attachment["attachment_id"],
        attachment_owner_application_id=attachment["owner_application_id"],
        adapter_kind=attachment["adapter_kind"],
        resource_reference=attachment["resource_reference"],
        path=forwarded_path,
        query_string=query_string,
        identity_audience=attachment["audience"],
    )


def route_admission_mode(
    configuration: dict[str, Any],
    application_id: str,
) -> str | None:
    """Return the compiled admission mode for one routed application."""

    modes = [
        item["policy"]["mode"]
        for item in configuration["admission_policies"]
        if item["application_id"] == application_id
    ]
    return modes[0] if len(modes) == 1 else None


def route_admission_policy(
    configuration: dict[str, Any],
    application_id: str,
) -> dict[str, Any] | None:
    """Return the one compiled admission policy for an application."""

    policies = [
        item["policy"]
        for item in configuration["admission_policies"]
        if item["application_id"] == application_id
    ]
    return policies[0] if len(policies) == 1 else None


def render_catalogue(configuration: dict[str, Any]) -> bytes:
    """Render the active catalogue as bounded, escaped HTML."""

    active_routes = _active_application_routes(configuration)
    entries: list[str] = []
    for item in sorted(
        configuration["catalogue"],
        key=lambda entry: entry["application_id"],
    ):
        if (
            active_routes.get(item["application_id"]) != item["route_prefix"]
            or route_admission_mode(configuration, item["application_id"])
            != item["admission_mode"]
        ):
            continue
        route = html.escape(item["route_prefix"], quote=True)
        title = html.escape(item["title"], quote=True)
        summary = html.escape(item["summary"], quote=True)
        admission = html.escape(item["admission_mode"], quote=True)
        entries.append(
            f'<li><a href="{route}">{title}</a><p>{summary}</p>'
            f'<span data-admission="{admission}">{admission}</span></li>'
        )
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        "<title>Comfforts Apps</title></head><body><main>"
        f"<h1>Applications</h1><ul>{''.join(entries)}</ul>"
        "</main></body></html>\n"
    ).encode("utf-8")
