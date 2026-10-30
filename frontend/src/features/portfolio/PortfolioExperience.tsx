import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FileSpreadsheet,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { PageHeader } from "../../components/PageHeader";
import { StateNotice } from "../../components/StateNotice";
import { api, ClientApiError, fileToBase64 } from "../../lib/api";
import {
  formatCurrency,
  formatDateTime,
  formatPercent,
} from "../../lib/format";
import type {
  CalculationWarning,
  ImportedPortfolio,
  ManualHoldingRow,
  PortfolioImportApiRequest,
} from "../../types/contracts";

const chartColors = [
  "#1c5c50",
  "#32796b",
  "#64a595",
  "#e4a83a",
  "#c96b45",
  "#6f7d91",
];

const portfolioNoticeDurationMs = 4_000;

interface SnapshotWarningGroup {
  code: string;
  message: string;
  scope: "holding" | "portfolio";
  holdingIds: string[];
}

function groupSnapshotWarnings(
  warnings: CalculationWarning[],
): SnapshotWarningGroup[] {
  const groups = new Map<string, SnapshotWarningGroup>();

  for (const warning of warnings) {
    const scope = warning.holding_id === null ? "portfolio" : "holding";
    const key = JSON.stringify([scope, warning.code, warning.message]);
    const existing = groups.get(key);
    if (existing) {
      if (
        warning.holding_id !== null &&
        !existing.holdingIds.includes(warning.holding_id)
      ) {
        existing.holdingIds.push(warning.holding_id);
      }
      continue;
    }
    groups.set(key, {
      code: warning.code,
      message: warning.message,
      scope,
      holdingIds: warning.holding_id === null ? [] : [warning.holding_id],
    });
  }

  return [...groups.values()];
}

function sourceKind(file: File): "json" | "csv" | "xlsx" {
  const extension = file.name.split(".").at(-1)?.toLowerCase();
  if (extension === "csv") return "csv";
  if (extension === "xlsx") return "xlsx";
  return "json";
}

function initialRow(index: number): ManualHoldingRow {
  return {
    account_id: "account-1",
    account_type: "taxable",
    holding_id: `holding-${index + 1}`,
    identifier_type: "ticker",
    identifier_value: index === 0 ? "DEMO" : "",
    quantity: index === 0 ? "10" : "",
    currency: "USD",
    asset_class: "Equity",
    user_price: index === 0 ? "100" : "",
  };
}

