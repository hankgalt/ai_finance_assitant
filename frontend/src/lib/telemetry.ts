import { onCLS, onFCP, onINP, onLCP, onTTFB } from "web-vitals";

import type { BrowserTelemetryEvent } from "../types/contracts";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

export type BrowserPage = BrowserTelemetryEvent["page"];

export function emitBrowserTelemetry(
  event: Omit<BrowserTelemetryEvent, "schema_version">,
): void {
  const body: BrowserTelemetryEvent = { schema_version: "1", ...event };
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (event.trace_id) {
    const spanBytes = new Uint8Array(8);
    globalThis.crypto.getRandomValues(spanBytes);
    const spanId = Array.from(spanBytes, (value) =>
      value.toString(16).padStart(2, "0"),
    ).join("");
    headers.traceparent = `00-${event.trace_id}-${spanId}-01`;
  }
  if (event.request_id) headers["X-Request-ID"] = event.request_id;
  void fetch(apiBaseUrl + "/api/v1/telemetry/browser", {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    keepalive: true,
  }).catch(() => undefined);
}

export function recordNavigation(page: BrowserPage): void {
  emitBrowserTelemetry({ kind: "navigation", page });
}

export function startWebVitals(): void {
  const report = (metric: {
    name: "CLS" | "FCP" | "INP" | "LCP" | "TTFB";
    value: number;
    rating: "good" | "needs-improvement" | "poor";
  }) => {
    emitBrowserTelemetry({
      kind: "web_vital",
      page: "shell",
      metric_name: metric.name,
      metric_value: metric.value,
      rating: metric.rating,
    });
  };

  onCLS(report);
  onFCP(report);
  onINP(report);
  onLCP(report);
  onTTFB(report);
}
