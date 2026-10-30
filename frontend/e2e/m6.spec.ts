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
  let sessionSequence = 0;
  let archivedSessionIds: string[] = [];
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
    if (path === "/api/v1/sessions" && request.method() === "POST") {
      sessionSequence += 1;
      return json(
        {
          session_id: `session-e2e-${sessionSequence}`,
          label: "Local demo",
          state: "active",
          created_at: now,
          updated_at: now,
          expires_at: "2026-10-30T12:00:00Z",
          archived_at: null,
        },
        201,
      );
    }
    if (
      path === "/api/v1/sessions" &&
      request.method() === "GET" &&
      url.searchParams.get("state") === "archived"
    )
      return json({
        items: archivedSessionIds.map((sessionId) => ({
          session_id: sessionId,
          label: "Local demo",
          state: "archived",
          created_at: now,
          updated_at: now,
          expires_at: "2026-10-30T12:00:00Z",
          archived_at: now,
        })),
      });
    if (
      /^\/api\/v1\/sessions\/session-e2e-\d+\/archive$/.test(path) &&
      request.method() === "POST"
    ) {
      const sessionId = path.split("/").at(-2) ?? "";
      archivedSessionIds = [...archivedSessionIds, sessionId];
      return json({
        session_id: sessionId,
        label: "Local demo",
        state: "archived",
        created_at: now,
        updated_at: now,
        expires_at: "2026-10-30T12:00:00Z",
        archived_at: now,
      });
    }
    if (
      /^\/api\/v1\/sessions\/session-e2e-\d+$/.test(path) &&
      request.method() === "GET"
    )
      return json({
        session_id: path.split("/").at(-1),
        label: "Local demo",
        state: "active",
        created_at: now,
        updated_at: now,
        expires_at: "2026-10-30T12:00:00Z",
        archived_at: null,
      });
    if (
      /^\/api\/v1\/sessions\/session-e2e-\d+$/.test(path) &&
      request.method() === "DELETE"
    ) {
      archivedSessionIds = archivedSessionIds.filter(
        (sessionId) => sessionId !== path.split("/").at(-1),
      );
      return route.fulfill({ status: 204 });
    }
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

