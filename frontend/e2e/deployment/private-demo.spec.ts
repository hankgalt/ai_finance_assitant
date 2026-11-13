import AxeBuilder from "@axe-core/playwright";
import {
  expect,
  test,
  type APIRequestContext,
  type APIResponse,
  type Page,
} from "@playwright/test";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const targetPath = "/finance_assistant/";
const apiRoot = "/finance_assistant/api";
const ownerEmail = "vtalwar.w@comfforts.com";
const enabled = process.env.AIFA_RUN_DEPLOYED_QUALIFICATION === "true";
const revision = process.env.AIFA_DEPLOYMENT_REVISION ?? "";
const evidencePath = process.env.AIFA_DEPLOYMENT_EVIDENCE_TEMP ?? "";
const priorEvidencePath = process.env.AIFA_PRIOR_EVIDENCE_FILE ?? "";
const portfolioFixture = fileURLToPath(
  new URL(
    "../../../backend/data/calculations/portfolio-import.valid.v1.json",
    import.meta.url,
  ),
);

type JsonObject = Record<string, unknown>;

interface PrincipalView {
  principal_id: string;
  email: string;
  role: string;
  status: string;
  identity_mode: string;
}

interface DependencyCheck {
  name: string;
  status: string;
  expected: JsonObject;
}

interface HealthSummary {
  status: string;
  readiness: { status: string; checks: DependencyCheck[] };
}

interface SessionRecord {
  session_id: string;
  state: "active" | "archived";
}

interface RunResult {
  status: string;
  summary: string;
  agent_results: Array<{ evidence: unknown[] }>;
}

interface RunRecord {
  execution_id: string;
  request_message: string | null;
  status: string;
  result: RunResult | null;
}

interface RunList {
  items: RunRecord[];
}

interface RunEvent {
  event_id: string;
  sequence: number;
}

interface RunEventHistory {
  events: RunEvent[];
}

interface ImportedPortfolio {
  portfolio_id: string;
  label: string | null;
}

interface PortfolioSnapshot {
  snapshot_id: string;
}

interface PriorEvidence {
  path: string;
  sha256: string;
}

test.skip(
  !enabled,
  "Run only through make qualify-private-demo after the reviewed operator preflight.",
);

function apiPath(path: string): string {
  return `${apiRoot}${path}`;
}

async function jsonResponse<T>(
  response: APIResponse,
  label: string,
): Promise<T> {
  expect(
    response.ok(),
    `${label}: ${response.status()} ${await response.text()}`,
  ).toBeTruthy();
  return (await response.json()) as T;
}

