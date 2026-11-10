import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { App } from "./App";

const principalId = "principal-local-test";
const scopedStorageKey = `aifa.session.${principalId}`;

type Handler = (
  url: string,
  method: string,
) => ReturnType<typeof response> | undefined;

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

function sessionRecord(sessionId: string, state = "active") {
  return {
    session_id: sessionId,
    label: "Local demo",
    state,
    created_at: "2026-10-29T12:00:00Z",
    updated_at: "2026-10-29T12:00:00Z",
    expires_at: "2026-10-30T12:00:00Z",
    archived_at: state === "archived" ? "2026-10-29T13:00:00Z" : null,
  };
}

function problem(code: string, message: string, status: number) {
  return response(
    {
      error: {
        code,
        category: "internal",
        message,
        retryable: true,
        attempt_count: 1,
        safe_details: {},
      },
    },
    status,
  );
}

function stubFetch(handler: Handler = () => undefined) {
  const requests: Array<{ method: string; url: string }> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request, init: RequestInit = {}) => {
      const url = String(input);
      const method = init.method ?? "GET";
      requests.push({ method, url });
      const handled = handler(url, method);
      if (handled) return handled;
      if (url.endsWith("/api/health")) {
        return response({
          schema_version: "1",
          status: "ok",
          mode: "test",
          liveness: {
            status: "ok",
            service: "AI Finance Assistant API",
            version: "0.1.0",
          },
          readiness: { status: "ready", checks: [] },
        });
      }
      if (url.endsWith("/api/v1/identity"))
        return response({
          principal_id: principalId,
          email: "local-owner@example.invalid",
          role: "owner",
          status: "active",
          identity_mode: "loopback_development",
        });
      if (url.endsWith("/api/v1/sessions") && method === "POST")
        return response(sessionRecord("session-new"), 201);
      if (url.includes("?state=archived")) return response({ items: [] });
      if (url.includes("/runs")) return response({ items: [] });
      if (url.includes("/portfolios")) return response([]);
      if (url.includes("/telemetry/browser")) return response(undefined, 204);
      return response({});
    }),
  );
  return requests;
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

