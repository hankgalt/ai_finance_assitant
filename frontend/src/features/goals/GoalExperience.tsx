import { useMutation } from "@tanstack/react-query";
import { Calculator, Sparkles } from "lucide-react";
import { useState, type FormEvent } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { PageHeader } from "../../components/PageHeader";
import { StateNotice } from "../../components/StateNotice";
import { api } from "../../lib/api";
import { formatCurrency, formatPercent } from "../../lib/format";
import type { GoalProjectionRequest } from "../../types/contracts";

const minimumExpectedReturn = 1;
const maximumExpectedReturn = 9;
const conservativeOffset = 3;
const optimisticOffset = 2;

function scenarioRates(expectedReturn: number) {
  return [
    {
      label: "Conservative",
      annualReturnRate: Math.max(0, expectedReturn - conservativeOffset),
    },
    { label: "Expected", annualReturnRate: expectedReturn },
    {
      label: "Optimistic",
      annualReturnRate: expectedReturn + optimisticOffset,
    },
  ];
}

function displayRate(rate: number): string {
  return `${Number.isInteger(rate) ? rate.toFixed(0) : rate.toFixed(1)}%`;
}

function decimalRate(percent: number | string): string {
  return String(Number(percent) / 100);
}

function uniqueWarnings(warnings: string[]): string[] {
  const seen = new Set<string>();
  return warnings.flatMap((warning) => {
    const normalized = warning.trim().replaceAll(/\s+/g, " ");
    const key = normalized.toLocaleLowerCase();
    if (!normalized || seen.has(key)) return [];
    seen.add(key);
    return [normalized];
  });
}

