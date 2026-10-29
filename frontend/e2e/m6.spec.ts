import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

const now = "2026-10-29T12:00:00Z";

function provenance() {
  return {
    provider: "deterministic-fixture",
    mode: "credential_free",
    entitlement: "demo",
    served_at: now,
    retrieved_at: now,
    data_as_of: now,
    delay_status: "delayed",
    timestamp_quality: "exact",
    cache_status: "hit",
    cache_layer: "memory",
    cache_coverage: "complete",
    cache_age_seconds: 2,
    is_stale: false,
    is_synthetic: true,
    request_id: "provider-request",
    attempts: 1,
  };
}

function importedPortfolio() {
  return {
    schema_version: "1",
    portfolio_id: "portfolio-demo",
    label: "Demo portfolio",
    base_currency: "USD",
    imported_at: now,
    source_kind: "manual",
    source_file_hash: "a".repeat(64),
    accounts: [
      {
        account_id: "account-1",
        portfolio_id: "portfolio-demo",
        account_type: "taxable",
        institution_label: null,
        holdings: [
          {
            holding_id: "holding-1",
            account_id: "account-1",
            source_row: 1,
            security: { identifier_type: "ticker", value: "DEMO" },
            quantity: "10",
            currency: "USD",
            asset_class: "Equity",
            user_price: "100",
            user_price_as_of: now,
            user_price_provenance: "Manual M6 entry",
          },
        ],
      },
    ],
  };
}

async function mockApi(page: Page) {
  let saved = false;
  await page.route("**/api/**", async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const json = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(body),
      });
    if (path === "/api/health")
      return json({
        schema_version: "1",
        status: "ok",
        mode: "test",
        liveness: { status: "ok", service: "API", version: "1" },
        readiness: { status: "ok", checks: [] },
      });
    if (path === "/api/v1/telemetry/browser")
      return route.fulfill({ status: 204 });
    if (path === "/api/v1/sessions" && request.method() === "POST")
      return json(
        {
          session_id: "session-e2e",
          label: "Local demo",
          created_at: now,
          updated_at: now,
          expires_at: "2026-10-30T12:00:00Z",
        },
        201,
      );
    if (path === "/api/v1/sessions/session-e2e" && request.method() === "GET")
      return json({
        session_id: "session-e2e",
        label: "Local demo",
        created_at: now,
        updated_at: now,
        expires_at: "2026-10-30T12:00:00Z",
      });
    if (path.endsWith("/runs") && request.method() === "GET")
      return json({ items: [] });
    if (path.endsWith("/portfolios") && request.method() === "GET")
      return json(saved ? [importedPortfolio()] : []);
    if (path.endsWith("/portfolio-imports/validate")) {
      const payload = request.postDataJSON() as {
        payload: { rows: Array<{ identifier_value: string }> };
      };
      const accepted = payload.payload.rows[0]?.identifier_value !== "BAD";
      return json({
        schema_version: "1",
        source_kind: "manual",
        source_file_hash: "a".repeat(64),
        accepted,
        portfolio: accepted ? importedPortfolio() : null,
        findings: accepted
          ? []
          : [
              {
                code: "UNKNOWN_IDENTIFIER",
                severity: "error",
                scope: "field",
                message: "Use a supported identifier.",
                row_number: 1,
                field: "identifier_value",
              },
            ],
      });
    }
    if (path.endsWith("/portfolios") && request.method() === "POST") {
      saved = true;
      return json(
        {
          schema_version: "1",
          source_kind: "manual",
          source_file_hash: "a".repeat(64),
          accepted: true,
          portfolio: importedPortfolio(),
          findings: [],
        },
        201,
      );
    }
    if (path.endsWith("/snapshots"))
      return json(
        {
          schema_version: "1",
          snapshot_id: "snapshot-1",
          portfolio_id: "portfolio-demo",
          calculated_at: now,
          calculation_policy_version: "finance-calculation-v1",
          quote_set_id: "imported",
          security_reference_ids: [],
          base_currency: "USD",
          base_currency_total: "1000",
          totals_by_currency: [
            {
              currency: "USD",
              priced_value: "1000",
              priced_holding_count: 1,
              total_holding_count: 1,
              holding_count_coverage_percent: "100",
            },
          ],
          holding_valuations: [
            {
              holding_id: "holding-1",
              account_id: "account-1",
              currency: "USD",
              quantity: "10",
              price: "100",
              price_source: "user_import",
              market_value: "1000",
              allocation_percent: "100",
              asset_class: "Equity",
            },
          ],
          concentrations: [],
          expense_metrics: [],
          diversification: [],
          unpriced_holding_ids: [],
          warnings: [],
        },
        201,
      );
    if (path.endsWith("/market/quotes"))
      return json({
        status: "success",
        quote: {
          requested_symbol: "DEMO",
          resolved_symbol: "DEMO",
          price: "101.25",
          currency: "USD",
          currency_source: "request",
        },
        provenance: provenance(),
        error: null,
        warnings: [],
      });
    if (path.endsWith("/market/history"))
      return json({
        status: "success",
        series: {
          requested_symbol: "DEMO",
          resolved_symbol: "DEMO",
          currency: "USD",
          currency_source: "request",
          adjustment_basis: "raw",
          bars: [
            {
              trading_date: "2026-10-27",
              open: "98",
              high: "101",
              low: "97",
              close: "100",
              volume: "10000",
            },
            {
              trading_date: "2026-10-28",
              open: "100",
              high: "102",
              low: "99",
              close: "101.25",
              volume: "12000",
            },
          ],
        },
        provenance: provenance(),
        error: null,
        warnings: [],
      });
    if (path.endsWith("/goal-projections"))
      return json({
        schema_version: "1",
        projection_id: "goal-1",
        calculation_policy_version: "goal-projection-v1",
        currency: "USD",
        horizon_months: 120,
        contribution_frequency: "monthly",
        contribution_timing: "end",
        risk_tolerance: "moderate",
        cash_flow_summary_id: null,
        scenarios: [
          {
            label: "Conservative",
            nominal_future_value: "140000",
            inflation_adjusted_value: "109000",
            total_contributions: "115000",
            modeled_growth: "25000",
            nominal_shortfall_or_surplus: "40000",
            contribution_count: 120,
            annual_return_rate: "0.03",
            annual_inflation_rate: "0.025",
            annual_fee_rate: "0.0025",
          },
          {
            label: "Expected",
            nominal_future_value: "170000",
            inflation_adjusted_value: "132000",
            total_contributions: "115000",
            modeled_growth: "55000",
            nominal_shortfall_or_surplus: "70000",
            contribution_count: 120,
            annual_return_rate: "0.06",
            annual_inflation_rate: "0.025",
            annual_fee_rate: "0.0025",
          },
          {
            label: "Optimistic",
            nominal_future_value: "195000",
            inflation_adjusted_value: "151000",
            total_contributions: "115000",
            modeled_growth: "80000",
            nominal_shortfall_or_surplus: "95000",
            contribution_count: 120,
            annual_return_rate: "0.08",
            annual_inflation_rate: "0.025",
            annual_fee_rate: "0.0025",
          },
        ],
        warnings: ["Scenario results are estimates, not guarantees."],
      });
    return json(
      {
        error: {
          code: "UNMOCKED",
          category: "internal",
          message: `Unmocked ${path}`,
          retryable: false,
          attempt_count: 1,
          safe_details: {},
        },
      },
      500,
    );
  });
}

