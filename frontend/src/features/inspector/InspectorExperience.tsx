import { useQuery } from "@tanstack/react-query";
import {
  Background,
  Controls,
  MarkerType,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Crosshair, RefreshCw, Radio } from "lucide-react";
import { useMemo, useState } from "react";

import { PageHeader } from "../../components/PageHeader";
import { StateNotice } from "../../components/StateNotice";
import { api, readRunStream } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import type { RunEvent } from "../../types/contracts";
import {
  buildInspectorModel,
  formatSequencePositions,
  isRunEvent,
} from "./inspectorModel";

function shortId(value: string | null): string {
  if (!value) return "Not available";
  return value.length > 20 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value;
}

function humanize(value: string): string {
  return value.replaceAll("_", " ");
}

function metadataValue(value: unknown): string {
  if (value === null) return "Not available";
  if (["string", "number", "boolean"].includes(typeof value))
    return String(value);
  return "Structured value withheld from this compact view";
}

function RunEventDetails({ event }: { event: RunEvent }) {
  return (
    <section
      className="panel inspector-details"
      aria-labelledby="event-detail-heading"
    >
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Recorded event #{event.sequence}</p>
          <h3 id="event-detail-heading">{humanize(event.event_type)}</h3>
        </div>
        <span className={`inspector-status status-${event.status}`}>
          {event.status}
        </span>
      </div>

      <p className="inspector-event-summary">{event.summary}</p>
      <dl className="inspector-detail-grid">
        <div>
          <dt>Node</dt>
          <dd>{event.node_id}</dd>
        </div>
        <div>
          <dt>Agent</dt>
          <dd>{event.agent_id ?? "Not applicable"}</dd>
        </div>
        <div>
          <dt>Started</dt>
          <dd>{formatDateTime(event.started_at)}</dd>
        </div>
        <div>
          <dt>Completed</dt>
          <dd>{formatDateTime(event.completed_at)}</dd>
        </div>
        <div>
          <dt>Measured duration</dt>
          <dd>
            {event.duration_ms === null
              ? `Not available — ${event.duration_unavailable_reason ?? "no reason recorded"}`
              : `${event.duration_ms} ms`}
          </dd>
        </div>
        <div>
          <dt>Parent event</dt>
          <dd>{event.parent_event_id ?? "Not recorded"}</dd>
        </div>
      </dl>

      {event.routing ? (
        <div className="inspector-evidence-block">
          <h4>Recorded routing decision</h4>
          <p>
            Outcome: {event.routing.outcome}. Reason category:{" "}
            {event.routing.reason_category}.
          </p>
          <p>
            Selected nodes:{" "}
            {event.routing.selected_node_ids.length
              ? event.routing.selected_node_ids.join(", ")
              : "None recorded"}
          </p>
        </div>
      ) : null}

      {event.tool_result ? (
        <div className="inspector-evidence-block">
          <h4>Safe tool result</h4>
          <p>
            {event.tool_name ?? "Tool"}: {event.tool_result.result_status}
            {event.tool_result.provider
              ? ` via ${event.tool_result.provider}`
              : ""}
            {event.tool_result.record_count === null
              ? ""
              : ` · ${event.tool_result.record_count} records`}
          </p>
          <p>
            Cache: {event.tool_result.cache_status ?? "Not available"} ·
            Freshness: {event.tool_result.freshness ?? "Not available"}
          </p>
        </div>
      ) : null}

      {event.retrieval ? (
        <div className="inspector-evidence-block">
          <h4>Retrieval sources</h4>
          <p>Strategy: {event.retrieval.strategy}</p>
          {event.retrieval.sources.length ? (
            <ol className="inspector-source-list">
              {event.retrieval.sources.map((source) => (
                <li key={`${source.collection_version}:${source.chunk_id}`}>
                  <strong>{source.logical_kb}</strong> · collection{" "}
                  {source.collection_version} · source {source.source_id} ·
                  chunk {source.chunk_id} · rank {source.rank}
                  {source.score === null
                    ? ""
                    : ` · ${source.score_type ?? "score"} ${source.score}`}
                </li>
              ))}
            </ol>
          ) : (
            <p>No source records were recorded.</p>
          )}
        </div>
      ) : null}

      <div className="inspector-evidence-block">
        <h4>Model usage and cost</h4>
        {event.usage.availability === "unavailable" ? (
          <p>
            Not available —{" "}
            {event.usage.unavailable_reason ?? "no reason recorded"}
          </p>
        ) : (
          <p>
            {event.usage.total_tokens ?? "Unknown"} total tokens
            {event.usage.input_tokens === null
              ? ""
              : ` · ${event.usage.input_tokens} input`}
            {event.usage.output_tokens === null
              ? ""
              : ` · ${event.usage.output_tokens} output`}{" "}
            · {event.usage.availability} by {event.usage.method}
          </p>
        )}
        <p>
          Cost:{" "}
          {event.usage.cost_amount === null
            ? `Not available — ${event.usage.cost_unavailable_reason ?? "no reason recorded"}`
            : `${event.usage.cost_amount} ${event.usage.cost_currency}`}
        </p>
      </div>

      {event.error ? (
        <StateNotice tone="error" title={event.error.code}>
          {event.error.message} Attempt {event.error.attempt_count}.
        </StateNotice>
      ) : null}

      {Object.keys(event.safe_metadata).length ? (
        <div className="inspector-evidence-block">
          <h4>Allow-listed metadata</h4>
          <dl className="inspector-metadata-list">
            {Object.entries(event.safe_metadata).map(([key, value]) => (
              <div key={key}>
                <dt>{humanize(key)}</dt>
                <dd>{metadataValue(value)}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}
    </section>
  );
}

export function InspectorExperience({ sessionId }: { sessionId: string }) {
  const [requestedExecutionId, setRequestedExecutionId] = useState("");
  const [selectedEventId, setSelectedEventId] = useState("");
  const [streamEventsByExecution, setStreamEventsByExecution] = useState<
    Record<string, RunEvent[]>
  >({});
  const [streamError, setStreamError] = useState<string | null>(null);
  const [isReconnecting, setIsReconnecting] = useState(false);

  const runs = useQuery({
    queryKey: ["runs", sessionId, "inspector"],
    queryFn: () => api.listRuns(sessionId),
  });

  const selectedExecutionId = runs.data?.items.some(
    (run) => run.execution_id === requestedExecutionId,
  )
    ? requestedExecutionId
    : (runs.data?.items[0]?.execution_id ?? "");

  const history = useQuery({
    queryKey: ["run-events", sessionId, selectedExecutionId],
    queryFn: () => api.runEvents(sessionId, selectedExecutionId),
    enabled: Boolean(selectedExecutionId),
  });

  const model = useMemo(
    () =>
      buildInspectorModel(
        [
          ...(history.data?.events ?? []),
          ...(streamEventsByExecution[selectedExecutionId] ?? []),
        ],
        selectedExecutionId,
      ),
    [history.data, selectedExecutionId, streamEventsByExecution],
  );

  const effectiveSelectedEventId = model.events.some(
    (event) => event.event_id === selectedEventId,
  )
    ? selectedEventId
    : (model.events.at(-1)?.event_id ?? "");

  const selectedEvent =
    model.events.find((event) => event.event_id === effectiveSelectedEventId) ??
    null;
  const selectedRun = runs.data?.items.find(
    (run) => run.execution_id === selectedExecutionId,
  );
  const isSynthetic = model.events.some((event) => {
    const provider = event.tool_result?.provider?.toLowerCase() ?? "";
    return (
      "fixture_version" in event.safe_metadata ||
      ["fake", "synthetic", "deterministic"].some((marker) =>
        provider.includes(marker),
      )
    );
  });

  const graphNodes: Node[] = model.nodes.map((node) => ({
    id: node.id,
    position: { x: node.x, y: node.y },
    data: {
      label: (
        <span className="inspector-node-label">
          <strong>{node.label}</strong>
          <small className="inspector-node-sequences">
            Events {formatSequencePositions(node.sequences)}
          </small>
          <small>
            {node.eventIds.length} recorded event
            {node.eventIds.length === 1 ? "" : "s"} · {node.status}
          </small>
        </span>
      ),
    },
    className: `inspector-node status-${node.status}`,
  }));
  const graphEdges: Edge[] = model.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label: edge.kind === "recorded_route" ? "route" : "parent",
    markerEnd: { type: MarkerType.ArrowClosed },
  }));

  const reconnect = async () => {
    if (!selectedExecutionId) return;
    setIsReconnecting(true);
    setStreamError(null);
    try {
      const lastEventId = model.events.at(-1)?.event_id;
      const frames = await readRunStream(
        sessionId,
        selectedExecutionId,
        lastEventId,
        "inspector",
      );
      setStreamEventsByExecution((current) => ({
        ...current,
        [selectedExecutionId]: [
          ...(current[selectedExecutionId] ?? []),
          ...frames
            .filter((frame) => frame.event === "run_event")
            .map((frame) => frame.data)
            .filter(isRunEvent),
        ],
      }));
      await history.refetch();
    } catch {
      setStreamError(
        "The event stream could not resume. Persisted event history remains authoritative.",
      );
    } finally {
      setIsReconnecting(false);
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="Measured execution evidence"
        title="Agent execution inspector"
        description="Inspect persisted RunEvents. Dynamic nodes and edges appear only when a recorded event supports them."
        action={
          <span className="milestone-chip status-ready">M7 measured view</span>
        }
      />

      {runs.isPending ? (
        <StateNotice title="Loading authorized Runs" />
      ) : runs.isError ? (
        <StateNotice tone="error" title="Runs could not be loaded">
          The selected Session remains unchanged. Retry when the backend is
          available.
        </StateNotice>
      ) : !runs.data.items.length ? (
        <section
          className="empty-state"
          aria-labelledby="inspector-empty-heading"
        >
          <Crosshair aria-hidden="true" size={34} />
          <h3 id="inspector-empty-heading">No recorded Runs in this Session</h3>
          <p>
            Complete an Assistant request first. The Inspector will then load
            its persisted execution evidence without reconstructing a path from
            the response.
          </p>
        </section>
      ) : (
        <div className="inspector-experience">
          <section
            className="panel inspector-toolbar"
            aria-labelledby="run-selector-heading"
          >
            <div>
              <p className="eyebrow">Authorized Session history</p>
              <h3 id="run-selector-heading">Select a Run</h3>
            </div>
            <label className="field inspector-run-selector">
              Recorded Run
              <select
                value={selectedExecutionId}
                onChange={(event) => {
                  setRequestedExecutionId(event.target.value);
                  setSelectedEventId("");
                  setStreamError(null);
                }}
              >
                {runs.data.items.map((run) => (
                  <option key={run.execution_id} value={run.execution_id}>
                    Run {shortId(run.execution_id)} · {run.status} ·{" "}
                    {formatDateTime(run.created_at)}
                  </option>
                ))}
              </select>
            </label>
            <button
              className="secondary-button"
              disabled={
                !selectedExecutionId || history.isPending || isReconnecting
              }
              onClick={() => void reconnect()}
              type="button"
            >
              {isReconnecting ? (
                <RefreshCw className="spin" aria-hidden="true" size={17} />
              ) : (
                <Radio aria-hidden="true" size={17} />
              )}
              {isReconnecting ? "Resuming…" : "Resume event stream"}
            </button>
          </section>

          {streamError ? (
            <StateNotice tone="warning" title="Live reconnect unavailable">
              {streamError}
            </StateNotice>
          ) : null}
          {isSynthetic ? (
            <StateNotice tone="warning" title="Synthetic fixture evidence">
              Recorded metadata identifies deterministic, fake, or synthetic
              fixture evidence. This execution is not presented as a live
              provider run.
            </StateNotice>
          ) : null}

          {history.isPending ? (
            <StateNotice title="Loading persisted RunEvents" />
          ) : history.isError ? (
            <StateNotice tone="error" title="RunEvents could not be loaded">
              No execution path is shown because the authoritative event history
              is unavailable.
            </StateNotice>
          ) : (
            <>
              <section
                className="panel inspector-correlation"
                aria-labelledby="correlation-heading"
              >
                <div>
                  <p className="eyebrow">Support correlation</p>
                  <h3 id="correlation-heading">Recorded identifiers</h3>
                </div>
                <dl>
                  <div>
                    <dt>Execution</dt>
                    <dd>{selectedExecutionId}</dd>
                  </div>
                  <div>
                    <dt>Workflow</dt>
                    <dd>
                      {selectedRun?.workflow_id ?? "Not available"} @{" "}
                      {selectedRun?.workflow_version ?? "unknown"}
                    </dd>
                  </div>
                  <div>
                    <dt>Trace</dt>
                    <dd>
                      {model.events[0]?.trace_id ??
                        `Not available — ${model.events[0]?.trace_unavailable_reason ?? "no reason recorded"}`}
                    </dd>
                  </div>
                </dl>
              </section>

              {model.duplicateCount || model.missingSequenceCount ? (
                <StateNotice tone="warning" title="Recovered event ordering">
                  {model.duplicateCount} duplicate event
                  {model.duplicateCount === 1 ? " was" : "s were"} removed;{" "}
                  {model.missingSequenceCount} sequence position
                  {model.missingSequenceCount === 1 ? " is" : "s are"} not
                  present in the loaded history.
                </StateNotice>
              ) : null}

              {!model.events.length ? (
                <StateNotice title="No persisted events for this Run">
                  The Inspector does not infer a path from the Run status or
                  final response.
                </StateNotice>
              ) : (
                <div className="inspector-grid">
                  <section
                    className="panel inspector-graph-panel"
                    aria-labelledby="graph-heading"
                  >
                    <div className="panel-heading">
                      <div>
                        <p className="eyebrow">Recorded relationships only</p>
                        <h3 id="graph-heading">Measured execution graph</h3>
                      </div>
                    </div>
                    <p className="recovery-note inspector-graph-sequence-note">
                      Node labels list exact persisted event sequence positions.
                      Ranges contain only consecutive positions; parallel
                      branches may interleave.
                    </p>
                    <div
                      className="inspector-graph"
                      aria-label="Measured execution graph"
                    >
                      <ReactFlow
                        edges={graphEdges}
                        fitView
                        nodes={graphNodes}
                        nodesConnectable={false}
                        nodesDraggable={false}
                        panOnDrag
                      >
                        <Background />
                        <Controls showInteractive={false} />
                      </ReactFlow>
                    </div>
                    {!model.edges.length ? (
                      <p className="recovery-note">
                        No recorded cross-node relationship is available. Nodes
                        are shown without inferred edges.
                      </p>
                    ) : null}
                  </section>

                  <section
                    className="panel inspector-timeline"
                    aria-labelledby="timeline-heading"
                  >
                    <div className="panel-heading">
                      <div>
                        <p className="eyebrow">Accessible graph alternative</p>
                        <h3 id="timeline-heading">Ordered event timeline</h3>
                      </div>
                    </div>
                    <ol>
                      {model.events.map((event) => (
                        <li key={event.event_id}>
                          <button
                            aria-current={
                              event.event_id === effectiveSelectedEventId
                                ? "true"
                                : undefined
                            }
                            className={
                              event.event_id === effectiveSelectedEventId
                                ? "active"
                                : ""
                            }
                            onClick={() => setSelectedEventId(event.event_id)}
                            type="button"
                          >
                            <span>
                              <strong>#{event.sequence}</strong>{" "}
                              {humanize(event.event_type)}
                            </span>
                            <small>
                              {event.node_id} · {event.status} ·{" "}
                              {event.duration_ms === null
                                ? "duration unavailable"
                                : `${event.duration_ms} ms`}
                            </small>
                          </button>
                        </li>
                      ))}
                    </ol>
                  </section>
                </div>
              )}

              {selectedEvent ? <RunEventDetails event={selectedEvent} /> : null}

              <p className="recovery-note inspector-recovery">
                Recovery: {history.data?.recovery ?? "Not available"}. Response
                cache activity is not shown until M6.1 records it through this
                same generic RunEvent interface.
              </p>
            </>
          )}
        </div>
      )}
    </>
  );
}