export function PortfolioExperience({ sessionId }: { sessionId: string }) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"manual" | "file">("manual");
  const [file, setFile] = useState<File | null>(null);
  const [portfolioId] = useState(() => `portfolio-${Date.now()}`);
  const nextHoldingNumber = useRef(2);
  const [label, setLabel] = useState("Demo portfolio");
  const [rows, setRows] = useState<ManualHoldingRow[]>([initialRow(0)]);
  const [clientError, setClientError] = useState<string | null>(null);
  const [reviewedRequest, setReviewedRequest] =
    useState<PortfolioImportApiRequest | null>(null);
  const [snapshotId, setSnapshotId] = useState<string | null>(null);
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [deletePortfolioId, setDeletePortfolioId] = useState<string | null>(
    null,
  );
  const [portfolioNotice, setPortfolioNotice] = useState<
    "saved" | "deleted" | null
  >(null);
  const importDialogRef = useRef<HTMLDialogElement>(null);

  const portfolios = useQuery({
    queryKey: ["portfolios", sessionId],
    queryFn: () => api.listPortfolios(sessionId),
  });
  const validate = useMutation({
    mutationFn: (request: PortfolioImportApiRequest) =>
      api.validatePortfolio(sessionId, request),
    onSuccess: (result, request) =>
      setReviewedRequest(result.accepted ? request : null),
  });
  const save = useMutation({
    mutationFn: (request: PortfolioImportApiRequest) =>
      api.savePortfolio(sessionId, request),
    onSuccess: async () => {
      setReviewedRequest(null);
      setIsImportOpen(false);
      setPortfolioNotice("saved");
      await queryClient.invalidateQueries({
        queryKey: ["portfolios", sessionId],
      });
    },
  });
  const snapshot = useMutation({
    mutationFn: (savedPortfolioId: string) =>
      api.createSnapshot(sessionId, savedPortfolioId),
    onSuccess: (result) => setSnapshotId(result.snapshot_id),
  });
  const removePortfolio = useMutation({
    mutationFn: (portfolioIdToDelete: string) =>
      api.deletePortfolio(sessionId, portfolioIdToDelete),
    onSuccess: async (_, portfolioIdToDelete) => {
      if (snapshot.data?.portfolio_id === portfolioIdToDelete) {
        snapshot.reset();
        setSnapshotId(null);
      }
      setDeletePortfolioId(null);
      setPortfolioNotice("deleted");
      queryClient.setQueryData<ImportedPortfolio[]>(
        ["portfolios", sessionId],
        (current) =>
          current?.filter(
            (portfolio) => portfolio.portfolio_id !== portfolioIdToDelete,
          ) ?? [],
      );
      await queryClient.invalidateQueries({
        queryKey: ["portfolios", sessionId],
      });
    },
  });

  const createRequest = async (): Promise<PortfolioImportApiRequest> => {
    const metadata = {
      portfolio_id: portfolioId,
      label: label || null,
      base_currency: "USD",
      imported_at: new Date().toISOString(),
    };
    if (mode === "file") {
      if (!file) throw new Error("Choose a JSON, CSV, or XLSX file first.");
      return {
        schema_version: "1",
        metadata,
        payload: {
          kind: sourceKind(file),
          content_base64: await fileToBase64(file),
          filename: file.name,
        },
      };
    }
    return {
      schema_version: "1",
      metadata,
      payload: {
        kind: "manual",
        rows: rows.map((row) => ({
          ...row,
          user_price_as_of: new Date().toISOString(),
          user_price_provenance: "Manual M6 entry",
        })),
      },
    };
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setReviewedRequest(null);
    setClientError(null);
    void createRequest()
      .then((request) => validate.mutate(request))
      .catch((error: Error) => {
        validate.reset();
        setClientError(error.message);
      });
  };

  const updateRow = (
    index: number,
    field: keyof ManualHoldingRow,
    value: string,
  ) => {
    setReviewedRequest(null);
    setRows(
      rows.map((row, rowIndex) =>
        rowIndex === index ? { ...row, [field]: value } : row,
      ),
    );
  };

  const openImportDialog = () => {
    setClientError(null);
    setReviewedRequest(null);
    setPortfolioNotice(null);
    validate.reset();
    removePortfolio.reset();
    setIsImportOpen(true);
  };

  const closeImportDialog = () => {
    const dialog = importDialogRef.current;
    if (dialog?.open && typeof dialog.close === "function") {
      dialog.close();
      return;
    }
    setIsImportOpen(false);
  };

  useEffect(() => {
    const dialog = importDialogRef.current;
    if (!isImportOpen || dialog === null) return;

    if (typeof dialog.showModal === "function") {
      dialog.showModal();
    } else {
      dialog.setAttribute("open", "");
    }

    return () => {
      if (dialog.open && typeof dialog.close === "function") dialog.close();
    };
  }, [isImportOpen]);

  useEffect(() => {
    if (portfolioNotice === null) return;
    const timeoutId = window.setTimeout(
      () => setPortfolioNotice(null),
      portfolioNoticeDurationMs,
    );
    return () => window.clearTimeout(timeoutId);
  }, [portfolioNotice]);

  const latestSnapshot = snapshot.data;
  const snapshotWarningGroups = useMemo(
    () => groupSnapshotWarnings(latestSnapshot?.warnings ?? []),
    [latestSnapshot],
  );
  const allocationData = useMemo(
    () =>
      latestSnapshot?.holding_valuations
        .filter((holding) => holding.market_value !== null)
        .map((holding) => ({
          name: holding.holding_id,
          value: Number(holding.market_value),
        })) ?? [],
    [latestSnapshot],
  );

  return (
    <>
      <PageHeader
        eyebrow="Imported evidence + deterministic analysis"
        title="Portfolio dashboard"
        description="Review every import finding before saving. Values and allocations come from the backend calculation policy, never browser arithmetic."
        action={
          <div className="portfolio-header-actions">
            <span className="milestone-chip">
              {portfolios.data?.length ?? 0} saved
            </span>
            <button
              className="primary-button"
              onClick={openImportDialog}
              type="button"
            >
              <FileSpreadsheet aria-hidden="true" size={18} /> Import portfolio
            </button>
          </div>
        }
      />

      {isImportOpen ? (
        <dialog
          aria-describedby="import-description"
          aria-labelledby="import-heading"
          className="import-dialog"
          onClose={() => setIsImportOpen(false)}
          ref={importDialogRef}
        >
          <div className="import-dialog-heading">
            <div>
              <p className="eyebrow">New portfolio</p>
              <h3 id="import-heading">Import positions</h3>
              <p id="import-description">
                Validate every imported value before adding this portfolio to
                your saved library.
              </p>
            </div>
            <button
              aria-label="Close portfolio import"
              autoFocus
              className="icon-button"
              onClick={closeImportDialog}
              type="button"
            >
              <X aria-hidden="true" size={20} />
            </button>
          </div>
          <div className="import-dialog-body">
            <div className="segmented" aria-label="Import method">
              <button
                aria-pressed={mode === "manual"}
                onClick={() => {
                  setMode("manual");
                  setReviewedRequest(null);
                }}
                type="button"
              >
                Manual
              </button>
              <button
                aria-pressed={mode === "file"}
                onClick={() => {
                  setMode("file");
                  setReviewedRequest(null);
                }}
                type="button"
              >
                JSON / CSV / XLSX
              </button>
            </div>
            <form className="form-grid" onSubmit={submit}>
              <label className="field field-wide">
                Portfolio label
                <input
                  value={label}
                  onChange={(event) => setLabel(event.target.value)}
                  maxLength={128}
                />
              </label>
              {mode === "manual" ? (
                <div className="manual-rows field-wide">
                  {rows.map((row, index) => (
                    <fieldset className="manual-row" key={row.holding_id}>
                      <legend>Holding {index + 1}</legend>
                      <div className="manual-row-heading">
                        <span>Account {row.account_id}</span>
                        {rows.length > 1 ? (
                          <button
                            aria-label={`Remove holding ${index + 1}`}
                            className="text-button"
                            onClick={() =>
                              setRows(
                                rows.filter(
                                  (_, rowIndex) => rowIndex !== index,
                                ),
                              )
                            }
                            type="button"
                          >
                            <Trash2 aria-hidden="true" size={15} /> Remove
                          </button>
                        ) : null}
                      </div>
                      <div className="form-grid">
                        <label className="field">
                          Symbol
                          <input
                            required
                            value={row.identifier_value}
                            onChange={(event) =>
                              updateRow(
                                index,
                                "identifier_value",
                                event.target.value.toUpperCase(),
                              )
                            }
                          />
                        </label>
                        <label className="field">
                          Quantity
                          <input
                            min="0"
                            required
                            step="any"
                            type="number"
                            value={row.quantity}
                            onChange={(event) =>
                              updateRow(index, "quantity", event.target.value)
                            }
                          />
                        </label>
                        <label className="field">
                          Price per unit
                          <input
                            min="0.01"
                            required
                            step="any"
                            type="number"
                            value={row.user_price}
                            onChange={(event) =>
                              updateRow(index, "user_price", event.target.value)
                            }
                          />
                        </label>
                        <label className="field">
                          Asset class
                          <input
                            value={row.asset_class}
                            onChange={(event) =>
                              updateRow(
                                index,
                                "asset_class",
                                event.target.value,
                              )
                            }
                          />
                        </label>
                        <label className="field">
                          Account type
                          <select
                            value={row.account_type}
                            onChange={(event) =>
                              updateRow(
                                index,
                                "account_type",
                                event.target.value,
                              )
                            }
                          >
                            <option value="taxable">Taxable</option>
                            <option value="traditional_ira">
                              Traditional IRA
                            </option>
                            <option value="roth_ira">Roth IRA</option>
                          </select>
                        </label>
                        <label className="field">
                          Currency
                          <input
                            maxLength={3}
                            required
                            value={row.currency}
                            onChange={(event) =>
                              updateRow(
                                index,
                                "currency",
                                event.target.value.toUpperCase(),
                              )
                            }
                          />
                        </label>
                      </div>
                    </fieldset>
                  ))}
                  <button
                    className="secondary-button add-holding"
                    onClick={() => {
                      setRows([
                        ...rows,
                        initialRow(nextHoldingNumber.current - 1),
                      ]);
                      nextHoldingNumber.current += 1;
                    }}
                    type="button"
                  >
                    <Plus aria-hidden="true" size={16} /> Add holding
                  </button>
                </div>
              ) : (
                <label className="file-drop field-wide">
                  <FileSpreadsheet aria-hidden="true" />
                  <span>{file ? file.name : "Choose a portfolio file"}</span>
                  <small>
                    Maximum 2 MB. Files are validated as untrusted input.
                  </small>
                  <input
                    accept=".json,.csv,.xlsx"
                    onChange={(event) =>
                      setFile(event.target.files?.[0] ?? null)
                    }
                    required
                    type="file"
                  />
                </label>
              )}
              <button
                className="primary-button field-wide"
                disabled={validate.isPending}
                type="submit"
              >
                <ShieldCheck aria-hidden="true" size={18} />{" "}
                {validate.isPending ? "Validating…" : "Validate import"}
              </button>
            </form>

            {clientError ? (
              <StateNotice tone="error" title="File could not be prepared">
                {clientError}
              </StateNotice>
            ) : null}

            {validate.isError ? (
              <StateNotice tone="error" title="Import could not be validated">
                {validate.error instanceof Error
                  ? validate.error.message
                  : "Review the input and try again."}
              </StateNotice>
            ) : null}
            {validate.data ? (
              <section className="validation-review" aria-live="polite">
                <h4>
                  {validate.data.accepted
                    ? "Ready for your approval"
                    : "Corrections required"}
                </h4>
                {validate.data.findings.length ? (
                  <ul>
                    {validate.data.findings.map((finding, index) => (
                      <li
                        className={`finding-${finding.severity}`}
                        key={`${finding.code}-${index}`}
                      >
                        <strong>{finding.code.replaceAll("_", " ")}</strong> —{" "}
                        {finding.message}
                        {finding.row_number
                          ? ` (row ${finding.row_number})`
                          : ""}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p>No validation findings.</p>
                )}
                {reviewedRequest ? (
                  <button
                    className="primary-button"
                    disabled={save.isPending}
                    onClick={() => save.mutate(reviewedRequest)}
                    type="button"
                  >
                    {save.isPending ? "Saving…" : "Save validated portfolio"}
                  </button>
                ) : null}
              </section>
            ) : null}
          </div>
        </dialog>
      ) : null}

      <section
        className="panel portfolio-library"
        aria-labelledby="saved-heading"
      >
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Portfolio library</p>
            <h3 id="saved-heading">Saved portfolios</h3>
          </div>
          <button
            aria-label="Refresh portfolios"
            className="icon-button"
            onClick={() => void portfolios.refetch()}
            type="button"
          >
            <RefreshCw size={18} />
          </button>
        </div>
        {portfolios.isPending ? (
          <StateNotice title="Loading saved portfolios" />
        ) : null}
        {portfolios.isError ? (
          <StateNotice tone="error" title="Saved portfolios unavailable" />
        ) : null}
        {portfolioNotice === "saved" ? (
          <StateNotice tone="success" title="Portfolio saved">
            The validated result is now the authoritative saved import.
          </StateNotice>
        ) : null}
        {portfolioNotice === "deleted" ? (
          <StateNotice tone="success" title="Portfolio deleted">
            The imported Portfolio and its saved Snapshots were permanently
            removed from this Session.
          </StateNotice>
        ) : null}
        {portfolios.data?.length === 0 ? (
          <div className="compact-empty">
            <Plus aria-hidden="true" />
            <p>Import a portfolio to begin analysis.</p>
          </div>
        ) : null}
        <div className="saved-list">
          {portfolios.data?.map((portfolio) => {
            const holdingCount = portfolio.accounts.reduce(
              (count, account) => count + account.holdings.length,
              0,
            );
            const portfolioLabel = portfolio.label ?? portfolio.portfolio_id;
            return (
              <article key={portfolio.portfolio_id}>
                <div>
                  <strong>{portfolioLabel}</strong>
                  <span>
                    {holdingCount} holding{holdingCount === 1 ? "" : "s"} ·{" "}
                    {portfolio.source_kind.toUpperCase()}
                  </span>
                  <span>Imported {formatDateTime(portfolio.imported_at)}</span>
                </div>
                {deletePortfolioId === portfolio.portfolio_id ? (
                  <div
                    aria-labelledby={`delete-${portfolio.portfolio_id}`}
                    className="portfolio-delete-confirmation"
                    role="group"
                  >
                    <strong id={`delete-${portfolio.portfolio_id}`}>
                      Delete {portfolioLabel}?
                    </strong>
                    <p>
                      This permanently removes the imported Portfolio and all of
                      its saved Snapshots from this Session.
                    </p>
                    {removePortfolio.isError ? (
                      <p className="clear-session-error" role="alert">
                        {removePortfolio.error instanceof ClientApiError
                          ? removePortfolio.error.message
                          : "The Portfolio could not be deleted."}
                      </p>
                    ) : null}
                    <div className="portfolio-actions">
                      <button
                        autoFocus
                        className="danger-button"
                        disabled={removePortfolio.isPending}
                        onClick={() =>
                          removePortfolio.mutate(portfolio.portfolio_id)
                        }
                        type="button"
                      >
                        {removePortfolio.isPending
                          ? "Deleting…"
                          : "Delete portfolio"}
                      </button>
                      <button
                        className="text-button"
                        disabled={removePortfolio.isPending}
                        onClick={() => {
                          removePortfolio.reset();
                          setDeletePortfolioId(null);
                        }}
                        type="button"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="portfolio-actions">
                    <button
                      className="secondary-button"
                      disabled={snapshot.isPending || removePortfolio.isPending}
                      onClick={() => snapshot.mutate(portfolio.portfolio_id)}
                      type="button"
                    >
                      Analyze
                    </button>
                    <button
                      aria-label={`Delete ${portfolioLabel}`}
                      className="portfolio-delete-button"
                      disabled={snapshot.isPending || removePortfolio.isPending}
                      onClick={() => {
                        setPortfolioNotice(null);
                        save.reset();
                        removePortfolio.reset();
                        setDeletePortfolioId(portfolio.portfolio_id);
                      }}
                      type="button"
                    >
                      <Trash2 aria-hidden="true" size={15} /> Delete
                    </button>
                  </div>
                )}
              </article>
            );
          })}
        </div>
        {snapshot.isError ? (
          <StateNotice tone="error" title="Analysis unavailable">
            {snapshot.error instanceof ClientApiError
              ? snapshot.error.message
              : "Try again."}
          </StateNotice>
        ) : null}
      </section>

      {latestSnapshot ? (
        <section
          className="results-section"
          aria-labelledby="allocation-heading"
        >
          <div className="results-heading">
            <div>
              <p className="eyebrow">Backend snapshot</p>
              <h3 id="allocation-heading">Allocation and coverage</h3>
            </div>
            <span className="schema-chip">
              {latestSnapshot.calculation_policy_version}
            </span>
          </div>
          <p className="result-context">
            Calculated {formatDateTime(latestSnapshot.calculated_at)} · Snapshot{" "}
            {snapshotId}
          </p>
          <div className="metric-row">
            <div>
              <span>Total</span>
              <strong>
                {formatCurrency(
                  latestSnapshot.base_currency_total,
                  latestSnapshot.base_currency,
                )}
              </strong>
            </div>
            <div>
              <span>Priced holdings</span>
              <strong>
                {latestSnapshot.holding_valuations.length -
                  latestSnapshot.unpriced_holding_ids.length}{" "}
                / {latestSnapshot.holding_valuations.length}
              </strong>
            </div>
            <div>
              <span>Coverage</span>
              <strong>
                {formatPercent(
                  latestSnapshot.totals_by_currency[0]
                    ?.holding_count_coverage_percent ?? null,
                )}
              </strong>
            </div>
          </div>
          <div className="chart-table-layout">
            <div
              className="chart-frame"
              role="img"
              aria-label="Portfolio value by holding donut chart"
            >
              <ResponsiveContainer height={280} width="100%">
                <PieChart>
                  <Pie
                    data={allocationData}
                    dataKey="value"
                    innerRadius={62}
                    isAnimationActive={false}
                    nameKey="name"
                    outerRadius={105}
                  >
                    {allocationData.map((item, index) => (
                      <Cell
                        fill={chartColors[index % chartColors.length]}
                        key={item.name}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value) =>
                      formatCurrency(
                        Number(value),
                        latestSnapshot.base_currency,
                      )
                    }
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="table-scroll">
              <table>
                <caption>Authoritative holding valuations</caption>
                <thead>
                  <tr>
                    <th scope="col">Holding</th>
                    <th scope="col">Value</th>
                    <th scope="col">Allocation</th>
                    <th scope="col">Price source</th>
                  </tr>
                </thead>
                <tbody>
                  {latestSnapshot.holding_valuations.map((holding) => (
                    <tr key={holding.holding_id}>
                      <th scope="row">{holding.holding_id}</th>
                      <td>
                        {formatCurrency(holding.market_value, holding.currency)}
                      </td>
                      <td>{formatPercent(holding.allocation_percent)}</td>
                      <td>
                        {holding.price_source?.replaceAll("_", " ") ??
                          "Unpriced"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          {snapshotWarningGroups.map((warning) => (
            <StateNotice
              key={JSON.stringify([
                warning.scope,
                warning.code,
                warning.message,
              ])}
              tone="warning"
              title={warning.code.replaceAll("_", " ")}
            >
              <p>{warning.message}</p>
              {warning.holdingIds.length === 1 ? (
                <p className="snapshot-warning-scope">
                  Holding: {warning.holdingIds[0]}.
                </p>
              ) : null}
              {warning.holdingIds.length > 1 ? (
                <details className="snapshot-warning-scope">
                  <summary>
                    Applies to {warning.holdingIds.length} holdings.
                  </summary>
                  <ul aria-label={`${warning.code} affected holdings`}>
                    {warning.holdingIds.map((holdingId) => (
                      <li key={holdingId}>{holdingId}</li>
                    ))}
                  </ul>
                </details>
              ) : null}
            </StateNotice>
          ))}
        </section>
      ) : null}
    </>
  );
}
