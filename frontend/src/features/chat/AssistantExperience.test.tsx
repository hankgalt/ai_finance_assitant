import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { api, readRunStream } from "../../lib/api";
import type { ImportedPortfolio, RunRecord } from "../../types/contracts";
import { AssistantExperience, RunCard } from "./AssistantExperience";

vi.mock("../../lib/api", () => ({
  api: {
    continueRun: vi.fn(),
    createRun: vi.fn(),
    listPortfolios: vi.fn(),
    listRuns: vi.fn(),
  },
  ClientApiError: class ClientApiError extends Error {},
  readRunStream: vi.fn(),
}));

const portfolio = (portfolioId: string, label: string): ImportedPortfolio => ({
  schema_version: "1",
  portfolio_id: portfolioId,
  label,
  base_currency: "USD",
  imported_at: "2026-10-29T20:38:00Z",
  source_kind: "manual",
  source_file_hash: "a".repeat(64),
  accounts: [],
});

const createdRun: RunRecord = {
  execution_id: "run-portfolio-question",
  session_id: "session-test",
  workflow_id: "finance-assistant",
  workflow_version: "1",
  status: "running",
  request_message: "How many holdings have usable prices?",
  result: null,
  created_at: "2026-10-29T20:38:00Z",
  updated_at: "2026-10-29T20:38:00Z",
};

const clarificationRun: RunRecord = {
  ...createdRun,
  status: "clarification",
  result: {
    schema_version: "1",
    execution_id: createdRun.execution_id,
    session_id: createdRun.session_id,
    workflow_id: createdRun.workflow_id,
    workflow_version: createdRun.workflow_version,
    status: "clarification",
    selected_agent_ids: ["portfolio_analysis"],
    agent_results: [],
    summary: "Select the saved Portfolio you want me to analyze.",
    warnings: [],
    errors: [],
    required_input: {
      kind: "portfolio_selection",
      agent_id: "portfolio_analysis",
      selection_mode: "one_or_explicit_comparison",
      prompt: "Select the saved Portfolio you want me to analyze.",
    },
    continuation_of_execution_id: null,
    trace_id: null,
    trace_unavailable_reason: null,
  },
};

function renderAssistant() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AssistantExperience sessionId="session-test" />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.listRuns).mockResolvedValue({ items: [] });
  vi.mocked(api.createRun).mockResolvedValue(createdRun);
  vi.mocked(api.continueRun).mockResolvedValue(createdRun);
  vi.mocked(readRunStream).mockResolvedValue([]);
});

test("shows the asked question and formats a safe Markdown response", () => {
  const question = "What's the difference between ETFs and mutual funds?";
  const answer = `**ETFs and mutual funds both pool investors’ money.**

| Feature | ETFs | Mutual funds |
|---|---|---|
| Pricing | Intraday | End of day |

<img src="invalid" onerror="alert('unsafe')">`;
  const run = {
    execution_id: "run-markdown",
    session_id: "session-test",
    workflow_id: "finance-assistant",
    workflow_version: "1",
    status: "completed",
    request_message: question,
    result: {
      schema_version: "1",
      execution_id: "run-markdown",
      session_id: "session-test",
      workflow_id: "finance-assistant",
      workflow_version: "1",
      status: "completed",
      selected_agent_ids: ["finance_qa"],
      agent_results: [
        {
          schema_version: "1",
          agent_id: "finance_qa",
          status: "ok",
          summary: answer,
          facts: [],
          evidence: [],
          visualization: null,
          as_of: null,
          warnings: [],
          errors: [],
        },
      ],
      summary: answer,
      warnings: [],
      errors: [],
      trace_id: null,
      trace_unavailable_reason: null,
    },
    created_at: "2026-10-29T20:38:00Z",
    updated_at: "2026-10-29T20:38:01Z",
  } satisfies RunRecord & { request_message: string };

  const { container } = render(<RunCard isLatest run={run} />);

  const renderedQuestion = screen.queryByText(question);
  const renderedAnswer = screen.queryByText(
    "ETFs and mutual funds both pool investors’ money.",
    { selector: "strong" },
  );
  expect.soft(renderedQuestion?.tagName).toBe("STRONG");
  expect.soft(renderedAnswer).toBeInTheDocument();
  expect
    .soft(
      Boolean(
        renderedQuestion &&
        renderedAnswer &&
        renderedQuestion.compareDocumentPosition(renderedAnswer) &
          Node.DOCUMENT_POSITION_FOLLOWING,
      ),
    )
    .toBe(true);
  expect.soft(screen.queryByRole("table")).toBeInTheDocument();
  expect
    .soft(screen.queryByRole("columnheader", { name: "Feature" }))
    .toBeInTheDocument();
  expect
    .soft(screen.queryByRole("cell", { name: "Intraday" }))
    .toBeInTheDocument();
  expect.soft(container.querySelector("img")).not.toBeInTheDocument();
});

test("does not load or display Portfolio selection before a relevant response", async () => {
  vi.mocked(api.listPortfolios).mockResolvedValue([
    portfolio("portfolio-1", "Retirement portfolio"),
  ]);
  renderAssistant();

  await screen.findByText("What would you like to understand?");
  expect(screen.queryByLabelText("Saved Portfolio")).not.toBeInTheDocument();
  expect(api.listPortfolios).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Message the finance assistant"), {
    target: { value: "How many holdings have usable prices?" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Send message" }));

  await waitFor(() =>
    expect(api.createRun).toHaveBeenCalledWith(
      "session-test",
      "How many holdings have usable prices?",
    ),
  );
});

test("asks for an explicit Portfolio selection after the routed clarification", async () => {
  vi.mocked(api.listRuns).mockResolvedValue({ items: [clarificationRun] });
  vi.mocked(api.listPortfolios).mockResolvedValue([
    portfolio("portfolio-1", "Retirement portfolio"),
  ]);
  renderAssistant();

  const selector = await screen.findByLabelText("Saved Portfolio");
  expect(selector).toHaveValue("");
  fireEvent.change(selector, { target: { value: "portfolio-1" } });
  fireEvent.click(screen.getByRole("button", { name: "Continue analysis" }));

  await waitFor(() =>
    expect(api.continueRun).toHaveBeenCalledWith(
      "session-test",
      "run-portfolio-question",
      ["portfolio-1"],
    ),
  );
});

test("offers an explicit separate comparison when several Portfolios are available", async () => {
  vi.mocked(api.listRuns).mockResolvedValue({ items: [clarificationRun] });
  vi.mocked(api.listPortfolios).mockResolvedValue([
    portfolio("portfolio-1", "Retirement portfolio"),
    portfolio("portfolio-2", "Taxable portfolio"),
  ]);
  renderAssistant();

  const selector = await screen.findByLabelText("Saved Portfolio");
  await screen.findByRole("option", {
    name: "All saved Portfolios — compare separately",
  });
  expect(selector).toHaveValue("");
  fireEvent.change(selector, {
    target: { value: "all:run-portfolio-question" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Continue analysis" }));

  await waitFor(() =>
    expect(api.continueRun).toHaveBeenCalledWith(
      "session-test",
      "run-portfolio-question",
      ["portfolio-1", "portfolio-2"],
    ),
  );
});
