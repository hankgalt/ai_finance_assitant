import { afterEach, expect, test, vi } from "vitest";

const callbacks = vi.hoisted(
  () => new Map<string, (metric: unknown) => void>(),
);

vi.mock("web-vitals", () => ({
  onCLS: (callback: (metric: unknown) => void) =>
    callbacks.set("CLS", callback),
  onFCP: (callback: (metric: unknown) => void) =>
    callbacks.set("FCP", callback),
  onINP: (callback: (metric: unknown) => void) =>
    callbacks.set("INP", callback),
  onLCP: (callback: (metric: unknown) => void) =>
    callbacks.set("LCP", callback),
  onTTFB: (callback: (metric: unknown) => void) =>
    callbacks.set("TTFB", callback),
}));

import { startWebVitals } from "./telemetry";

afterEach(() => {
  callbacks.clear();
  vi.unstubAllGlobals();
});

test("registers the supported Web Vitals and emits only bounded metric fields", async () => {
  const bodies: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_input, init: RequestInit = {}) => {
      bodies.push(String(init.body));
      return { ok: true, status: 204 };
    }),
  );
  startWebVitals();
  expect([...callbacks.keys()].sort()).toEqual([
    "CLS",
    "FCP",
    "INP",
    "LCP",
    "TTFB",
  ]);
  callbacks.get("LCP")?.({
    name: "LCP",
    value: 1210,
    rating: "good",
    entries: ["not exported"],
  });
  await vi.waitFor(() => expect(bodies).toHaveLength(1));
  expect(JSON.parse(bodies[0] ?? "{}")).toEqual({
    schema_version: "1",
    kind: "web_vital",
    page: "shell",
    metric_name: "LCP",
    metric_value: 1210,
    rating: "good",
  });
});
