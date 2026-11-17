"""Strict Cloud Run attachment resolution for the Shared Edge."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import re
from typing import Any, Mapping, Protocol
from urllib.parse import urlsplit


ADAPTER_KIND = "gcp-cloud-run-v1"
APPLICATION_OWNER_LABEL = "application_id"
STATE_OWNER_LABEL = "state_owner"
APPLICATION_AUDIENCE_ANNOTATION = "comfforts.com/identity-audience"
INVOKER_ROLE = "roles/run.invoker"
READY_STATE = 4
MAX_IAM_BINDINGS = 256
MAX_IAM_MEMBERS = 256

_APPLICATION_ID_PATTERN = re.compile(r"[a-z][a-z0-9-]{1,61}[a-z0-9]")
_REGION_PATTERN = re.compile(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?")
_SERVICE_PATTERN = re.compile(r"[a-z](?:[a-z0-9-]{0,47}[a-z0-9])?")
_RESOURCE_PATTERN = re.compile(
    r"urn:comfforts:app-platform:gcp:cloud-run:"
    r"(?P<project_number>[1-9][0-9]{0,18}):"
    r"(?P<region>[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?):"
    r"(?P<service_name>[a-z](?:[a-z0-9-]{0,47}[a-z0-9])?)"
)
_EDGE_CALLER_PATTERN = re.compile(
    r"serviceAccount:[a-z][a-z0-9-]{4,28}[a-z0-9]@"
    r"[a-z][a-z0-9-]{4,28}[a-z0-9]\.iam\.gserviceaccount\.com"
)
_RUN_APP_HOST_PATTERN = re.compile(
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+run\.app"
)


class AttachmentUnavailable(RuntimeError):
    """An attachment could not be resolved without weakening its boundary."""


@dataclass(frozen=True, slots=True)
class CloudRunResource:
    """One exact Cloud Run service coordinate from an inert attachment URN."""

    project_number: str
    region: str
    service_name: str

    def __post_init__(self) -> None:
        if (
            re.fullmatch(r"[1-9][0-9]{0,18}", self.project_number) is None
            or int(self.project_number) > 9_223_372_036_854_775_807
        ):
            raise ValueError("invalid Cloud Run project number")
        if _REGION_PATTERN.fullmatch(self.region) is None:
            raise ValueError("invalid Cloud Run region")
        if _SERVICE_PATTERN.fullmatch(self.service_name) is None:
            raise ValueError("invalid Cloud Run service name")

    @property
    def provider_name(self) -> str:
        return (
            f"projects/{self.project_number}/locations/{self.region}/services/"
            f"{self.service_name}"
        )


def parse_cloud_run_reference(value: str) -> CloudRunResource:
    """Parse the exact Version 1 Cloud Run attachment reference grammar."""

    if not isinstance(value, str):
        raise ValueError("invalid Cloud Run resource reference")
    match = _RESOURCE_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError("invalid Cloud Run resource reference")
    return CloudRunResource(**match.groupdict())


@dataclass(frozen=True, slots=True)
class AttachmentResolutionRequest:
    """Registration-derived facts that provider metadata must corroborate."""

    adapter_kind: str
    resource_reference: str
    owner_application_id: str
    audience: str | None


@dataclass(frozen=True, slots=True)
class CloudRunServiceMetadata:
    """Trusted provider readback projected into the resolver's bounded model."""

    resource: CloudRunResource
    target_uri: str
    ready: bool
    owner_application_id: str | None
    audience: str | None
    invoker_principals: frozenset[str]


@dataclass(frozen=True, slots=True)
class ResolvedAttachment:
    """Provider-derived target facts safe for the later proxy boundary."""

    adapter_kind: str
    resource: CloudRunResource
    target_uri: str
    audience: str | None


class CloudRunMetadataProvider(Protocol):
    async def describe(
        self,
        resource: CloudRunResource,
    ) -> CloudRunServiceMetadata: ...


class AttachmentResolver(Protocol):
    async def resolve(
        self,
        request: AttachmentResolutionRequest,
    ) -> ResolvedAttachment: ...


class InMemoryCloudRunMetadataProvider:
    """Deterministic exact-key provider metadata for local verification."""

    def __init__(
        self,
        services: Mapping[CloudRunResource, CloudRunServiceMetadata],
    ) -> None:
        self._services = dict(services)
        self.requests: list[CloudRunResource] = []
        self.available = True

    async def describe(
        self,
        resource: CloudRunResource,
    ) -> CloudRunServiceMetadata:
        self.requests.append(resource)
        if not self.available or resource not in self._services:
            raise AttachmentUnavailable("Cloud Run metadata unavailable")
        return self._services[resource]


def _mapping(value: Any) -> dict[str, str]:
    try:
        result = dict(value)
    except (TypeError, ValueError) as error:
        raise AttachmentUnavailable("Cloud Run metadata unavailable") from error
    if len(result) > 256 or any(
        not isinstance(key, str)
        or not isinstance(item, str)
        or len(key) > 253
        or len(item) > 512
        for key, item in result.items()
    ):
        raise AttachmentUnavailable("Cloud Run metadata unavailable")
    return result


