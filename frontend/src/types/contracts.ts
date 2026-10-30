export type HealthStatus = "ok" | "degraded" | "not_ready";
export type CheckStatus =
  "ready" | "not_configured" | "not_implemented" | "failed";

export interface DependencyCheck {
  name: string;
  status: CheckStatus;
  detail: string;
  expected: Record<string, unknown>;
}

export interface HealthSummary {
  schema_version: "1";
  status: HealthStatus;
  mode: string;
  liveness: {
    status: HealthStatus;
    service: string;
    version: string;
  };
  readiness: {
    status: HealthStatus;
    checks: DependencyCheck[];
  };
}

export type EventType =
  | "run_started"
  | "run_completed"
  | "run_partial"
  | "run_failed"
  | "route_selected"
  | "node_started"
  | "node_completed"
  | "node_failed"
  | "node_skipped"
  | "tool_started"
  | "tool_completed"
  | "tool_failed"
  | "retrieval_started"
  | "retrieval_completed"
  | "retrieval_failed"
  | "model_started"
  | "model_completed"
  | "model_failed"
  | "response_chunk";

export type EventStatus =
  "pending" | "running" | "completed" | "partial" | "failed" | "skipped";

export interface RunEvent {
  schema_version: "1";
  event_id: string;
  execution_id: string;
  trace_id: string | null;
  trace_unavailable_reason: string | null;
  session_id: string;
  workflow_id: string;
  workflow_version: string;
  sequence: number;
  node_id: string;
  agent_id: string | null;
  tool_call_id: string | null;
  tool_name: string | null;
  parent_event_id: string | null;
  event_type: EventType;
  status: EventStatus;
  started_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  duration_unavailable_reason: string | null;
  routing: {
    selected_node_ids: string[];
    outcome: string;
    reason_category: string;
  } | null;
  tool_result: {
    result_status: EventStatus;
    provider: string | null;
    record_count: number | null;
    freshness: string | null;
    cache_status: string | null;
    error_reference: string | null;
  } | null;
  error: {
    code: string;
    category: string;
    message: string;
    retryable: boolean;
    attempt_count: number;
    safe_details: Record<string, unknown>;
  } | null;
  usage: {
    availability: "measured" | "estimated" | "unavailable";
    input_tokens: number | null;
    output_tokens: number | null;
    total_tokens: number | null;
    cost_amount: number | null;
    cost_currency: string | null;
    method: string | null;
    unavailable_reason: string | null;
  };
  retrieval: {
    strategy: string;
    sources: Array<{
      logical_kb: string;
      collection_version: string;
      source_id: string;
      chunk_id: string;
      rank: number;
      score: number | null;
      score_type: string | null;
    }>;
  } | null;
  summary: string;
  safe_metadata: Record<string, unknown>;
}

// M5 contract-verified resource types. The backend OpenAPI document remains authoritative.
export interface SessionRecord {
  session_id: string;
  label: string | null;
  state: "active" | "archived";
  created_at: string;
  updated_at: string;
  expires_at: string;
  archived_at: string | null;
}

export type StoredRunStatus =
  "running" | "completed" | "partial" | "failed" | "clarification";

export interface SafeError {
  code: string;
  category: string;
  message: string;
  retryable: boolean;
  attempt_count: number;
  safe_details: Record<string, unknown>;
}

export interface EvidenceReference {
  evidence_id: string;
  title: string;
  publisher: string;
  canonical_url: string;
  source_anchor: string | null;
}

export interface AgentResult {
  schema_version: "1";
  agent_id: string;
  status: "ok" | "partial" | "error" | "clarification";
  summary: string;
  facts: Array<Record<string, unknown>>;
  evidence: EvidenceReference[];
  visualization: Record<string, unknown> | null;
  as_of: string | null;
  warnings: string[];
  errors: SafeError[];
}

export interface WorkflowRunResult {
  schema_version: "1";
  execution_id: string;
  session_id: string;
  workflow_id: string;
  workflow_version: string;
  status: Exclude<StoredRunStatus, "running">;
  selected_agent_ids: string[];
  agent_results: AgentResult[];
  summary: string;
  warnings: string[];
  errors: SafeError[];
  trace_id: string | null;
  trace_unavailable_reason: string | null;
}

