import type {
  ApiErrorResponse,
  GoalProjectionRequest,
  GoalProjectionResult,
  HistoricalResult,
  ImportedPortfolio,
  PortfolioImportApiRequest,
  PortfolioImportResult,
  PortfolioSnapshot,
  QuoteResult,
  RunList,
  RunRecord,
  SessionList,
  SessionRecord,
  SseFrame,
} from "../types/contracts";
import { emitBrowserTelemetry, type BrowserPage } from "./telemetry";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

type ApiRoute =
  | "health"
  | "sessions"
  | "runs"
  | "run_stream"
  | "portfolio_imports"
  | "portfolios"
  | "snapshots"
  | "market_quotes"
  | "market_history"
  | "goals";

export class ClientApiError extends Error {
  constructor(
    message: string,
    public readonly status: number | null,
    public readonly code: string,
  ) {
    super(message);
  }
}

function randomHex(bytes: number): string {
  const values = new Uint8Array(bytes);
  globalThis.crypto.getRandomValues(values);
  return Array.from(values, (value) =>
    value.toString(16).padStart(2, "0"),
  ).join("");
}

function failureCategory(status: number | null): string {
  if (status === null) return "network";
  if (status === 401 || status === 403 || status === 404)
    return "authorization";
  if (status === 409) return "conflict";
  if (status === 429) return "rate_limited";
  if (status === 503) return "not_ready";
  if (status === 408 || status === 504) return "timeout";
  if (status >= 500) return "internal";
  return status >= 400 ? "validation" : "none";
}

function statusClass(
  status: number | null,
): "2xx" | "4xx" | "5xx" | "network_error" {
  if (status === null) return "network_error";
  if (status >= 500) return "5xx";
  if (status >= 400) return "4xx";
  return "2xx";
}

async function apiRequest<T>(
  path: string,
  route: ApiRoute,
  page: BrowserPage,
  init: RequestInit = {},
): Promise<T> {
  const traceId = randomHex(16);
  const requestId = `web-${randomHex(12)}`;
  const startedAt = performance.now();
  let responseStatus: number | null = null;

  try {
    const response = await fetch(apiBaseUrl + path, {
      ...init,
      headers: {
        Accept: "application/json",
        traceparent: `00-${traceId}-${randomHex(8)}-01`,
        "X-Request-ID": requestId,
        ...init.headers,
      },
    });
    responseStatus = response.status;
    if (!response.ok) {
      let problem: ApiErrorResponse | null = null;
      try {
        problem = (await response.json()) as ApiErrorResponse;
      } catch {
        problem = null;
      }
      throw new ClientApiError(
        problem?.error.message ??
          `The request failed with status ${response.status}.`,
        response.status,
        problem?.error.code ?? "HTTP_REQUEST_FAILED",
      );
    }
    if (response.status === 204) return undefined as T;
    const contentType = response.headers?.get("content-type") ?? "";
    if (contentType.includes("text/event-stream"))
      return (await response.text()) as T;
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ClientApiError) throw error;
    throw new ClientApiError(
      "The backend could not be reached.",
      null,
      "NETWORK_UNAVAILABLE",
    );
  } finally {
    emitBrowserTelemetry({
      kind: "api_timing",
      page,
      api_route: route,
      status_class: statusClass(responseStatus),
      failure_category: failureCategory(responseStatus),
      duration_ms: Math.max(0, performance.now() - startedAt),
      trace_id: traceId,
      request_id: requestId,
    });
  }
}

function jsonBody(value: unknown, idempotencyKey?: string): RequestInit {
  return {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
    },
    body: JSON.stringify(value),
  };
}