test("wraps assistant table cells and keeps every column visible at a narrow viewport", async ({
  page,
}) => {
  const markdown = `**ETFs and mutual funds both pool investors’ money.**

| Feature | ETFs (exchange-traded funds) | Mutual funds |
|---|---|---|
| Buying and selling | Trade on an exchange through a brokerage account | Buy from or redeem with the fund or an intermediary |
| Pricing | Market prices change during the trading day | Transactions use the daily net asset value |`;
  const run = {
    execution_id: "run-wide-table",
    session_id: "session-e2e-1",
    workflow_id: "finance-assistant",
    workflow_version: "1",
    status: "completed",
    request_message: "What's the difference between ETFs and mutual funds?",
    result: {
      schema_version: "1",
      execution_id: "run-wide-table",
      session_id: "session-e2e-1",
      workflow_id: "finance-assistant",
      workflow_version: "1",
      status: "completed",
      selected_agent_ids: ["finance_qa"],
      agent_results: [
        {
          schema_version: "1",
          agent_id: "finance_qa",
          status: "ok",
          summary: markdown,
          facts: [],
          evidence: [],
          visualization: null,
          as_of: now,
          warnings: [],
          errors: [],
        },
      ],
      summary: markdown,
      warnings: [],
      errors: [],
      trace_id: null,
      trace_unavailable_reason: null,
    },
    created_at: now,
    updated_at: now,
  };

  await page.setViewportSize({ width: 390, height: 844 });
  await page.route(
    /\/api\/v1\/sessions\/session-e2e-\d+\/runs$/,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [run] }),
      });
    },
  );
  await page.reload();

  const runCard = page.locator(".run-card");
  await expect(runCard).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();

  const layout = await page.evaluate(() => {
    const card = document.querySelector<HTMLElement>(".run-card");
    const markdownNarrative = document.querySelector<HTMLElement>(
      ".markdown-narrative",
    );
    const table = markdownNarrative?.querySelector<HTMLTableElement>("table");
    const cells = table
      ? [...table.querySelectorAll<HTMLTableCellElement>("th, td")]
      : [];
    if (!card || !markdownNarrative || !table || cells.length === 0)
      throw new Error("Run card was not rendered");
    const cardBounds = card.getBoundingClientRect();
    const tableBounds = table.getBoundingClientRect();
    return {
      documentClientWidth: document.documentElement.clientWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      cardLeft: cardBounds.left,
      cardRight: cardBounds.right,
      tableLeft: tableBounds.left,
      tableRight: tableBounds.right,
      tableClientWidth: table.clientWidth,
      tableScrollWidth: table.scrollWidth,
      narrativeClientWidth: markdownNarrative.clientWidth,
      narrativeScrollWidth: markdownNarrative.scrollWidth,
      cellsStayWithinTable: cells.every((cell) => {
        const bounds = cell.getBoundingClientRect();
        return (
          bounds.left >= tableBounds.left - 1 &&
          bounds.right <= tableBounds.right + 1 &&
          cell.scrollWidth <= cell.clientWidth + 1
        );
      }),
      cellWhiteSpace: getComputedStyle(cells.at(-1)!).whiteSpace,
      cellOverflowWrap: getComputedStyle(cells.at(-1)!).overflowWrap,
    };
  });

  expect(layout.documentScrollWidth).toBeLessThanOrEqual(
    layout.documentClientWidth,
  );
  expect(layout.cardLeft).toBeGreaterThanOrEqual(0);
  expect(layout.cardRight).toBeLessThanOrEqual(layout.documentClientWidth);
  expect(layout.tableLeft).toBeGreaterThanOrEqual(layout.cardLeft);
  expect(layout.tableRight).toBeLessThanOrEqual(layout.cardRight);
  expect(layout.tableScrollWidth).toBeLessThanOrEqual(layout.tableClientWidth);
  expect(layout.narrativeScrollWidth).toBeLessThanOrEqual(
    layout.narrativeClientWidth,
  );
  expect(layout.cellsStayWithinTable).toBe(true);
  expect(layout.cellWhiteSpace).toBe("normal");
  expect(layout.cellOverflowWrap).toBe("anywhere");
});

test("separates Run metadata, citations, and supplemental messages", async ({
  page,
}) => {
  const run = {
    execution_id: "run-spacing",
    session_id: "session-e2e-1",
    workflow_id: "finance-assistant",
    workflow_version: "1",
    status: "completed",
    request_message: null,
    result: {
      schema_version: "1",
      execution_id: "run-spacing",
      session_id: "session-e2e-1",
      workflow_id: "finance-assistant",
      workflow_version: "1",
      status: "completed",
      selected_agent_ids: ["finance_qa"],
      agent_results: [
        {
          schema_version: "1",
          agent_id: "finance_qa",
          status: "partial",
          summary: "ETFs and mutual funds both pool investors’ money.",
          facts: [],
          evidence: [
            {
              evidence_id: "evidence-spacing",
              title: "Fund characteristics",
              publisher: "Investor.gov",
              canonical_url: "https://www.investor.gov/fund-characteristics",
              source_anchor: null,
            },
          ],
          visualization: null,
          as_of: now,
          warnings: ["Additional context is unavailable."],
          errors: [],
        },
      ],
      summary: "ETFs and mutual funds both pool investors’ money.",
      warnings: [],
      errors: [],
      trace_id: null,
      trace_unavailable_reason: null,
    },
    created_at: now,
    updated_at: now,
  };

  await page.route(
    /\/api\/v1\/sessions\/session-e2e-\d+\/runs$/,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [run] }),
      });
    },
  );
  await page.reload();
  await expect(
    page.getByText("Additional context is unavailable."),
  ).toBeVisible();

  const spacing = await page.evaluate(() => {
    const meta = document.querySelector<HTMLElement>(".run-meta");
    const answer = document.querySelector<HTMLElement>(".agent-answer");
    const citations = document.querySelector<HTMLElement>(".citation-list");
    const message = document.querySelector<HTMLElement>(".inline-warning");
    if (!meta || !answer || !citations || !message)
      throw new Error("Run card spacing fixture was not rendered");
    const metaBounds = meta.getBoundingClientRect();
    const answerBounds = answer.getBoundingClientRect();
    const citationBounds = citations.getBoundingClientRect();
    const messageBounds = message.getBoundingClientRect();
    return {
      metaToDivider: answerBounds.top - metaBounds.bottom,
      citationsToMessage: messageBounds.top - citationBounds.bottom,
    };
  });

  expect(spacing.metaToDivider).toBeGreaterThanOrEqual(16);
  expect(spacing.citationsToMessage).toBeGreaterThanOrEqual(24);
});