export interface RunRecord {
  execution_id: string;
  session_id: string;
  workflow_id: string;
  workflow_version: string;
  status: StoredRunStatus;
  request_message: string | null;
  result: WorkflowRunResult | null;
  created_at: string;
  updated_at: string;
}

export interface RunEventHistory {
  execution_id: string;
  events: RunEvent[];
  recovery: string;
}

export type ProviderCacheLayer =
  "memory" | "durable" | "provider" | "not_applicable";

export type ProviderCacheCoverage =
  | "complete"
  | "partial"
  | "stale"
  | "missing"
  | "unavailable"
  | "not_applicable";

export interface SessionList {
  items: SessionRecord[];
}

export interface RunList {
  items: RunRecord[];
}

export interface ApiErrorResponse {
  error: SafeError;
}

export interface PortfolioImportMetadata {
  portfolio_id: string;
  label: string | null;
  base_currency: string;
  imported_at: string;
}

export interface ManualHoldingRow {
  account_id: string;
  account_type: string;
  holding_id: string;
  identifier_type: string;
  identifier_value: string;
  quantity: string;
  currency: string;
  asset_class?: string;
  user_price?: string;
  user_price_as_of?: string;
  user_price_provenance?: string;
}

export type PortfolioImportApiRequest = {
  schema_version: "1";
  metadata: PortfolioImportMetadata;
  payload:
    | { kind: "manual"; rows: ManualHoldingRow[] }
    | {
        kind: "json" | "csv" | "xlsx";
        content_base64: string;
        filename: string;
      };
};

export interface ImportFinding {
  code: string;
  severity: "warning" | "error" | "fatal";
  scope: "file" | "row" | "field";
  message: string;
  row_number: number | null;
  field: string | null;
}

export interface ImportedHolding {
  holding_id: string;
  account_id: string;
  source_row: number;
  security: { identifier_type: string; value: string };
  quantity: string;
  currency: string;
  asset_class: string | null;
  user_price: string | null;
  user_price_as_of: string | null;
  user_price_provenance: string | null;
}

export interface ImportedPortfolio {
  schema_version: "1";
  portfolio_id: string;
  label: string | null;
  base_currency: string;
  imported_at: string;
  source_kind: "manual" | "json" | "csv" | "xlsx";
  source_file_hash: string;
  accounts: Array<{
    account_id: string;
    portfolio_id: string;
    account_type: string;
    institution_label: string | null;
    holdings: ImportedHolding[];
  }>;
}

export interface PortfolioImportResult {
  schema_version: "1";
  source_kind: "manual" | "json" | "csv" | "xlsx";
  source_file_hash: string;
  accepted: boolean;
  portfolio: ImportedPortfolio | null;
  findings: ImportFinding[];
}

export interface CalculationWarning {
  code: string;
  message: string;
  holding_id: string | null;
}

export interface HoldingValuation {
  holding_id: string;
  account_id: string;
  currency: string;
  quantity: string;
  price: string | null;
  price_source: "quote_set" | "user_import" | null;
  market_value: string | null;
  allocation_percent: string | null;
  asset_class: string | null;
}

export interface PortfolioSnapshot {
  schema_version: "1";
  snapshot_id: string;
  portfolio_id: string;
  calculated_at: string;
  calculation_policy_version: "finance-calculation-v1";
  quote_set_id: string;
  security_reference_ids: string[];
  base_currency: string;
  base_currency_total: string | null;
  totals_by_currency: Array<{
    currency: string;
    priced_value: string;
    priced_holding_count: number;
    total_holding_count: number;
    holding_count_coverage_percent: string;
  }>;
  holding_valuations: HoldingValuation[];
  concentrations: Array<{
    classification: "asset_class" | "sector";
    currency: string;
    category: string;
    market_value: string;
    percent_of_classified_value: string;
    classified_value_coverage_percent: string;
  }>;
  expense_metrics: Array<Record<string, unknown>>;
  diversification: Array<Record<string, unknown>>;
  unpriced_holding_ids: string[];
  warnings: CalculationWarning[];
}

