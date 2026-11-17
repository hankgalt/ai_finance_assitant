from __future__ import annotations

import asyncio
import hashlib
import unittest
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, cast

from edge import RuntimeAdapters, RuntimeConfiguration, create_app
from edge._generation import GoogleCloudStorageGenerationSource


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


def valid_generation_payload() -> bytes:
    return (
        PROJECT_ROOT / "contracts/test-vectors/valid/compiled-active.v1.json"
    ).read_bytes()


def generation_configuration(
    *,
    content_digest: str = GENERATION_CONTENT_DIGEST,
    generation_digest: str = GENERATION_DIGEST,
) -> RuntimeConfiguration:
    return RuntimeConfiguration(
        profile="qualification-v1",
        generation_bucket=GENERATION_BUCKET,
        generation_object=GENERATION_OBJECT,
        generation_object_generation=GENERATION_OBJECT_GENERATION,
        generation_content_digest=content_digest,
        generation_digest=generation_digest,
    )


async def request(
    app: AsgiApplication,
    path: str = "/",
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
            "method": "GET",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "root_path": "",
            "headers": [],
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
    return start["status"], dict(start["headers"]), body


async def request_during_lifespan(
    app: AsgiApplication,
    path: str,
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
    response = await request(app, path)
    await incoming.put({"type": "lifespan.shutdown"})
    shutdown = await outgoing.get()
    await lifespan_task
    if shutdown["type"] != "lifespan.shutdown.complete":
        raise AssertionError(f"unexpected shutdown result: {shutdown['type']}")
    return startup, response


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


class SharedEdgeInterfaceTest(unittest.TestCase):
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
            request_during_lifespan(app, "/unknown")
        )

        self.assertEqual(startup["type"], "lifespan.startup.complete")
        self.assertEqual(body, b"platform routing unavailable\n")

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
            request_during_lifespan(app, "/unknown")
        )

        self.assertEqual(startup["type"], "lifespan.startup.complete")
        self.assertEqual(status, 503)
        self.assertEqual(headers[b"cache-control"], b"no-store")
        self.assertEqual(body, b"platform routing unavailable\n")

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