def _unconditional_invokers(policy: Any) -> frozenset[str]:
    bindings = getattr(policy, "bindings", ())
    if (
        not isinstance(bindings, Sequence)
        or isinstance(bindings, (str, bytes))
        or len(bindings) > MAX_IAM_BINDINGS
    ):
        raise AttachmentUnavailable("Cloud Run IAM metadata unavailable")
    invokers: set[str] = set()
    for binding in bindings:
        if getattr(binding, "role", None) != INVOKER_ROLE:
            continue
        condition = getattr(binding, "condition", None)
        if condition is not None and getattr(condition, "expression", ""):
            continue
        members = getattr(binding, "members", ())
        if (
            not isinstance(members, Sequence)
            or isinstance(members, (str, bytes))
            or len(members) > MAX_IAM_MEMBERS
        ):
            raise AttachmentUnavailable("Cloud Run IAM metadata unavailable")
        if any(not isinstance(member, str) or len(member) > 512 for member in members):
            raise AttachmentUnavailable("Cloud Run IAM metadata unavailable")
        invokers.update(members)
    return frozenset(invokers)


class GoogleCloudRunMetadataProvider:
    """Read one exact Cloud Run service and its IAM policy through an injected client."""

    def __init__(self, services_client: Any) -> None:
        self._services_client = services_client

    async def describe(
        self,
        resource: CloudRunResource,
    ) -> CloudRunServiceMetadata:
        try:
            service = await self._services_client.get_service(
                name=resource.provider_name,
            )
            if getattr(service, "name", None) != resource.provider_name:
                raise AttachmentUnavailable("Cloud Run resource scope mismatch")
            policy = await self._services_client.get_iam_policy(
                request={"resource": resource.provider_name},
            )
            labels = _mapping(getattr(service, "labels", {}))
            annotations = _mapping(getattr(service, "annotations", {}))
            generation = getattr(service, "generation", None)
            observed_generation = getattr(service, "observed_generation", None)
            terminal_condition = getattr(service, "terminal_condition", None)
            latest_ready_revision = getattr(service, "latest_ready_revision", None)
            target_uri = getattr(service, "uri", None)
            ready = (
                getattr(service, "reconciling", None) is False
                and isinstance(generation, int)
                and not isinstance(generation, bool)
                and generation > 0
                and observed_generation == generation
                and getattr(terminal_condition, "type_", None) == "Ready"
                and getattr(terminal_condition, "state", None) == READY_STATE
                and isinstance(latest_ready_revision, str)
                and latest_ready_revision.startswith(
                    f"{resource.provider_name}/revisions/"
                )
                and isinstance(target_uri, str)
                and not getattr(service, "invoker_iam_disabled", True)
            )
            owner = (
                labels.get(APPLICATION_OWNER_LABEL)
                if labels.get(STATE_OWNER_LABEL) == "application"
                else None
            )
            audience = annotations.get(APPLICATION_AUDIENCE_ANNOTATION)
            invokers = _unconditional_invokers(policy)
        except AttachmentUnavailable:
            raise
        except Exception as error:
            raise AttachmentUnavailable("Cloud Run metadata unavailable") from error

        return CloudRunServiceMetadata(
            resource=resource,
            target_uri=target_uri if isinstance(target_uri, str) else "",
            ready=ready,
            owner_application_id=owner,
            audience=audience,
            invoker_principals=invokers,
        )


def _valid_target_uri(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and isinstance(hostname, str)
        and _RUN_APP_HOST_PATTERN.fullmatch(hostname) is not None
        and parsed.username is None
        and parsed.password is None
        and port is None
        and parsed.path == ""
        and not parsed.query
        and not parsed.fragment
    )


class CloudRunAttachmentResolver:
    """Resolve one reviewed Cloud Run URN without discovery or ownership transfer."""

    def __init__(
        self,
        provider: CloudRunMetadataProvider,
        edge_caller_principal: str,
    ) -> None:
        if _EDGE_CALLER_PATTERN.fullmatch(edge_caller_principal) is None:
            raise ValueError("invalid edge caller principal")
        self._provider = provider
        self._edge_caller_principal = edge_caller_principal

    async def resolve(
        self,
        request: AttachmentResolutionRequest,
    ) -> ResolvedAttachment:
        if request.adapter_kind != ADAPTER_KIND:
            raise AttachmentUnavailable("unsupported attachment adapter")
        try:
            resource = parse_cloud_run_reference(request.resource_reference)
        except ValueError as error:
            raise AttachmentUnavailable("invalid Cloud Run resource reference") from error
        if _APPLICATION_ID_PATTERN.fullmatch(request.owner_application_id) is None:
            raise AttachmentUnavailable("invalid application owner")
        expected_audience = (
            None
            if request.audience is None
            else (
                "urn:comfforts:app-platform:audience:"
                f"{request.owner_application_id}"
            )
        )
        if request.audience != expected_audience:
            raise AttachmentUnavailable("invalid application audience")
        try:
            metadata = await self._provider.describe(resource)
        except Exception as error:
            raise AttachmentUnavailable("Cloud Run metadata unavailable") from error
        if (
            not isinstance(metadata, CloudRunServiceMetadata)
            or metadata.resource != resource
            or metadata.ready is not True
            or metadata.owner_application_id != request.owner_application_id
            or metadata.audience != request.audience
            or not isinstance(metadata.invoker_principals, frozenset)
            or self._edge_caller_principal not in metadata.invoker_principals
            or not _valid_target_uri(metadata.target_uri)
        ):
            raise AttachmentUnavailable("Cloud Run attachment unavailable")
        return ResolvedAttachment(
            adapter_kind=ADAPTER_KIND,
            resource=resource,
            target_uri=metadata.target_uri,
            audience=metadata.audience,
        )
