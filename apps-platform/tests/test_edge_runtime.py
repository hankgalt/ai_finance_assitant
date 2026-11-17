from __future__ import annotations

import asyncio
import unittest
from collections.abc import Awaitable, Callable
from typing import Any, cast

from edge import RuntimeAdapters, RuntimeConfiguration, create_app


AsgiScope = dict[str, Any]
AsgiMessage = dict[str, Any]
AsgiReceive = Callable[[], Awaitable[AsgiMessage]]
AsgiSend = Callable[[AsgiMessage], Awaitable[None]]
AsgiApplication = Callable[[AsgiScope, AsgiReceive, AsgiSend], Awaitable[None]]


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


class SharedEdgeInterfaceTest(unittest.TestCase):
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
