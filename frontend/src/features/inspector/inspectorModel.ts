import type { EventStatus, RunEvent } from "../../types/contracts";

export type InspectorEdgeKind = "recorded_parent" | "recorded_route";

export interface InspectorGraphNode {
  id: string;
  label: string;
  status: EventStatus;
  firstSequence: number;
  sequences: number[];
  eventIds: string[];
  x: number;
  y: number;
}

export interface InspectorGraphEdge {
  id: string;
  source: string;
  target: string;
  kind: InspectorEdgeKind;
  evidenceEventId: string;
}

export interface InspectorModel {
  executionId: string | null;
  events: RunEvent[];
  nodes: InspectorGraphNode[];
  edges: InspectorGraphEdge[];
  duplicateCount: number;
  ignoredCrossExecutionCount: number;
  missingSequenceCount: number;
}

function eventOrder(left: RunEvent, right: RunEvent): number {
  return (
    left.sequence - right.sequence ||
    left.started_at.localeCompare(right.started_at) ||
    left.event_id.localeCompare(right.event_id)
  );
}

function humanizeIdentifier(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function formatSequencePositions(values: number[]): string {
  const sequences = [...new Set(values)].sort((left, right) => left - right);
  if (!sequences.length) return "No recorded positions";

  const ranges: string[] = [];
  let start = sequences[0]!;
  let end = start;
  for (const sequence of sequences.slice(1)) {
    if (sequence === end + 1) {
      end = sequence;
      continue;
    }
    ranges.push(start === end ? `#${start}` : `#${start}–#${end}`);
    start = sequence;
    end = sequence;
  }
  ranges.push(start === end ? `#${start}` : `#${start}–#${end}`);
  return ranges.join(", ");
}

export function buildInspectorModel(
  input: RunEvent[],
  expectedExecutionId?: string,
): InspectorModel {
  const sorted = [...input].sort(eventOrder);
  const executionId = expectedExecutionId ?? sorted[0]?.execution_id ?? null;
  const scoped = sorted.filter((event) => event.execution_id === executionId);
  const seen = new Set<string>();
  const events = scoped.filter((event) => {
    if (seen.has(event.event_id)) return false;
    seen.add(event.event_id);
    return true;
  });
  const duplicateCount = scoped.length - events.length;
  const ignoredCrossExecutionCount = sorted.length - scoped.length;

  const sequenceValues = [...new Set(events.map((event) => event.sequence))];
  const missingSequenceCount = sequenceValues.length
    ? Math.max(
        0,
        sequenceValues.at(-1)! - sequenceValues[0]! + 1 - sequenceValues.length,
      )
    : 0;

  const nodeEvents = new Map<string, RunEvent[]>();
  for (const event of events) {
    const existing = nodeEvents.get(event.node_id) ?? [];
    existing.push(event);
    nodeEvents.set(event.node_id, existing);
  }

  const nodes = [...nodeEvents.entries()]
    .map(([nodeId, recordedEvents]) => {
      const latest = recordedEvents.at(-1)!;
      return {
        id: nodeId,
        label: humanizeIdentifier(nodeId),
        status: latest.status,
        firstSequence: recordedEvents[0]!.sequence,
        sequences: recordedEvents.map((event) => event.sequence),
        eventIds: recordedEvents.map((event) => event.event_id),
      };
    })
    .sort((left, right) => left.firstSequence - right.firstSequence)
    .map((node, index) => ({
      ...node,
      x: (index % 3) * 250,
      y: Math.floor(index / 3) * 145,
    }));

  const recordedNodeIds = new Set(nodes.map((node) => node.id));
  const eventsById = new Map(events.map((event) => [event.event_id, event]));
  const edgeKeys = new Set<string>();
  const edges: InspectorGraphEdge[] = [];

  const addEdge = (
    source: string,
    target: string,
    kind: InspectorEdgeKind,
    evidenceEventId: string,
  ) => {
    if (
      source === target ||
      !recordedNodeIds.has(source) ||
      !recordedNodeIds.has(target)
    )
      return;
    const key = `${kind}:${source}:${target}`;
    if (edgeKeys.has(key)) return;
    edgeKeys.add(key);
    edges.push({
      id: key,
      source,
      target,
      kind,
      evidenceEventId,
    });
  };

  for (const event of events) {
    for (const selectedNodeId of event.routing?.selected_node_ids ?? []) {
      addEdge(event.node_id, selectedNodeId, "recorded_route", event.event_id);
    }
    if (event.parent_event_id) {
      const parent = eventsById.get(event.parent_event_id);
      if (parent) {
        addEdge(
          parent.node_id,
          event.node_id,
          "recorded_parent",
          event.event_id,
        );
      }
    }
  }

  return {
    executionId,
    events,
    nodes,
    edges,
    duplicateCount,
    ignoredCrossExecutionCount,
    missingSequenceCount,
  };
}

export function isRunEvent(value: unknown): value is RunEvent {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<RunEvent>;
  return (
    candidate.schema_version === "1" &&
    typeof candidate.event_id === "string" &&
    typeof candidate.execution_id === "string" &&
    typeof candidate.sequence === "number" &&
    typeof candidate.node_id === "string"
  );
}
