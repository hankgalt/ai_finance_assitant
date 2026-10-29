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
  created_at: string;
  updated_at: string;
  expires_at: string;
}

export type StoredRunStatus =
  "running" | "completed" | "partial" | "failed" | "clarification";

export interface WorkflowRunResult {
  schema_version: "1";
  execution_id: string;
  session_id: string;
  workflow_id: string;
  workflow_version: string;
  status: Exclude<StoredRunStatus, "running">;
  selected_agent_ids: string[];
  agent_results: Array<Record<string, unknown>>;
  summary: string;
  warnings: string[];
  errors: Array<Record<string, unknown>>;
  trace_id: string | null;
  trace_unavailable_reason: string | null;
}

export interface RunRecord {
  execution_id: string;
  session_id: string;
  workflow_id: string;
  workflow_version: string;
  status: StoredRunStatus;
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
