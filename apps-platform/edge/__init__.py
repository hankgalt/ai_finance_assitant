"""Public interface for the App Platform Shared Edge."""

from ._runtime import RuntimeAdapters, RuntimeConfiguration, create_app

__all__ = ["RuntimeAdapters", "RuntimeConfiguration", "create_app"]