export const api = {
  health: (signal?: AbortSignal) =>
    apiRequest<import("../types/contracts").HealthSummary>(
      "/api/health",
      "health",
      "shell",
      { signal },
    ),
  createSession: (label = "Local demo") =>
    apiRequest<SessionRecord>(
      "/api/v1/sessions",
      "sessions",
      "shell",
      jsonBody({ label }),
    ),
  getSession: (sessionId: string) =>
    apiRequest<SessionRecord>(
      `/api/v1/sessions/${sessionId}`,
      "sessions",
      "shell",
    ),
  listSessions: (state?: "active" | "archived") =>
    apiRequest<SessionList>(
      `/api/v1/sessions${state ? `?state=${state}` : ""}`,
      "sessions",
      "history",
    ),
  archiveSession: (sessionId: string) =>
    apiRequest<SessionRecord>(
      `/api/v1/sessions/${sessionId}/archive`,
      "sessions",
      "shell",
      jsonBody({}),
    ),
  deleteSession: (sessionId: string) =>
    apiRequest<void>(`/api/v1/sessions/${sessionId}`, "sessions", "shell", {
      method: "DELETE",
    }),
  listRuns: (sessionId: string) =>
    apiRequest<RunList>(
      `/api/v1/sessions/${sessionId}/runs`,
      "runs",
      "assistant",
    ),
  createRun: (sessionId: string, message: string) =>
    apiRequest<RunRecord>(
      `/api/v1/sessions/${sessionId}/runs`,
      "runs",
      "assistant",
      jsonBody({ message }, `run-${randomHex(12)}`),
    ),
  validatePortfolio: (sessionId: string, request: PortfolioImportApiRequest) =>
    apiRequest<PortfolioImportResult>(
      `/api/v1/sessions/${sessionId}/portfolio-imports/validate`,
      "portfolio_imports",
      "portfolio",
      jsonBody(request),
    ),
  savePortfolio: (sessionId: string, request: PortfolioImportApiRequest) =>
    apiRequest<PortfolioImportResult>(
      `/api/v1/sessions/${sessionId}/portfolios`,
      "portfolios",
      "portfolio",
      jsonBody(request, `portfolio-${request.metadata.portfolio_id}`),
    ),
  listPortfolios: (sessionId: string) =>
    apiRequest<ImportedPortfolio[]>(
      `/api/v1/sessions/${sessionId}/portfolios`,
      "portfolios",
      "portfolio",
    ),
  createSnapshot: (sessionId: string, portfolioId: string) =>
    apiRequest<PortfolioSnapshot>(
      `/api/v1/sessions/${sessionId}/portfolios/${portfolioId}/snapshots`,
      "snapshots",
      "portfolio",
      jsonBody({
        security_references: [],
        quote_set: {
          quote_set_id: `imported-prices-${randomHex(8)}`,
          quotes: [],
        },
      }),
    ),
  quote: (sessionId: string, symbol: string, currency: string) =>
    apiRequest<QuoteResult>(
      `/api/v1/sessions/${sessionId}/market/quotes`,
      "market_quotes",
      "market",
      jsonBody({ symbol, currency }),
    ),
  history: (
    sessionId: string,
    symbol: string,
    currency: string,
    start: string,
    end: string,
  ) =>
    apiRequest<HistoricalResult>(
      `/api/v1/sessions/${sessionId}/market/history`,
      "market_history",
      "market",
      jsonBody({ symbol, currency, start_date: start, end_date: end }),
    ),
  goalProjection: (sessionId: string, request: GoalProjectionRequest) =>
    apiRequest<GoalProjectionResult>(
      `/api/v1/sessions/${sessionId}/goal-projections`,
      "goals",
      "goals",
      jsonBody(request),
    ),
};

export async function readRunStream(
  sessionId: string,
  executionId: string,
  lastEventId?: string,
): Promise<SseFrame[]> {
  const path = `/api/v1/sessions/${sessionId}/runs/${executionId}/stream`;
  const text = await apiRequest<string>(path, "run_stream", "assistant", {
    headers: {
      Accept: "text/event-stream",
      ...(lastEventId ? { "Last-Event-ID": lastEventId } : {}),
    },
  });
  return parseSse(typeof text === "string" ? text : "");
}

export function parseSse(text: string): SseFrame[] {
  return text
    .split(/\n\n+/)
    .map((block) => block.trim())
    .filter(Boolean)
    .map((block) => {
      const values = new Map(
        block.split("\n").map((line) => {
          const separator = line.indexOf(":");
          return [line.slice(0, separator), line.slice(separator + 1).trim()];
        }),
      );
      return {
        id: values.get("id") ?? "",
        event: (values.get("event") ?? "run_event") as SseFrame["event"],
        data: JSON.parse(values.get("data") ?? "{}") as SseFrame["data"],
      };
    });
}

export async function fileToBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return btoa(binary);
}