async function expectNoSeriousAxeViolations(page: Page) {
  const scan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(
    scan.violations.filter((item) =>
      ["critical", "serious"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
}

async function capture(page: Page, path: string) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path, fullPage: true });
}

test.beforeEach(async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Ask, explore, decide" }),
  ).toBeVisible();
});

test("completes all M6 product workflows with accessible alternatives", async ({
  page,
}) => {
  const csp = await page
    .locator('meta[http-equiv="Content-Security-Policy"]')
    .getAttribute("content");
  expect(csp).toContain("object-src 'none'");
  expect(csp).not.toContain("langsmith");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("main")).toBeFocused();
  await expectNoSeriousAxeViolations(page);
  await capture(page, "../docs/evidence/m6/assistant-empty.png");

  await page.getByRole("button", { name: "Portfolio" }).click();
  await page.getByLabel("Symbol").fill("BAD");
  await page.getByRole("button", { name: "Validate import" }).click();
  await expect(
    page.getByRole("heading", { name: "Corrections required" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Save validated portfolio" }),
  ).toHaveCount(0);
  await page.getByLabel("Symbol").fill("DEMO");
  await page.getByRole("button", { name: "Validate import" }).click();
  await expect(
    page.getByRole("heading", { name: "Ready for your approval" }),
  ).toBeVisible();
  await expectNoSeriousAxeViolations(page);
  await capture(page, "../docs/evidence/m6/portfolio-validation.png");
  await page.getByRole("button", { name: "Save validated portfolio" }).click();
  await expect(page.getByText("1 holding · MANUAL")).toBeVisible();
  await page.getByRole("button", { name: "Analyze" }).click();
  await expect(
    page.getByRole("heading", { name: "Allocation and coverage" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Market" }).click();
  await page.getByRole("button", { name: "View market data" }).click();
  await expect(page.getByRole("heading", { name: "$101.25" })).toBeVisible();
  await expect(page.getByText("Synthetic demo data").first()).toBeVisible();
  await expect(
    page.getByRole("table", { name: "Daily provider observations" }),
  ).toBeVisible();
  await expectNoSeriousAxeViolations(page);
  await capture(page, "../docs/evidence/m6/market-success.png");

  await page.getByRole("button", { name: "Goals" }).click();
  await page.getByRole("button", { name: "Compare scenarios" }).click();
  await expect(
    page.getByRole("heading", { name: "Scenario comparison" }),
  ).toBeVisible();
  await expect(
    page.getByRole("table", {
      name: "Backend-calculated scenario outcomes and assumptions",
    }),
  ).toBeVisible();
  await expectNoSeriousAxeViolations(page);
  await capture(page, "../docs/evidence/m6/goals-success.png");
});

test("keeps navigation and core content usable at a narrow viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await page.getByRole("button", { name: "Toggle navigation" }).click();
  await expect(
    page.getByRole("navigation", { name: "Primary navigation" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Market" }).click();
  await expect(
    page.getByRole("heading", { name: "Market overview" }),
  ).toBeVisible();
  await page.route("**/market/history", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "unavailable",
        series: {
          requested_symbol: "DEMO",
          resolved_symbol: "DEMO",
          currency: "USD",
          currency_source: "request",
          adjustment_basis: "raw",
          bars: [
            {
              trading_date: "2026-10-28",
              open: "100",
              high: "102",
              low: "99",
              close: "101.25",
              volume: "12000",
            },
          ],
        },
        provenance: {
          ...provenance(),
          cache_status: "stale",
          cache_layer: "durable",
          cache_coverage: "stale",
          cache_age_seconds: 86400,
          is_stale: true,
        },
        error: {
          code: "UNAVAILABLE",
          message: "Provider unavailable; cached observations retained.",
          retryable: true,
          retry_after_seconds: null,
        },
        warnings: [],
      }),
    });
  });
  await page.getByRole("button", { name: "View market data" }).click();
  await expect(page.getByText("Showing stale cached history")).toBeVisible();
  await capture(page, "../docs/evidence/m6/mobile-market.png");
});
