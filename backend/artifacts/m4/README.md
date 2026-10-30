# M4 evidence bundle

This directory contains privacy-safe evidence for the M4 LangGraph and six-agent milestone.

- `graph.mermaid` is emitted from the compiled graph definition.
- `routing-confusion-matrix.v1.json` summarizes the versioned 44-case scripted model-routing contract dataset, including two explicit out-of-scope cases. It is not evidence of live-model semantic accuracy.
- `run-event-trace-sample.v1.json` captures one credential-free Finance Q&A execution and its correlated OpenTelemetry spans. It contains fixture identifiers and no prompt, holding, transaction, credential, or hidden-reasoning payload.
- `failure-examples.v1.json` maps bounded failure behavior to automated tests.
- `test-results.json` records the final focused and repository qualification commands.

LangSmith was not configured for the original qualification. A later privacy-hidden synthetic verification delivered a root run named `finance-assistant` to project `ai_finance_assistant`; no external identifier or payload is retained in this bundle. Automated tests verify that the adapter is disabled by default, hides inputs and outputs when enabled, and assigns the workflow identifier to the root trace.
