"""App Platform test package with loopback-only network enforcement."""

from ._network_guard import install_loopback_only_guard


install_loopback_only_guard()
