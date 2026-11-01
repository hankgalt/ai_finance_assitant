"""Read-only Model Context Protocol adapter for approved application capabilities."""

from ai_finance_assistant.mcp_adapter.server import McpDependencies, create_mcp_server

__all__ = ["McpDependencies", "create_mcp_server"]
