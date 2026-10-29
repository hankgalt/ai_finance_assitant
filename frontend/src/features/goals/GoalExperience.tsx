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

const initialScenarios = [
  {
    label: "Conservative",
    annual_return_rate: "3",
    annual_inflation_rate: "2.5",
    annual_fee_rate: "0.25",
  },
  {
    label: "Expected",
    annual_return_rate: "6",
    annual_inflation_rate: "2.5",
    annual_fee_rate: "0.25",
  },
  {
    label: "Optimistic",
    annual_return_rate: "8",
    annual_inflation_rate: "2.5",
    annual_fee_rate: "0.25",
  },
];

export function GoalExperience({ sessionId }: { sessionId: string }) {
  const [startingAmount, setStartingAmount] = useState("25000");
  const [goalAmount, setGoalAmount] = useState("100000");
  const [contribution, setContribution] = useState("750");
  const [years, setYears] = useState("10");
  const [timing, setTiming] = useState<"beginning" | "end">("end");
  const [risk, setRisk] =
    useState<GoalProjectionRequest["risk_tolerance"]>("moderate");
  const [scenarios, setScenarios] = useState(initialScenarios);
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
      scenarios: scenarios.map((scenario) => ({
        label: scenario.label,
        annual_return_rate: String(Number(scenario.annual_return_rate) / 100),
        annual_inflation_rate: String(
          Number(scenario.annual_inflation_rate) / 100,
        ),
        annual_fee_rate: String(Number(scenario.annual_fee_rate) / 100),
      })),
    });
  };
  const result = projection.data;
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
        description="Compare editable assumptions without treating any scenario as a forecast. Every result is calculated by the versioned backend policy."
        action={<span className="milestone-chip">Monthly contributions</span>}
      />
      <form className="goal-layout" onSubmit={submit}>
        <section className="panel" aria-labelledby="goal-basics-heading">
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
            <label className="field">
              Risk tolerance
              <select
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
            </label>
          </div>
        </section>
        <section className="panel" aria-labelledby="scenario-heading">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Editable assumptions</p>
              <h3 id="scenario-heading">Three scenarios</h3>
            </div>
            <Sparkles aria-hidden="true" />
          </div>
          <div className="scenario-grid">
            {scenarios.map((scenario, index) => (
              <fieldset key={scenario.label}>
                <legend>{scenario.label}</legend>
                <label className="field">
                  Return %
                  <input
                    max="1000"
                    min="-99"
                    required
                    step="0.1"
                    type="number"
                    value={scenario.annual_return_rate}
                    onChange={(event) =>
                      setScenarios(
                        scenarios.map((item, itemIndex) =>
                          itemIndex === index
                            ? {
                                ...item,
                                annual_return_rate: event.target.value,
                              }
                            : item,
                        ),
                      )
                    }
                  />
                </label>
                <label className="field">
                  Inflation %
                  <input
                    max="1000"
                    min="-99"
                    required
                    step="0.1"
                    type="number"
                    value={scenario.annual_inflation_rate}
                    onChange={(event) =>
                      setScenarios(
                        scenarios.map((item, itemIndex) =>
                          itemIndex === index
                            ? {
                                ...item,
                                annual_inflation_rate: event.target.value,
                              }
                            : item,
                        ),
                      )
                    }
                  />
                </label>
                <label className="field">
                  Fee %
                  <input
                    max="100"
                    min="0"
                    required
                    step="0.01"
                    type="number"
                    value={scenario.annual_fee_rate}
                    onChange={(event) =>
                      setScenarios(
                        scenarios.map((item, itemIndex) =>
                          itemIndex === index
                            ? { ...item, annual_fee_rate: event.target.value }
                            : item,
                        ),
                      )
                    }
                  />
                </label>
              </fieldset>
            ))}
          </div>
          <p className="form-help">
            Returns, inflation, and fees are assumptions—not promises or market
            forecasts.
          </p>
          <button
            className="primary-button"
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
            <span>{result.risk_tolerance.replaceAll("_", " ")} tolerance</span>
            <span>{result.currency}</span>
          </div>
          {result.warnings.map((warning) => (
            <StateNotice
              key={warning}
              tone="warning"
              title="Projection limitation"
            >
              {warning}
            </StateNotice>
          ))}
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
                    dataKey="nominal"
                    fill="#1c5c50"
                    isAnimationActive={false}
                    name="Nominal future value"
                  />
                  <Bar
                    dataKey="real"
                    fill="#e4a83a"
                    isAnimationActive={false}
                    name="Inflation-adjusted value"
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
        </section>
      ) : null}
    </>
  );
}
