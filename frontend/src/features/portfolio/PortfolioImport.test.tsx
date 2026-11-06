import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { api, fileToBase64 } from "../../lib/api";
import type {
  ImportedPortfolio,
  PortfolioImportApiRequest,
  PortfolioImportResult,
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

const portfolio: ImportedPortfolio = {
  schema_version: "1",
  portfolio_id: "portfolio-1",
  label: "Retirement",
  base_currency: "USD",
  imported_at: "2026-10-30T16:00:00Z",
  source_kind: "manual",
  source_file_hash: "a".repeat(64),
  accounts: [
    {
      account_id: "account-1",
      portfolio_id: "portfolio-1",
      account_type: "taxable",
      institution_label: null,
      holdings: [],
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
  base_currency_total: "0.00",
  totals_by_currency: [],
  holding_valuations: [],
  concentrations: [],
  expense_metrics: [],
  diversification: [],
  unpriced_holding_ids: [],
  warnings: [],
};

function accepted(
  findings: PortfolioImportResult["findings"] = [],
): PortfolioImportResult {
  return {
    schema_version: "1",
    source_kind: "manual",
    source_file_hash: "a".repeat(64),
    accepted: true,
    portfolio,
    findings,
  };
}

function renderPortfolio() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <PortfolioExperience sessionId="session-test" />
    </QueryClientProvider>,
  );
}

async function openImport() {
  fireEvent.click(
    await screen.findByRole("button", { name: "Import portfolio" }),
  );
  return screen.findByRole("dialog", { name: "Import positions" });
}

function lastRequest(
  mock: typeof api.validatePortfolio,
): PortfolioImportApiRequest {
  const call = vi.mocked(mock).mock.calls.at(-1);
  if (!call) throw new Error("expected a request");
  return call[1];
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.listPortfolios).mockResolvedValue([portfolio]);
  vi.mocked(api.createSnapshot).mockResolvedValue(snapshot);
  vi.mocked(api.deletePortfolio).mockResolvedValue(undefined);
});

test("edits manual holdings, reviews warning findings, and saves the reviewed request", async () => {
  vi.mocked(api.validatePortfolio).mockResolvedValue(
    accepted([
      {
        code: "PRICE_STALE",
        severity: "warning",
        scope: "field",
        message: "The supplied price is older than one day.",
        row_number: 2,
        field: "user_price",
      },
    ]),
  );
  vi.mocked(api.savePortfolio).mockResolvedValue(accepted());
  renderPortfolio();
  const dialog = await openImport();

  fireEvent.click(within(dialog).getByRole("button", { name: "Add holding" }));
  fireEvent.click(within(dialog).getByRole("button", { name: "Add holding" }));
  fireEvent.click(
    within(dialog).getByRole("button", { name: "Remove holding 3" }),
  );
  const second = within(dialog).getByRole("group", { name: "Holding 2" });
  fireEvent.change(within(second).getByLabelText("Symbol"), {
    target: { value: "bnd" },
  });
  fireEvent.change(within(second).getByLabelText("Quantity"), {
    target: { value: "4" },
  });
  fireEvent.change(within(second).getByLabelText("Price per unit"), {
    target: { value: "72.5" },
  });
  fireEvent.change(within(second).getByLabelText("Asset class"), {
    target: { value: "Fixed income" },
  });
  fireEvent.change(within(second).getByLabelText("Account type"), {
    target: { value: "roth_ira" },
  });
  fireEvent.change(within(second).getByLabelText("Currency"), {
    target: { value: "usd" },
  });
  fireEvent.change(within(dialog).getByLabelText("Portfolio label"), {
    target: { value: "Retirement" },
  });
  fireEvent.click(
    within(dialog).getByRole("button", { name: "Validate import" }),
  );

  expect(
    await within(dialog).findByText("Validation findings"),
  ).toBeInTheDocument();
  expect(
    within(dialog).getByText(/older than one day\. \(row 2\)/),
  ).toBeInTheDocument();
  expect(
    within(dialog).getByText(
      "Validation completed. Review the findings below.",
    ),
  ).toBeInTheDocument();
  const request = lastRequest(api.validatePortfolio);
  expect(request.metadata.label).toBe("Retirement");
  expect(request.payload.kind).toBe("manual");
  if (request.payload.kind !== "manual") throw new Error("manual expected");
  expect(request.payload.rows).toHaveLength(2);
  expect(request.payload.rows[1]).toMatchObject({
    identifier_value: "BND",
    quantity: "4",
    user_price: "72.5",
    asset_class: "Fixed income",
    account_type: "roth_ira",
    currency: "USD",
    user_price_provenance: "Manual M6 entry",
  });

  fireEvent.click(
    within(dialog).getByRole("button", { name: "Save validated portfolio" }),
  );

  await waitFor(() =>
    expect(api.savePortfolio).toHaveBeenCalledWith("session-test", request),
  );
  await waitFor(() =>
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
  );
  expect(screen.getByText("Portfolio saved")).toBeInTheDocument();
});

