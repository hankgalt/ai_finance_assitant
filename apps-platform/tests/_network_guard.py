"""Fail the deterministic gate before any non-loopback network operation."""

from __future__ import annotations

import ipaddress
import socket
from typing import Any


_ORIGINAL_GETADDRINFO = socket.getaddrinfo
_ORIGINAL_SOCKET = socket.socket
_INSTALLED = False


def _loopback_host(host: Any) -> bool:
    if isinstance(host, bytes):
        try:
            host = host.decode("ascii")
        except UnicodeDecodeError:
            return False
    if not isinstance(host, str):
        return False
    try:
        return ipaddress.ip_address(host.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


def _require_loopback(address: Any) -> None:
    if (
        not isinstance(address, tuple)
        or not address
        or not _loopback_host(address[0])
    ):
        raise AssertionError(
            "AP-EVAL-M6 rejected a non-loopback network attempt"
        )


class _LoopbackOnlySocket(_ORIGINAL_SOCKET):
    def bind(self, address: Any) -> None:
        if self.family != socket.AF_UNIX:
            _require_loopback(address)
        return super().bind(address)

    def connect(self, address: Any) -> None:
        if self.family != socket.AF_UNIX:
            _require_loopback(address)
        return super().connect(address)

    def connect_ex(self, address: Any) -> int:
        if self.family != socket.AF_UNIX:
            _require_loopback(address)
        return super().connect_ex(address)

    def sendto(self, data: Any, *args: Any) -> int:
        if self.family != socket.AF_UNIX:
            if not args:
                raise AssertionError("network destination is missing")
            _require_loopback(args[-1])
        return super().sendto(data, *args)


def _loopback_getaddrinfo(
    host: Any,
    port: Any,
    family: int = 0,
    type: int = 0,
    proto: int = 0,
    flags: int = 0,
) -> list[Any]:
    if not _loopback_host(host):
        raise AssertionError(
            "AP-EVAL-M6 rejected DNS or a non-loopback network attempt"
        )
    return _ORIGINAL_GETADDRINFO(host, port, family, type, proto, flags)


def install_loopback_only_guard() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    socket.socket = _LoopbackOnlySocket
    socket.getaddrinfo = _loopback_getaddrinfo
    _INSTALLED = True
