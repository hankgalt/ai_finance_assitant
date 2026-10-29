import { useMutation } from "@tanstack/react-query";
import { RefreshCw, Search } from "lucide-react";
import { useState, type FormEvent } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { PageHeader } from "../../components/PageHeader";
import { ProvenancePanel } from "../../components/ProvenancePanel";
import { StateNotice } from "../../components/StateNotice";
import { api } from "../../lib/api";
import { formatCurrency } from "../../lib/format";

const today = new Date();
const monthAgo = new Date(today);
monthAgo.setDate(today.getDate() - 30);
const dateValue = (value: Date) => value.toISOString().slice(0, 10);

export function MarketExperience({ sessionId }: { sessionId: string }) {
  const [symbol, setSymbol] = useState("DEMO");
  const [currency, setCurrency] = useState("USD");
  const [startDate, setStartDate] = useState(dateValue(monthAgo));
  const [endDate, setEndDate] = useState(dateValue(today));
  const market = useMutation({
    mutationFn: () =>
      Promise.all([
        api.quote(
          sessionId,
          symbol.trim().toUpperCase(),
          currency.toUpperCase(),
        ),
        api.history(
          sessionId,
          symbol.trim().toUpperCase(),
          currency.toUpperCase(),
          startDate,
          endDate,
        ),
      ]),
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    market.mutate();
  };
  const quote = market.data?.[0];
  const history = market.data?.[1];
  const bars = history?.series?.bars ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Provider-backed market evidence"
        title="Market overview"
        description="Inspect a current quote and daily history with the provider, cache layer, freshness, and synthetic status always visible."
        action={
          quote ? (
            <span
              className={`milestone-chip ${quote.provenance.is_stale ? "status-warning" : "status-ready"}`}
            >
              {quote.provenance.is_stale ? "Stale fallback" : quote.status}
            </span>
          ) : undefined
        }
      />
      <section
        className="panel market-search"
        aria-labelledby="market-search-heading"
      >
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Market query</p>
            <h3 id="market-search-heading">Price history</h3>
          </div>
          <Search aria-hidden="true" />
        </div>
        <form className="inline-form" onSubmit={submit}>
          <label className="field">
            Symbol
            <input
              required
              value={symbol}
              onChange={(event) => setSymbol(event.target.value)}
            />
          </label>
          <label className="field">
            Currency
            <input
              maxLength={3}
              required
              value={currency}
              onChange={(event) => setCurrency(event.target.value)}
            />
          </label>
          <label className="field">
            From
            <input
              required
              type="date"
              value={startDate}
              onChange={(event) => setStartDate(event.target.value)}
            />
          </label>
          <label className="field">
            To
            <input
              required
              type="date"
              value={endDate}
              onChange={(event) => setEndDate(event.target.value)}
            />
          </label>
          <button
            className="primary-button"
            disabled={market.isPending}
            type="submit"
          >
            {market.isPending ? (
              <RefreshCw className="spin" size={18} />
            ) : (
              <Search size={18} />
            )}{" "}
            {market.isPending ? "Loading" : "View market data"}
          </button>
        </form>
      </section>

      {market.isError ? (
        <StateNotice tone="error" title="Market data could not be loaded">
          The provider or backend is unavailable. Your saved product data is
          unchanged.
        </StateNotice>
      ) : null}
      {quote?.error ? (
        <StateNotice tone="error" title={quote.error.code.replaceAll("_", " ")}>
          {quote.error.message}
        </StateNotice>
      ) : null}
      {history?.error && !history.series ? (
        <StateNotice
          tone="error"
          title={history.error.code.replaceAll("_", " ")}
        >
          {history.error.message}
        </StateNotice>
      ) : null}
      {quote?.quote ? (
        <section className="market-result" aria-labelledby="quote-heading">
          <div className="quote-hero">
            <div>
              <p className="eyebrow">{quote.quote.resolved_symbol}</p>
              <h3 id="quote-heading">
                {formatCurrency(quote.quote.price, quote.quote.currency)}
              </h3>
              <p>
                {quote.provenance.delay_status.replaceAll("_", " ")} ·{" "}
                {quote.provenance.timestamp_quality.replaceAll("_", " ")}
              </p>
            </div>
            {quote.warnings.map((warning) => (
              <span className="inline-warning" key={warning.code}>
                {warning.message}
              </span>
            ))}
          </div>
          <ProvenancePanel provenance={quote.provenance} />
        </section>
      ) : null}

      {history?.series ? (
        <section className="results-section" aria-labelledby="history-heading">
          <div className="results-heading">
            <div>
              <p className="eyebrow">Daily observations</p>
              <h3 id="history-heading">
                {history.series.resolved_symbol} closing price
              </h3>
            </div>
            <span className="schema-chip">
              {history.series.adjustment_basis} series
            </span>
          </div>
          {history.provenance.is_stale ? (
            <StateNotice tone="warning" title="Showing stale cached history">
              The provider failed, so the last reusable observations are shown
              with their original timestamps.
            </StateNotice>
          ) : null}
          <ProvenancePanel provenance={history.provenance} />
          {bars.length ? (
            <div className="chart-table-stack">
              <div
                className="chart-frame chart-wide"
                role="img"
                aria-label={`${history.series.resolved_symbol} daily closing price line chart`}
              >
                <ResponsiveContainer height={320} width="100%">
                  <LineChart data={bars}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="trading_date" minTickGap={24} />
                    <YAxis domain={["auto", "auto"]} width={70} />
                    <Tooltip
                      formatter={(value) =>
                        formatCurrency(Number(value), history.series?.currency)
                      }
                    />
                    <Line
                      dataKey="close"
                      dot={{ r: 3 }}
                      isAnimationActive={false}
                      stroke="#1c5c50"
                      strokeWidth={2.5}
                      type="monotone"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="table-scroll market-table">
                <table>
                  <caption>Daily provider observations</caption>
                  <thead>
                    <tr>
                      <th scope="col">Date</th>
                      <th scope="col">Open</th>
                      <th scope="col">High</th>
                      <th scope="col">Low</th>
                      <th scope="col">Close</th>
                      <th scope="col">Volume</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bars.map((bar) => (
                      <tr key={bar.trading_date}>
                        <th scope="row">{bar.trading_date}</th>
                        <td>
                          {formatCurrency(bar.open, history.series?.currency)}
                        </td>
                        <td>
                          {formatCurrency(bar.high, history.series?.currency)}
                        </td>
                        <td>
                          {formatCurrency(bar.low, history.series?.currency)}
                        </td>
                        <td>
                          {formatCurrency(bar.close, history.series?.currency)}
                        </td>
                        <td>{Number(bar.volume).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <StateNotice title="No observations in this range" />
          )}
        </section>
      ) : null}
    </>
  );
}
