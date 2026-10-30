import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
          state: "active",
          created_at: "2026-10-29T12:00:00Z",
          updated_at: "2026-10-29T12:00:00Z",
          expires_at: "2026-10-30T12:00:00Z",
          archived_at: null,
        },
        201,
      );
    }
    if (url.includes("/runs")) return response({ items: [] });
    if (url.includes("/portfolios")) return response([]);
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

test("renders accessible navigation destinations and the assistant workflow", async () => {
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
    "History",
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

test("renders each response, source, and supplemental warning once", async () => {
  const fallback = successfulFetch();
  const narrative = Array.from(
    { length: 20 },
    () =>
      "ETFs and mutual funds share features but differ in trading and pricing.",
  ).join(" ");
  const diversificationWarning =
    "Diversification can reduce some investment risks, but both types of funds can lose value.";
  const taxWarning =
    "Tax outcomes depend on the fund and account type; this comparison concerns taxable accounts.";
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string | URL | Request) => {
      if (String(input).includes("/runs")) {
        return Promise.resolve(
          response({
            items: [
              {
                execution_id: "run-long-narrative",
                session_id: "session-test",
                workflow_id: "finance-assistant",
                workflow_version: "1",
                status: "completed",
                result: {
                  schema_version: "1",
                  execution_id: "run-long-narrative",
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
                      summary: narrative,
                      facts: [],
                      evidence: [
                        {
                          evidence_id: "fund-guide-introduction",
                          title: "Mutual Funds and ETFs",
                          publisher: "Investor.gov",
                          canonical_url:
                            "https://www.investor.gov/introduction-investing/investing-basics/investment-products/mutual-funds-and-exchange-traded-funds-etfs",
                          source_anchor: "Introduction",
                        },
                        {
                          evidence_id: "fund-guide-tax",
                          title: "Mutual Funds and ETFs",
                          publisher: "Investor.gov",
                          canonical_url:
                            "https://www.investor.gov/introduction-investing/investing-basics/investment-products/mutual-funds-and-exchange-traded-funds-etfs",
                          source_anchor: "Tax considerations",
                        },
                      ],
                      visualization: null,
                      as_of: null,
                      warnings: [diversificationWarning, taxWarning],
                      errors: [],
                    },
                  ],
                  summary: narrative,
                  warnings: [diversificationWarning, taxWarning],
                  errors: [],
                  trace_id: null,
                  trace_unavailable_reason: null,
                },
                created_at: "2026-10-29T23:03:20Z",
                updated_at: "2026-10-29T23:03:21Z",
              },
            ],
          }),
        );
      }
      return fallback(input);
    }),
  );

  renderApp();

  expect.soft(await screen.findAllByText(narrative)).toHaveLength(1);
  expect
    .soft(
      screen.getAllByRole("link", {
        name: "Mutual Funds and ETFs — Investor.gov",
      }),
    )
    .toHaveLength(1);
  expect.soft(screen.getAllByText(diversificationWarning)).toHaveLength(1);
  expect.soft(screen.getAllByText(taxWarning)).toHaveLength(1);
  expect(
    screen.queryByText("The summary was truncated due to a generation error."),
  ).not.toBeInTheDocument();
});

test("archives the active backend session and opens a fresh local session", async () => {
  const fallback = successfulFetch();
  const requests: Array<{ method: string; url: string }> = [];
  let createdSessions = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string | URL | Request, init: RequestInit = {}) => {
      const url = String(input);
      const method = init.method ?? "GET";
      requests.push({ method, url });
      if (url.endsWith("/api/v1/sessions") && method === "POST") {
        createdSessions += 1;
        return Promise.resolve(
          response(
            {
              session_id: `session-${createdSessions}`,
              label: "Local demo",
              state: "active",
              created_at: "2026-10-29T12:00:00Z",
              updated_at: "2026-10-29T12:00:00Z",
              expires_at: "2026-10-30T12:00:00Z",
              archived_at: null,
            },
            201,
          ),
        );
      }
      if (
        url.endsWith("/api/v1/sessions/session-1/archive") &&
        method === "POST"
      )
        return Promise.resolve(
          response({
            session_id: "session-1",
            label: "Local demo",
            state: "archived",
            created_at: "2026-10-29T12:00:00Z",
            updated_at: "2026-10-29T13:00:00Z",
            expires_at: "2026-10-30T12:00:00Z",
            archived_at: "2026-10-29T13:00:00Z",
          }),
        );
      return fallback(input);
    }),
  );

  renderApp();
  await screen.findByRole("heading", { name: "Ask, explore, decide" });
  expect(localStorage.getItem("aifa.local-session-id")).toBe("session-1");

  fireEvent.click(screen.getByRole("button", { name: "Clear active session" }));
  expect(
    screen.getByText(/Preserve this Session and its saved history/),
  ).toBeInTheDocument();
  fireEvent.click(
    screen.getByRole("button", { name: "Archive and start fresh" }),
  );

  await waitFor(() =>
    expect(localStorage.getItem("aifa.local-session-id")).toBe("session-2"),
  );
  expect(requests).toContainEqual({
    method: "POST",
    url: "/api/v1/sessions/session-1/archive",
  });
  expect(
    await screen.findByRole("heading", { name: "Ask, explore, decide" }),
  ).toBeInTheDocument();
});

