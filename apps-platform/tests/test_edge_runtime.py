from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import json
import unittest
from collections.abc import Awaitable, Callable
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import google_crc32c
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
from joserfc import jwk, jwt
from google.cloud import run_v2
from google.iam.v1 import policy_pb2
from starlette.responses import PlainTextResponse

from edge import (
    ApplicationIdentityVerifier,
    RuntimeAdapters,
    RuntimeConfiguration,
    create_app,
)
from edge._attachments import (
    AttachmentResolutionRequest,
    AttachmentUnavailable,
    CloudRunAttachmentResolver,
    CloudRunResource,
    CloudRunServiceMetadata,
    GoogleCloudRunMetadataProvider,
    InMemoryCloudRunMetadataProvider,
    parse_cloud_run_reference,
)
from edge._assertions import (
    AssertionIssuer,
    CloudKmsAssertionKeys,
    InMemoryAssertionKeys,
    KmsKeyVersion,
    AssertionUnavailable,
)
from edge._generation import GoogleCloudStorageGenerationSource
from edge._identity import (
    AuthlibGoogleOidc,
    FirestoreIdentityStore,
    IdentityUnavailable,
    InMemoryIdentityStore,
    LoginFlow,
    PlatformIdentity,
    PlatformSession,
)
from edge.verification import HttpJwksFetcher, InMemoryJwksFetcher


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AsgiScope = dict[str, Any]
AsgiMessage = dict[str, Any]
AsgiReceive = Callable[[], Awaitable[AsgiMessage]]
AsgiSend = Callable[[AsgiMessage], Awaitable[None]]
AsgiApplication = Callable[[AsgiScope, AsgiReceive, AsgiSend], Awaitable[None]]

GENERATION_BUCKET = "qualification-config"
GENERATION_OBJECT = "compiled/generation-2.json"
GENERATION_OBJECT_GENERATION = 7
GENERATION_CONTENT_DIGEST = (
    "sha256:697e0ef7d5c03490afe2e82f990fa306"
    "ad5a19b37b575de1b70634bc966f930e"
)
GENERATION_DIGEST = (
    "sha256:dbbf3a48ddfa7457bb5260bf4060958f"
    "31c2485317a255d51b7adca86c9f9224"
)


def assertion_test_jwks() -> tuple[dict[str, Any], dict[str, Any]]:
    fixture = json.loads(
        (PROJECT_ROOT / "tests/fixtures/assertion-test-keys.jwk.json").read_text(
            encoding="utf-8"
        )
    )
    private_key = fixture["current"]
    public_keys = []
    for item in fixture.values():
        public_keys.append(
            {
                "alg": "ES256",
                "crv": item["crv"],
                "kid": item["kid"],
                "kty": item["kty"],
                "use": "sig",
                "x": item["x"],
                "y": item["y"],
            }
        )
    return private_key, {"keys": public_keys}


def assertion_components(
    clock: FixedClock,
    correlation_ids: list[str] | None = None,
) -> tuple[AssertionIssuer, InMemoryAssertionKeys]:
    private_key, jwks = assertion_test_jwks()
    keys = InMemoryAssertionKeys(private_key, jwks["keys"])
    issuer = AssertionIssuer(
        keys,
        clock,
        FixedTokenSource(
            correlation_ids or ["correlation-012345678901234"]
        ),
    )
    return issuer, keys


