import { render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";

import type {
  HoldingValuation,
  PortfolioSnapshot,
  UnrealizedPerformance,
} from "../../types/contracts";
import { PerformanceSection } from "./PerformanceSection";

const limitation =
  "Unrealized price change against imported cost basis only. It excludes dividends.";

function holding(
  holdingId: string,
  overrides: Partial<HoldingValuation> = {},
): HoldingValuation {
  return {
    holding_id: holdingId,
    account_id: "account-1",
    currency: "USD",
    quantity: "10",
    price: "150",
    price_source: "user_import",
    market_value: "1500.00",
    allocation_percent: "50.0000",
    asset_class: "Equity",
    cost_basis_total: null,
    unrealized_gain: null,
    unrealized_return_percent: null,
    acquisition_date: null,
    holding_period_days: null,
    annualized_return_percent: null,
    ...overrides,
  };
}

function summary(
  overrides: Partial<UnrealizedPerformance> = {},
): UnrealizedPerformance {
  return {
    version: "unrealized-performance-v1",
    currency: "USD",
    priced_holding_count: 3,
    holdings_with_cost_basis: 2,
    cost_basis_total: "1600.00",
    market_value_with_cost_basis: "2000.00",
    unrealized_gain: "400.00",
    unrealized_return_percent: "25.0000",
    cost_basis_value_coverage_percent: "80.0000",
    limitation,
    ...overrides,
  };
}

function snapshot(
  holdings: HoldingValuation[],
  performance: UnrealizedPerformance[] | undefined,
): PortfolioSnapshot {
  return {
    schema_version: "1",
    snapshot_id: "snapshot-1",
    portfolio_id: "portfolio-1",
    calculated_at: "2026-10-27T12:00:00Z",
    calculation_policy_version: "finance-calculation-v2",
    quote_set_id: "quotes-1",
    security_reference_ids: [],
    base_currency: "USD",
    base_currency_total: "2500.00",
    totals_by_currency: [],
    holding_valuations: holdings,
    concentrations: [],
    expense_metrics: [],
    diversification: [],
    performance,
    unpriced_holding_ids: [],
    warnings: [],
  };
}

const gain = holding("holding-gain", {
  cost_basis_total: "1000.00",
  unrealized_gain: "500.00",
  unrealized_return_percent: "50.0000",
  acquisition_date: "2024-10-27",
  holding_period_days: 730,
  annualized_return_percent: "22.4745",
});
const loss = holding("holding-loss", {
  market_value: "500.00",
  cost_basis_total: "600.00",
  unrealized_gain: "-100.00",
  unrealized_return_percent: "-16.6667",
  acquisition_date: "2026-04-30",
  holding_period_days: 180,
});
const noCost = holding("holding-no-cost", { market_value: "500.00" });

test("shows signed summary metrics, coverage, limitation, chart, and holding table", () => {
  render(
    <PerformanceSection
      snapshot={snapshot([gain, loss, noCost], [summary()])}
    />,
  );

  expect(
    screen.getByRole("heading", { name: "Unrealized gain and loss" }),
  ).toBeInTheDocument();
  const metrics = screen.getByRole("group", {
    name: "USD unrealized performance",
  });
  expect(within(metrics).getByText("$1,600.00")).toBeInTheDocument();
  expect(within(metrics).getByText("+$400.00")).toHaveClass("value-gain");
  expect(within(metrics).getByText("+25.00%")).toBeInTheDocument();
  expect(within(metrics).getByText("80.00%")).toBeInTheDocument();
  expect(
    within(metrics).getByText("2 of 3 priced holdings"),
  ).toBeInTheDocument();
  expect(screen.getByText(limitation)).toBeInTheDocument();
  expect(
    screen.getByRole("img", {
      name: "Unrealized gain or loss by holding bar chart",
    }),
  ).toBeInTheDocument();

  const table = screen.getByRole("table", {
    name: "Unrealized performance by holding",
  });
  const rows = within(table).getAllByRole("row");
  expect(rows).toHaveLength(3);
  expect(within(rows[1]!).getByText("+$500.00")).toHaveClass("value-gain");
  expect(within(rows[1]!).getByText("730 days")).toBeInTheDocument();
  expect(within(rows[1]!).getByText("+22.47%")).toBeInTheDocument();
  expect(within(rows[2]!).getByText("-$100.00")).toHaveClass("value-loss");
  expect(within(rows[2]!).getByText("-16.67%")).toHaveClass("value-loss");
  expect(
    within(rows[2]!).getByText("Under 1 year or not available"),
  ).toBeInTheDocument();
  expect(within(table).queryByText("holding-no-cost")).not.toBeInTheDocument();
});

test("explains how to add cost basis when none was imported", () => {
  render(
    <PerformanceSection
      snapshot={snapshot(
        [noCost],
        [
          summary({
            holdings_with_cost_basis: 0,
            cost_basis_total: "0.00",
            market_value_with_cost_basis: "0.00",
            unrealized_gain: "0.00",
            unrealized_return_percent: null,
            cost_basis_value_coverage_percent: "0.0000",
          }),
        ],
      )}
    />,
  );

  expect(screen.getByText("No cost basis was imported")).toBeInTheDocument();
  expect(screen.getByText("Not available")).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

test("does not plot gains in different currencies on one axis", () => {
  const euro = holding("holding-euro", {
    currency: "EUR",
    cost_basis_total: "100.00",
    unrealized_gain: "10.00",
    unrealized_return_percent: "10.0000",
  });
  render(
    <PerformanceSection
      snapshot={snapshot(
        [gain, euro],
        [summary(), summary({ currency: "EUR" })],
      )}
    />,
  );

  expect(screen.getByText("Chart not shown")).toBeInTheDocument();
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(
    screen.getByRole("group", { name: "EUR unrealized performance" }),
  ).toBeInTheDocument();
});

test("reports when no holding has both cost basis and a price", () => {
  const unpriced = holding("holding-unpriced", {
    market_value: null,
    price: null,
    price_source: null,
    cost_basis_total: "200.00",
  });
  render(<PerformanceSection snapshot={snapshot([unpriced], [summary()])} />);

  expect(
    screen.getByText("No holding has both a cost basis and a usable price."),
  ).toBeInTheDocument();
});

test("renders nothing for snapshots calculated before performance existed", () => {
  const { container } = render(
    <PerformanceSection snapshot={snapshot([gain], undefined)} />,
  );

  expect(container).toBeEmptyDOMElement();
});