test("preserves the active session when backend archiving fails", async () => {
  const fallback = successfulFetch();
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string | URL | Request, init: RequestInit = {}) => {
      if (
        String(input).endsWith("/api/v1/sessions/session-test/archive") &&
        init.method === "POST"
      ) {
        return Promise.resolve(
          response(
            {
              error: {
                code: "SESSION_ARCHIVE_FAILED",
                category: "internal",
                message: "The Session could not be archived safely.",
                retryable: true,
                attempt_count: 1,
                safe_details: {},
              },
            },
            503,
          ),
        );
      }
      return fallback(input);
    }),
  );

  renderApp();
  await screen.findByRole("heading", { name: "Ask, explore, decide" });
  fireEvent.click(screen.getByRole("button", { name: "Clear active session" }));
  fireEvent.click(
    screen.getByRole("button", { name: "Archive and start fresh" }),
  );

  expect(
    await screen.findByText("The Session could not be archived safely."),
  ).toHaveAttribute("role", "alert");
  expect(localStorage.getItem("aifa.local-session-id")).toBe("session-test");
});

test("views and permanently deletes an archived Session from history", async () => {
  const fallback = successfulFetch();
  let archivedExists = true;
  const requests: Array<{ method: string; url: string }> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string | URL | Request, init: RequestInit = {}) => {
      const url = String(input);
      const method = init.method ?? "GET";
      requests.push({ method, url });
      if (url.endsWith("/api/v1/sessions?state=archived")) {
        return Promise.resolve(
          response({
            items: archivedExists
              ? [
                  {
                    session_id: "session-archived",
                    label: "Local demo",
                    state: "archived",
                    created_at: "2026-10-28T12:00:00Z",
                    updated_at: "2026-10-29T12:00:00Z",
                    expires_at: "2026-11-28T12:00:00Z",
                    archived_at: "2026-10-29T12:00:00Z",
                  },
                ]
              : [],
          }),
        );
      }
      if (url.endsWith("/sessions/session-archived/runs"))
        return Promise.resolve(response({ items: [] }));
      if (
        url.endsWith("/api/v1/sessions/session-archived") &&
        method === "DELETE"
      ) {
        archivedExists = false;
        return Promise.resolve(response(undefined, 204));
      }
      return fallback(input);
    }),
  );

  renderApp();
  await screen.findByRole("heading", { name: "Ask, explore, decide" });
  fireEvent.click(screen.getByRole("button", { name: "History" }));

  expect(
    await screen.findByRole("heading", { name: "Session history" }),
  ).toBeInTheDocument();
  fireEvent.click(
    await screen.findByRole("button", { name: /View conversation/ }),
  );
  expect(
    await screen.findByText("This Session has no saved Runs"),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /^Delete$/ }));
  expect(
    screen.getByText("Permanently delete this Session?"),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Delete permanently" }));

  expect(
    await screen.findByRole("heading", { name: "No archived Sessions" }),
  ).toBeInTheDocument();
  expect(requests).toContainEqual({
    method: "DELETE",
    url: "/api/v1/sessions/session-archived",
  });
});

test("preserves an archived Session when permanent deletion fails", async () => {
  const fallback = successfulFetch();
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string | URL | Request, init: RequestInit = {}) => {
      const url = String(input);
      if (url.endsWith("/api/v1/sessions?state=archived")) {
        return Promise.resolve(
          response({
            items: [
              {
                session_id: "session-archived",
                label: "Preserved Session",
                state: "archived",
                created_at: "2026-10-28T12:00:00Z",
                updated_at: "2026-10-29T12:00:00Z",
                expires_at: "2026-11-28T12:00:00Z",
                archived_at: "2026-10-29T12:00:00Z",
              },
            ],
          }),
        );
      }
      if (
        url.endsWith("/api/v1/sessions/session-archived") &&
        init.method === "DELETE"
      ) {
        return Promise.resolve(
          response(
            {
              error: {
                code: "SESSION_DELETE_FAILED",
                category: "internal",
                message: "The archived Session could not be deleted safely.",
                retryable: true,
                attempt_count: 1,
                safe_details: {},
              },
            },
            503,
          ),
        );
      }
      return fallback(input);
    }),
  );

  renderApp();
  await screen.findByRole("heading", { name: "Ask, explore, decide" });
  fireEvent.click(screen.getByRole("button", { name: "History" }));
  await screen.findByText("Preserved Session");
  fireEvent.click(screen.getByRole("button", { name: /^Delete$/ }));
  fireEvent.click(screen.getByRole("button", { name: "Delete permanently" }));

  expect(
    await screen.findByText(
      "The archived Session could not be deleted safely.",
    ),
  ).toHaveAttribute("role", "alert");
  expect(screen.getByText("Preserved Session")).toBeInTheDocument();
  expect(localStorage.getItem("aifa.local-session-id")).toBe("session-test");
});
