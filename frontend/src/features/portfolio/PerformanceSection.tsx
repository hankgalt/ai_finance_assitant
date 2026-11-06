import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { StateNotice } from "../../components/StateNotice";
import { formatCurrency, formatPercent } from "../../lib/format";
import type { PortfolioSnapshot } from "../../types/contracts";

const gainColor = "#1c5c50";
const lossColor = "#a83f35";

function signed(value: string | null | undefined): "gain" | "loss" | "flat" {
  if (value === null || value === undefined) return "flat";
  const numeric = Number(value);
  if (numeric > 0) return "gain";
  if (numeric < 0) return "loss";
  return "flat";
}

function signedCurrency(value: string | null | undefined, currency: string) {
  if (value === null || value === undefined) return "Not available";
  const formatted = formatCurrency(value, currency);
  return signed(value) === "gain" ? `+${formatted}` : formatted;
}

function signedPercent(value: string | null | undefined) {
  if (value === null || value === undefined) return "Not available";
  const formatted = formatPercent(value);
  return signed(value) === "gain" ? `+${formatted}` : formatted;
}

export function PerformanceSection({
  portfolioLabel = null,
  snapshot,
}: {
  portfolioLabel?: string | null;
  snapshot: PortfolioSnapshot;
}) {
  const summaries = snapshot.performance ?? [];
  if (!summaries.length) return null;

  const rows = snapshot.holding_valuations.filter(
    (holding) =>
      holding.cost_basis_total !== null &&
      holding.cost_basis_total !== undefined,
  );
  const chartData = rows
    .filter(
      (holding) =>
        holding.unrealized_gain !== null &&
        holding.unrealized_gain !== undefined,
    )
    .map((holding) => ({
      name: holding.holding_id,
      gain: Number(holding.unrealized_gain),
      currency: holding.currency,
    }));
  const chartCurrencies = new Set(chartData.map((item) => item.currency));
  const chartCurrency = chartData[0]?.currency ?? snapshot.base_currency;
  const hasCostBasis = summaries.some(
    (summary) => summary.holdings_with_cost_basis > 0,
  );

  return (
    <section className="results-section" aria-labelledby="performance-heading">
      <div className="results-heading">
        <div>
          <p className="eyebrow">
            Cost-basis performance
            {portfolioLabel ? ` · ${portfolioLabel}` : ""}
          </p>
          <h3 id="performance-heading">Unrealized gain and loss</h3>
        </div>
        <span className="schema-chip">{summaries[0]!.version}</span>
      </div>
      {summaries.map((summary) => (
        <div
          className="metric-row metric-row-four"
          key={summary.currency}
          aria-label={`${summary.currency} unrealized performance`}
          role="group"
        >
          <div>
            <span>Cost basis</span>
            <strong>
              {formatCurrency(summary.cost_basis_total, summary.currency)}
            </strong>
          </div>
          <div>
            <span>Unrealized gain/loss</span>
            <strong className={`value-${signed(summary.unrealized_gain)}`}>
              {signedCurrency(summary.unrealized_gain, summary.currency)}
            </strong>
          </div>
          <div>
            <span>Return on cost</span>
            <strong
              className={`value-${signed(summary.unrealized_return_percent)}`}
            >
              {signedPercent(summary.unrealized_return_percent)}
            </strong>
          </div>
          <div>
            <span>Cost-basis coverage</span>
            <strong>
              {formatPercent(summary.cost_basis_value_coverage_percent)}
            </strong>
            <small>
              {summary.holdings_with_cost_basis} of{" "}
              {summary.priced_holding_count} priced holdings
            </small>
          </div>
        </div>
      ))}
      <p className="result-context">{summaries[0]!.limitation}</p>
      {!hasCostBasis ? (
        <StateNotice title="No cost basis was imported">
          Add cost basis amount, cost basis basis (total or per unit), and
          acquisition date to the import to see unrealized gain and loss.
        </StateNotice>
      ) : null}
      {rows.length ? (
        <div className="chart-table-layout">
          {chartData.length && chartCurrencies.size === 1 ? (
            <div
              className="chart-frame"
              role="img"
              aria-label="Unrealized gain or loss by holding bar chart"
            >
              <ResponsiveContainer height={280} width="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" hide />
                  <YAxis width={80} />
                  <Tooltip
                    formatter={(value) =>
                      signedCurrency(String(value), chartCurrency)
                    }
                  />
                  <Bar dataKey="gain" isAnimationActive={false}>
                    {chartData.map((item) => (
                      <Cell
                        fill={item.gain < 0 ? lossColor : gainColor}
                        key={item.name}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <StateNotice title="Chart not shown">
              {chartData.length
                ? "Holdings use more than one currency, so gains are listed in the table without a shared chart axis."
                : "No holding has both a cost basis and a usable price."}
            </StateNotice>
          )}
          <div className="table-scroll">
            <table>
              <caption>Unrealized performance by holding</caption>
              <thead>
                <tr>
                  <th scope="col">Holding</th>
                  <th scope="col">Cost basis</th>
                  <th scope="col">Gain/loss</th>
                  <th scope="col">Return on cost</th>
                  <th scope="col">Held</th>
                  <th scope="col">Annualized</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((holding) => (
                  <tr key={holding.holding_id}>
                    <th scope="row">{holding.holding_id}</th>
                    <td>
                      {formatCurrency(
                        holding.cost_basis_total ?? null,
                        holding.currency,
                      )}
                    </td>
                    <td className={`value-${signed(holding.unrealized_gain)}`}>
                      {signedCurrency(
                        holding.unrealized_gain,
                        holding.currency,
                      )}
                    </td>
                    <td
                      className={`value-${signed(holding.unrealized_return_percent)}`}
                    >
                      {signedPercent(holding.unrealized_return_percent)}
                    </td>
                    <td>
                      {holding.holding_period_days === null ||
                      holding.holding_period_days === undefined
                        ? "Not available"
                        : `${holding.holding_period_days.toLocaleString()} days`}
                    </td>
                    <td>
                      {holding.annualized_return_percent
                        ? signedPercent(holding.annualized_return_percent)
                        : "Under 1 year or not available"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
}
