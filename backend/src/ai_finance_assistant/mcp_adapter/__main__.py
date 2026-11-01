"""Run the owner-only read-only MCP adapter over stdio."""

from ai_finance_assistant.api.services import ApplicationServices
from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.mcp_adapter.server import McpDependencies, create_mcp_server


def main() -> None:
    services = ApplicationServices(Settings())
    try:
        create_mcp_server(McpDependencies.from_services(services)).run(transport="stdio")
    finally:
        services.close()


if __name__ == "__main__":
    main()
