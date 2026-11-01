import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

const now = "2026-10-30T17:00:00Z";

function usage(measured = false) {
  return measured
    ? {
        availability: "measured",
        input_tokens: 120,
        output_tokens: 48,
        total_tokens: 168,
        cost_amount: null,
        cost_currency: null,
        cost_unavailable_reason: "The provider did not report request cost.",
        method: "provider_usage",
        unavailable_reason: null,
      }
    : {
        availability: "unavailable",
        input_tokens: null,
        output_tokens: null,
        total_tokens: null,
        cost_amount: null,
        cost_currency: null,
        cost_unavailable_reason: "No model request was made.",
        method: null,
        unavailable_reason: "No model usage applies to this event.",
      };
}

function recordedEvent(
  executionId: string,
  sequence: number,
  nodeId: string,
  eventType: string,
  status: string,
  overrides: Record<string, unknown> = {},
) {
  return {
    schema_version: "1",
    event_id: `${executionId}-event-${sequence}`,
    execution_id: executionId,
    trace_id: `trace-${executionId}`,
    trace_unavailable_reason: null,
    session_id: "session-m7-e2e",
    workflow_id: "finance-assistant",
    workflow_version: "1",
    sequence,
    node_id: nodeId,
    agent_id: nodeId.includes("finance") ? "finance_qa" : null,
    tool_call_id: null,
    tool_name: null,
    parent_event_id: sequence ? `${executionId}-event-${sequence - 1}` : null,
    event_type: eventType,
    status,
    started_at: now,
    completed_at: status === "running" ? null : now,
    duration_ms: status === "running" ? null : sequence + 2,
    duration_unavailable_reason:
      status === "running" ? "The event is still running." : null,
    routing: null,
    tool_result: null,
    error: null,
    usage: usage(),
    retrieval: null,
    summary: `Recorded ${eventType.replaceAll("_", " ")}.`,
    safe_metadata: {},
    ...overrides,
  };
}

const runRecords = [
  ["run-success", "completed"],
  ["run-partial", "partial"],
  ["run-failure", "failed"],
].map(([executionId, status]) => ({
  execution_id: executionId,
  session_id: "session-m7-e2e",
  workflow_id: "finance-assistant",
  workflow_version: "1",
  status,
  request_message: "This prompt is intentionally not rendered by Inspector.",
  result: null,
  created_at: now,
  updated_at: now,
}));

const eventsByRun: Record<string, unknown[]> = {
  "run-success": [
    recordedEvent("run-success", 0, "workflow", "run_started", "running", {
      safe_metadata: { fixture_version: "m7-e2e-v1" },
    }),
    recordedEvent("run-success", 1, "router", "route_selected", "completed", {
      routing: {
        selected_node_ids: ["finance_qa"],
        outcome: "finance education",
        reason_category: "finance_question",
      },
    }),
    recordedEvent(
      "run-success",
      2,
      "finance_qa",
      "retrieval_completed",
      "completed",
      {
        retrieval: {
          strategy: "dense",
          sources: [
            {
              logical_kb: "finance_education",
              collection_version: "finance-v1",
              source_id: "investor-gov-funds",
              chunk_id: "funds-001",
              rank: 1,
              score: 0.91,
              score_type: "cosine_similarity",
            },
          ],
        },
      },
    ),
    recordedEvent(
      "run-success",
      3,
      "finance_qa",
      "tool_completed",
      "completed",
      {
        tool_call_id: "tool-retrieval-1",
        tool_name: "finance_retrieval",
        tool_result: {
          result_status: "completed",
          provider: "deterministic_fixture",
          record_count: 1,
          freshness: "versioned",
          cache_status: "not_applicable",
          error_reference: null,
        },
      },
    ),
    recordedEvent(
      "run-success",
      4,
      "finance_qa",
      "model_completed",
      "completed",
      { usage: usage(true) },
    ),
    recordedEvent("run-success", 5, "workflow", "run_completed", "completed"),
  ],
  "run-partial": [
    recordedEvent("run-partial", 0, "workflow", "run_started", "running", {
      safe_metadata: { fixture_version: "m7-e2e-v1" },
    }),
    recordedEvent("run-partial", 1, "router", "route_selected", "completed", {
      routing: {
        selected_node_ids: ["market_analysis"],
        outcome: "market analysis",
        reason_category: "market_question",
      },
    }),
    recordedEvent(
      "run-partial",
      2,
      "market_analysis",
      "node_completed",
      "partial",
    ),
    recordedEvent("run-partial", 3, "workflow", "run_partial", "partial"),
  ],
  "run-failure": [
    recordedEvent("run-failure", 0, "workflow", "run_started", "running", {
      safe_metadata: { fixture_version: "m7-e2e-v1" },
    }),
    recordedEvent("run-failure", 1, "router", "route_selected", "completed", {
      routing: {
        selected_node_ids: ["finance_qa"],
        outcome: "finance education",
        reason_category: "finance_question",
      },
    }),
    recordedEvent("run-failure", 2, "finance_qa", "node_failed", "failed", {
      error: {
        code: "NO_EVIDENCE",
        category: "no_evidence",
        message: "No authoritative evidence was available.",
        retryable: false,
        attempt_count: 1,
        safe_details: {},
      },
    }),
    recordedEvent("run-failure", 3, "workflow", "run_failed", "failed", {
      error: {
        code: "WORKFLOW_FAILED",
        category: "workflow",
        message: "The workflow could not complete.",
        retryable: false,
        attempt_count: 1,
        safe_details: {},
      },
    }),
  ],
};

