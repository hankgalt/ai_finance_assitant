import { Component, type ErrorInfo, type ReactNode } from "react";

import { emitBrowserTelemetry } from "../lib/telemetry";

export class ErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    void error;
    void info;
    emitBrowserTelemetry({
      kind: "error_boundary",
      page: "shell",
      failure_category: "internal",
    });
  }

  render() {
    if (this.state.failed) {
      return (
        <main className="fatal-state">
          <p className="eyebrow">Interface recovery</p>
          <h1>This view could not be displayed</h1>
          <p>
            Your saved backend data was not changed. Reload this interface to
            try again.
          </p>
          <button
            className="primary-button"
            onClick={() => this.setState({ failed: false })}
            type="button"
          >
            Try again
          </button>
        </main>
      );
    }
    return this.props.children;
  }
}