export function GoalExperience({ sessionId }: { sessionId: string }) {
  const [startingAmount, setStartingAmount] = useState("25000");
  const [goalAmount, setGoalAmount] = useState("100000");
  const [contribution, setContribution] = useState("750");
  const [years, setYears] = useState("10");
  const [timing, setTiming] = useState<"beginning" | "end">("end");
  const [risk, setRisk] =
    useState<GoalProjectionRequest["risk_tolerance"]>("moderate");
  const [expectedReturn, setExpectedReturn] = useState(6);
  const [inflationRate, setInflationRate] = useState("2.5");
  const [annualFeeRate, setAnnualFeeRate] = useState("0.25");
  const projection = useMutation({
    mutationFn: (request: GoalProjectionRequest) =>
      api.goalProjection(sessionId, request),
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    projection.mutate({
      schema_version: "1",
      projection_id: `goal-${Date.now()}`,
      currency: "USD",
      starting_amount: startingAmount,
      goal_amount: goalAmount || null,
      contribution_amount: contribution,
      contribution_frequency: "monthly",
      contribution_timing: timing,
      horizon_months: Math.round(Number(years) * 12),
      risk_tolerance: risk,
      cash_flow_summary_id: null,
      scenarios: scenarioRates(expectedReturn).map((scenario) => ({
        label: scenario.label,
        annual_return_rate: decimalRate(scenario.annualReturnRate),
        annual_inflation_rate: decimalRate(inflationRate),
        annual_fee_rate: decimalRate(annualFeeRate),
      })),
    });
  };
  const derivedScenarios = scenarioRates(expectedReturn);
  const result = projection.data;
  const warnings = uniqueWarnings(result?.warnings ?? []);
  const chartData =
    result?.scenarios.map((scenario) => ({
      name: scenario.label,
      nominal: Number(scenario.nominal_future_value),
      real: Number(scenario.inflation_adjusted_value),
    })) ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Deterministic scenario modeling"
        title="Plan toward a goal"
        description="Compare editable assumptions without treating any scenario as a forecast."
        action={<span className="milestone-chip">Monthly contributions</span>}
      />
      <form className="goal-layout" onSubmit={submit}>
        <section
          className="panel goal-input-panel"
          aria-labelledby="goal-basics-heading"
        >
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Goal inputs</p>
              <h3 id="goal-basics-heading">Starting point</h3>
            </div>
            <Calculator aria-hidden="true" />
          </div>
          <div className="form-grid">
            <label className="field">
              Starting amount
              <input
                min="0"
                required
                step="any"
                type="number"
                value={startingAmount}
                onChange={(event) => setStartingAmount(event.target.value)}
              />
            </label>
            <label className="field">
              Goal amount
              <input
                min="0"
                step="any"
                type="number"
                value={goalAmount}
                onChange={(event) => setGoalAmount(event.target.value)}
              />
            </label>
            <label className="field">
              Monthly contribution
              <input
                min="0"
                required
                step="any"
                type="number"
                value={contribution}
                onChange={(event) => setContribution(event.target.value)}
              />
            </label>
            <label className="field">
              Years
              <input
                max="100"
                min="1"
                required
                type="number"
                value={years}
                onChange={(event) => setYears(event.target.value)}
              />
            </label>
            <label className="field">
              Contribution timing
              <select
                value={timing}
                onChange={(event) =>
                  setTiming(event.target.value as "beginning" | "end")
                }
              >
                <option value="end">End of month</option>
                <option value="beginning">Beginning of month</option>
              </select>
            </label>
            <div className="field">
              <label htmlFor="goal-risk-tolerance">
                Risk tolerance (context only)
              </label>
              <select
                aria-describedby="goal-risk-tolerance-help"
                id="goal-risk-tolerance"
                value={risk}
                onChange={(event) =>
                  setRisk(
                    event.target
                      .value as GoalProjectionRequest["risk_tolerance"],
                  )
                }
              >
                <option value="not_declared">Not declared</option>
                <option value="conservative">Conservative</option>
                <option value="moderate">Moderate</option>
                <option value="aggressive">Aggressive</option>
              </select>
            </div>
          </div>
          <p
            className="form-help goal-risk-context"
            id="goal-risk-tolerance-help"
          >
            Recorded with the projection, but it does not change return
            assumptions or select investments.
          </p>
        </section>
        <section
          className="panel goal-assumptions-panel"
          aria-labelledby="scenario-heading"
        >
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Editable assumptions</p>
              <h3 id="scenario-heading">Scenario assumptions</h3>
            </div>
            <Sparkles aria-hidden="true" />
          </div>
          <div className="expected-return-control field">
            <label htmlFor="expected-return">Expected annual return</label>
            <div className="rate-slider-row">
              <input
                aria-describedby="expected-return-help"
                aria-valuetext={`${displayRate(expectedReturn)} expected annual return`}
                id="expected-return"
                max={maximumExpectedReturn}
                min={minimumExpectedReturn}
                onChange={(event) =>
                  setExpectedReturn(Number(event.target.value))
                }
                step="0.5"
                type="range"
                value={expectedReturn}
              />
              <output htmlFor="expected-return">
                {displayRate(expectedReturn)}
              </output>
            </div>
            <small className="field-help" id="expected-return-help">
              Select 1%–9%. Conservative is 3 percentage points lower (with a 0%
              floor); optimistic is 2 points higher.
            </small>
          </div>
          <dl
            aria-label="Derived annual return scenarios"
            className="scenario-rate-preview"
          >
            {derivedScenarios.map((scenario) => (
              <div key={scenario.label}>
                <dt>{scenario.label}</dt>
                <dd>{displayRate(scenario.annualReturnRate)}</dd>
              </div>
            ))}
          </dl>
          <div className="form-grid shared-scenario-inputs">
            <label className="field">
              Annual inflation %
              <input
                max="1000"
                min="-99"
                onChange={(event) => setInflationRate(event.target.value)}
                required
                step="0.1"
                type="number"
                value={inflationRate}
              />
            </label>
            <label className="field">
              Annual fee %
              <input
                max="100"
                min="0"
                onChange={(event) => setAnnualFeeRate(event.target.value)}
                required
                step="0.01"
                type="number"
                value={annualFeeRate}
              />
            </label>
          </div>
          <p className="form-help">
            All three scenarios use the shared inflation and fee assumptions.
            These inputs are illustrations—not promises or market forecasts.
          </p>
          <button
            className="primary-button goal-submit"
            disabled={projection.isPending}
            type="submit"
          >
            {projection.isPending ? "Calculating…" : "Compare scenarios"}
          </button>
        </section>
      </form>

      {projection.isError ? (
        <StateNotice tone="error" title="Projection unavailable">
          Check the assumptions and try again. No estimate was created in the
          browser.
        </StateNotice>
      ) : null}
      {result ? (
        <section
          className="results-section"
          aria-labelledby="goal-results-heading"
        >
          <div className="results-heading">
            <div>
              <p className="eyebrow">Backend result</p>
              <h3 id="goal-results-heading">Scenario comparison</h3>
            </div>
            <span className="schema-chip">
              {result.calculation_policy_version}
            </span>
          </div>
          <div className="assumption-strip">
            <span>{result.horizon_months} months</span>
            <span>{result.contribution_timing} contributions</span>
            <span>
              {result.risk_tolerance.replaceAll("_", " ")} tolerance (context
              only)
            </span>
            <span>{result.currency}</span>
          </div>
          <div className="chart-table-stack">
            <div
              className="chart-frame chart-wide"
              role="img"
              aria-label="Nominal and inflation-adjusted goal scenario comparison bar chart"
            >
              <ResponsiveContainer height={320} width="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" />
                  <YAxis width={84} />
                  <Tooltip
                    formatter={(value) =>
                      formatCurrency(Number(value), result.currency)
                    }
                  />
                  <Legend />
                  <Bar
                    dataKey="real"
                    fill="#e4a83a"
                    isAnimationActive={false}
                    name="Inflation-adjusted value"
                  />
                  <Bar
                    dataKey="nominal"
                    fill="#1c5c50"
                    isAnimationActive={false}
                    name="Nominal future value"
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="table-scroll">
              <table>
                <caption>
                  Backend-calculated scenario outcomes and assumptions
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Scenario</th>
                    <th scope="col">Nominal</th>
                    <th scope="col">Inflation adjusted</th>
                    <th scope="col">Contributions</th>
                    <th scope="col">Growth</th>
                    <th scope="col">Assumed return</th>
                  </tr>
                </thead>
                <tbody>
                  {result.scenarios.map((scenario) => (
                    <tr key={scenario.label}>
                      <th scope="row">{scenario.label}</th>
                      <td>
                        {formatCurrency(
                          scenario.nominal_future_value,
                          result.currency,
                        )}
                      </td>
                      <td>
                        {formatCurrency(
                          scenario.inflation_adjusted_value,
                          result.currency,
                        )}
                      </td>
                      <td>
                        {formatCurrency(
                          scenario.total_contributions,
                          result.currency,
                        )}
                      </td>
                      <td>
                        {formatCurrency(
                          scenario.modeled_growth,
                          result.currency,
                        )}
                      </td>
                      <td>
                        {formatPercent(scenario.annual_return_rate, true)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          {warnings.length ? (
            <aside
              aria-label="Projection limitations"
              className="goal-warning-summary"
            >
              <strong>Projection limitations</strong>
              <ul>
                {warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </aside>
          ) : null}
        </section>
      ) : null}
    </>
  );
}