async function expectNoSeriousAxeViolations(page: Page): Promise<void> {
  const scan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(
    scan.violations.filter((item) =>
      ["critical", "serious"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
}

async function storedSessionId(
  page: Page,
  principalId: string,
): Promise<string | null> {
  return page.evaluate(({ key }) => window.localStorage.getItem(key), {
    key: `aifa.session.${principalId}`,
  });
}

async function cleanupSession(
  request: APIRequestContext,
  sessionId: string,
): Promise<boolean> {
  const current = await request.get(apiPath(`/v1/sessions/${sessionId}`));
  if (current.status() === 404) return true;
  if (!current.ok()) return false;
  const session = (await current.json()) as SessionRecord;
  if (session.state === "active") {
    const archived = await request.post(
      apiPath(`/v1/sessions/${sessionId}/archive`),
      {
        data: {},
      },
    );
    if (!archived.ok()) return false;
  }
  const deleted = await request.delete(apiPath(`/v1/sessions/${sessionId}`));
  return deleted.status() === 204 || deleted.status() === 404;
}

test("qualifies the assembled credential-free private demo", async ({
  page,
  context,
}) => {
  expect(revision).toMatch(/^[0-9a-f]{40}$/);
  expect(evidencePath).not.toBe("");
  expect(priorEvidencePath).not.toBe("");
  const priorEvidence = JSON.parse(
    readFileSync(priorEvidencePath, "utf8"),
  ) as PriorEvidence[];
  expect(priorEvidence).toHaveLength(5);

  console.log(
    `Complete Google/IAP sign-in as ${ownerEmail} in the opened Chrome window. ` +
      "The qualification resumes automatically after the application shell loads.",
  );
  await page.goto(targetPath, { waitUntil: "domcontentloaded" });
  const request = context.request;
  const createdSessions = new Set<string>();
  let principalId: string | null = null;
  let cleanupPassed = false;
  try {
    await expect(
      page.getByRole("heading", { name: "Ask, explore, decide" }),
    ).toBeVisible({ timeout: 5 * 60 * 1_000 });

    const identity = await jsonResponse<PrincipalView>(
      await request.get(apiPath("/v1/identity")),
      "owner identity",
    );
    principalId = identity.principal_id;
    expect(identity).toMatchObject({
      email: ownerEmail,
      role: "owner",
      status: "active",
      identity_mode: "iap",
    });

    const health = await jsonResponse<HealthSummary>(
      await request.get(apiPath("/health")),
      "managed readiness",
    );
    expect(health.status).toBe("ok");
    expect(health.readiness.status).toBe("ok");
    const checks = new Map(
      health.readiness.checks.map((check) => [check.name, check]),
    );
    for (const name of [
      "storage.postgresql",
      "security.iap_identity",
      "provider.market",
      "provider.news",
      "provider_cache.rights",
      "response_cache.redis",
      "qdrant.finance_education",
      "qdrant.tax_education",
    ]) {
      expect(checks.get(name)?.status, `${name} readiness`).toBe("ready");
    }
    expect(checks.get("provider.market")?.expected.mode).toBe(
      "credential_free",
    );
    expect(checks.get("provider.news")?.expected.mode).toBe("credential_free");
    expect(checks.get("qdrant.finance_education")?.expected.active_alias).toBe(
      "finance_education_active",
    );
    expect(checks.get("qdrant.tax_education")?.expected.active_alias).toBe(
      "tax_education_active",
    );

    await expect(page.getByText(`${ownerEmail} · owner`)).toBeVisible();
    await expectNoSeriousAxeViolations(page);

    await expect
      .poll(() => storedSessionId(page, identity.principal_id))
      .not.toBeNull();
    const initialSessionId = await storedSessionId(page, identity.principal_id);
    expect(initialSessionId).not.toBeNull();
    createdSessions.add(initialSessionId!);

    const label = `Qualification ${revision.slice(0, 8)}`;
    const qualificationSession = await jsonResponse<SessionRecord>(
      await request.post(apiPath("/v1/sessions"), { data: { label } }),
      "qualification Session creation",
    );
    createdSessions.add(qualificationSession.session_id);
    await page.evaluate(
      ({ key, value }) => window.localStorage.setItem(key, value),
      {
        key: `aifa.session.${identity.principal_id}`,
        value: qualificationSession.session_id,
      },
    );
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "Ask, explore, decide" }),
    ).toBeVisible();

    await page
      .getByLabel("Message the finance assistant")
      .fill("What is an ETF?");
    await page.getByRole("button", { name: "Send message" }).click();
    await expect(
      page.getByText(
        "Educational explanation grounded in the cited Finance evidence.",
      ),
    ).toBeVisible({ timeout: 2 * 60 * 1_000 });
    await expect(page.getByRole("list", { name: "Sources" })).toBeVisible();

    const runs = await jsonResponse<RunList>(
      await request.get(
        apiPath(`/v1/sessions/${qualificationSession.session_id}/runs`),
      ),
      "Assistant Run history",
    );
    const run = runs.items.find(
      (item) => item.request_message === "What is an ETF?",
    );
    expect(run?.status).toBe("completed");
    expect(run?.result?.status).toBe("completed");
    expect(run?.result?.summary).not.toBe("");
    expect(run?.result?.agent_results[0]?.evidence.length).toBeGreaterThan(0);
    expect(run).toBeDefined();

    const eventHistory = await jsonResponse<RunEventHistory>(
      await request.get(
        apiPath(
          `/v1/sessions/${qualificationSession.session_id}/runs/${run!.execution_id}/events`,
        ),
      ),
      "persisted RunEvents",
    );
    expect(eventHistory.events.length).toBeGreaterThan(0);
    expect(eventHistory.events.map((event) => event.sequence)).toEqual(
      eventHistory.events.map((_, index) => index + 1),
    );
    const replay = await request.get(
      apiPath(
        `/v1/sessions/${qualificationSession.session_id}/runs/${run!.execution_id}/stream`,
      ),
      {
        headers: {
          Accept: "text/event-stream",
          "Last-Event-ID": eventHistory.events[0]!.event_id,
        },
      },
    );
    expect(replay.ok()).toBeTruthy();
    expect(replay.headers()["content-type"]).toContain("text/event-stream");
    const replayText = await replay.text();
    expect(replayText).toContain("event: run_event");
    expect(replayText).not.toContain(
      `id: ${eventHistory.events[0]!.event_id}\n`,
    );

    await page.getByRole("button", { name: "Portfolio", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Portfolio dashboard" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Import portfolio" }).click();
    const importDialog = page.getByRole("dialog", { name: "Import positions" });
    await importDialog
      .getByRole("button", { name: "JSON / CSV / XLSX" })
      .click();
    await importDialog
      .getByLabel("Choose a portfolio file")
      .setInputFiles(portfolioFixture);
    const portfolioLabel = `Synthetic ${revision.slice(0, 8)}`;
    await importDialog.getByLabel("Portfolio label").fill(portfolioLabel);
    await importDialog.getByRole("button", { name: "Validate import" }).click();
    await expect(
      importDialog
        .getByRole("status")
        .filter({ hasText: "Ready for approval" }),
    ).toBeVisible();
    await importDialog
      .getByRole("button", { name: "Save validated portfolio" })
      .click();
    await expect(
      page.getByRole("status").filter({ hasText: "Portfolio saved" }),
    ).toBeVisible();

    const portfolios = await jsonResponse<ImportedPortfolio[]>(
      await request.get(
        apiPath(`/v1/sessions/${qualificationSession.session_id}/portfolios`),
      ),
      "saved Portfolios",
    );
    const portfolio = portfolios.find((item) => item.label === portfolioLabel);
    expect(portfolio).toBeDefined();
    const portfolioCard = page
      .locator(".portfolio-library article")
      .filter({ hasText: portfolioLabel });
    await portfolioCard.getByRole("button", { name: "Analyze" }).click();
    await expect(
      page.getByRole("heading", { name: "Allocation and coverage" }),
    ).toBeVisible();
    const snapshots = await jsonResponse<PortfolioSnapshot[]>(
      await request.get(
        apiPath(
          `/v1/sessions/${qualificationSession.session_id}/portfolios/${portfolio!.portfolio_id}/snapshots`,
        ),
      ),
      "Portfolio Snapshots",
    );
    expect(snapshots.length).toBeGreaterThan(0);
    expect(snapshots[0]?.snapshot_id).toMatch(/^snapshot-/);
    await expectNoSeriousAxeViolations(page);

    await page.getByRole("button", { name: "Market" }).click();
    await page.getByRole("button", { name: "View market data" }).click();
    await expect(page.getByText("Synthetic demo data").first()).toBeVisible();
    await expect(
      page.getByRole("table", { name: "Daily provider observations" }),
    ).toBeVisible();
    await expectNoSeriousAxeViolations(page);

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

    await page.getByRole("button", { name: "Inspector" }).click();
    await expect(
      page.getByRole("heading", { name: "Measured execution graph" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Ordered event timeline" }),
    ).toBeVisible();
    await expect(page.locator(".inspector-timeline li")).toHaveCount(
      eventHistory.events.length,
    );
    await page.getByRole("button", { name: "Resume event stream" }).click();
    await expect(
      page.getByRole("button", { name: "Resume event stream" }),
    ).toBeEnabled();
    await expectNoSeriousAxeViolations(page);

    await page.getByRole("button", { name: "Assistant" }).click();
    await page.getByRole("button", { name: "Clear active session" }).click();
    await page.getByRole("button", { name: "Archive and start fresh" }).click();
    await expect
      .poll(() => storedSessionId(page, identity.principal_id))
      .not.toBe(qualificationSession.session_id);
    const replacement = await storedSessionId(page, identity.principal_id);
    expect(replacement).not.toBeNull();
    createdSessions.add(replacement!);

    await page.getByRole("button", { name: "History" }).click();
    await expect(
      page.getByRole("heading", { name: "Session history" }),
    ).toBeVisible();
    const historyCard = page
      .locator(".history-list article")
      .filter({ hasText: label });
    await expect(historyCard).toBeVisible();
    await historyCard
      .getByRole("button", { name: "View conversation" })
      .click();
    await expect(page.getByText("What is an ETF?")).toBeVisible();
    await historyCard.getByRole("button", { name: "Delete" }).click();
    await historyCard
      .getByRole("button", { name: "Delete permanently" })
      .click();
    await expect(historyCard).toHaveCount(0);
    await expectNoSeriousAxeViolations(page);

    createdSessions.delete(qualificationSession.session_id);
  } finally {
    if (principalId !== null) {
      const currentSessionId = await storedSessionId(page, principalId);
      if (currentSessionId !== null) createdSessions.add(currentSessionId);
    }
    const cleanupResults = await Promise.all(
      [...createdSessions].map((sessionId) =>
        cleanupSession(request, sessionId),
      ),
    );
    cleanupPassed = cleanupResults.every(Boolean);
  }

  expect(
    cleanupPassed,
    "all qualification-created Sessions were deleted",
  ).toBeTruthy();
  const evidence = {
    schema_version: "1",
    status: "qualified",
    qualification_revision: revision,
    generated_at: new Date().toISOString(),
    target: "https://apps.comfforts.com/finance_assistant",
    access: {
      owner: ownerEmail,
      identity_mode: "iap",
      anonymous: "denied_by_prior_edge_evidence",
      direct_origin: "denied_by_prior_edge_evidence",
    },
    deployed_images: {
      backend: process.env.AIFA_DEPLOYED_BACKEND_IMAGE,
      frontend: process.env.AIFA_DEPLOYED_FRONTEND_IMAGE,
    },
    provider_boundary: {
      provider_mode: "credential_free",
      model_mode: "credential_free",
      live_provider_secrets_present: false,
    },
    prior_evidence: priorEvidence,
    journeys: {
      owner_iap_identity: "passed",
      managed_readiness_and_active_knowledge: "passed",
      assistant_run_and_sse_replay: "passed",
      portfolio_import_snapshot_and_context: "passed",
      credential_free_market_provenance: "passed",
      goal_projection: "passed",
      history_archive_and_delete: "passed",
      inspector_run_event_reconciliation: "passed",
      accessibility_critical_views:
        "passed_no_serious_or_critical_axe_findings",
      synthetic_state_cleanup: "passed",
    },
    limitations: [
      "Owner-only private-demo qualification; viewer admission is disabled.",
      "Live OpenAI, market, and news providers were not enabled or called.",
      "Backup/PITR, HA, load/soak, SLO/alert, and incident rehearsals remain deferred.",
    ],
    secret_payloads_recorded: false,
  };
  writeFileSync(evidencePath, `${JSON.stringify(evidence, null, 2)}\n`, {
    encoding: "utf8",
    mode: 0o600,
  });
});