export type ProviderStatus =
  | "success"
  | "empty"
  | "invalid_request"
  | "unauthorized"
  | "entitlement_required"
  | "rate_limited"
  | "timeout"
  | "malformed_response"
  | "unavailable"
  | "budget_exhausted"
  | "circuit_open"
  | "concurrency_limited";

export interface ProviderEnvelope {
  provider: string;
  mode: "live" | "credential_free";
  entitlement: string;
  served_at: string;
  retrieved_at: string | null;
  data_as_of: string | null;
  delay_status: string;
  timestamp_quality: string;
  cache_status: string;
  cache_layer: ProviderCacheLayer;
  cache_coverage: ProviderCacheCoverage;
  cache_age_seconds: number | null;
  is_stale: boolean;
  is_synthetic: boolean;
  request_id: string | null;
  attempts: number;
}

export interface ProviderError {
  code: string;
  message: string;
  retryable: boolean;
  retry_after_seconds: number | null;
}

export interface QuoteResult {
  status: ProviderStatus;
  quote: {
    requested_symbol: string;
    resolved_symbol: string;
    price: string;
    currency: string;
    currency_source: "request" | "provider";
  } | null;
  provenance: ProviderEnvelope;
  error: ProviderError | null;
  warnings: Array<{ code: string; message: string }>;
}

export interface PriceBar {
  trading_date: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string;
}

export interface HistoricalResult {
  status: ProviderStatus;
  series: {
    requested_symbol: string;
    resolved_symbol: string;
    currency: string;
    currency_source: "request" | "provider";
    adjustment_basis: "raw" | "adjusted" | "unknown";
    bars: PriceBar[];
  } | null;
  provenance: ProviderEnvelope;
  error: ProviderError | null;
  warnings: Array<{ code: string; message: string }>;
}

export interface GoalProjectionRequest {
  schema_version: "1";
  projection_id: string;
  currency: string;
  starting_amount: string;
  goal_amount: string | null;
  contribution_amount: string;
  contribution_frequency: "monthly" | "quarterly" | "annual";
  contribution_timing: "beginning" | "end";
  horizon_months: number;
  risk_tolerance: "conservative" | "moderate" | "aggressive" | "not_declared";
  cash_flow_summary_id: string | null;
  scenarios: Array<{
    label: string;
    annual_return_rate: string;
    annual_inflation_rate: string;
    annual_fee_rate: string;
  }>;
}

export interface GoalProjectionResult {
  schema_version: "1";
  projection_id: string;
  calculation_policy_version: "goal-projection-v1";
  currency: string;
  horizon_months: number;
  contribution_frequency: string;
  contribution_timing: string;
  risk_tolerance: string;
  cash_flow_summary_id: string | null;
  scenarios: Array<{
    label: string;
    nominal_future_value: string;
    inflation_adjusted_value: string;
    total_contributions: string;
    modeled_growth: string;
    nominal_shortfall_or_surplus: string | null;
    contribution_count: number;
    annual_return_rate: string;
    annual_inflation_rate: string;
    annual_fee_rate: string;
  }>;
  warnings: string[];
}

export interface BrowserTelemetryEvent {
  schema_version: "1";
  kind: "navigation" | "api_timing" | "web_vital" | "error_boundary";
  page:
    | "shell"
    | "assistant"
    | "portfolio"
    | "market"
    | "goals"
    | "history"
    | "inspector";
  api_route?: string;
  status_class?: "2xx" | "4xx" | "5xx" | "network_error";
  failure_category?: string;
  duration_ms?: number;
  metric_name?: "CLS" | "FCP" | "INP" | "LCP" | "TTFB";
  metric_value?: number;
  rating?: "good" | "needs-improvement" | "poor";
  trace_id?: string;
  request_id?: string;
}

export interface SseFrame {
  id: string;
  event: "run_event" | "response_chunk";
  data:
    | RunEvent
    | {
        execution_id: string;
        chunk_id: string;
        text: string;
        terminal: boolean;
      };
}
