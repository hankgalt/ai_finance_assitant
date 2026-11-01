from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mcp import Client, StdioServerParameters

from ai_finance_assistant.finance.goal_projection import GoalProjection
from ai_finance_assistant.finance.portfolio_analysis import PortfolioAnalysis
from ai_finance_assistant.finance.portfolio_import import PortfolioImport
from ai_finance_assistant.knowledge.models import Evidence, LogicalKnowledgeBase
from ai_finance_assistant.mcp_adapter import McpDependencies, create_mcp_server
from ai_finance_assistant.providers.fake import FakeMarketDataProvider
from ai_finance_assistant.workflow.retrieval import StaticKnowledgeRetrieval

BACKEND_ROOT = Path(__file__).parents[1]
NOW = datetime(2026, 10, 31, 18, 0, tzinfo=UTC)


def _evidence(logical_kb: LogicalKnowledgeBase) -> Evidence:
    return Evidence(
        chunk_id=f"{logical_kb.value}-chunk",
        document_id=f"{logical_kb.value}-document",
        title="Diversification basics",
        publisher="Investor Education Test Publisher",
        canonical_url="https://example.invalid/diversification",
        section_path="Basics",
        text="Diversification cannot eliminate investment loss.",
        score=0.95,
        rank=1,
        collection_name=f"{logical_kb.value}_v1",
        collection_version="v1",
        document_version="v1",
        content_hash="a" * 64,
        fetched_at=NOW,
        tax_years=(2026,) if logical_kb == LogicalKnowledgeBase.TAX else (),
        jurisdiction="US-Federal",
    )


def _server() -> Any:
    return create_mcp_server(
        McpDependencies(
            knowledge=StaticKnowledgeRetrieval(
                {
                    LogicalKnowledgeBase.FINANCE: (_evidence(LogicalKnowledgeBase.FINANCE),),
                    LogicalKnowledgeBase.TAX: (_evidence(LogicalKnowledgeBase.TAX),),
                }
            ),
            market=FakeMarketDataProvider(),
            portfolio_import=PortfolioImport(),
            portfolio_analysis=PortfolioAnalysis(),
            goal_projection=GoalProjection(),
        )
    )


def test_mcp_tools_are_read_only_and_use_validated_application_modules() -> None:
    async def exercise() -> None:
        async with Client(_server(), raise_exceptions=True) as client:
            listed = await client.list_tools()
            tools = {tool.name: tool for tool in listed.tools}
            assert set(tools) == {
                "search_education",
                "get_market_quote",
                "analyze_portfolio",
                "project_goal",
            }
            assert all(
                tool.annotations is not None
                and tool.annotations.read_only_hint is True
                and tool.annotations.destructive_hint is False
                for tool in tools.values()
            )

            education = await client.call_tool(
                "search_education",
                {
                    "request": {
                        "query": "What is diversification?",
                        "knowledge_base": "finance_education",
                        "jurisdiction": "US",
                        "limit": 5,
                    }
                },
            )
            assert not education.is_error
            assert education.structured_content["evidence"][0]["publisher"] == (
                "Investor Education Test Publisher"
            )

            quote = await client.call_tool(
                "get_market_quote",
                {"request": {"symbol": "DEMO", "currency": "USD"}},
            )
            assert not quote.is_error
            assert quote.structured_content["quote"]["price"] == "123.45"
            assert quote.structured_content["provenance"]["is_synthetic"] is True

            portfolio = await client.call_tool(
                "analyze_portfolio",
                {
                    "request": {
                        "metadata": {
                            "portfolio_id": "mcp-demo",
                            "label": "MCP demo",
                            "base_currency": "USD",
                            "imported_at": "2026-10-31T18:00:00Z",
                        },
                        "payload": {
                            "kind": "manual",
                            "rows": [
                                {
                                    "account_id": "account-1",
                                    "account_type": "taxable",
                                    "holding_id": "holding-1",
                                    "identifier_type": "ticker",
                                    "identifier_value": "DEMO",
                                    "quantity": "2",
                                    "currency": "USD",
                                    "user_price": "10",
                                    "user_price_as_of": "2026-10-31T18:00:00Z",
                                    "user_price_provenance": "synthetic MCP fixture",
                                }
                            ],
                        },
                    }
                },
            )
            assert not portfolio.is_error
            assert portfolio.structured_content["import_result"]["accepted"] is True
            assert portfolio.structured_content["snapshot"]["base_currency_total"] == "20.00"

            goal = await client.call_tool(
                "project_goal",
                {
                    "request": {
                        "projection_id": "mcp-goal",
                        "currency": "USD",
                        "starting_amount": "10000",
                        "goal_amount": "25000",
                        "contribution_amount": "500",
                        "contribution_frequency": "monthly",
                        "contribution_timing": "end",
                        "horizon_months": 24,
                        "risk_tolerance": "moderate",
                        "scenarios": [
                            {
                                "label": "illustrative",
                                "annual_return_rate": "0.05",
                                "annual_inflation_rate": "0.02",
                                "annual_fee_rate": "0.001",
                            }
                        ],
                    }
                },
            )
            assert not goal.is_error
            assert goal.structured_content["projection_id"] == "mcp-goal"
            assert "not forecasts or guarantees" in goal.structured_content["warnings"][0]

    asyncio.run(exercise())


def test_external_stdio_client_lists_and_invokes_read_only_tool(tmp_path: Path) -> None:
    async def exercise() -> None:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "ai_finance_assistant.mcp_adapter"],
            cwd=BACKEND_ROOT,
            env={
                "AIFA_ENV_FILE": str(BACKEND_ROOT / ".test.env"),
                "AIFA_STORAGE_PATH": str(tmp_path / "mcp-application.sqlite3"),
            },
        )
        async with Client(parameters, raise_exceptions=True) as client:
            listed = await client.list_tools()
            assert {tool.name for tool in listed.tools} == {
                "search_education",
                "get_market_quote",
                "analyze_portfolio",
                "project_goal",
            }
            result = await client.call_tool(
                "get_market_quote",
                {"request": {"symbol": "DEMO", "currency": "USD"}},
            )
            assert not result.is_error
            assert result.structured_content["provenance"]["is_synthetic"] is True

    asyncio.run(exercise())
