import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, expect, test, vi } from "vitest";

import type { RunEvent } from "../../types/contracts";
import { api, readRunStream } from "../../lib/api";
import { InspectorExperience } from "./InspectorExperience";

vi.mock("@xyflow/react", () => ({
  MarkerType: { ArrowClosed: "arrowclosed" },
  ReactFlow: ({
    children,
    edges,
    nodes,
  }: {
    children: ReactNode;
    edges: Array<{ id: string }>;
    nodes: Array<{ id: string; data: { label: ReactNode } }>;
  }) => (
    <div data-edge-count={edges.length} data-testid="measured-graph">
      {nodes.map((node) => (
        <div key={node.id}>{node.data.label}</div>
      ))}
      {children}
    </div>
  ),
  Background: () => null,
  Controls: () => null,
}));

vi.mock("../../lib/api", () => ({
  api: {
    listRuns: vi.fn(),
    runEvents: vi.fn(),
  },
  readRunStream: vi.fn(),
}));

function recordedEvent(overrides: Partial<RunEvent> = {}): RunEvent {
  return {
    schema_version: "1",
    event_id: "event-1",
    execution_id: "run-1",
    trace_id: null,
    trace_unavailable_reason: "Tracing was disabled.",
    session_id: "session-1",
    workflow_id: "finance-assistant",
    workflow_version: "1",
    sequence: 1,
    node_id: "finance_qa",
    agent_id: "finance_qa",
    tool_call_id: null,
    tool_name: null,
    parent_event_id: null,
    event_type: "node_completed",
    status: "completed",
    started_at: "2026-10-30T17:00:00Z",
    completed_at: "2026-10-30T17:00:00Z",
    duration_ms: null,
    duration_unavailable_reason: "Clock data was unavailable.",
    routing: null,
    tool_result: null,
    error: null,
    usage: {
      availability: "unavailable",
      input_tokens: null,
      output_tokens: null,
      total_tokens: null,
      cost_amount: null,
      cost_currency: null,
      cost_unavailable_reason: "Provider did not report cost.",
      method: null,
      unavailable_reason: "Provider did not report tokens.",
    },
    retrieval: null,
    summary: "Finance Q&A completed with grounded evidence.",
    safe_metadata: { prompt_version: "finance-qa-v2" },
    ...overrides,
  };
}

function renderInspector() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <InspectorExperience sessionId="session-1" />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.listRuns).mockResolvedValue({
    items: [
      {
        execution_id: "run-1",
        session_id: "session-1",
        workflow_id: "finance-assistant",
        workflow_version: "1",
        status: "completed",
        request_message: "Secret raw prompt that must not render",
        result: null,
        created_at: "2026-10-30T17:00:00Z",
        updated_at: "2026-10-30T17:00:00Z",
      },
    ],
  });
  vi.mocked(api.runEvents).mockResolvedValue({
    execution_id: "run-1",
    events: [recordedEvent()],
    recovery: "Resume with Last-Event-ID.",
  });
  vi.mocked(readRunStream).mockResolvedValue([]);
});

test("renders measured graph, accessible timeline, and unavailable measurements", async () => {
  renderInspector();

  expect(
    await screen.findByRole("heading", { name: "Measured execution graph" }),
  ).toBeInTheDocument();
  expect(screen.getByTestId("measured-graph")).toHaveAttribute(
    "data-edge-count",
    "0",
  );
  expect(screen.getByText("Events #1")).toBeInTheDocument();
  expect(
    screen.getByText(/Ranges contain only consecutive positions/i),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Ordered event timeline" }),
  ).toBeInTheDocument();
  expect(screen.getByText(/duration unavailable/i)).toBeInTheDocument();
  expect(screen.getByText(/Clock data was unavailable/)).toBeInTheDocument();
  expect(screen.getByText("finance-qa-v2")).toBeInTheDocument();
  expect(
    screen.queryByText("Secret raw prompt that must not render"),
  ).not.toBeInTheDocument();
});

test("resumes SSE from the latest persisted event and keeps REST authoritative", async () => {
  renderInspector();
  await screen.findByRole("heading", { name: "Measured execution graph" });
  const resume = await screen.findByRole("button", {
    name: "Resume event stream",
  });
  fireEvent.click(resume);

  await waitFor(() =>
    expect(readRunStream).toHaveBeenCalledWith(
      "session-1",
      "run-1",
      "event-1",
      "inspector",
    ),
  );
  expect(api.runEvents).toHaveBeenCalledTimes(2);
});

test("labels deterministic provider records as synthetic evidence", async () => {
  vi.mocked(api.runEvents).mockResolvedValue({
    execution_id: "run-1",
    events: [
      recordedEvent({
        tool_call_id: "tool-1",
        tool_name: "market_data",
        event_type: "tool_completed",
        tool_result: {
          result_status: "completed",
          provider: "deterministic_fixture",
          record_count: 1,
          freshness: "fixture",
          cache_status: "not_applicable",
          error_reference: null,
        },
      }),
    ],
    recovery: "Resume with Last-Event-ID.",
  });

  renderInspector();
  expect(
    await screen.findByText("Synthetic fixture evidence"),
  ).toBeInTheDocument();
});