test("keeps the clear active session action visible beside a long conversation", async ({
  page,
}) => {
  const longSummary = Array.from(
    { length: 40 },
    (_, index) =>
      `Paragraph ${index + 1}. This saved response makes the conversation taller than the viewport.`,
  ).join("\n\n");
  const run = {
    execution_id: "run-long-sidebar",
    session_id: "session-e2e-1",
    workflow_id: "finance-assistant",
    workflow_version: "1",
    status: "completed",
    request_message: "Explain this topic in detail.",
    result: {
      schema_version: "1",
      execution_id: "run-long-sidebar",
      session_id: "session-e2e-1",
      workflow_id: "finance-assistant",
      workflow_version: "1",
      status: "completed",
      selected_agent_ids: [],
      agent_results: [],
      summary: longSummary,
      warnings: [],
      errors: [],
      trace_id: null,
      trace_unavailable_reason: null,
    },
    created_at: now,
    updated_at: now,
  };

  await page.setViewportSize({ width: 1280, height: 720 });
  await page.route(
    /\/api\/v1\/sessions\/session-e2e-\d+\/runs$/,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [run] }),
      });
    },
  );
  await page.reload();

  const clearSession = page.getByRole("button", {
    name: "Clear active session",
  });
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollHeight))
    .toBeGreaterThan(1440);
  await expect(clearSession).toBeInViewport();
  const initialBounds = await clearSession.boundingBox();

  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight / 2));
  await expect
    .poll(() => page.evaluate(() => window.scrollY))
    .toBeGreaterThan(0);
  await expect(clearSession).toBeInViewport();
  const scrolledBounds = await clearSession.boundingBox();

  expect(initialBounds).not.toBeNull();
  expect(scrolledBounds).not.toBeNull();
  expect(Math.abs(scrolledBounds!.y - initialBounds!.y)).toBeLessThanOrEqual(1);
  expect(scrolledBounds!.y + scrolledBounds!.height).toBeLessThanOrEqual(720);
});

test("archives the active session and deletes it only from history", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Clear active session" }).click();
  await expect(
    page.getByText(/Preserve this Session and its saved history/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Archive and start fresh" }),
  ).toBeFocused();
  await capture(page, "../docs/evidence/m6/session-clear-confirmation.png");
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(
    page.getByText(/Preserve this Session and its saved history/),
  ).toHaveCount(0);
  await expect
    .poll(() =>
      page.evaluate(() => localStorage.getItem("aifa.local-session-id")),
    )
    .toBe("session-e2e-1");

  await page.getByRole("button", { name: "Clear active session" }).click();
  await page.getByRole("button", { name: "Archive and start fresh" }).click();

  await expect
    .poll(() =>
      page.evaluate(() => localStorage.getItem("aifa.local-session-id")),
    )
    .toBe("session-e2e-2");
  await expect(
    page.getByRole("heading", { name: "Ask, explore, decide" }),
  ).toBeVisible();
  await expect(
    page.getByText("What would you like to understand?"),
  ).toBeVisible();

  await page.getByRole("button", { name: "History" }).click();
  await expect(
    page.getByRole("heading", { name: "Session history" }),
  ).toBeVisible();
  await expect(page.getByText("Archived Oct 29, 2026")).toBeVisible();
  await capture(page, "../docs/evidence/m6/session-history.png");
  await page.getByRole("button", { name: /^Delete$/ }).click();
  await expect(
    page.getByText("Permanently delete this Session?"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Delete permanently" }).click();
  await expect(
    page.getByRole("heading", { name: "No archived Sessions" }),
  ).toBeVisible();
});