async function ready() {
  await screen.findByRole("heading", { name: "Ask, explore, decide" });
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("navigates to every product view inside the same session", async () => {
  stubFetch();
  renderApp();
  await ready();

  fireEvent.click(screen.getByRole("button", { name: "Portfolio" }));
  expect(
    await screen.findByRole("heading", { name: "Portfolio dashboard" }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Market" }));
  expect(
    await screen.findByRole("heading", { name: "Market overview" }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Goals" }));
  expect(
    await screen.findByRole("heading", { name: "Plan toward a goal" }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "History" }));
  expect(
    await screen.findByRole("heading", { name: "No archived Sessions" }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Assistant" }));
  await ready();
});

test("restores an active stored session instead of creating another", async () => {
  localStorage.setItem("aifa.local-session-id", "session-stored");
  const requests = stubFetch((url, method) =>
    url.endsWith("/api/v1/sessions/session-stored") && method === "GET"
      ? response(sessionRecord("session-stored"))
      : undefined,
  );

  renderApp();
  await ready();

  expect(localStorage.getItem(scopedStorageKey)).toBe("session-stored");
  expect(localStorage.getItem("aifa.local-session-id")).toBeNull();
  expect(requests).not.toContainEqual({
    method: "POST",
    url: "/finance_assistant/api/v1/sessions",
  });
});

test("keeps browser session pointers isolated by Application Principal", async () => {
  localStorage.setItem(scopedStorageKey, "session-owner");
  const viewerPrincipalId = "principal-viewer-test";
  stubFetch((url) =>
    url.endsWith("/api/v1/identity")
      ? response({
          principal_id: viewerPrincipalId,
          email: "viewer@gmail.com",
          role: "viewer",
          status: "active",
          identity_mode: "iap",
        })
      : undefined,
  );

  renderApp();
  await ready();

  expect(localStorage.getItem(scopedStorageKey)).toBe("session-owner");
  expect(localStorage.getItem(`aifa.session.${viewerPrincipalId}`)).toBe(
    "session-new",
  );
});

test("replaces a stored session that was archived elsewhere", async () => {
  localStorage.setItem("aifa.local-session-id", "session-archived");
  stubFetch((url, method) =>
    url.endsWith("/api/v1/sessions/session-archived") && method === "GET"
      ? response(sessionRecord("session-archived", "archived"))
      : undefined,
  );

  renderApp();
  await ready();

  expect(localStorage.getItem(scopedStorageKey)).toBe("session-new");
});

test("replaces a stored session the backend no longer knows", async () => {
  localStorage.setItem("aifa.local-session-id", "session-missing");
  stubFetch((url, method) =>
    url.endsWith("/api/v1/sessions/session-missing") && method === "GET"
      ? problem("SESSION_NOT_FOUND", "Session not found.", 404)
      : undefined,
  );

  renderApp();
  await ready();

  expect(localStorage.getItem(scopedStorageKey)).toBe("session-new");
});

test("keeps the stored session and offers retry when restore fails unexpectedly", async () => {
  localStorage.setItem("aifa.local-session-id", "session-stored");
  let failures = 1;
  stubFetch((url, method) => {
    if (!url.endsWith("/api/v1/sessions/session-stored") || method !== "GET")
      return undefined;
    if (failures > 0) {
      failures -= 1;
      return problem("STORAGE_UNAVAILABLE", "Storage is unavailable.", 503);
    }
    return response(sessionRecord("session-stored"));
  });

  renderApp();

  expect(
    await screen.findByText("A private session could not be opened"),
  ).toBeInTheDocument();
  expect(localStorage.getItem(scopedStorageKey)).toBe("session-stored");
  fireEvent.click(screen.getByRole("button", { name: "Retry session" }));
  await ready();
  expect(localStorage.getItem(scopedStorageKey)).toBe("session-stored");
});

test("toggles the mobile navigation and cancels session clearing", async () => {
  const requests = stubFetch();
  renderApp();
  await ready();

  const toggle = screen.getByRole("button", { name: "Toggle navigation" });
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(toggle);
  expect(toggle).toHaveAttribute("aria-expanded", "true");

  fireEvent.click(screen.getByRole("button", { name: "Clear active session" }));
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

  await waitFor(() =>
    expect(
      screen.queryByRole("button", { name: "Archive and start fresh" }),
    ).not.toBeInTheDocument(),
  );
  expect(requests.some((request) => request.url.endsWith("/archive"))).toBe(
    false,
  );
});

test("shows a retryable history error without hiding the shell", async () => {
  let failures = 1;
  stubFetch((url) => {
    if (!url.includes("?state=archived")) return undefined;
    if (failures > 0) {
      failures -= 1;
      return problem("HISTORY_UNAVAILABLE", "History is unavailable.", 503);
    }
    return response({ items: [] });
  });
  renderApp();
  await ready();

  fireEvent.click(screen.getByRole("button", { name: "History" }));

  expect(
    await screen.findByText("Session history unavailable"),
  ).toBeInTheDocument();
  expect(screen.getByText("History is unavailable.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Retry/ }));
  expect(
    await screen.findByRole("heading", { name: "No archived Sessions" }),
  ).toBeInTheDocument();
});

test("reports an unavailable archived conversation and cancels deletion", async () => {
  stubFetch((url) => {
    if (url.includes("?state=archived"))
      return response({ items: [sessionRecord("session-old", "archived")] });
    if (url.endsWith("/sessions/session-old/runs"))
      return problem("RUNS_UNAVAILABLE", "Runs are unavailable.", 503);
    return undefined;
  });
  renderApp();
  await ready();
  fireEvent.click(screen.getByRole("button", { name: "History" }));

  fireEvent.click(
    await screen.findByRole("button", { name: /View conversation/ }),
  );
  expect(
    await screen.findByText("Conversation unavailable"),
  ).toBeInTheDocument();
  expect(screen.getByText("Runs are unavailable.")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: /^Delete$/ }));
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(
    screen.queryByText("Permanently delete this Session?"),
  ).not.toBeInTheDocument();
});
