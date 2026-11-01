# Backend and Inspector reconciliation

Contract version: `contracts/m7-inspector-contract.v1.json`

| Persisted RunEvent evidence | Inspector use |
| --- | --- |
| `execution_id`, `session_id`, workflow identity | Authorized Run selection and correlation |
| stable `event_id` | deduplication and SSE resume cursor |
| `sequence` and timestamps | ordered timeline plus exact node event-position labels; never an inferred graph edge |
| `node_id` | dynamic node identity |
| `parent_event_id` | recorded parent edge when both nodes exist |
| `routing.selected_node_ids` | recorded routing edge when both nodes exist |
| status and safe summary | node/timeline/detail presentation |
| duration and unavailable reason | measured value or explicit unavailable state |
| safe routing/tool/retrieval/usage/error fields | bounded detail sections |
| trace identity or unavailable reason | support correlation only |

The projection test feeds duplicate and out-of-order events, a sequence gap, an unrecorded routing
target, a recorded parent relationship, a failed node, and a second execution. It verifies that the
result contains one execution, stable ordering, exact node positions with only consecutive ranges,
no unrecorded target, no sequence-derived edge, and the measured failed status.

The Inspector never uses `RunRecord.result` or `request_message` to create execution evidence and
does not fetch an external trace viewer. The M5 event history remains the source of truth after an
SSE reconnect.