async function mockM7Api(page: Page) {
  await page.route("**/api/**", async (route: Route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(body),
      });
    if (path === "/api/health")
      return json({
        schema_version: "1",
        status: "ok",
        mode: "test",
        liveness: { status: "ok", service: "API", version: "1" },
        readiness: { status: "ok", checks: [] },
      });
    if (path === "/api/v1/telemetry/browser")
      return route.fulfill({ status: 204 });
    if (path === "/api/v1/sessions" && request.method() === "POST")
      return json(
        {
          session_id: "session-m7-e2e",
          label: "M7 fixture",
          state: "active",
          created_at: now,
          updated_at: now,
          expires_at: "2026-10-31T17:00:00Z",
          archived_at: null,
        },
        201,
      );
    if (path.endsWith("/runs") && request.method() === "GET")
      return json({ items: runRecords });
    const eventMatch = path.match(/\/runs\/(run-[^/]+)\/events$/);
    if (eventMatch)
      return json({
        execution_id: eventMatch[1],
        events: eventsByRun[eventMatch[1]!] ?? [],
        recovery: "Resume with Last-Event-ID, then reload persisted history.",
      });
    if (path.endsWith("/stream"))
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: "",
      });
    return json({});
  });
}

test("Inspector renders recorded success, partial, and failure paths accessibly", async ({
  page,
}) => {
  await mockM7Api(page);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Ask, explore, decide" }),
  ).toBeVisible();
  const inspectorNavigation = page.getByRole("button", { name: "Inspector" });
  await inspectorNavigation.click();
  await expect(inspectorNavigation).toHaveAttribute("aria-current", "page");

  await expect(
    page.getByRole("heading", { name: "Measured execution graph" }),
  ).toBeVisible();
  await expect(
    page.getByText("Synthetic fixture evidence", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Events #0, #5", { exact: true })).toBeVisible();
  await expect(page.getByText("Events #2–#4", { exact: true })).toBeVisible();
  await expect(
    page.getByText("This prompt is intentionally not rendered by Inspector."),
  ).toHaveCount(0);
  if (process.env.AIFA_PLAYWRIGHT_CAPTURE_EVIDENCE !== "false") {
    await page.screenshot({
      path: "../docs/evidence/m7/inspector-success.png",
      fullPage: true,
    });
  }

  const selector = page.getByLabel("Recorded Run");
  await selector.selectOption("run-partial");
  await expect(page.getByText("run partial", { exact: true })).toBeVisible();
  if (process.env.AIFA_PLAYWRIGHT_CAPTURE_EVIDENCE !== "false") {
    await page.screenshot({
      path: "../docs/evidence/m7/inspector-partial.png",
      fullPage: true,
    });
  }

  await selector.selectOption("run-failure");
  await expect(page.getByText("WORKFLOW_FAILED")).toBeVisible();
  await expect(
    page.getByText("The workflow could not complete."),
  ).toBeVisible();
  if (process.env.AIFA_PLAYWRIGHT_CAPTURE_EVIDENCE !== "false") {
    await page.screenshot({
      path: "../docs/evidence/m7/inspector-failure.png",
      fullPage: true,
    });
  }

  const axe = await new AxeBuilder({ page }).analyze();
  expect(
    axe.violations.filter((violation) =>
      ["critical", "serious"].includes(violation.impact ?? ""),
    ),
  ).toEqual([]);
});
