import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { api, readRunStream } from "../../lib/api";
import { TEST_WORKFLOW_ID } from "../../test/config";
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
  workflow_id: TEST_WORKFLOW_ID,
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

const completedPortfolioRun: RunRecord = {
  ...createdRun,
  execution_id: "run-portfolio-completed",
  status: "completed",
  result: {
    schema_version: "1",
    execution_id: "run-portfolio-completed",
    session_id: createdRun.session_id,
    workflow_id: createdRun.workflow_id,
    workflow_version: createdRun.workflow_version,
    status: "completed",
    selected_agent_ids: ["portfolio_analysis"],
    agent_results: [],
    summary: "Portfolio analysis complete.",
    warnings: [],
    errors: [],
    required_input: null,
    continuation_of_execution_id: "run-portfolio-question",
    portfolio_context_references: ["portfolio-1"],
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
    workflow_id: TEST_WORKFLOW_ID,
    workflow_version: "1",
    status: "completed",
    request_message: question,
    result: {
      schema_version: "1",
      execution_id: "run-markdown",
      session_id: "session-test",
      workflow_id: TEST_WORKFLOW_ID,
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

test("shows a combined response while keeping specialist sources and details", () => {
  const run = {
    execution_id: "run-multi-domain",
    session_id: "session-test",
    workflow_id: TEST_WORKFLOW_ID,
    workflow_version: "1",
    status: "completed",
    request_message:
      "How does diversification interact with taxable investing?",
    result: {
      schema_version: "1",
      execution_id: "run-multi-domain",
      session_id: "session-test",
      workflow_id: TEST_WORKFLOW_ID,
      workflow_version: "1",
      status: "completed",
      selected_agent_ids: ["finance_qa", "tax_education"],
      agent_results: [
        {
          schema_version: "1",
          agent_id: "finance_qa",
          status: "ok",
          summary: "Finance specialist explanation.",
          facts: [],
          evidence: [
            {
              evidence_id: "finance-source",
              title: "Diversification basics",
              publisher: "Investor Education Test Publisher",
              canonical_url: "https://example.invalid/diversification",
              source_anchor: null,
            },
          ],
          visualization: null,
          as_of: null,
          warnings: [],
          errors: [],
        },
        {
          schema_version: "1",
          agent_id: "tax_education",
          status: "ok",
          summary: "Tax specialist explanation.",
          facts: [],
          evidence: [],
          visualization: null,
          as_of: null,
          warnings: ["State tax treatment is not covered."],
          errors: [],
        },
      ],
      summary: "Combined finance and tax explanation.",
      warnings: [],
      errors: [],
      required_input: null,
      continuation_of_execution_id: null,
      trace_id: null,
      trace_unavailable_reason: null,
    },
    created_at: "2026-10-31T20:38:00Z",
    updated_at: "2026-10-31T20:38:01Z",
  } satisfies RunRecord & { request_message: string };

  render(<RunCard isLatest run={run} />);

  expect(screen.getByText("Combined response")).toBeInTheDocument();
  expect(
    screen.getByText("Combined finance and tax explanation."),
  ).toBeInTheDocument();
  expect(screen.getByText("finance qa sources and notes")).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: /Diversification basics/ }),
  ).toBeInTheDocument();
  expect(screen.getAllByText("View specialist response")).toHaveLength(2);
  expect(
    screen.getByText("State tax treatment is not covered."),
  ).toBeInTheDocument();
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

test("shows only an import message when a Portfolio question has no saved Portfolio", async () => {
  vi.mocked(api.listRuns).mockResolvedValue({ items: [clarificationRun] });
  vi.mocked(api.listPortfolios).mockResolvedValue([]);
  renderAssistant();

  expect(
    await screen.findByText(
      "No saved Portfolios are available. Import one in the Portfolio view, then ask again.",
    ),
  ).toBeInTheDocument();
  expect(
    screen.queryByText("Select the saved Portfolio you want me to analyze."),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByText("Portfolio selection required"),
  ).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Saved Portfolio")).not.toBeInTheDocument();
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

test("shows active portfolio context and sends an explicit switch with the next question", async () => {
  vi.mocked(api.listRuns).mockResolvedValue({
    items: [completedPortfolioRun],
  });
  vi.mocked(api.listPortfolios).mockResolvedValue([
    portfolio("portfolio-1", "Retirement portfolio"),
    portfolio("portfolio-2", "Taxable portfolio"),
  ]);
  vi.mocked(api.createRun).mockResolvedValue({
    ...completedPortfolioRun,
    execution_id: "run-switched-portfolio",
    result: {
      ...completedPortfolioRun.result!,
      execution_id: "run-switched-portfolio",
      continuation_of_execution_id: null,
      portfolio_context_references: ["portfolio-2"],
    },
  });
  renderAssistant();

  expect(await screen.findByText("Retirement portfolio")).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Change Portfolio" }));
  const dialog = await screen.findByRole("dialog", {
    name: "Change Portfolio",
  });
  expect(
    within(
      screen.getByLabelText("Message the finance assistant").closest("form")!,
    ).queryByLabelText("Portfolio for next portfolio question"),
  ).not.toBeInTheDocument();
  fireEvent.change(
    within(dialog).getByLabelText("Portfolio for next portfolio question"),
    { target: { value: "portfolio-2" } },
  );
  fireEvent.click(
    within(dialog).getByRole("button", { name: "Use selected Portfolio" }),
  );
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Message the finance assistant"), {
    target: { value: "How concentrated is it?" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Send message" }));

  await waitFor(() =>
    expect(api.createRun).toHaveBeenCalledWith(
      "session-test",
      "How concentrated is it?",
      ["portfolio-2"],
    ),
  );
});
