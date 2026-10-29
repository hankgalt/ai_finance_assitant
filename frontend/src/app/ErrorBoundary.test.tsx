import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ErrorBoundary } from "./ErrorBoundary";

function BrokenView(): never {
  throw new Error("private financial payload must not be emitted");
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("recovers with a safe message and emits only a bounded error category", async () => {
  const bodies: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_input, init: RequestInit = {}) => {
      bodies.push(String(init.body));
      return { ok: true, status: 204 };
    }),
  );
  vi.spyOn(console, "error").mockImplementation(() => undefined);
  render(
    <ErrorBoundary>
      <BrokenView />
    </ErrorBoundary>,
  );
  expect(
    screen.getByRole("heading", { name: "This view could not be displayed" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  await vi.waitFor(() => expect(bodies).toHaveLength(1));
  expect(bodies[0]).toContain('"failure_category":"internal"');
  expect(bodies[0]).not.toContain("private financial payload");
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(
    screen.getByRole("heading", { name: "This view could not be displayed" }),
  ).toBeInTheDocument();
});