def signed_test_assertion(
    keys: InMemoryAssertionKeys,
    payload: dict[str, Any],
    *,
    key_id: str | None = None,
) -> str:
    def encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    header = {
        "alg": "ES256",
        "kid": key_id or keys.active_key_id,
        "typ": "JWT",
    }
    header_segment = encode(
        json.dumps(
            header,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    payload_segment = encode(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    signing_input = f"{header_segment}.{payload_segment}"
    signature = asyncio.run(
        keys.sign_digest(hashlib.sha256(signing_input.encode("ascii")).digest())
    )
    return f"{signing_input}.{encode(signature)}"


class ResponseHeaders(dict[bytes, bytes]):
    def __init__(self, pairs: list[tuple[bytes, bytes]]) -> None:
        super().__init__(pairs)
        self._pairs = pairs

    def get_all(self, name: bytes) -> list[bytes]:
        expected = name.lower()
        return [value for key, value in self._pairs if key.lower() == expected]


def valid_generation_payload() -> bytes:
    return (
        PROJECT_ROOT / "contracts/test-vectors/valid/compiled-active.v1.json"
    ).read_bytes()


def generation_configuration(
    *,
    content_digest: str = GENERATION_CONTENT_DIGEST,
    generation_digest: str = GENERATION_DIGEST,
    external_origin: str | None = None,
) -> RuntimeConfiguration:
    return RuntimeConfiguration(
        profile="qualification-v1",
        generation_bucket=GENERATION_BUCKET,
        generation_object=GENERATION_OBJECT,
        generation_object_generation=GENERATION_OBJECT_GENERATION,
        generation_content_digest=content_digest,
        generation_digest=generation_digest,
        external_origin=external_origin,
    )


def compiled_generation() -> dict[str, Any]:
    return json.loads(valid_generation_payload())


def configured_generation(
    document: dict[str, Any],
    *,
    external_origin: str | None = None,
) -> tuple[RuntimeConfiguration, StaticGenerationSource]:
    payload = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    configuration = generation_configuration(
        content_digest="sha256:" + hashlib.sha256(payload).hexdigest(),
        generation_digest=document["generation_digest"],
        external_origin=external_origin,
    )
    return configuration, StaticGenerationSource(
        bucket=GENERATION_BUCKET,
        object_name=GENERATION_OBJECT,
        object_generation=GENERATION_OBJECT_GENERATION,
        payload=payload,
    )


def compiled_attachment(
    attachment_id: str,
    mount_path: str,
    forwarding_mode: str,
) -> dict[str, Any]:
    return {
        "contract_version": 1,
        "owner_application_id": "alpha-app",
        "attachment_id": attachment_id,
        "adapter_kind": "contract-test-v1",
        "resource_reference": (
            "urn:comfforts:app-platform:contract-test:alpha-app:"
            f"{attachment_id}"
        ),
        "mount_path": mount_path,
        "forwarding_mode": forwarding_mode,
        "identity_requirement": "none",
        "audience": None,
        "ingress_mode": "shared_edge_only",
    }


def protected_generation(
    mode: str,
    *,
    members: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    document = compiled_generation()
    document["catalogue"][0]["admission_mode"] = mode
    policy: dict[str, Any] = {"mode": mode}
    if members is not None:
        policy["members"] = members
    document["admission_policies"][0]["policy"] = policy
    attachment = document["routes"][0]["attachments"][0]
    attachment["identity_requirement"] = "verified"
    attachment["audience"] = (
        "urn:comfforts:app-platform:audience:alpha-app"
    )
    return document


def cloud_run_generation(
    *,
    adapter_kind: str = "gcp-cloud-run-v1",
    resource_reference: str = (
        "urn:comfforts:app-platform:gcp:cloud-run:455651441682:"
        "us-west1:alpha-app"
    ),
    audience: str | None = None,
) -> dict[str, Any]:
    document = compiled_generation()
    attachment = document["routes"][0]["attachments"][0]
    attachment.update(
        adapter_kind=adapter_kind,
        resource_reference=resource_reference,
        identity_requirement="verified" if audience is not None else "none",
        audience=audience,
    )
    return document


def cookie_value(headers: ResponseHeaders, name: str) -> str:
    prefix = f"{name}=".encode("ascii")
    matches = [
        value[len(prefix) :].split(b";", 1)[0].decode("ascii")
        for value in headers.get_all(b"set-cookie")
        if value.startswith(prefix)
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected one {name} cookie, got {len(matches)}")
    return matches[0]


async def request(
    app: AsgiApplication,
    path: str = "/",
    *,
    method: str = "GET",
    raw_path: bytes | None = None,
    query_string: bytes = b"",
    headers: tuple[tuple[bytes, bytes], ...] = (),
) -> tuple[int, dict[bytes, bytes], bytes]:
    incoming = [{"type": "http.request", "body": b"", "more_body": False}]
    outgoing: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return incoming.pop(0)

    async def send(message: dict[str, Any]) -> None:
        outgoing.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "scheme": "https",
            "method": method,
            "path": path,
            "raw_path": raw_path if raw_path is not None else path.encode("utf-8"),
            "query_string": query_string,
            "root_path": "",
            "headers": list(headers),
            "client": ("127.0.0.1", 43210),
            "server": ("testserver", 443),
        },
        receive,
        send,
    )

    start = next(
        message for message in outgoing if message["type"] == "http.response.start"
    )
    body = b"".join(
        message.get("body", b"")
        for message in outgoing
        if message["type"] == "http.response.body"
    )
    return start["status"], ResponseHeaders(start["headers"]), body


async def request_during_lifespan(
    app: AsgiApplication,
    path: str,
    *,
    method: str = "GET",
    raw_path: bytes | None = None,
    query_string: bytes = b"",
    headers: tuple[tuple[bytes, bytes], ...] = (),
) -> tuple[dict[str, Any], tuple[int, dict[bytes, bytes], bytes]]:
    incoming: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    outgoing: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def receive() -> dict[str, Any]:
        return await incoming.get()

    async def send(message: dict[str, Any]) -> None:
        await outgoing.put(message)

    lifespan_task = asyncio.create_task(
        app(
            {
                "type": "lifespan",
                "asgi": {"version": "3.0", "spec_version": "2.0"},
                "state": {},
            },
            receive,
            send,
        )
    )
    await incoming.put({"type": "lifespan.startup"})
    startup = await outgoing.get()
    if startup["type"] != "lifespan.startup.complete":
        try:
            await lifespan_task
        except Exception as error:
            raise AssertionError(f"startup failed: {startup}") from error
        raise AssertionError(f"unexpected startup result: {startup}")
    response = await request(
        app,
        path,
        method=method,
        raw_path=raw_path,
        query_string=query_string,
        headers=headers,
    )
    await incoming.put({"type": "lifespan.shutdown"})
    shutdown = await outgoing.get()
    await lifespan_task
    if shutdown["type"] != "lifespan.shutdown.complete":
        raise AssertionError(f"unexpected shutdown result: {shutdown['type']}")
    return startup, response


async def websocket_during_lifespan(
    app: AsgiApplication,
    path: str,
    *,
    query_string: bytes = b"",
    headers: tuple[tuple[bytes, bytes], ...] = (),
    subprotocols: tuple[str, ...] = ("chat",),
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    lifespan_incoming: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    lifespan_outgoing: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def lifespan_receive() -> dict[str, Any]:
        return await lifespan_incoming.get()

    async def lifespan_send(message: dict[str, Any]) -> None:
        await lifespan_outgoing.put(message)

    lifespan_task = asyncio.create_task(
        app(
            {
                "type": "lifespan",
                "asgi": {"version": "3.0", "spec_version": "2.0"},
                "state": {},
            },
            lifespan_receive,
            lifespan_send,
        )
    )
    await lifespan_incoming.put({"type": "lifespan.startup"})
    startup = await lifespan_outgoing.get()
    incoming: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    outgoing: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return await incoming.get()

    async def send(message: dict[str, Any]) -> None:
        outgoing.append(message)

    await incoming.put({"type": "websocket.connect"})
    await app(
        {
            "type": "websocket",
            "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1",
            "scheme": "wss",
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": query_string,
            "headers": list(headers),
            "state": {},
            "client": ("127.0.0.1", 43210),
            "server": ("testserver", 443),
            "subprotocols": list(subprotocols),
        },
        receive,
        send,
    )
    await lifespan_incoming.put({"type": "lifespan.shutdown"})
    await lifespan_outgoing.get()
    await lifespan_task
    return startup, outgoing


async def failed_startup(
    app: AsgiApplication,
) -> tuple[dict[str, Any], str]:
    incoming: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    outgoing: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def receive() -> dict[str, Any]:
        return await incoming.get()

    async def send(message: dict[str, Any]) -> None:
        await outgoing.put(message)

    lifespan_task = asyncio.create_task(
        app(
            {
                "type": "lifespan",
                "asgi": {"version": "3.0", "spec_version": "2.0"},
                "state": {},
            },
            receive,
            send,
        )
    )
    await incoming.put({"type": "lifespan.startup"})
    startup = await outgoing.get()
    try:
        await lifespan_task
    except RuntimeError as error:
        return startup, str(error)
    raise AssertionError("startup failure did not raise RuntimeError")


class StaticGenerationSource:
    def __init__(
        self,
        *,
        bucket: str,
        object_name: str,
        object_generation: int,
        payload: bytes,
    ) -> None:
        self._binding = (bucket, object_name, object_generation)
        self._payload = payload
        self.load_count = 0

    async def load(
        self,
        *,
        bucket: str,
        object_name: str,
        object_generation: int,
    ) -> bytes:
        self.load_count += 1
        if (bucket, object_name, object_generation) != self._binding:
            raise LookupError("generation binding is unavailable")
        return self._payload


class FailingGenerationSource:
    async def load(
        self,
        *,
        bucket: str,
        object_name: str,
        object_generation: int,
    ) -> bytes:
        del bucket, object_name, object_generation
        raise PermissionError("provider-secret-marker")


class RecordingRouteHandoff:
    def __init__(self) -> None:
        self.requests: list[Any] = []

    async def dispatch(self, request: Any) -> None:
        self.requests.append(request)


class RecordingApplicationProxy:
    def __init__(self) -> None:
        self.http_requests: list[Any] = []
        self.websocket_requests: list[Any] = []

    async def forward_http(self, request: Any, routed: Any) -> Any:
        self.http_requests.append((request, routed))
        return PlainTextResponse(
            "proxied\n",
            status_code=202,
            headers={"X-Application-Proxy": "bounded"},
        )

    async def forward_websocket(self, websocket: Any, routed: Any) -> None:
        self.websocket_requests.append(routed)
        await websocket.accept(subprotocol="chat")
        await websocket.send_text("proxied")
        await websocket.close(code=1000)


class FixedClock:
    def __init__(self, value: int) -> None:
        self.value = value

    def now(self) -> int:
        return self.value


class FixedTokenSource:
    def __init__(self, values: list[str]) -> None:
        self._values = values

    def token(self, entropy_bytes: int) -> str:
        del entropy_bytes
        return self._values.pop(0)


class FakeGoogleOidc:
    def __init__(self, identity: PlatformIdentity) -> None:
        self.identity = identity
        self.authorization_requests: list[dict[str, str]] = []
        self.authentication_requests: list[dict[str, str]] = []
        self.failure: Exception | None = None

    async def authorization_url(
        self,
        *,
        redirect_uri: str,
        state: str,
        nonce: str,
        code_verifier: str,
    ) -> str:
        self.authorization_requests.append(
            {
                "redirect_uri": redirect_uri,
                "state": state,
                "nonce": nonce,
                "code_verifier": code_verifier,
            }
        )
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
            {
                "state": state,
                "nonce": nonce,
                "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
                "code_challenge_method": "S256",
            }
        )

    async def authenticate(
        self,
        *,
        code: str,
        redirect_uri: str,
        nonce: str,
        code_verifier: str,
    ) -> PlatformIdentity:
        self.authentication_requests.append(
            {
                "code": code,
                "redirect_uri": redirect_uri,
                "nonce": nonce,
                "code_verifier": code_verifier,
            }
        )
        if self.failure is not None:
            raise self.failure
        return self.identity


class FakeCloudKmsClient:
    def __init__(self, keys: dict[str, ec.EllipticCurvePrivateKey]) -> None:
        self.keys = keys
        self.sign_requests: list[dict[str, Any]] = []
        self.public_key_requests: list[dict[str, Any]] = []
        self.corrupt_signature_checksum = False

    async def asymmetric_sign(self, *, request: dict[str, Any]) -> Any:
        self.sign_requests.append(request)
        digest = request["digest"]["sha256"]
        if request["digest_crc32c"] != google_crc32c.value(digest):
            raise RuntimeError("request checksum mismatch")
        signature = self.keys[request["name"]].sign(
            digest,
            ec.ECDSA(Prehashed(hashes.SHA256())),
        )
        checksum = google_crc32c.value(signature)
        if self.corrupt_signature_checksum:
            checksum += 1
        return SimpleNamespace(
            name=request["name"],
            signature=signature,
            signature_crc32c=checksum,
            verified_digest_crc32c=True,
            protection_level=SimpleNamespace(name="SOFTWARE"),
        )

    async def get_public_key(self, *, request: dict[str, Any]) -> Any:
        self.public_key_requests.append(request)
        pem = self.keys[request["name"]].public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return SimpleNamespace(
            name=request["name"],
            pem=pem.decode("ascii"),
            pem_crc32c=google_crc32c.value(pem),
            algorithm=SimpleNamespace(name="EC_SIGN_P256_SHA256"),
            protection_level=SimpleNamespace(name="SOFTWARE"),
        )


class FakeFirestoreSnapshot:
    def __init__(self, value: dict[str, Any] | None) -> None:
        self.exists = value is not None
        self._value = value

    def to_dict(self) -> dict[str, Any] | None:
        return copy.deepcopy(self._value)


class FakeFirestoreDocument:
    def __init__(self, documents: dict[str, dict[str, Any]], key: str) -> None:
        self._documents = documents
        self._key = key

    async def create(self, value: dict[str, Any]) -> None:
        if self._key in self._documents:
            raise RuntimeError("already exists")
        self._documents[self._key] = copy.deepcopy(value)

    async def get(self, *, transaction: Any = None) -> FakeFirestoreSnapshot:
        del transaction
        return FakeFirestoreSnapshot(self._documents.get(self._key))

    async def delete(self) -> None:
        self._documents.pop(self._key, None)

    def delete_now(self) -> None:
        self._documents.pop(self._key, None)


class FakeFirestoreCollection:
    def __init__(self, documents: dict[str, dict[str, Any]]) -> None:
        self._documents = documents

    def document(self, key: str) -> FakeFirestoreDocument:
        return FakeFirestoreDocument(self._documents, key)


class FakeFirestoreTransaction:
    def __init__(self) -> None:
        self._deletes: list[FakeFirestoreDocument] = []

    def delete(self, document: FakeFirestoreDocument) -> None:
        self._deletes.append(document)

    async def commit(self) -> None:
        for document in self._deletes:
            document.delete_now()

    async def rollback(self) -> None:
        self._deletes.clear()


class FakeFirestoreClient:
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, dict[str, Any]]] = {}

    def collection(self, name: str) -> FakeFirestoreCollection:
        return FakeFirestoreCollection(self.collections.setdefault(name, {}))

    def transaction(self) -> FakeFirestoreTransaction:
        return FakeFirestoreTransaction()


class StaticStorageBlob:
    def __init__(self, *, generation: int, payload: bytes) -> None:
        self._generation = generation
        self._payload = payload

    def download_as_bytes(
        self,
        *,
        start: int,
        end: int,
        raw_download: bool,
        if_generation_match: int,
        checksum: str,
    ) -> bytes:
        if start != 0 or end != 1_048_576:
            raise ValueError("download range is not bounded")
        if not raw_download:
            raise ValueError("download must preserve stored bytes")
        if if_generation_match != self._generation:
            raise LookupError("object generation is unavailable")
        if checksum != "auto":
            raise ValueError("checksum mode is unsupported")
        return self._payload


class StaticStorageBucket:
    def __init__(
        self,
        *,
        object_name: str,
        object_generation: int,
        payload: bytes,
    ) -> None:
        self._object_name = object_name
        self._object_generation = object_generation
        self._payload = payload

    def blob(self, object_name: str, *, generation: int) -> StaticStorageBlob:
        if object_name != self._object_name or generation != self._object_generation:
            raise LookupError("object binding is unavailable")
        return StaticStorageBlob(generation=generation, payload=self._payload)


class StaticStorageClient:
    def __init__(
        self,
        *,
        bucket: str,
        object_name: str,
        object_generation: int,
        payload: bytes,
    ) -> None:
        self._bucket = bucket
        self._stored_bucket = StaticStorageBucket(
            object_name=object_name,
            object_generation=object_generation,
            payload=payload,
        )

    def bucket(self, bucket: str) -> StaticStorageBucket:
        if bucket != self._bucket:
            raise LookupError("bucket is unavailable")
        return self._stored_bucket


class IdentityAdapterTest(unittest.TestCase):
    def test_google_oidc_adapter_verifies_signed_identity_and_discards_tokens(
        self,
    ) -> None:
        signing_key = jwk.RSAKey.import_key(
            json.loads(
                (
                    PROJECT_ROOT
                    / "tests/fixtures/oidc-test-private.jwk.json"
                ).read_text(encoding="utf-8")
            )
        )
        id_token = jwt.encode(
            {"alg": "RS256", "kid": "ap-m6-w5-test-only"},
            {
                "iss": "accounts.google.com",
                "sub": "google-subject-1",
                "aud": "test-client",
                "iat": 1_700_000_000,
                "exp": 4_102_444_800,
                "nonce": "expected-nonce",
                "email": "display@example.com",
            },
            signing_key,
            algorithms=["RS256"],
        )
        requests: list[httpx.Request] = []

        def provider(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.path == "/.well-known/openid-configuration":
                return httpx.Response(
                    200,
                    json={
                        "issuer": "https://accounts.google.com",
                        "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
                        "token_endpoint": "https://oauth2.googleapis.com/token",
                        "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
                    },
                )
            if request.url == "https://oauth2.googleapis.com/token":
                return httpx.Response(
                    200,
                    json={
                        "access_token": "must-be-discarded",
                        "refresh_token": "must-also-be-discarded",
                        "token_type": "Bearer",
                        "id_token": id_token,
                    },
                )
            if request.url == "https://www.googleapis.com/oauth2/v3/certs":
                return httpx.Response(
                    200,
                    json={"keys": [signing_key.as_dict(private=False)]},
                )
            return httpx.Response(404)

        adapter = AuthlibGoogleOidc(
            client_id="test-client",
            client_secret="test-secret",
            transport=httpx.MockTransport(provider),
        )

        authorization_url = asyncio.run(
            adapter.authorization_url(
                redirect_uri="https://apps-staging.comfforts.com/_platform/auth/callback",
                state="expected-state",
                nonce="expected-nonce",
                code_verifier="v" * 43,
            )
        )
        identity = asyncio.run(
            adapter.authenticate(
                code="provider-code",
                redirect_uri="https://apps-staging.comfforts.com/_platform/auth/callback",
                nonce="expected-nonce",
                code_verifier="v" * 43,
            )
        )

        authorization_query = parse_qs(urlsplit(authorization_url).query)
        self.assertEqual(authorization_query["code_challenge_method"], ["S256"])
        self.assertEqual(
            identity,
            PlatformIdentity(
                "https://accounts.google.com",
                "google-subject-1",
                "display@example.com",
            ),
        )
        self.assertEqual([request.method for request in requests], ["GET", "GET", "POST", "GET"])
        self.assertNotIn("must-be-discarded", repr(identity))

        with self.assertRaises(IdentityUnavailable):
            asyncio.run(
                adapter.authenticate(
                    code="provider-code",
                    redirect_uri="https://apps-staging.comfforts.com/_platform/auth/callback",
                    nonce="wrong-nonce",
                    code_verifier="v" * 43,
                )
            )

    def test_firestore_adapter_hashes_opaque_ids_and_consumes_flows_once(self) -> None:
        client = FakeFirestoreClient()
        store = FirestoreIdentityStore(client, collection_prefix="qualification")
        flow = LoginFlow(
            state="state",
            nonce="nonce",
            code_verifier="verifier",
            return_to="/alpha",
            expires_at=2_000,
        )
        session = PlatformSession(
            PlatformIdentity(
                "https://accounts.google.com",
                "subject",
                "display@example.com",
            ),
            expires_at=29_800,
        )

        asyncio.run(store.put_flow("opaque-flow-id", flow))
        first_flow = asyncio.run(store.consume_flow("opaque-flow-id"))
        second_flow = asyncio.run(store.consume_flow("opaque-flow-id"))
        asyncio.run(store.put_session("opaque-session-id", session))
        loaded_session = asyncio.run(store.get_session("opaque-session-id"))
        asyncio.run(store.delete_session("opaque-session-id"))

        self.assertEqual(first_flow, flow)
        self.assertIsNone(second_flow)
        self.assertEqual(loaded_session, session)
        self.assertIsNone(asyncio.run(store.get_session("opaque-session-id")))
        stored_keys = {
            key
            for collection in client.collections.values()
            for key in collection
        }
        self.assertNotIn("opaque-flow-id", stored_keys)
        self.assertNotIn("opaque-session-id", stored_keys)

    def test_cloud_kms_adapter_binds_versions_and_validates_integrity(self) -> None:
        raw_keys = json.loads(
            (PROJECT_ROOT / "tests/fixtures/assertion-test-keys.jwk.json").read_text(
                encoding="utf-8"
            )
        )
        current_resource = (
            "projects/comfforts-platform-non-prod/locations/us-west1/"
            "keyRings/platform/cryptoKeys/identity/cryptoKeyVersions/2"
        )
        previous_resource = (
            "projects/comfforts-platform-non-prod/locations/us-west1/"
            "keyRings/platform/cryptoKeys/identity/cryptoKeyVersions/1"
        )
        client = FakeCloudKmsClient(
            {
                current_resource: jwk.ECKey.import_key(
                    raw_keys["current"]
                ).raw_value,
                previous_resource: jwk.ECKey.import_key(
                    raw_keys["previous"]
                ).raw_value,
            }
        )
        current = KmsKeyVersion("kms-version-2", current_resource)
        previous = KmsKeyVersion("kms-version-1", previous_resource)
        adapter = CloudKmsAssertionKeys(
            client,
            active_key=current,
            published_keys=(previous, current),
        )

        signature = asyncio.run(adapter.sign_digest(b"d" * 32))
        public_keys = asyncio.run(adapter.verification_keys())

        self.assertEqual(len(signature), 64)
        self.assertEqual(
            {item["kid"] for item in public_keys},
            {"kms-version-1", "kms-version-2"},
        )
        self.assertTrue(all("d" not in item for item in public_keys))
        self.assertEqual(client.sign_requests[0]["name"], current_resource)
        self.assertEqual(len(client.public_key_requests), 2)

        client.corrupt_signature_checksum = True
        with self.assertRaises(AssertionUnavailable):
            asyncio.run(adapter.sign_digest(b"e" * 32))


class ApplicationVerificationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FixedClock(10_000)
        _, self.keys = assertion_components(self.clock)
        self.jwks = {"keys": list(asyncio.run(self.keys.verification_keys()))}
        self.payload = {
            "contract_version": 1,
            "issuer": "https://accounts.google.com",
            "subject": "verified-subject",
            "audience": "urn:comfforts:app-platform:audience:alpha-app",
            "issued_at": 10_000,
            "expires_at": 10_060,
            "correlation_id": "correlation-0001",
        }

    def verifier(
        self,
        *,
        clock: FixedClock | None = None,
        expected_issuer: str = "https://accounts.google.com",
        expected_audience: str = (
            "urn:comfforts:app-platform:audience:alpha-app"
        ),
        fetcher: InMemoryJwksFetcher | None = None,
    ) -> ApplicationIdentityVerifier:
        return ApplicationIdentityVerifier(
            expected_issuer=expected_issuer,
            expected_audience=expected_audience,
            key_fetcher=fetcher or InMemoryJwksFetcher([self.jwks]),
            clock=clock or self.clock,
        )

    def test_application_verifier_rejects_invalid_assertions_with_stable_codes(
        self,
    ) -> None:
        valid = signed_test_assertion(self.keys, self.payload)
        signature_parts = valid.split(".")
        signature = signature_parts[2]
        forged = ".".join(
            (
                signature_parts[0],
                signature_parts[1],
                ("A" if signature[0] != "A" else "B") + signature[1:],
            )
        )
        wrong_version = dict(self.payload, contract_version=2)
        wrong_issuer = dict(self.payload, issuer="https://issuer.example")
        wrong_audience = dict(
            self.payload,
            audience="urn:comfforts:app-platform:audience:other-app",
        )
        overlong = dict(self.payload, expires_at=10_061)
        cases = (
            ("missing", None, self.clock, "assertion_missing"),
            ("malformed", "not-an-assertion", self.clock, "assertion_malformed"),
            ("forged", forged, self.clock, "assertion_signature_invalid"),
            (
                "wrong version",
                signed_test_assertion(self.keys, wrong_version),
                self.clock,
                "identity_contract_invalid",
            ),
            (
                "wrong issuer",
                signed_test_assertion(self.keys, wrong_issuer),
                self.clock,
                "identity_issuer_invalid",
            ),
            (
                "wrong audience",
                signed_test_assertion(self.keys, wrong_audience),
                self.clock,
                "identity_audience_invalid",
            ),
            (
                "expired after skew",
                valid,
                FixedClock(10_091),
                "identity_expired",
            ),
            (
                "premature beyond skew",
                signed_test_assertion(
                    self.keys,
                    dict(self.payload, issued_at=10_031, expires_at=10_091),
                ),
                self.clock,
                "identity_not_yet_valid",
            ),
            (
                "lifetime too long",
                signed_test_assertion(self.keys, overlong),
                self.clock,
                "identity_lifetime_invalid",
            ),
        )

        for label, assertion, clock, code in cases:
            with self.subTest(label=label):
                result = asyncio.run(
                    self.verifier(clock=clock).verify(assertion)
                )
                self.assertFalse(result.accepted)
                self.assertEqual(result.code, code)
                self.assertIsNone(result.identity)

    def test_unknown_key_refreshes_once_and_rotation_overlap_verifies(self) -> None:
        valid = signed_test_assertion(self.keys, self.payload)
        current = next(
            item
            for item in self.jwks["keys"]
            if item["kid"] == "ap-m6-w6-current-test-only"
        )
        previous = next(
            item
            for item in self.jwks["keys"]
            if item["kid"] == "ap-m6-w6-previous-test-only"
        )
        fetcher = InMemoryJwksFetcher(
            [
                {"keys": [previous]},
                {"keys": [current, previous]},
            ]
        )
        verifier = self.verifier(fetcher=fetcher)

        result = asyncio.run(verifier.verify(valid))

        self.assertTrue(result.accepted)
        self.assertEqual(fetcher.fetch_count, 2)

        raw_keys = json.loads(
            (PROJECT_ROOT / "tests/fixtures/assertion-test-keys.jwk.json").read_text(
                encoding="utf-8"
            )
        )
        previous_keys = InMemoryAssertionKeys(
            raw_keys["previous"],
            self.jwks["keys"],
        )
        previous_assertion = signed_test_assertion(previous_keys, self.payload)
        overlap_result = asyncio.run(verifier.verify(previous_assertion))
        self.assertTrue(overlap_result.accepted)
        self.assertEqual(fetcher.fetch_count, 2)

    def test_clock_skew_boundary_is_inclusive_without_a_replay_claim(self) -> None:
        expiry_boundary = signed_test_assertion(self.keys, self.payload)
        future_boundary = signed_test_assertion(
            self.keys,
            dict(self.payload, issued_at=10_030, expires_at=10_090),
        )
        expiry_verifier = self.verifier(clock=FixedClock(10_090))
        future_verifier = self.verifier(clock=FixedClock(10_000))

        first = asyncio.run(expiry_verifier.verify(expiry_boundary))
        repeated = asyncio.run(expiry_verifier.verify(expiry_boundary))
        future = asyncio.run(future_verifier.verify(future_boundary))

        self.assertTrue(first.accepted)
        self.assertTrue(repeated.accepted)
        self.assertTrue(future.accepted)

    def test_unknown_and_stale_verification_keys_fail_closed(self) -> None:
        valid = signed_test_assertion(self.keys, self.payload)
        unknown = signed_test_assertion(
            self.keys,
            self.payload,
            key_id="unknown-key-version",
        )
        unknown_fetcher = InMemoryJwksFetcher([self.jwks])
        unknown_result = asyncio.run(
            self.verifier(fetcher=unknown_fetcher).verify(unknown)
        )
        stale_fetcher = InMemoryJwksFetcher([self.jwks])
        stale_clock = FixedClock(10_000)
        stale_verifier = self.verifier(
            clock=stale_clock,
            fetcher=stale_fetcher,
        )
        self.assertTrue(asyncio.run(stale_verifier.verify(valid)).accepted)
        stale_clock.value = 10_900
        stale_fetcher.available = False
        stale_result = asyncio.run(stale_verifier.verify(valid))

        self.assertEqual(unknown_result.code, "assertion_key_unknown")
        self.assertEqual(unknown_fetcher.fetch_count, 2)
        self.assertFalse(stale_result.accepted)
        self.assertEqual(stale_result.code, "verification_keys_unavailable")

    def test_http_jwks_fetcher_verifies_without_external_network(self) -> None:
        valid = signed_test_assertion(self.keys, self.payload)
        observed: list[httpx.Request] = []

        def platform(request: httpx.Request) -> httpx.Response:
            observed.append(request)
            return httpx.Response(200, json=self.jwks)

        async def verify() -> Any:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(platform)
            ) as client:
                fetcher = HttpJwksFetcher(
                    client,
                    "https://apps-staging.comfforts.com/.well-known/jwks.json",
                )
                return await self.verifier(fetcher=fetcher).verify(valid)

        result = asyncio.run(verify())

        self.assertTrue(result.accepted)
        self.assertEqual(len(observed), 1)
        self.assertEqual(
            str(observed[0].url),
            "https://apps-staging.comfforts.com/.well-known/jwks.json",
        )


class StaticCloudRunServicesClient:
    def __init__(self, service: Any, policy: Any) -> None:
        self.service = service
        self.policy = policy
        self.service_requests: list[str] = []
        self.policy_requests: list[dict[str, str]] = []

    async def get_service(self, *, name: str) -> Any:
        self.service_requests.append(name)
        return self.service

    async def get_iam_policy(self, *, request: dict[str, str]) -> Any:
        self.policy_requests.append(request)
        return self.policy


class CloudRunAttachmentTest(unittest.TestCase):
    resource_reference = (
        "urn:comfforts:app-platform:gcp:cloud-run:455651441682:"
        "us-west1:alpha-app"
    )
    edge_caller = (
        "serviceAccount:apps-platform-edge@comfforts-platform-non-prod."
        "iam.gserviceaccount.com"
    )
    audience = "urn:comfforts:app-platform:audience:alpha-app"
    target_uri = "https://alpha-app-455651441682.us-west1.run.app"

    def resource(self) -> CloudRunResource:
        return CloudRunResource(
            project_number="455651441682",
            region="us-west1",
            service_name="alpha-app",
        )

    def metadata(self) -> CloudRunServiceMetadata:
        return CloudRunServiceMetadata(
            resource=self.resource(),
            target_uri=self.target_uri,
            ready=True,
            owner_application_id="alpha-app",
            audience=self.audience,
            invoker_principals=frozenset({self.edge_caller}),
        )

    def request(self) -> AttachmentResolutionRequest:
        return AttachmentResolutionRequest(
            adapter_kind="gcp-cloud-run-v1",
            resource_reference=self.resource_reference,
            owner_application_id="alpha-app",
            audience=self.audience,
        )

    def test_reference_parser_accepts_only_the_exact_cloud_run_urn(self) -> None:
        resource = parse_cloud_run_reference(self.resource_reference)

        self.assertEqual(resource, self.resource())
        self.assertEqual(
            resource.provider_name,
            "projects/455651441682/locations/us-west1/services/alpha-app",
        )

        rejected = (
            "https://alpha-app.example.test",
            "google_cloud_run_v2_service.alpha-app",
            "urn:comfforts:app-platform:gcp:cloud-run:user@example.com:us-west1:app",
            "urn:comfforts:app-platform:gcp:cloud-run:0455651441682:us-west1:app",
            "urn:comfforts:app-platform:gcp:cloud-run:9223372036854775808:us-west1:app",
            "urn:comfforts:app-platform:gcp:cloud-run:455651441682:US-west1:app",
            "urn:comfforts:app-platform:gcp:cloud-run:455651441682:us-west1:app-",
            "urn:comfforts:app-platform:gcp:cloud-run:455651441682:us-west1:"
            + "a" * 50,
            "urn:comfforts:app-platform:gcp:cloud-run:455651441682:us-west1:app?x=1",
            "urn:comfforts:app-platform:gcp:cloud-run:455651441682:us-west1:app:extra",
        )
        for value in rejected:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_cloud_run_reference(value)

    def test_resolver_binds_exact_metadata_owner_caller_and_audience(self) -> None:
        provider = InMemoryCloudRunMetadataProvider(
            {self.resource(): self.metadata()}
        )
        resolver = CloudRunAttachmentResolver(provider, self.edge_caller)

        resolved = asyncio.run(resolver.resolve(self.request()))

        self.assertEqual(provider.requests, [self.resource()])
        self.assertEqual(resolved.resource, self.resource())
        self.assertEqual(resolved.target_uri, self.target_uri)
        self.assertEqual(resolved.audience, self.audience)

    def test_resolver_rejects_every_mismatched_or_unavailable_fact(self) -> None:
        other_resource = CloudRunResource(
            project_number="455651441683",
            region="us-west1",
            service_name="alpha-app",
        )
        cases = (
            ("project", replace(self.metadata(), resource=other_resource)),
            (
                "region",
                replace(
                    self.metadata(),
                    resource=replace(self.resource(), region="us-central1"),
                ),
            ),
            (
                "service",
                replace(
                    self.metadata(),
                    resource=replace(self.resource(), service_name="other-app"),
                ),
            ),
            ("readiness", replace(self.metadata(), ready=False)),
            (
                "ownership",
                replace(self.metadata(), owner_application_id="other-app"),
            ),
            (
                "caller",
                replace(self.metadata(), invoker_principals=frozenset()),
            ),
            (
                "audience",
                replace(
                    self.metadata(),
                    audience="urn:comfforts:app-platform:audience:other-app",
                ),
            ),
            (
                "target",
                replace(self.metadata(), target_uri="https://attacker.example.test"),
            ),
            (
                "malformed target",
                replace(
                    self.metadata(),
                    target_uri="https://alpha-app.us-west1.run.app:invalid",
                ),
            ),
        )
        for label, metadata in cases:
            with self.subTest(label=label):
                provider = InMemoryCloudRunMetadataProvider(
                    {self.resource(): metadata}
                )
                resolver = CloudRunAttachmentResolver(provider, self.edge_caller)
                with self.assertRaises(AttachmentUnavailable):
                    asyncio.run(resolver.resolve(self.request()))

        unavailable = InMemoryCloudRunMetadataProvider({})
        with self.assertRaises(AttachmentUnavailable):
            asyncio.run(
                CloudRunAttachmentResolver(
                    unavailable,
                    self.edge_caller,
                ).resolve(self.request())
            )

        failing = InMemoryCloudRunMetadataProvider(
            {self.resource(): self.metadata()}
        )
        failing.available = False
        with self.assertRaises(AttachmentUnavailable):
            asyncio.run(
                CloudRunAttachmentResolver(
                    failing,
                    self.edge_caller,
                ).resolve(self.request())
            )

    def test_resolver_rejects_unsupported_adapter_before_provider_access(self) -> None:
        provider = InMemoryCloudRunMetadataProvider(
            {self.resource(): self.metadata()}
        )
        request = replace(self.request(), adapter_kind="unreviewed-v1")

        with self.assertRaises(AttachmentUnavailable):
            asyncio.run(
                CloudRunAttachmentResolver(provider, self.edge_caller).resolve(request)
            )

        self.assertEqual(provider.requests, [])

    def test_google_provider_uses_injected_client_and_exact_resource_only(self) -> None:
        resource = self.resource()
        client = StaticCloudRunServicesClient(
            run_v2.Service(
                name=resource.provider_name,
                labels={
                    "state_owner": "application",
                    "application_id": "alpha-app",
                },
                annotations={"comfforts.com/identity-audience": self.audience},
                reconciling=False,
                generation=7,
                observed_generation=7,
                terminal_condition=run_v2.Condition(
                    type_="Ready",
                    state=run_v2.Condition.State.CONDITION_SUCCEEDED,
                ),
                latest_ready_revision=(
                    f"{resource.provider_name}/revisions/alpha-app-00007"
                ),
                uri=self.target_uri,
                invoker_iam_disabled=False,
            ),
            policy_pb2.Policy(
                bindings=(
                    {
                        "role": "roles/run.invoker",
                        "members": (self.edge_caller,),
                    },
                ),
            ),
        )
        provider = GoogleCloudRunMetadataProvider(client)

        self.assertEqual(client.service_requests, [])
        self.assertEqual(client.policy_requests, [])

        metadata = asyncio.run(provider.describe(resource))

        self.assertEqual(client.service_requests, [resource.provider_name])
        self.assertEqual(
            client.policy_requests,
            [{"resource": resource.provider_name}],
        )
        self.assertEqual(metadata, self.metadata())

    def test_google_provider_does_not_treat_conditional_or_disabled_iam_as_grant(
        self,
    ) -> None:
        resource = self.resource()
        service = SimpleNamespace(
            name=resource.provider_name,
            labels={
                "state_owner": "application",
                "application_id": "alpha-app",
            },
            annotations={"comfforts.com/identity-audience": self.audience},
            reconciling=False,
            generation=1,
            observed_generation=1,
            terminal_condition=SimpleNamespace(type_="Ready", state=4),
            latest_ready_revision=f"{resource.provider_name}/revisions/alpha-app-00001",
            uri=self.target_uri,
            invoker_iam_disabled=True,
        )
        policy = SimpleNamespace(
            bindings=(
                SimpleNamespace(
                    role="roles/run.invoker",
                    members=(self.edge_caller,),
                    condition=SimpleNamespace(expression="request.time < timestamp('2030-01-01T00:00:00Z')"),
                ),
            )
        )

        metadata = asyncio.run(
            GoogleCloudRunMetadataProvider(
                StaticCloudRunServicesClient(service, policy)
            ).describe(resource)
        )

        self.assertFalse(metadata.ready)
        self.assertEqual(metadata.invoker_principals, frozenset())


class SharedEdgeInterfaceTest(unittest.TestCase):
    def test_root_catalogue_is_a_safe_projection_of_the_bound_generation(self) -> None:
        document = compiled_generation()
        document["catalogue"][0]["title"] = 'Alpha & "Friends"'
        document["catalogue"][0]["summary"] = "Useful 'tools' & reports"
        configuration, source = configured_generation(document)
        app = create_app(
            configuration,
            RuntimeAdapters(generation_source=source),
        )

        startup, (status, headers, body) = asyncio.run(
            request_during_lifespan(app, "/")
        )

        self.assertEqual(startup["type"], "lifespan.startup.complete")
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"content-type"], b"text/html; charset=utf-8")
        self.assertEqual(headers[b"cache-control"], b"no-store")
        self.assertIn(b'href="/alpha"', body)
        self.assertIn(b"Alpha &amp; &quot;Friends&quot;", body)
        self.assertIn(b"Useful &#x27;tools&#x27; &amp; reports", body)
        self.assertNotIn(b"resource_reference", body)
        self.assertNotIn(b"contract-test-v1", body)

    def test_reserved_unknown_and_malformed_paths_fail_closed(self) -> None:
        configuration, source = configured_generation(compiled_generation())
        app = create_app(
            configuration,
            RuntimeAdapters(generation_source=source),
        )
        closed_paths = (
            "/unknown",
            "/alphabet",
            "/Alpha",
            "/_platform",
            "/_platform/status",
            "/.well-known",
        )
        malformed_paths = (
            ("/alpha//item", None),
            ("/alpha/./item", None),
            ("/alpha/../item", None),
            ("/alpha\\item", None),
            ("/alpha item", None),
            ("/alpha/item", b"/alpha/%69tem"),
            ("/alpha/item", b"/alpha/\xffitem"),
        )

        for path in closed_paths:
            with self.subTest(path=path):
                _, (status, headers, body) = asyncio.run(
                    request_during_lifespan(app, path)
                )
                self.assertEqual(status, 404)
                self.assertEqual(headers[b"cache-control"], b"no-store")
                self.assertEqual(body, b"not found\n")
        for path, raw_path in malformed_paths:
            with self.subTest(path=path, raw_path=raw_path):
                _, (status, headers, body) = asyncio.run(
                    request_during_lifespan(app, path, raw_path=raw_path)
                )
                self.assertEqual(status, 400)
                self.assertEqual(headers[b"cache-control"], b"no-store")
                self.assertEqual(body, b"invalid request\n")

    def test_registered_route_selects_longest_mount_and_rewrites_path(self) -> None:
        document = compiled_generation()
        document["routes"][0]["attachments"] = [
            compiled_attachment("root", "/", "strip_application_prefix"),
            compiled_attachment("raw", "/raw", "preserve"),
            compiled_attachment("api", "/api", "strip_application_prefix"),
            compiled_attachment("api-v1", "/api/v1", "strip_attachment_mount"),
        ]
        configuration, source = configured_generation(document)
        handoff = RecordingRouteHandoff()
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                route_handoff=handoff,
            ),
        )
        cases = (
            ("/alpha", b"", "root", "/"),
            ("/alpha/", b"", "root", "/"),
            ("/alpha/api/item", b"page=1", "api", "/api/item"),
            ("/alpha/api/v1/item", b"page=2", "api-v1", "/item"),
            (
                "/alpha/raw/File.Name",
                b"view=full",
                "raw",
                "/alpha/raw/File.Name",
            ),
        )

        for path, query_string, attachment_id, forwarded_path in cases:
            with self.subTest(path=path):
                _, (status, _, body) = asyncio.run(
                    request_during_lifespan(
                        app,
                        path,
                        query_string=query_string,
                    )
                )
                routed = handoff.requests[-1]
                self.assertEqual(status, 503)
                self.assertEqual(body, b"application forwarding unavailable\n")
                self.assertEqual(routed.application_id, "alpha-app")
                self.assertEqual(routed.attachment_id, attachment_id)
                self.assertEqual(routed.path, forwarded_path)
                self.assertEqual(routed.query_string, query_string)

        self.assertEqual(len(handoff.requests), len(cases))

    def test_cloud_run_route_resolves_provider_metadata_before_handoff(self) -> None:
        document = cloud_run_generation()
        configuration, source = configured_generation(document)
        resource = parse_cloud_run_reference(
            document["routes"][0]["attachments"][0]["resource_reference"]
        )
        edge_caller = (
            "serviceAccount:apps-platform-edge@comfforts-platform-non-prod."
            "iam.gserviceaccount.com"
        )
        target_uri = "https://alpha-app-455651441682.us-west1.run.app"
        provider = InMemoryCloudRunMetadataProvider(
            {
                resource: CloudRunServiceMetadata(
                    resource=resource,
                    target_uri=target_uri,
                    ready=True,
                    owner_application_id="alpha-app",
                    audience=None,
                    invoker_principals=frozenset({edge_caller}),
                )
            }
        )
        handoff = RecordingRouteHandoff()
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                attachment_resolver=CloudRunAttachmentResolver(
                    provider,
                    edge_caller,
                ),
                route_handoff=handoff,
            ),
        )

        _, (status, _, body) = asyncio.run(
            request_during_lifespan(app, "/alpha/report")
        )

        self.assertEqual(status, 503)
        self.assertEqual(body, b"application forwarding unavailable\n")
        self.assertEqual(provider.requests, [resource])
        self.assertEqual(len(handoff.requests), 1)
        routed = handoff.requests[0]
        self.assertEqual(routed.adapter_kind, "gcp-cloud-run-v1")
        self.assertEqual(
            routed.resource_reference,
            document["routes"][0]["attachments"][0]["resource_reference"],
        )
        self.assertIsNotNone(routed.resolved_attachment)
        self.assertEqual(routed.resolved_attachment.target_uri, target_uri)

    def test_resolved_http_route_is_delivered_through_application_proxy(self) -> None:
        document = cloud_run_generation()
        configuration, source = configured_generation(document)
        resource = parse_cloud_run_reference(
            document["routes"][0]["attachments"][0]["resource_reference"]
        )
        edge_caller = (
            "serviceAccount:apps-platform-edge@comfforts-platform-non-prod."
            "iam.gserviceaccount.com"
        )
        provider = InMemoryCloudRunMetadataProvider(
            {
                resource: CloudRunServiceMetadata(
                    resource=resource,
                    target_uri=(
                        "https://alpha-app-455651441682.us-west1.run.app"
                    ),
                    ready=True,
                    owner_application_id="alpha-app",
                    audience=None,
                    invoker_principals=frozenset({edge_caller}),
                )
            }
        )
        proxy = RecordingApplicationProxy()
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                attachment_resolver=CloudRunAttachmentResolver(
                    provider,
                    edge_caller,
                ),
                application_proxy=proxy,
            ),
        )

        _, (status, headers, body) = asyncio.run(
            request_during_lifespan(
                app,
                "/alpha/report",
                query_string=b"view=summary",
            )
        )

        self.assertEqual(status, 202)
        self.assertEqual(headers[b"x-application-proxy"], b"bounded")
        self.assertEqual(body, b"proxied\n")
        self.assertEqual(len(proxy.http_requests), 1)
        routed = proxy.http_requests[0][1]
        self.assertEqual(routed.path, "/report")
        self.assertEqual(routed.query_string, b"view=summary")
        self.assertIsNotNone(routed.resolved_attachment)

    def test_resolved_websocket_route_is_delivered_through_application_proxy(
        self,
    ) -> None:
        document = cloud_run_generation()
        configuration, source = configured_generation(document)
        resource = parse_cloud_run_reference(
            document["routes"][0]["attachments"][0]["resource_reference"]
        )
        edge_caller = (
            "serviceAccount:apps-platform-edge@comfforts-platform-non-prod."
            "iam.gserviceaccount.com"
        )
        provider = InMemoryCloudRunMetadataProvider(
            {
                resource: CloudRunServiceMetadata(
                    resource=resource,
                    target_uri=(
                        "https://alpha-app-455651441682.us-west1.run.app"
                    ),
                    ready=True,
                    owner_application_id="alpha-app",
                    audience=None,
                    invoker_principals=frozenset({edge_caller}),
                )
            }
        )
        proxy = RecordingApplicationProxy()
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                attachment_resolver=CloudRunAttachmentResolver(
                    provider,
                    edge_caller,
                ),
                application_proxy=proxy,
            ),
        )

        _, outgoing = asyncio.run(
            websocket_during_lifespan(
                app,
                "/alpha/stream",
                query_string=b"view=summary",
            )
        )

        self.assertEqual(
            [message["type"] for message in outgoing],
            ["websocket.accept", "websocket.send", "websocket.close"],
        )
        self.assertEqual(outgoing[0]["subprotocol"], "chat")
        self.assertEqual(outgoing[1]["text"], "proxied")
        self.assertEqual(outgoing[2]["code"], 1000)
        self.assertEqual(len(proxy.websocket_requests), 1)
        routed = proxy.websocket_requests[0]
        self.assertEqual(routed.path, "/stream")
        self.assertEqual(routed.query_string, b"view=summary")

    def test_cloud_run_resolution_failure_never_reaches_handoff(self) -> None:
        edge_caller = (
            "serviceAccount:apps-platform-edge@comfforts-platform-non-prod."
            "iam.gserviceaccount.com"
        )
        cases = (
            (
                "missing resolver",
                cloud_run_generation(),
                None,
            ),
            (
                "unsupported adapter",
                cloud_run_generation(adapter_kind="unreviewed-v1"),
                CloudRunAttachmentResolver(
                    InMemoryCloudRunMetadataProvider({}),
                    edge_caller,
                ),
            ),
            (
                "invalid reference",
                cloud_run_generation(
                    resource_reference=(
                        "urn:comfforts:app-platform:gcp:cloud-run:"
                        "455651441682:us-west1:alpha-app:extra"
                    )
                ),
                CloudRunAttachmentResolver(
                    InMemoryCloudRunMetadataProvider({}),
                    edge_caller,
                ),
            ),
            (
                "unresolved service",
                cloud_run_generation(),
                CloudRunAttachmentResolver(
                    InMemoryCloudRunMetadataProvider({}),
                    edge_caller,
                ),
            ),
        )
        for label, document, resolver in cases:
            with self.subTest(label=label):
                configuration, source = configured_generation(document)
                handoff = RecordingRouteHandoff()
                app = create_app(
                    configuration,
                    RuntimeAdapters(
                        generation_source=source,
                        attachment_resolver=resolver,
                        route_handoff=handoff,
                    ),
                )

                _, (status, _, body) = asyncio.run(
                    request_during_lifespan(app, "/alpha")
                )

                self.assertEqual(status, 503)
                self.assertEqual(body, b"application attachment unavailable\n")
                self.assertFalse(handoff.requests)

    def test_route_path_limit_is_enforced_before_handoff(self) -> None:
        configuration, source = configured_generation(compiled_generation())
        handoff = RecordingRouteHandoff()
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                route_handoff=handoff,
            ),
        )
        accepted_path = "/alpha/" + "a" * (4_096 - len("/alpha/"))
        rejected_path = accepted_path + "a"

        _, (accepted_status, _, _) = asyncio.run(
            request_during_lifespan(app, accepted_path)
        )
        _, (rejected_status, _, rejected_body) = asyncio.run(
            request_during_lifespan(app, rejected_path)
        )

        self.assertEqual(accepted_status, 503)
        self.assertEqual(rejected_status, 400)
        self.assertEqual(rejected_body, b"invalid request\n")
        self.assertEqual(len(handoff.requests), 1)

    def test_protected_route_does_not_reach_handoff_before_admission_exists(self) -> None:
        document = compiled_generation()
        document["catalogue"][0]["admission_mode"] = "authenticated"
        document["admission_policies"][0]["policy"] = {"mode": "authenticated"}
        attachment = document["routes"][0]["attachments"][0]
        attachment["identity_requirement"] = "verified"
        attachment["audience"] = (
            "urn:comfforts:app-platform:audience:alpha-app"
        )
        configuration, source = configured_generation(document)
        handoff = RecordingRouteHandoff()
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                route_handoff=handoff,
            ),
        )

        _, (status, _, body) = asyncio.run(
            request_during_lifespan(app, "/alpha")
        )

        self.assertEqual(status, 503)
        self.assertEqual(body, b"identity unavailable\n")
        self.assertFalse(handoff.requests)

    def test_protected_route_enters_platform_owned_login(self) -> None:
        configuration, source = configured_generation(
            protected_generation("authenticated"),
            external_origin="https://apps-staging.comfforts.com",
        )
        handoff = RecordingRouteHandoff()
        store = InMemoryIdentityStore()
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                route_handoff=handoff,
                google_oidc=FakeGoogleOidc(
                    PlatformIdentity("https://accounts.google.com", "visitor-1")
                ),
                identity_store=store,
                clock=FixedClock(1_000),
                token_source=FixedTokenSource([]),
            ),
        )

        _, (status, headers, body) = asyncio.run(
            request_during_lifespan(
                app,
                "/alpha/report",
                query_string=b"view=summary",
            )
        )

        self.assertEqual(status, 303)
        self.assertEqual(
            headers[b"location"],
            b"/_platform/login?return_to=%2Falpha%2Freport%3Fview%3Dsummary",
        )
        self.assertEqual(headers[b"cache-control"], b"no-store")
        self.assertEqual(body, b"")
        self.assertFalse(handoff.requests)

    def test_login_uses_pkce_and_keeps_transient_material_server_side(self) -> None:
        configuration, source = configured_generation(
            protected_generation("authenticated"),
            external_origin="https://apps-staging.comfforts.com",
        )
        store = InMemoryIdentityStore()
        oidc = FakeGoogleOidc(
            PlatformIdentity("https://accounts.google.com", "visitor-1")
        )
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                google_oidc=oidc,
                identity_store=store,
                clock=FixedClock(10_000),
                token_source=FixedTokenSource(
                    [
                        "flow-id-01234567890123456789",
                        "state-01234567890123456789012",
                        "nonce-01234567890123456789012",
                        verifier,
                    ]
                ),
            ),
        )

        _, (status, headers, _) = asyncio.run(
            request_during_lifespan(
                app,
                "/_platform/login",
                query_string=b"return_to=%2Falpha",
            )
        )

        self.assertEqual(status, 303)
        provider_query = parse_qs(urlsplit(headers[b"location"].decode()).query)
        self.assertEqual(provider_query["code_challenge_method"], ["S256"])
        self.assertEqual(
            provider_query["code_challenge"],
            ["E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"],
        )
        flow_id = cookie_value(headers, "__Host-comfforts-oidc")
        self.assertEqual(flow_id, "flow-id-01234567890123456789")
        self.assertIn(b"Secure", headers.get_all(b"set-cookie")[0])
        self.assertIn(b"HttpOnly", headers.get_all(b"set-cookie")[0])
        self.assertIn(b"SameSite=lax", headers.get_all(b"set-cookie")[0])
        self.assertNotIn(b"Domain=", headers.get_all(b"set-cookie")[0])
        self.assertEqual(store.flows[flow_id].return_to, "/alpha")
        self.assertEqual(store.flows[flow_id].expires_at, 10_600)
        self.assertEqual(oidc.authorization_requests[0]["code_verifier"], verifier)

    def test_callback_creates_absolute_session_and_authenticated_handoff(self) -> None:
        configuration, source = configured_generation(
            protected_generation("authenticated"),
            external_origin="https://apps-staging.comfforts.com",
        )
        identity = PlatformIdentity(
            "https://accounts.google.com",
            "visitor-1",
            "display@example.com",
        )
        store = InMemoryIdentityStore()
        flow_id = "flow-id-01234567890123456789"
        store.flows[flow_id] = LoginFlow(
            state="expected-state-0123456789012",
            nonce="expected-nonce-0123456789012",
            code_verifier="verifier-012345678901234567890123456789012345",
            return_to="/alpha/report?view=summary",
            expires_at=2_000,
        )
        oidc = FakeGoogleOidc(identity)
        handoff = RecordingRouteHandoff()
        clock = FixedClock(1_000)
        assertion_issuer, verification_keys = assertion_components(clock)
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                route_handoff=handoff,
                google_oidc=oidc,
                identity_store=store,
                clock=clock,
                token_source=FixedTokenSource(
                    ["session-id-01234567890123456789"]
                ),
                assertion_issuer=assertion_issuer,
                verification_key_source=verification_keys,
            ),
        )

        _, (callback_status, callback_headers, _) = asyncio.run(
            request_during_lifespan(
                app,
                "/_platform/auth/callback",
                query_string=b"state=expected-state-0123456789012&code=provider-code",
                headers=((b"cookie", f"__Host-comfforts-oidc={flow_id}".encode()),),
            )
        )
        session_id = cookie_value(callback_headers, "__Host-comfforts-session")
        _, (route_status, route_headers, _) = asyncio.run(
            request_during_lifespan(
                app,
                "/alpha/report",
                headers=(
                    (b"cookie", f"__Host-comfforts-session={session_id}".encode()),
                ),
            )
        )

        self.assertEqual(callback_status, 303)
        self.assertEqual(
            callback_headers[b"location"],
            b"/alpha/report?view=summary",
        )
        self.assertEqual(len(callback_headers.get_all(b"set-cookie")), 2)
        self.assertNotIn(flow_id, store.flows)
        self.assertEqual(store.sessions[session_id].expires_at, 29_800)
        self.assertEqual(store.sessions[session_id].identity.email, "display@example.com")
        self.assertEqual(route_status, 503)
        self.assertEqual(route_headers.get_all(b"set-cookie"), [])
        self.assertIsNotNone(
            handoff.requests[0].verified_identity_assertion
        )
        self.assertEqual(
            oidc.authentication_requests[0]["nonce"],
            "expected-nonce-0123456789012",
        )

    def test_restricted_admission_uses_exact_issuer_and_subject_not_email(self) -> None:
        member = {
            "issuer": "https://accounts.google.com",
            "subject": "approved-subject",
        }
        configuration, source = configured_generation(
            protected_generation("restricted", members=[member]),
            external_origin="https://apps-staging.comfforts.com",
        )
        store = InMemoryIdentityStore()
        store.sessions["approved-session-01234567890"] = PlatformSession(
            identity=PlatformIdentity(
                member["issuer"], member["subject"], "same@example.com"
            ),
            expires_at=10_000,
        )
        store.sessions["denied-session-0123456789012"] = PlatformSession(
            identity=PlatformIdentity(
                member["issuer"], "different-subject", "same@example.com"
            ),
            expires_at=10_000,
        )
        handoff = RecordingRouteHandoff()
        clock = FixedClock(1_000)
        assertion_issuer, verification_keys = assertion_components(clock)
        adapters = RuntimeAdapters(
            generation_source=source,
            route_handoff=handoff,
            google_oidc=FakeGoogleOidc(
                PlatformIdentity(member["issuer"], member["subject"])
            ),
            identity_store=store,
            clock=clock,
            token_source=FixedTokenSource([]),
            assertion_issuer=assertion_issuer,
            verification_key_source=verification_keys,
        )
        app = create_app(configuration, adapters)

        _, (approved, _, _) = asyncio.run(
            request_during_lifespan(
                app,
                "/alpha",
                headers=((b"cookie", b"__Host-comfforts-session=approved-session-01234567890"),),
            )
        )
        _, (denied, _, denied_body) = asyncio.run(
            request_during_lifespan(
                app,
                "/alpha",
                headers=((b"cookie", b"__Host-comfforts-session=denied-session-0123456789012"),),
            )
        )

        self.assertEqual(approved, 503)
        self.assertEqual(denied, 403)
        self.assertEqual(denied_body, b"forbidden\n")
        self.assertEqual(len(handoff.requests), 1)

    def test_public_route_remains_anonymous_when_session_store_is_unavailable(self) -> None:
        configuration, source = configured_generation(compiled_generation())
        store = InMemoryIdentityStore()
        store.available = False
        handoff = RecordingRouteHandoff()
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                route_handoff=handoff,
                identity_store=store,
                clock=FixedClock(1_000),
            ),
        )

        _, (status, _, _) = asyncio.run(
            request_during_lifespan(
                app,
                "/alpha",
                headers=((b"cookie", b"__Host-comfforts-session=unavailable-session-0123456"),),
            )
        )

        self.assertEqual(status, 503)
        self.assertEqual(len(handoff.requests), 1)
        self.assertIsNone(handoff.requests[0].verified_identity_assertion)

    def test_public_route_carries_identity_only_for_a_valid_session(self) -> None:
        document = compiled_generation()
        attachment = document["routes"][0]["attachments"][0]
        attachment["identity_requirement"] = "verified"
        attachment["audience"] = (
            "urn:comfforts:app-platform:audience:alpha-app"
        )
        configuration, source = configured_generation(document)
        identity = PlatformIdentity(
            "https://accounts.google.com", "optional-subject"
        )
        store = InMemoryIdentityStore()
        store.sessions["optional-session-012345678901"] = PlatformSession(
            identity=identity,
            expires_at=10_000,
        )
        handoff = RecordingRouteHandoff()
        clock = FixedClock(1_000)
        assertion_issuer, verification_keys = assertion_components(clock)
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                route_handoff=handoff,
                identity_store=store,
                clock=clock,
                assertion_issuer=assertion_issuer,
                verification_key_source=verification_keys,
            ),
        )

        asyncio.run(
            request_during_lifespan(
                app,
                "/alpha",
                headers=((b"cookie", b"__Host-comfforts-session=optional-session-012345678901"),),
            )
        )
        asyncio.run(request_during_lifespan(app, "/alpha"))

        self.assertIsNotNone(
            handoff.requests[0].verified_identity_assertion
        )
        self.assertIsNone(
            handoff.requests[1].verified_identity_assertion
        )

    def test_identity_dependency_failures_are_closed_and_redacted(self) -> None:
        configuration, source = configured_generation(
            protected_generation("authenticated"),
            external_origin="https://apps-staging.comfforts.com",
        )
        store = InMemoryIdentityStore()
        flow_id = "failure-flow-01234567890123456"
        store.flows[flow_id] = LoginFlow(
            state="expected-state-0123456789012",
            nonce="expected-nonce-0123456789012",
            code_verifier="verifier-012345678901234567890123456789012345",
            return_to="/alpha",
            expires_at=2_000,
        )
        oidc = FakeGoogleOidc(
            PlatformIdentity("https://accounts.google.com", "visitor-1")
        )
        oidc.failure = RuntimeError("provider included a sensitive diagnostic")
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                google_oidc=oidc,
                identity_store=store,
                clock=FixedClock(1_000),
                token_source=FixedTokenSource([]),
            ),
        )

        _, (mismatch_status, _, mismatch_body) = asyncio.run(
            request_during_lifespan(
                app,
                "/_platform/auth/callback",
                query_string=b"state=wrong-state&code=provider-code",
                headers=((b"cookie", f"__Host-comfforts-oidc={flow_id}".encode()),),
            )
        )
        store.flows[flow_id] = LoginFlow(
            state="expected-state-0123456789012",
            nonce="expected-nonce-0123456789012",
            code_verifier="verifier-012345678901234567890123456789012345",
            return_to="/alpha",
            expires_at=2_000,
        )
        _, (provider_status, _, provider_body) = asyncio.run(
            request_during_lifespan(
                app,
                "/_platform/auth/callback",
                query_string=b"state=expected-state-0123456789012&code=provider-code",
                headers=((b"cookie", f"__Host-comfforts-oidc={flow_id}".encode()),),
            )
        )
        store.available = False
        _, (store_status, _, store_body) = asyncio.run(
            request_during_lifespan(
                app,
                "/alpha",
                headers=((b"cookie", b"__Host-comfforts-session=unavailable-session-0123456"),),
            )
        )

        self.assertEqual((mismatch_status, mismatch_body), (400, b"invalid identity response\n"))
        self.assertEqual((provider_status, provider_body), (503, b"identity unavailable\n"))
        self.assertEqual((store_status, store_body), (503, b"identity unavailable\n"))
        self.assertNotIn(b"sensitive", provider_body)

    def test_expired_session_reauthenticates_without_silent_renewal(self) -> None:
        configuration, source = configured_generation(
            protected_generation("authenticated"),
            external_origin="https://apps-staging.comfforts.com",
        )
        store = InMemoryIdentityStore()
        session_id = "expired-session-0123456789012"
        store.sessions[session_id] = PlatformSession(
            identity=PlatformIdentity(
                "https://accounts.google.com", "visitor-1"
            ),
            expires_at=1_000,
        )
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                google_oidc=FakeGoogleOidc(
                    PlatformIdentity("https://accounts.google.com", "visitor-1")
                ),
                identity_store=store,
                clock=FixedClock(1_000),
                token_source=FixedTokenSource([]),
            ),
        )

        _, (status, headers, _) = asyncio.run(
            request_during_lifespan(
                app,
                "/alpha",
                headers=((b"cookie", f"__Host-comfforts-session={session_id}".encode()),),
            )
        )

        self.assertEqual(status, 303)
        self.assertEqual(headers[b"location"], b"/_platform/login?return_to=%2Falpha")
        self.assertNotIn(session_id, store.sessions)
        self.assertEqual(headers.get_all(b"set-cookie"), [])

    def test_logout_clears_server_session_and_rejects_external_return(self) -> None:
        configuration, source = configured_generation(
            compiled_generation(),
            external_origin="https://apps-staging.comfforts.com",
        )
        store = InMemoryIdentityStore()
        session_id = "logout-session-01234567890123"
        store.sessions[session_id] = PlatformSession(
            identity=PlatformIdentity(
                "https://accounts.google.com", "visitor-1"
            ),
            expires_at=10_000,
        )
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                identity_store=store,
                clock=FixedClock(1_000),
            ),
        )

        _, (status, headers, _) = asyncio.run(
            request_during_lifespan(
                app,
                "/_platform/logout",
                query_string=b"return_to=%2Falpha",
                headers=((b"cookie", f"__Host-comfforts-session={session_id}".encode()),),
            )
        )
        _, (invalid_status, _, invalid_body) = asyncio.run(
            request_during_lifespan(
                app,
                "/_platform/logout",
                query_string=b"return_to=https%3A%2F%2Fevil.example",
            )
        )

        self.assertEqual(status, 303)
        self.assertEqual(headers[b"location"], b"/alpha")
        self.assertNotIn(session_id, store.sessions)
        self.assertIn(b"Max-Age=0", headers.get_all(b"set-cookie")[0])
        self.assertEqual(invalid_status, 400)
        self.assertEqual(invalid_body, b"invalid return location\n")

    def test_edge_replaces_visitor_assertion_with_minimized_application_assertion(
        self,
    ) -> None:
        configuration, source = configured_generation(
            protected_generation("authenticated")
        )
        identity = PlatformIdentity(
            "https://accounts.google.com",
            "verified-subject",
            "display-only@example.com",
        )
        store = InMemoryIdentityStore()
        session_id = "assertion-session-012345678901"
        store.sessions[session_id] = PlatformSession(identity, expires_at=20_000)
        clock = FixedClock(10_000)
        issuer, keys = assertion_components(
            clock,
            ["request-correlation-0001"],
        )
        handoff = RecordingRouteHandoff()
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                route_handoff=handoff,
                identity_store=store,
                clock=clock,
                assertion_issuer=issuer,
                verification_key_source=keys,
            ),
        )

        _, (status, _, _) = asyncio.run(
            request_during_lifespan(
                app,
                "/alpha/report",
                headers=(
                    (b"cookie", f"__Host-comfforts-session={session_id}".encode()),
                    (
                        b"x-comfforts-verified-identity",
                        b"visitor-controlled-forged-value",
                    ),
                ),
            )
        )
        assertion = handoff.requests[0].verified_identity_assertion
        verifier = ApplicationIdentityVerifier(
            expected_issuer="https://accounts.google.com",
            expected_audience=(
                "urn:comfforts:app-platform:audience:alpha-app"
            ),
            key_fetcher=InMemoryJwksFetcher(
                [{"keys": list(asyncio.run(keys.verification_keys()))}]
            ),
            clock=clock,
        )
        result = asyncio.run(verifier.verify(assertion))

        self.assertEqual(status, 503)
        self.assertNotEqual(assertion, "visitor-controlled-forged-value")
        self.assertTrue(result.accepted)
        assert result.identity is not None
        self.assertEqual(result.identity.subject, "verified-subject")
        self.assertEqual(result.identity.issued_at, 10_000)
        self.assertEqual(result.identity.expires_at, 10_060)
        self.assertEqual(result.identity.correlation_id, "request-correlation-0001")
        self.assertFalse(hasattr(result.identity, "email"))

    def test_jwks_publishes_only_current_and_overlapping_public_keys(self) -> None:
        configuration, source = configured_generation(compiled_generation())
        clock = FixedClock(10_000)
        _, keys = assertion_components(clock)
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                verification_key_source=keys,
            ),
        )

        _, (status, headers, body) = asyncio.run(
            request_during_lifespan(app, "/.well-known/jwks.json")
        )
        payload = json.loads(body)

        self.assertEqual(status, 200)
        self.assertEqual(headers[b"cache-control"], b"public, max-age=900")
        self.assertEqual(headers[b"content-type"], b"application/json")
        self.assertEqual(len(payload["keys"]), 2)
        self.assertEqual(
            {item["kid"] for item in payload["keys"]},
            {
                "ap-m6-w6-current-test-only",
                "ap-m6-w6-previous-test-only",
            },
        )
        self.assertTrue(all("d" not in item for item in payload["keys"]))

    def test_protected_assertion_failure_is_closed_but_public_remains_anonymous(
        self,
    ) -> None:
        clock = FixedClock(10_000)
        issuer, keys = assertion_components(clock)
        keys.available = False
        identity = PlatformIdentity(
            "https://accounts.google.com", "verified-subject"
        )
        store = InMemoryIdentityStore()
        session_id = "failed-signing-session-0123456"
        store.sessions[session_id] = PlatformSession(identity, expires_at=20_000)
        protected_configuration, protected_source = configured_generation(
            protected_generation("authenticated")
        )
        protected_handoff = RecordingRouteHandoff()
        protected_app = create_app(
            protected_configuration,
            RuntimeAdapters(
                generation_source=protected_source,
                route_handoff=protected_handoff,
                identity_store=store,
                clock=clock,
                assertion_issuer=issuer,
            ),
        )
        public_document = compiled_generation()
        public_attachment = public_document["routes"][0]["attachments"][0]
        public_attachment["identity_requirement"] = "verified"
        public_attachment["audience"] = (
            "urn:comfforts:app-platform:audience:alpha-app"
        )
        public_configuration, public_source = configured_generation(public_document)
        public_handoff = RecordingRouteHandoff()
        public_app = create_app(
            public_configuration,
            RuntimeAdapters(
                generation_source=public_source,
                route_handoff=public_handoff,
                identity_store=store,
                clock=clock,
                assertion_issuer=issuer,
            ),
        )
        cookie = ((b"cookie", f"__Host-comfforts-session={session_id}".encode()),)

        _, (protected_status, _, protected_body) = asyncio.run(
            request_during_lifespan(protected_app, "/alpha", headers=cookie)
        )
        _, (public_status, _, _) = asyncio.run(
            request_during_lifespan(public_app, "/alpha", headers=cookie)
        )

        self.assertEqual(protected_status, 503)
        self.assertEqual(protected_body, b"identity assertion unavailable\n")
        self.assertFalse(protected_handoff.requests)
        self.assertEqual(public_status, 503)
        self.assertIsNone(
            public_handoff.requests[0].verified_identity_assertion
        )

    def test_non_active_application_entries_are_excluded_from_catalogue_and_routes(
        self,
    ) -> None:
        document = compiled_generation()
        for lifecycle in ("staged", "suspended", "retired"):
            application_id = f"{lifecycle}-app"
            route_prefix = f"/{lifecycle}"
            state = copy.deepcopy(document["application_states"][0])
            state.update(
                application_id=application_id,
                route_prefix=route_prefix,
                lifecycle=lifecycle,
            )
            catalogue = copy.deepcopy(document["catalogue"][0])
            catalogue.update(
                application_id=application_id,
                route_prefix=route_prefix,
                title=f"{lifecycle.title()} App",
            )
            route = copy.deepcopy(document["routes"][0])
            route.update(
                application_id=application_id,
                route_prefix=route_prefix,
            )
            route["attachments"][0].update(
                owner_application_id=application_id,
                resource_reference=(
                    "urn:comfforts:app-platform:contract-test:"
                    f"{application_id}:web"
                ),
            )
            policy = copy.deepcopy(document["admission_policies"][0])
            policy["application_id"] = application_id
            document["application_states"].append(state)
            document["catalogue"].append(catalogue)
            document["routes"].append(route)
            document["admission_policies"].append(policy)

        configuration, source = configured_generation(document)
        handoff = RecordingRouteHandoff()
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                route_handoff=handoff,
            ),
        )

        _, (catalogue_status, _, catalogue_body) = asyncio.run(
            request_during_lifespan(app, "/")
        )
        self.assertEqual(catalogue_status, 200)
        self.assertIn(b'href="/alpha"', catalogue_body)
        for lifecycle in ("staged", "suspended", "retired"):
            with self.subTest(lifecycle=lifecycle):
                route_prefix = f"/{lifecycle}"
                self.assertNotIn(route_prefix.encode("ascii"), catalogue_body)
                _, (status, _, body) = asyncio.run(
                    request_during_lifespan(app, route_prefix)
                )
                self.assertEqual(status, 404)
                self.assertEqual(body, b"not found\n")
        self.assertFalse(handoff.requests)

    def test_inconsistent_compiled_route_projection_fails_closed(self) -> None:
        document = compiled_generation()
        document["catalogue"][0]["route_prefix"] = "/other"
        document["routes"][0]["route_prefix"] = "/other"
        configuration, source = configured_generation(document)
        handoff = RecordingRouteHandoff()
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                route_handoff=handoff,
            ),
        )

        _, (_, _, catalogue_body) = asyncio.run(
            request_during_lifespan(app, "/")
        )
        _, (status, _, body) = asyncio.run(
            request_during_lifespan(app, "/other")
        )

        self.assertNotIn(b'href="/other"', catalogue_body)
        self.assertEqual(status, 404)
        self.assertEqual(body, b"not found\n")
        self.assertFalse(handoff.requests)

    def test_inconsistent_catalogue_admission_label_is_not_rendered(self) -> None:
        document = compiled_generation()
        document["catalogue"][0]["admission_mode"] = "authenticated"
        configuration, source = configured_generation(document)
        app = create_app(
            configuration,
            RuntimeAdapters(generation_source=source),
        )

        _, (status, _, body) = asyncio.run(
            request_during_lifespan(app, "/")
        )

        self.assertEqual(status, 200)
        self.assertNotIn(b'href="/alpha"', body)

    def test_ambiguous_attachment_mount_fails_closed(self) -> None:
        document = compiled_generation()
        document["routes"][0]["attachments"].append(
            compiled_attachment("other", "/", "preserve")
        )
        configuration, source = configured_generation(document)
        handoff = RecordingRouteHandoff()
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                route_handoff=handoff,
            ),
        )

        _, (status, _, body) = asyncio.run(
            request_during_lifespan(app, "/alpha")
        )

        self.assertEqual(status, 404)
        self.assertEqual(body, b"not found\n")
        self.assertFalse(handoff.requests)

    def test_ambiguous_application_route_fails_closed(self) -> None:
        document = compiled_generation()
        state = copy.deepcopy(document["application_states"][0])
        state["application_id"] = "other-app"
        route = copy.deepcopy(document["routes"][0])
        route["application_id"] = "other-app"
        route["attachments"][0].update(
            owner_application_id="other-app",
            resource_reference=(
                "urn:comfforts:app-platform:contract-test:other-app:web"
            ),
        )
        policy = copy.deepcopy(document["admission_policies"][0])
        policy["application_id"] = "other-app"
        document["application_states"].append(state)
        document["routes"].append(route)
        document["admission_policies"].append(policy)
        configuration, source = configured_generation(document)
        handoff = RecordingRouteHandoff()
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                route_handoff=handoff,
            ),
        )

        _, (status, _, body) = asyncio.run(
            request_during_lifespan(app, "/alpha")
        )

        self.assertEqual(status, 404)
        self.assertEqual(body, b"not found\n")
        self.assertFalse(handoff.requests)

    def test_gcs_adapter_binds_the_exact_object_generation(self) -> None:
        payload = valid_generation_payload()
        app = create_app(
            generation_configuration(),
            RuntimeAdapters(
                generation_source=GoogleCloudStorageGenerationSource(
                    StaticStorageClient(
                        bucket=GENERATION_BUCKET,
                        object_name=GENERATION_OBJECT,
                        object_generation=GENERATION_OBJECT_GENERATION,
                        payload=payload,
                    )
                )
            ),
        )

        startup, (_, _, body) = asyncio.run(
            request_during_lifespan(app, "/alpha")
        )

        self.assertEqual(startup["type"], "lifespan.startup.complete")
        self.assertEqual(body, b"application forwarding unavailable\n")

    def test_valid_immutable_generation_is_bound_at_startup(self) -> None:
        payload = valid_generation_payload()
        app = create_app(
            generation_configuration(),
            RuntimeAdapters(
                generation_source=StaticGenerationSource(
                    bucket=GENERATION_BUCKET,
                    object_name=GENERATION_OBJECT,
                    object_generation=GENERATION_OBJECT_GENERATION,
                    payload=payload,
                )
            ),
        )

        startup, (status, headers, body) = asyncio.run(
            request_during_lifespan(app, "/alpha")
        )

        self.assertEqual(startup["type"], "lifespan.startup.complete")
        self.assertEqual(status, 503)
        self.assertEqual(headers[b"cache-control"], b"no-store")
        self.assertEqual(body, b"application forwarding unavailable\n")

    def test_bound_generation_is_not_reloaded_during_process_lifetime(self) -> None:
        source = StaticGenerationSource(
            bucket=GENERATION_BUCKET,
            object_name=GENERATION_OBJECT,
            object_generation=GENERATION_OBJECT_GENERATION,
            payload=valid_generation_payload(),
        )
        app = create_app(
            generation_configuration(),
            RuntimeAdapters(generation_source=source),
        )

        asyncio.run(request_during_lifespan(app, "/first"))
        asyncio.run(request_during_lifespan(app, "/second"))

        self.assertEqual(source.load_count, 1)

    def test_generation_binding_must_be_complete_and_well_formed(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "generation binding must be complete",
        ):
            RuntimeConfiguration(
                profile="qualification-v1",
                generation_bucket=GENERATION_BUCKET,
            )

        with self.assertRaisesRegex(
            ValueError,
            "generation object generation is invalid",
        ):
            RuntimeConfiguration(
                profile="qualification-v1",
                generation_bucket=GENERATION_BUCKET,
                generation_object=GENERATION_OBJECT,
                generation_object_generation=cast(Any, True),
                generation_content_digest=GENERATION_CONTENT_DIGEST,
                generation_digest=GENERATION_DIGEST,
            )

        with self.assertRaisesRegex(ValueError, "generation digest is invalid"):
            generation_configuration(generation_digest="sha256:not-a-digest")

        with self.assertRaisesRegex(ValueError, "HTTPS origin"):
            generation_configuration(external_origin="http://apps.example.test/path")

    def test_generation_integrity_or_contract_failure_stops_startup(self) -> None:
        invalid_json = b"{"
        invalid_contract = b'{"contract_version":1}'
        cases = (
            (
                "content digest",
                valid_generation_payload(),
                generation_configuration(content_digest="sha256:" + "0" * 64),
                "GENERATION_CONTENT_DIGEST_MISMATCH",
            ),
            (
                "generation digest",
                valid_generation_payload(),
                generation_configuration(generation_digest="sha256:" + "0" * 64),
                "GENERATION_DIGEST_MISMATCH",
            ),
            (
                "JSON document",
                invalid_json,
                generation_configuration(
                    content_digest=(
                        "sha256:" + hashlib.sha256(invalid_json).hexdigest()
                    )
                ),
                "GENERATION_DOCUMENT_INVALID",
            ),
            (
                "compiled contract",
                invalid_contract,
                generation_configuration(
                    content_digest=(
                        "sha256:" + hashlib.sha256(invalid_contract).hexdigest()
                    )
                ),
                "GENERATION_CONTRACT_INVALID",
            ),
        )

        for label, payload, configuration, code in cases:
            with self.subTest(label=label):
                app = create_app(
                    configuration,
                    RuntimeAdapters(
                        generation_source=StaticGenerationSource(
                            bucket=GENERATION_BUCKET,
                            object_name=GENERATION_OBJECT,
                            object_generation=GENERATION_OBJECT_GENERATION,
                            payload=payload,
                        )
                    ),
                )

                startup, error = asyncio.run(failed_startup(app))

                self.assertEqual(startup["type"], "lifespan.startup.failed")
                self.assertEqual(error, f"generation startup failed: {code}")
                self.assertIn(code, startup["message"])

    def test_missing_or_failed_generation_source_stops_without_detail_leak(self) -> None:
        cases = (
            ("missing", RuntimeAdapters()),
            (
                "provider failure",
                RuntimeAdapters(generation_source=FailingGenerationSource()),
            ),
        )

        for label, adapters in cases:
            with self.subTest(label=label):
                app = create_app(generation_configuration(), adapters)

                startup, error = asyncio.run(failed_startup(app))

                self.assertEqual(startup["type"], "lifespan.startup.failed")
                self.assertEqual(
                    error,
                    "generation startup failed: GENERATION_SOURCE_UNAVAILABLE",
                )
                self.assertIn("GENERATION_SOURCE_UNAVAILABLE", startup["message"])
                self.assertNotIn("provider-secret-marker", startup["message"])

    def test_runtime_configuration_rejects_an_unknown_profile(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "unsupported runtime profile: unreviewed-profile",
        ):
            RuntimeConfiguration(
                profile=cast(Any, "unreviewed-profile"),
            )

    def test_unconfigured_edge_fails_closed_through_asgi_interface(self) -> None:
        app = create_app(
            RuntimeConfiguration(profile="qualification-v1"),
            RuntimeAdapters(),
        )

        status, headers, body = asyncio.run(request(app, "/unknown"))

        self.assertEqual(status, 503)
        self.assertEqual(headers[b"cache-control"], b"no-store")
        self.assertEqual(headers[b"content-type"], b"text/plain; charset=utf-8")
        self.assertEqual(body, b"platform unavailable\n")


if __name__ == "__main__":
    unittest.main()
