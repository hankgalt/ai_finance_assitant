import { expect, test } from "vitest";

import type { RunEvent } from "../../types/contracts";
import { buildInspectorModel, formatSequencePositions } from "./inspectorModel";

function event(
  sequence: number,
  nodeId: string,
  overrides: Partial<RunEvent> = {},
): RunEvent {
  return {
    schema_version: "1",
    event_id: `event-${sequence}-${nodeId}`,
    execution_id: "run-1",
    trace_id: "trace-1",
    trace_unavailable_reason: null,
    session_id: "session-1",
    workflow_id: "finance-assistant",
    workflow_version: "1",
    sequence,
    node_id: nodeId,
    agent_id: null,
    tool_call_id: null,
    tool_name: null,
    parent_event_id: null,
    event_type: "node_completed",
    status: "completed",
    started_at: `2026-10-30T10:00:${String(sequence).padStart(2, "0")}Z`,
    completed_at: `2026-10-30T10:00:${String(sequence).padStart(2, "0")}Z`,
    duration_ms: 4,
    duration_unavailable_reason: null,
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
      cost_unavailable_reason: "Model cost is not available.",
      method: null,
      unavailable_reason: "Model usage is not available.",
    },
    retrieval: null,
    summary: `Recorded ${nodeId} event.`,
    safe_metadata: {},
    ...overrides,
  };
}

test("deduplicates and orders recorded events without inventing sequence edges", () => {
  const second = event(2, "finance_qa");
  const model = buildInspectorModel([second, event(0, "workflow"), second]);

  expect(model.events.map((item) => item.sequence)).toEqual([0, 2]);
  expect(model.duplicateCount).toBe(1);
  expect(model.missingSequenceCount).toBe(1);
  expect(model.edges).toEqual([]);
  expect(
    model.nodes.find((node) => node.id === "finance_qa")?.sequences,
  ).toEqual([2]);
});

test("formats only consecutive recorded node positions as ranges", () => {
  expect(formatSequencePositions([12, 7, 8, 10, 8, 11])).toBe("#7–#8, #10–#12");
  expect(formatSequencePositions([1, 27])).toBe("#1, #27");
  expect(formatSequencePositions([])).toBe("No recorded positions");
});

test("creates only edges supported by recorded route or parent relationships", () => {
  const route = event(1, "router", {
    event_type: "route_selected",
    routing: {
      selected_node_ids: ["finance_qa", "unrecorded_agent"],
      outcome: "finance education",
      reason_category: "finance_question",
    },
  });
  const specialist = event(2, "finance_qa", {
    parent_event_id: route.event_id,
  });
  const model = buildInspectorModel([route, specialist]);

  expect(model.nodes.map((node) => node.id)).toEqual(["router", "finance_qa"]);
  expect(model.edges).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        source: "router",
        target: "finance_qa",
        kind: "recorded_route",
      }),
      expect.objectContaining({
        source: "router",
        target: "finance_qa",
        kind: "recorded_parent",
      }),
    ]),
  );
  expect(model.edges.some((edge) => edge.target === "unrecorded_agent")).toBe(
    false,
  );
});

test("isolates one execution and preserves measured failed status", () => {
  const model = buildInspectorModel(
    [
      event(0, "workflow"),
      event(1, "finance_qa", {
        event_type: "node_failed",
        status: "failed",
        error: {
          code: "NO_EVIDENCE",
          category: "no_evidence",
          message: "No evidence was available.",
          retryable: false,
          attempt_count: 1,
          safe_details: {},
        },
      }),
      event(0, "other-workflow", {
        execution_id: "run-2",
        event_id: "run-2-event-0",
        started_at: "2025-01-01T00:00:00Z",
      }),
    ],
    "run-1",
  );

  expect(model.executionId).toBe("run-1");
  expect(model.ignoredCrossExecutionCount).toBe(1);
  expect(model.nodes.find((node) => node.id === "finance_qa")?.status).toBe(
    "failed",
  );
});
