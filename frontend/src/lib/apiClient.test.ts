import { afterEach, expect, test, vi } from "vitest";

import type { PortfolioImportApiRequest } from "../types/contracts";
import { api, ClientApiError, fileToBase64, readRunStream } from "./api";

type Call = { url: string; init: RequestInit };

function stub(
  respond: (url: string) => {
    ok: boolean;
    status: number;
    contentType?: string;
    body?: unknown;
    text?: string;
    jsonError?: boolean;
  },
) {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request, init: RequestInit = {}) => {
      const url = String(input);
      calls.push({ url, init });
      if (url.includes("telemetry/browser"))
        return { ok: true, status: 204, headers: { get: (): null => null } };
      const result = respond(url);
      return {
        ok: result.ok,
        status: result.status,
        headers: { get: () => result.contentType ?? "application/json" },
        json: async () => {
          if (result.jsonError) throw new SyntaxError("not json");
          return result.body;
        },
        text: async () => result.text ?? "",
      };
    }),
  );
  return calls;
}

function productCalls(calls: Call[]) {
  return calls.filter((call) => !call.url.includes("telemetry/browser"));
}

async function telemetryBodies(calls: Call[], count: number) {
  await vi.waitFor(() =>
    expect(
      calls.filter((call) => call.url.includes("telemetry/browser")).length,
    ).toBeGreaterThanOrEqual(count),
  );
  return calls
    .filter((call) => call.url.includes("telemetry/browser"))
    .map(
      (call) => JSON.parse(String(call.init.body)) as Record<string, unknown>,
    );
}

afterEach(() => vi.unstubAllGlobals());

test("maps backend problem responses to typed client errors", async () => {
  stub(() => ({
    ok: false,
    status: 409,
    body: {
      error: { code: "IDEMPOTENCY_CONFLICT", message: "Request conflicts." },
    },
  }));

  const error = await api.getSession("session-1").catch((caught) => caught);

  expect(error).toBeInstanceOf(ClientApiError);
  expect(error).toMatchObject({
    message: "Request conflicts.",
    status: 409,
    code: "IDEMPOTENCY_CONFLICT",
  });
});

test("falls back to a generic message when an error body is not JSON", async () => {
  stub(() => ({ ok: false, status: 502, jsonError: true }));

  await expect(api.listRuns("session-1")).rejects.toMatchObject({
    message: "The request failed with status 502.",
    status: 502,
    code: "HTTP_REQUEST_FAILED",
  });
});

test("reports an unreachable backend without leaking transport details", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request) => {
      if (String(input).includes("telemetry/browser"))
        return { ok: true, status: 204, headers: { get: (): null => null } };
      throw new TypeError("Failed to fetch http://internal-host");
    }),
  );

  await expect(api.health()).rejects.toMatchObject({
    message: "The backend could not be reached.",
    status: null,
    code: "NETWORK_UNAVAILABLE",
  });
});

test("classifies request outcomes into bounded telemetry categories", async () => {
  const statuses = [200, 401, 409, 429, 503, 504, 500, 422];
  let index = 0;
  const calls = stub(() => {
    const status = statuses[index++] ?? 200;
    return { ok: status < 400, status, body: { items: [] } };
  });

  for (let attempt = 0; attempt < statuses.length; attempt += 1)
    await api.listSessions().catch(() => undefined);

  const bodies = await telemetryBodies(calls, statuses.length);
  const summaries = bodies.map((body) => {
    const events = (body.events ?? [body]) as Array<Record<string, unknown>>;
    return events.map((event) => [event.status_class, event.failure_category]);
  });
  expect(summaries.flat()).toEqual([
    ["2xx", "none"],
    ["4xx", "authorization"],
    ["4xx", "conflict"],
    ["4xx", "rate_limited"],
    ["5xx", "not_ready"],
    ["5xx", "timeout"],
    ["5xx", "internal"],
    ["4xx", "validation"],
  ]);
});