test("encodes selected CSV and XLSX files with their source kind", async () => {
  vi.mocked(fileToBase64).mockResolvedValue("ZW5jb2RlZA==");
  vi.mocked(api.validatePortfolio).mockResolvedValue({
    ...accepted(),
    accepted: false,
    portfolio: null,
  });
  renderPortfolio();
  const dialog = await openImport();
  fireEvent.click(
    within(dialog).getByRole("button", { name: "JSON / CSV / XLSX" }),
  );
  const fileInput = within(dialog).getByLabelText("Choose a portfolio file");

  for (const [name, kind] of [
    ["holdings.CSV", "csv"],
    ["holdings.xlsx", "xlsx"],
  ] as const) {
    fireEvent.change(fileInput, {
      target: { files: [new File(["data"], name)] },
    });
    // jsdom cannot attach a real FileList, so submit past the native `required` check.
    fireEvent.submit(fileInput.closest("form")!);
    await waitFor(() =>
      expect(lastRequest(api.validatePortfolio).payload).toEqual({
        kind,
        content_base64: "ZW5jb2RlZA==",
        filename: name,
      }),
    );
  }
  expect(
    await within(dialog).findByText("Review the input and validate it again."),
  ).toBeInTheDocument();
});

test("reports a file that cannot be prepared before any backend call", async () => {
  vi.mocked(fileToBase64).mockRejectedValue(
    new Error("The file is unreadable."),
  );
  renderPortfolio();
  const dialog = await openImport();
  fireEvent.click(
    within(dialog).getByRole("button", { name: "JSON / CSV / XLSX" }),
  );
  const form = dialog.querySelector("form");
  if (!form) throw new Error("form expected");

  fireEvent.submit(form);
  expect(
    await within(dialog).findByText("Choose a JSON, CSV, or XLSX file first."),
  ).toBeInTheDocument();

  fireEvent.change(within(dialog).getByLabelText("Choose a portfolio file"), {
    target: { files: [new File(["{}"], "broken.json")] },
  });
  fireEvent.submit(form);

  expect(
    await within(dialog).findByText("The file is unreadable."),
  ).toBeInTheDocument();
  expect(within(dialog).getByText("File could not be prepared")).toBeVisible();
  expect(api.validatePortfolio).not.toHaveBeenCalled();
  fireEvent.click(within(dialog).getByRole("button", { name: "Manual" }));
  expect(within(dialog).getByLabelText("Symbol")).toBeInTheDocument();
});

test("keeps validation and save failures visible inside the import dialog", async () => {
  vi.mocked(api.validatePortfolio)
    .mockRejectedValueOnce(new Error("Validation service unavailable."))
    .mockResolvedValueOnce(accepted());
  vi.mocked(api.savePortfolio).mockRejectedValue(
    new Error("Storage is read-only."),
  );
  renderPortfolio();
  const dialog = await openImport();
  const validate = within(dialog).getByRole("button", {
    name: "Validate import",
  });

  fireEvent.click(validate);
  expect(
    await within(dialog).findByText("Import could not be validated"),
  ).toBeInTheDocument();
  expect(
    within(dialog).getByText("Validation service unavailable."),
  ).toBeInTheDocument();

  fireEvent.click(validate);
  await within(dialog).findByText("Ready for approval");
  fireEvent.click(
    within(dialog).getByRole("button", { name: "Save validated portfolio" }),
  );

  expect(
    await within(dialog).findByText("Portfolio could not be saved"),
  ).toBeInTheDocument();
  expect(within(dialog).getByText("Storage is read-only.")).toBeInTheDocument();
  expect(screen.getByRole("dialog")).toBeInTheDocument();
});

test("clears the analysis when its portfolio is deleted and refreshes on request", async () => {
  vi.mocked(api.listPortfolios)
    .mockResolvedValueOnce([portfolio])
    .mockResolvedValueOnce([portfolio])
    .mockResolvedValue([]);
  renderPortfolio();
  await screen.findByRole("button", { name: "Analyze" });

  fireEvent.click(screen.getByRole("button", { name: "Refresh portfolios" }));
  await waitFor(() => expect(api.listPortfolios).toHaveBeenCalledTimes(2));
  fireEvent.click(await screen.findByRole("button", { name: "Analyze" }));
  expect(
    await screen.findByRole("heading", { name: "Allocation and coverage" }),
  ).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Delete Retirement" }));
  fireEvent.click(screen.getByRole("button", { name: "Delete portfolio" }));

  await waitFor(() =>
    expect(
      screen.queryByRole("heading", { name: "Allocation and coverage" }),
    ).not.toBeInTheDocument(),
  );
  expect(screen.getByText("Portfolio deleted")).toBeInTheDocument();
});
