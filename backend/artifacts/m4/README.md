# M4 evidence bundle

This directory contains privacy-safe evidence for the M4 LangGraph and six-agent milestone.

- `graph.mermaid` is emitted from the compiled graph definition.
- `routing-confusion-matrix.v1.json` summarizes the versioned 40-case routing dataset.
- `run-event-trace-sample.v1.json` captures one credential-free Finance Q&A execution and its correlated OpenTelemetry spans. It contains fixture identifiers and no prompt, holding, transaction, credential, or hidden-reasoning payload.
- `failure-examples.v1.json` maps bounded failure behavior to automated tests.
- `test-results.json` records the final focused and repository qualification commands.

LangSmith is optional and was not configured for qualification, so no external LangSmith trace was created. Automated tests verify that the adapter is disabled by default and, when enabled, constructs the client with inputs and outputs hidden.
