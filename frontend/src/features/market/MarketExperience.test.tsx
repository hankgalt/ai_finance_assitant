import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { api } from "../../lib/api";
import type {
  HistoricalResult,
  ProviderEnvelope,
  QuoteResult,
} from "../../types/contracts";
import { MarketExperience } from "./MarketExperience";

vi.mock("../../lib/api", () => ({
  api: { quote: vi.fn(), history: vi.fn() },
}));

function provenance(
  overrides: Partial<ProviderEnvelope> = {},
): ProviderEnvelope {
  return {
    provider: "alpha_vantage",
    mode: "live",
    entitlement: "end_of_day",
    served_at: "2026-10-30T21:00:00Z",
    retrieved_at: "2026-10-30T21:00:00Z",
    data_as_of: "2026-10-30T20:00:00Z",
    delay_status: "end_of_day",
    timestamp_quality: "provider_reported",
    cache_status: "provider_fetch",
    cache_layer: "provider",
    cache_coverage: "complete",
    cache_age_seconds: 0,
    is_stale: false,
    is_synthetic: false,
    request_id: "req-1",
    attempts: 1,
    ...overrides,
  };
}

const quote: QuoteResult = {
  status: "success",
  quote: {
    requested_symbol: "VTI",
    resolved_symbol: "VTI",
    price: "301.25",
    currency: "USD",
    currency_source: "request",
  },
  provenance: provenance(),
  error: null,
  warnings: [{ code: "END_OF_DAY", message: "Prices are end-of-day." }],
};

const history: HistoricalResult = {
  status: "success",
  series: {
    requested_symbol: "VTI",
    resolved_symbol: "VTI",
    currency: "USD",
    currency_source: "request",
    adjustment_basis: "adjusted",
    bars: [
      {
        trading_date: "2026-10-29",
        open: "298.00",
        high: "302.00",
        low: "297.50",
        close: "300.10",
        volume: "1200000",
      },
      {
        trading_date: "2026-10-30",
        open: "300.10",
        high: "303.00",
        low: "299.00",
        close: "301.25",
        volume: "1350000",
      },
    ],
  },
  provenance: provenance(),
  error: null,
  warnings: [],
};

function renderMarket() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MarketExperience sessionId="session-test" />
    </QueryClientProvider>,
  );
}

function search(symbol = " vti ", currency = "usd") {
  fireEvent.change(screen.getByLabelText("Symbol"), {
    target: { value: symbol },
  });
  fireEvent.change(screen.getByLabelText("Currency"), {
    target: { value: currency },
  });
  fireEvent.change(screen.getByLabelText("From"), {
    target: { value: "2026-10-01" },
  });
  fireEvent.change(screen.getByLabelText("To"), {
    target: { value: "2026-10-30" },
  });
  fireEvent.click(screen.getByRole("button", { name: /view market data/i }));
}

beforeEach(() => {
  vi.mocked(api.quote).mockReset();
  vi.mocked(api.history).mockReset();
});

test("normalizes the query and shows a quote, provenance, chart, and accessible table", async () => {
  vi.mocked(api.quote).mockResolvedValue(quote);
  vi.mocked(api.history).mockResolvedValue(history);
  renderMarket();

  search();

  expect(
    await screen.findByRole("heading", { name: "$301.25" }),
  ).toBeInTheDocument();
  expect(api.quote).toHaveBeenCalledWith("session-test", "VTI", "USD");
  expect(api.history).toHaveBeenCalledWith(
    "session-test",
    "VTI",
    "USD",
    "2026-10-01",
    "2026-10-30",
  );
  expect(screen.getByText("success")).toBeInTheDocument();
  expect(screen.getByText("Prices are end-of-day.")).toBeInTheDocument();
  expect(
    screen.getByText(/end of day · provider reported/),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "VTI closing price" }),
  ).toBeInTheDocument();
  expect(screen.getByText("adjusted series")).toBeInTheDocument();
  expect(
    screen.getByRole("img", { name: "VTI daily closing price line chart" }),
  ).toBeInTheDocument();
  const table = screen.getByRole("table", {
    name: "Daily provider observations",
  });
  const rows = within(table).getAllByRole("row");
  expect(rows).toHaveLength(3);
  expect(within(rows[2]!).getByText("1,350,000")).toBeInTheDocument();
  expect(
    screen.getAllByRole("region", { name: "Data provenance and freshness" }),
  ).toHaveLength(2);
  expect(screen.getAllByText("provider fetch")).toHaveLength(2);
});

test("labels stale fallback data and synthetic provenance truthfully", async () => {
  vi.mocked(api.quote).mockResolvedValue({
    ...quote,
    provenance: provenance({ is_stale: true, cache_coverage: "stale" }),
  });
  vi.mocked(api.history).mockResolvedValue({
    ...history,
    provenance: provenance({ is_stale: true, is_synthetic: true }),
  });
  renderMarket();

  search();

  expect(await screen.findByText("Stale fallback")).toBeInTheDocument();
  expect(screen.getByText("Showing stale cached history")).toBeInTheDocument();
  expect(screen.getByText("Stale cached data")).toBeInTheDocument();
  expect(screen.getByText("Synthetic demo data")).toBeInTheDocument();
});

test("shows typed provider errors and an empty range without inventing data", async () => {
  vi.mocked(api.quote).mockResolvedValue({
    ...quote,
    status: "rate_limited",
    quote: null,
    error: {
      code: "RATE_LIMITED",
      message: "The provider quota is exhausted.",
      retryable: true,
      retry_after_seconds: 60,
    },
    warnings: [],
  });
  vi.mocked(api.history).mockResolvedValue({
    ...history,
    series: { ...history.series!, bars: [] },
  });
  renderMarket();

  search();

  expect(await screen.findByText("RATE LIMITED")).toBeInTheDocument();
  expect(
    screen.getByText("The provider quota is exhausted."),
  ).toBeInTheDocument();
  expect(screen.getByText("No observations in this range")).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

test("shows history errors when no series is available", async () => {
  vi.mocked(api.quote).mockResolvedValue(quote);
  vi.mocked(api.history).mockResolvedValue({
    ...history,
    status: "unavailable",
    series: null,
    error: {
      code: "PROVIDER_UNAVAILABLE",
      message: "History is unavailable.",
      retryable: true,
      retry_after_seconds: null,
    },
  });
  renderMarket();

  search();

  expect(await screen.findByText("PROVIDER UNAVAILABLE")).toBeInTheDocument();
  expect(screen.getByText("History is unavailable.")).toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: /closing price/ }),
  ).not.toBeInTheDocument();
});

test("reports backend failures without implying saved data changed", async () => {
  vi.mocked(api.quote).mockRejectedValue(new Error("offline"));
  vi.mocked(api.history).mockResolvedValue(history);
  renderMarket();

  search();

  expect(
    await screen.findByText("Market data could not be loaded"),
  ).toBeInTheDocument();
  expect(screen.getByText(/saved product data is/)).toBeInTheDocument();
});