test("routes every product call to its versioned resource", async () => {
  const calls = stub((url) => ({
    ok: true,
    status: url.endsWith("/sessions/session-1") ? 204 : 200,
    body: { ok: true },
  }));
  const request = {
    schema_version: "1",
    metadata: {
      portfolio_id: "portfolio-9",
      label: null,
      base_currency: "USD",
      imported_at: "2026-10-30T00:00:00Z",
    },
    payload: { kind: "manual", rows: [] },
  } as unknown as PortfolioImportApiRequest;

  await api.listSessions("archived");
  await api.archiveSession("session-1");
  await api.deleteSession("session-1");
  await api.validatePortfolio("session-1", request);
  await api.savePortfolio("session-1", request);
  await api.listPortfolios("session-1");
  await api.createSnapshot("session-1", "portfolio-9");
  await api.quote("session-1", "VTI", "USD");
  await api.history("session-1", "VTI", "USD", "2026-10-01", "2026-10-30");
  await api.goalProjection("session-1", {
    projection_id: "goal-1",
  } as never);

  const product = productCalls(calls);
  expect(product.map((call) => [call.init.method ?? "GET", call.url])).toEqual([
    ["GET", "/api/v1/sessions?state=archived"],
    ["POST", "/api/v1/sessions/session-1/archive"],
    ["DELETE", "/api/v1/sessions/session-1"],
    ["POST", "/api/v1/sessions/session-1/portfolio-imports/validate"],
    ["POST", "/api/v1/sessions/session-1/portfolios"],
    ["GET", "/api/v1/sessions/session-1/portfolios"],
    ["POST", "/api/v1/sessions/session-1/portfolios/portfolio-9/snapshots"],
    ["POST", "/api/v1/sessions/session-1/market/quotes"],
    ["POST", "/api/v1/sessions/session-1/market/history"],
    ["POST", "/api/v1/sessions/session-1/goal-projections"],
  ]);
  expect(new Headers(product[4]!.init.headers).get("Idempotency-Key")).toBe(
    "portfolio-portfolio-9",
  );
  expect(new Headers(product[3]!.init.headers).has("Idempotency-Key")).toBe(
    false,
  );
  expect(JSON.parse(String(product[6]!.init.body))).toMatchObject({
    security_references: [],
    quote_set: { quotes: [] },
  });
  expect(JSON.parse(String(product[8]!.init.body))).toEqual({
    symbol: "VTI",
    currency: "USD",
    start_date: "2026-10-01",
    end_date: "2026-10-30",
  });
});

test("reads a replayable run stream with Last-Event-ID recovery", async () => {
  const calls = stub(() => ({
    ok: true,
    status: 200,
    contentType: "text/event-stream",
    text: 'id: evt:run-1:5\nevent: run_event\ndata: {"sequence":5}\n\n',
  }));

  const frames = await readRunStream("session-1", "run-1", "evt:run-1:4");
  const fresh = await readRunStream("session-1", "run-1");

  expect(frames).toEqual([
    { id: "evt:run-1:5", event: "run_event", data: { sequence: 5 } },
  ]);
  expect(fresh).toHaveLength(1);
  const [first, second] = productCalls(calls);
  expect(first!.url).toBe("/api/v1/sessions/session-1/runs/run-1/stream");
  expect(new Headers(first!.init.headers).get("Last-Event-ID")).toBe(
    "evt:run-1:4",
  );
  expect(new Headers(second!.init.headers).has("Last-Event-ID")).toBe(false);
  expect(new Headers(first!.init.headers).get("Accept")).toBe(
    "text/event-stream",
  );
});

test("defaults missing SSE fields to an empty run event", async () => {
  const calls = stub(() => ({
    ok: true,
    status: 200,
    contentType: "application/json",
    body: "id: only-id\n\n",
  }));

  await expect(readRunStream("session-1", "run-1")).resolves.toEqual([
    { id: "only-id", event: "run_event", data: {} },
  ]);
  expect(productCalls(calls)).toHaveLength(1);
});

test("encodes uploaded files as base64 in bounded chunks", async () => {
  // jsdom's File lacks arrayBuffer(); supply the one method fileToBase64 reads.
  const fileOf = (bytes: Uint8Array) =>
    ({ arrayBuffer: async () => bytes.buffer }) as unknown as File;
  const large = new Uint8Array(0x8000 + 3).fill(65);

  const encoded = await fileToBase64(fileOf(large));

  expect(atob(encoded)).toBe("A".repeat(0x8000 + 3));
  expect(await fileToBase64(fileOf(new TextEncoder().encode("{}")))).toBe(
    "e30=",
  );
});
