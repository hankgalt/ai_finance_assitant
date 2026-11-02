# Assistant workflow evidence

This directory contains privacy-safe evidence for the LangGraph workflow and six specialist agents.

- `workflow-graph.mermaid` is emitted from the compiled graph definition.
- `routing-evaluation.v1.json` summarizes the versioned 44-case scripted model-routing contract dataset, including two explicit out-of-scope cases. It is not evidence of live-model semantic accuracy.
- `failure-examples.v1.json` maps bounded failure behavior to automated tests.
- `backend/artifacts/observability/run-event-trace-sample.v1.json` captures one credential-free Finance Q&A execution and its correlated OpenTelemetry spans.
- `backend/artifacts/quality/assistant-test-results.json` records focused and repository qualification commands.

LangSmith was not configured for the original qualification. A later privacy-hidden synthetic verification delivered a root run named `finance-assistant` to project `ai_finance_assistant`; no external identifier or payload is retained in this bundle. Automated tests verify that the adapter is disabled by default, hides inputs and outputs when enabled, and assigns the workflow identifier to the root trace.

Milestone delivery history remains in `docs/M4_delivery_report.md`.
