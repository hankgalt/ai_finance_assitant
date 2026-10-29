import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { App } from "./App";

function response(
  data: unknown,
  status = 200,
  contentType = "application/json",
) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => contentType },
    json: async () => data,
    text: async () => String(data),
  };
}

function successfulFetch() {
  return vi.fn(async (input: string | URL | Request) => {
    const url = String(input);
    if (url.endsWith("/api/health")) {
      return response({
        schema_version: "1",
        status: "degraded",
        mode: "test",
        liveness: {
          status: "ok",
          service: "AI Finance Assistant API",
          version: "0.1.0",
        },
        readiness: { status: "not_ready", checks: [] },
      });
    }
    if (url.endsWith("/api/v1/sessions")) {
      return response(
        {
          session_id: "session-test",
          label: "Local demo",
          created_at: "2026-10-29T12:00:00Z",
          updated_at: "2026-10-29T12:00:00Z",
          expires_at: "2026-10-30T12:00:00Z",
        },
        201,
      );
    }
    if (url.includes("/runs")) return response({ items: [] });
    if (url.includes("/telemetry/browser")) return response(undefined, 204);
    return response({});
  });
}

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal("fetch", successfulFetch());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("renders five accessible navigation destinations and the assistant workflow", async () => {
  renderApp();
  expect(
    await screen.findByRole("heading", { name: "Ask, explore, decide" }),
  ).toBeInTheDocument();
  const navigation = screen.getByRole("navigation", {
    name: "Primary navigation",
  });
  expect(navigation).toBeInTheDocument();
  for (const name of [
    "Assistant",
    "Portfolio",
    "Market",
    "Goals",
    "Inspector",
  ]) {
    expect(screen.getByRole("button", { name })).toBeInTheDocument();
  }
});

test("labels the M7 inspector boundary without implying measured execution", async () => {
  renderApp();
  await screen.findByRole("heading", { name: "Ask, explore, decide" });
  fireEvent.click(screen.getByRole("button", { name: "Inspector" }));
  expect(
    screen.getByRole("heading", { name: "Agent execution inspector" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Scheduled for M7")).toBeInTheDocument();
  expect(
    screen.getByText(/No synthetic execution is shown/),
  ).toBeInTheDocument();
});

test("shows a friendly disconnected health state while preserving the app shell", async () => {
  const fallback = successfulFetch();
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string | URL | Request) => {
      if (String(input).endsWith("/api/health"))
        return Promise.reject(new Error("offline"));
      return fallback(input);
    }),
  );
  renderApp();
  expect(await screen.findByText("Backend disconnected")).toBeInTheDocument();
  expect(
    await screen.findByRole("heading", { name: "Ask, explore, decide" }),
  ).toBeInTheDocument();
});

test("distinguishes the latest assistant response from earlier run history", async () => {
  const fallback = successfulFetch();
  const result = (
    executionId: string,
    status: "failed" | "clarification",
    summary: string,
    createdAt: string,
  ) => ({
    execution_id: executionId,
    session_id: "session-test",
    workflow_id: "finance-assistant",
    workflow_version: "1",
    status,
    result: {
      schema_version: "1",
      execution_id: executionId,
      session_id: "session-test",
      workflow_id: "finance-assistant",
      workflow_version: "1",
      status,
      selected_agent_ids: [],
      agent_results: [],
      summary,
      warnings: [],
      errors: [],
      trace_id: null,
      trace_unavailable_reason: "Trace unavailable in fixture.",
    },
    created_at: createdAt,
    updated_at: createdAt,
  });
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string | URL | Request) => {
      if (String(input).includes("/runs")) {
        return Promise.resolve(
          response({
            items: [
              result(
                "run-latest",
                "failed",
                "No authoritative evidence matched the requested tax year.",
                "2026-10-29T17:42:51Z",
              ),
              result(
                "run-earlier",
                "clarification",
                "Please clarify which finance domain you need.",
                "2026-10-29T17:11:24Z",
              ),
            ],
          }),
        );
      }
      return fallback(input);
    }),
  );

  renderApp();

  expect(await screen.findByText("Latest response")).toBeInTheDocument();
  expect(screen.getByText("Earlier response")).toBeInTheDocument();
});
