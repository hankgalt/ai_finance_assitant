import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { api } from "../../lib/api";
import type {
  ImportedHolding,
  ImportedPortfolio,
  PortfolioSnapshot,
} from "../../types/contracts";
import { PortfolioExperience } from "./PortfolioExperience";

vi.mock("../../lib/api", () => ({
  api: {
    createSnapshot: vi.fn(),
    deletePortfolio: vi.fn(),
    listPortfolios: vi.fn(),
    savePortfolio: vi.fn(),
    validatePortfolio: vi.fn(),
  },
  ClientApiError: class ClientApiError extends Error {},
  fileToBase64: vi.fn(),
}));

function holding(holdingId: string): ImportedHolding {
  return {
    holding_id: holdingId,
    account_id: "account-1",
    source_row: 1,
    security: { identifier_type: "ticker", value: holdingId.toUpperCase() },
    quantity: "1",
    currency: "USD",
    asset_class: "Equity",
    user_price: "100",
    user_price_as_of: "2026-10-30T16:00:00Z",
    user_price_provenance: "test fixture",
  };
}

const holdings = [holding("holding-1"), holding("holding-2")];

const portfolio: ImportedPortfolio = {
  schema_version: "1",
  portfolio_id: "portfolio-1",
  label: "Warning fixture",
  base_currency: "USD",
  imported_at: "2026-10-30T16:00:00Z",
  source_kind: "json",
  source_file_hash: "fixture-hash",
  accounts: [
    {
      account_id: "account-1",
      portfolio_id: "portfolio-1",
      account_type: "taxable",
      institution_label: null,
      holdings,
    },
  ],
};

const snapshot: PortfolioSnapshot = {
  schema_version: "1",
  snapshot_id: "snapshot-1",
  portfolio_id: "portfolio-1",
  calculated_at: "2026-10-30T16:01:00Z",
  calculation_policy_version: "finance-calculation-v1",
  quote_set_id: "quote-set-1",
  security_reference_ids: [],
  base_currency: "USD",
  base_currency_total: "200.00",
  totals_by_currency: [
    {
      currency: "USD",
      priced_value: "200.00",
      priced_holding_count: 2,
      total_holding_count: 2,
      holding_count_coverage_percent: "100.00",
    },
  ],
  holding_valuations: holdings.map((item) => ({
    holding_id: item.holding_id,
    account_id: item.account_id,
    currency: item.currency,
    quantity: item.quantity,
    price: item.user_price,
    price_source: "user_import",
    market_value: "100.00",
    allocation_percent: "50.00",
    asset_class: item.asset_class,
  })),
  concentrations: [],
  expense_metrics: [],
  diversification: [],
  unpriced_holding_ids: [],
  warnings: holdings.map((item) => ({
    code: "USER_PRICE_USED",
    message: "The valuation used the preserved user-supplied price.",
    holding_id: item.holding_id,
  })),
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.listPortfolios).mockResolvedValue([portfolio]);
  vi.mocked(api.createSnapshot).mockResolvedValue(snapshot);
  vi.mocked(api.deletePortfolio).mockResolvedValue(undefined);
});

test("keeps saved portfolios primary and opens import in a modal", async () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <PortfolioExperience sessionId="session-test" />
    </QueryClientProvider>,
  );

  expect(
    await screen.findByRole("heading", { name: "Saved portfolios" }),
  ).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Symbol")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Import portfolio" }));

  const dialog = await screen.findByRole("dialog", {
    name: "Import positions",
  });
  expect(within(dialog).getByLabelText("Symbol")).toBeInTheDocument();
  expect(
    within(dialog).getByRole("button", { name: "Validate import" }),
  ).toBeInTheDocument();

  fireEvent.click(
    within(dialog).getByRole("button", { name: "Close portfolio import" }),
  );
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

test("groups equivalent snapshot warnings and reports their holding scope", async () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <PortfolioExperience sessionId="session-test" />
    </QueryClientProvider>,
  );

  fireEvent.click(await screen.findByRole("button", { name: "Analyze" }));

  expect(
    await screen.findByRole("heading", { name: "Allocation and coverage" }),
  ).toBeInTheDocument();
  expect(
    screen.getAllByText("USER PRICE USED", { selector: "strong" }),
  ).toHaveLength(1);
  expect(screen.getByText("Applies to 2 holdings.")).toBeInTheDocument();
});

test("confirms and permanently deletes a saved portfolio", async () => {
  vi.mocked(api.listPortfolios)
    .mockResolvedValueOnce([portfolio])
    .mockResolvedValueOnce([]);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <PortfolioExperience sessionId="session-test" />
    </QueryClientProvider>,
  );

  fireEvent.click(
    await screen.findByRole("button", { name: "Delete Warning fixture" }),
  );
  expect(screen.getByText("Delete Warning fixture?")).toBeInTheDocument();
  expect(
    screen.getByText(/permanently removes the imported Portfolio/),
  ).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.queryByText("Delete Warning fixture?")).not.toBeInTheDocument();

  fireEvent.click(
    screen.getByRole("button", { name: "Delete Warning fixture" }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Delete portfolio" }));

  await waitFor(() =>
    expect(api.deletePortfolio).toHaveBeenCalledWith(
      "session-test",
      "portfolio-1",
    ),
  );
  expect(
    await screen.findByText("Import a portfolio to begin analysis."),
  ).toBeInTheDocument();
  expect(screen.getByText("Portfolio deleted")).toBeInTheDocument();
});
