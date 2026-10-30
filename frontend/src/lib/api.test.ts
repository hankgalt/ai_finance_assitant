import { afterEach, expect, test, vi } from "vitest";

import { api, parseSse } from "./api";

afterEach(() => vi.unstubAllGlobals());

test("propagates W3C and request correlation without putting payloads in telemetry", async () => {
  const calls: Array<{ url: string; init: RequestInit }> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request, init: RequestInit = {}) => {
      calls.push({ url: String(input), init });
      if (String(input).includes("telemetry/browser")) {
        return {
          ok: true,
          status: 204,
          headers: { get: () => "application/json" },
          json: async () => ({}),
        };
      }
      return {
        ok: true,
        status: 201,
        headers: { get: () => "application/json" },
        json: async () => ({
          session_id: "session-1",
          label: "Sensitive label",
          created_at: "",
          updated_at: "",
          expires_at: "",
        }),
      };
    }),
  );

  await api.createSession("Sensitive label");
  await vi.waitFor(() => expect(calls.length).toBeGreaterThan(1));
  const requestHeaders = new Headers(calls[0]?.init.headers);
  const traceparent = requestHeaders.get("traceparent");
  expect(traceparent).toMatch(/^00-[a-f0-9]{32}-[a-f0-9]{16}-01$/);
  expect(requestHeaders.get("X-Request-ID")).toMatch(/^web-/);
  const telemetryBody = String(
    calls.find((call) => call.url.includes("telemetry/browser"))?.init.body,
  );
  const telemetryHeaders = new Headers(
    calls.find((call) => call.url.includes("telemetry/browser"))?.init.headers,
  );
  expect(telemetryHeaders.get("traceparent")?.split("-")[1]).toBe(
    traceparent?.split("-")[1],
  );
  expect(telemetryBody).not.toContain("Sensitive label");
  expect(telemetryBody).toContain("api_timing");
});

test("parses stable SSE ids for reconnect recovery", () => {
  const frames = parseSse(
    'id: evt:run-1:4\nevent: run_event\ndata: {"sequence":4}\n\nid: chunk:run-1:1\nevent: response_chunk\ndata: {"text":"done"}\n\n',
  );
  expect(frames.map((frame) => frame.id)).toEqual([
    "evt:run-1:4",
    "chunk:run-1:1",
  ]);
});

test("telemetry transport failure cannot fail a successful product request", async () => {
  let count = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      count += 1;
      if (count > 1) throw new Error("collector unavailable");
      return {
        ok: true,
        status: 201,
        headers: { get: () => "application/json" },
        json: async () => ({ session_id: "session-1" }),
      };
    }),
  );
  await expect(api.createSession()).resolves.toMatchObject({
    session_id: "session-1",
  });
});

test("deletes a Session-scoped portfolio through the authoritative API", async () => {
  const fetchMock = vi.fn(async () => ({
    ok: true,
    status: 204,
    headers: { get: () => null },
    json: async () => ({}),
  }));
  vi.stubGlobal("fetch", fetchMock);

  await expect(
    api.deletePortfolio("session-1", "portfolio-1"),
  ).resolves.toBeUndefined();

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/v1/sessions/session-1/portfolios/portfolio-1",
    expect.objectContaining({ method: "DELETE" }),
  );
});

test("submits only the explicitly selected contexts to the Run continuation", async () => {
  const fetchMock = vi.fn(
    async (_input: string | URL | Request, init: RequestInit) => {
      void init;
      return {
        ok: true,
        status: 201,
        headers: { get: () => "application/json" },
        json: async () => ({ execution_id: "run-1" }),
      };
    },
  );
  vi.stubGlobal("fetch", fetchMock);

  await api.continueRun("session-1", "run-clarification", [
    "portfolio-1",
    "portfolio-2",
  ]);

  const [url, request] = fetchMock.mock.calls[0]!;
  expect(url).toBe(
    "/api/v1/sessions/session-1/runs/run-clarification/continue",
  );
  expect(JSON.parse(String(request?.body))).toEqual({
    context_references: ["portfolio-1", "portfolio-2"],
  });
});
