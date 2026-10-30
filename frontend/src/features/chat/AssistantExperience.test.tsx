import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import type { RunRecord } from "../../types/contracts";
import { RunCard } from "./AssistantExperience";

test("shows the asked question and formats a safe Markdown response", () => {
  const question = "What's the difference between ETFs and mutual funds?";
  const answer = `**ETFs and mutual funds both pool investors’ money.**

| Feature | ETFs | Mutual funds |
|---|---|---|
| Pricing | Intraday | End of day |

<img src="invalid" onerror="alert('unsafe')">`;
  const run = {
    execution_id: "run-markdown",
    session_id: "session-test",
    workflow_id: "finance-assistant",
    workflow_version: "1",
    status: "completed",
    request_message: question,
    result: {
      schema_version: "1",
      execution_id: "run-markdown",
      session_id: "session-test",
      workflow_id: "finance-assistant",
      workflow_version: "1",
      status: "completed",
      selected_agent_ids: ["finance_qa"],
      agent_results: [
        {
          schema_version: "1",
          agent_id: "finance_qa",
          status: "ok",
          summary: answer,
          facts: [],
          evidence: [],
          visualization: null,
          as_of: null,
          warnings: [],
          errors: [],
        },
      ],
      summary: answer,
      warnings: [],
      errors: [],
      trace_id: null,
      trace_unavailable_reason: null,
    },
    created_at: "2026-10-29T20:38:00Z",
    updated_at: "2026-10-29T20:38:01Z",
  } satisfies RunRecord & { request_message: string };

  const { container } = render(<RunCard isLatest run={run} />);

  const renderedQuestion = screen.queryByText(question);
  const renderedAnswer = screen.queryByText(
    "ETFs and mutual funds both pool investors’ money.",
    { selector: "strong" },
  );
  expect.soft(renderedQuestion?.tagName).toBe("STRONG");
  expect.soft(renderedAnswer).toBeInTheDocument();
  expect
    .soft(
      Boolean(
        renderedQuestion &&
        renderedAnswer &&
        renderedQuestion.compareDocumentPosition(renderedAnswer) &
          Node.DOCUMENT_POSITION_FOLLOWING,
      ),
    )
    .toBe(true);
  expect.soft(screen.queryByRole("table")).toBeInTheDocument();
  expect
    .soft(screen.queryByRole("columnheader", { name: "Feature" }))
    .toBeInTheDocument();
  expect
    .soft(screen.queryByRole("cell", { name: "Intraday" }))
    .toBeInTheDocument();
  expect.soft(container.querySelector("img")).not.toBeInTheDocument();
});
