import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { App } from "./App";

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
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        schema_version: "1",
        status: "degraded",
        mode: "test",
        liveness: {
          status: "ok",
          service: "AI Finance Assistant API",
          version: "0.1.0",
        },
        readiness: { status: "not_ready", checks: [] },
      }),
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("renders five accessible navigation destinations", () => {
  renderApp();

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
    expect(
      screen.getByRole("button", { name: new RegExp(name) }),
    ).toBeInTheDocument();
  }
});

test("navigates to the inspector and labels synthetic data", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: /Inspector/ }));

  expect(
    screen.getByRole("heading", {
      name: "Agent Execution Inspector",
      level: 2,
    }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/Synthetic fixture · M0 contract preview/),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("list", { name: "Synthetic run events" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Synthetic route selected Finance Q&A."),
  ).toBeInTheDocument();
});

test("shows a friendly disconnected state when the backend is unavailable", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

  renderApp();

  expect(await screen.findByText("Backend disconnected")).toBeInTheDocument();
});
