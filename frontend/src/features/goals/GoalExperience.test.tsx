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
import type { GoalProjectionResult } from "../../types/contracts";
import { GoalExperience } from "./GoalExperience";

vi.mock("../../lib/api", () => ({
  api: { goalProjection: vi.fn() },
}));

const result: GoalProjectionResult = {
  schema_version: "1",
  projection_id: "goal-test",
  calculation_policy_version: "goal-projection-v1",
  currency: "USD",
  horizon_months: 120,
  contribution_frequency: "monthly",
  contribution_timing: "end",
  risk_tolerance: "moderate",
  cash_flow_summary_id: null,
  scenarios: [
    {
      label: "Expected",
      nominal_future_value: "165623.40",
      inflation_adjusted_value: "129021.19",
      total_contributions: "115000.00",
      modeled_growth: "50623.40",
      nominal_shortfall_or_surplus: "65623.40",
      contribution_count: 120,
      annual_return_rate: "0.06",
      annual_inflation_rate: "0.025",
      annual_fee_rate: "0.0025",
    },
  ],
  warnings: [
    "Scenarios are user-controlled illustrations, not forecasts or guarantees.",
    "  scenarios are user-controlled illustrations, not forecasts or guarantees.  ",
    "Declared risk tolerance is context only and does not select returns or investments.",
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.goalProjection).mockResolvedValue(result);
});

test("shows unique compact projection limitations after the result visualizations", async () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <GoalExperience sessionId="session-test" />
    </QueryClientProvider>,
  );

  fireEvent.change(screen.getByLabelText("Contribution timing"), {
    target: { value: "beginning" },
  });
  expect(
    screen.getByText(
      "Recorded with the projection, but it does not change return assumptions or select investments.",
    ),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Risk tolerance (context only)"), {
    target: { value: "conservative" },
  });
  const expectedReturn = screen.getByLabelText("Expected annual return");
  expect(expectedReturn).toHaveAttribute("min", "1");
  expect(expectedReturn).toHaveAttribute("max", "9");
  fireEvent.change(expectedReturn, {
    target: { value: "7.5" },
  });
  const derivedRates = screen.getByLabelText("Derived annual return scenarios");
  expect(within(derivedRates).getByText("4.5%")).toBeInTheDocument();
  expect(within(derivedRates).getByText("7.5%")).toBeInTheDocument();
  expect(within(derivedRates).getByText("9.5%")).toBeInTheDocument();
  expect(screen.getAllByLabelText("Annual inflation %")).toHaveLength(1);
  expect(screen.getAllByLabelText("Annual fee %")).toHaveLength(1);
  fireEvent.change(screen.getByLabelText("Annual inflation %"), {
    target: { value: "3" },
  });
  fireEvent.change(screen.getByLabelText("Annual fee %"), {
    target: { value: "0.4" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Compare scenarios" }));

  await waitFor(() =>
    expect(api.goalProjection).toHaveBeenCalledWith(
      "session-test",
      expect.objectContaining({
        contribution_timing: "beginning",
        risk_tolerance: "conservative",
        scenarios: [
          {
            label: "Conservative",
            annual_return_rate: "0.045",
            annual_inflation_rate: "0.03",
            annual_fee_rate: "0.004",
          },
          {
            label: "Expected",
            annual_return_rate: "0.075",
            annual_inflation_rate: "0.03",
            annual_fee_rate: "0.004",
          },
          {
            label: "Optimistic",
            annual_return_rate: "0.095",
            annual_inflation_rate: "0.03",
            annual_fee_rate: "0.004",
          },
        ],
      }),
    ),
  );

  const limitations = await screen.findByRole("complementary", {
    name: "Projection limitations",
  });
  expect(
    screen.getByText("moderate tolerance (context only)"),
  ).toBeInTheDocument();
  expect(within(limitations).getAllByRole("listitem")).toHaveLength(2);
  expect(
    within(limitations).getAllByText(
      "Scenarios are user-controlled illustrations, not forecasts or guarantees.",
    ),
  ).toHaveLength(1);
  expect(
    screen
      .getByRole("table", {
        name: "Backend-calculated scenario outcomes and assumptions",
      })
      .compareDocumentPosition(limitations) & Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy();
});
