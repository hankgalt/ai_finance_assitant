import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUp, BookOpen, RefreshCw } from "lucide-react";
import { useState, type FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { PageHeader } from "../../components/PageHeader";
import { StateNotice } from "../../components/StateNotice";
import { api, ClientApiError, readRunStream } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import type { RunRecord } from "../../types/contracts";

function MarkdownNarrative({ children }: { children: string }) {
  return (
    <div className="markdown-narrative">
      <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml>
        {children}
      </ReactMarkdown>
    </div>
  );
}

export function RunCard({
  run,
  isLatest,
}: {
  run: RunRecord;
  isLatest: boolean;
}) {
  const result = run.result;
  const positionLabel = isLatest ? "Latest response" : "Earlier response";
  if (!result) {
    return (
      <article className="run-card">
        <div className="run-meta">
          <span className="run-position">{positionLabel}</span>
          <span>Run in progress · {formatDateTime(run.created_at)}</span>
        </div>
        <p>The workflow has not produced a terminal result yet.</p>
      </article>
    );
  }
  const seenSourceUrls = new Set<string>();
  const evidenceByAgent = new Map(
    result.agent_results.map((agent) => [
      agent.agent_id,
      agent.evidence.filter((source) => {
        if (seenSourceUrls.has(source.canonical_url)) return false;
        seenSourceUrls.add(source.canonical_url);
        return true;
      }),
    ]),
  );
  const seenSupplementalMessages = new Set<string>();
  const supplementalMessagesByAgent = new Map(
    result.agent_results.map((agent) => [
      agent.agent_id,
      [...agent.warnings, ...agent.errors.map((error) => error.message)].filter(
        (message) => {
          if (seenSupplementalMessages.has(message)) return false;
          seenSupplementalMessages.add(message);
          return true;
        },
      ),
    ]),
  );
  const workflowWarnings = result.warnings.filter((warning) => {
    if (seenSupplementalMessages.has(warning)) return false;
    seenSupplementalMessages.add(warning);
    return true;
  });
  return (
    <article className="run-card">
      <div className="run-meta">
        <span className="run-position">{positionLabel}</span>
        <span className="run-status">
          <span className={`result-label result-${result.status}`}>
            {result.status}
          </span>
          <span>{formatDateTime(run.updated_at)}</span>
        </span>
      </div>
      {run.request_message ? (
        <p className="run-question">
          <span>You asked</span>
          <strong>{run.request_message}</strong>
        </p>
      ) : null}
      {result.agent_results.length === 0 ? (
        <MarkdownNarrative>{result.summary}</MarkdownNarrative>
      ) : null}
      {result.agent_results.map((agent) => (
        <section className="agent-answer" key={agent.agent_id}>
          <div className="agent-heading">
            <strong>{agent.agent_id.replaceAll("_", " ")}</strong>
            {agent.as_of ? (
              <span>As of {formatDateTime(agent.as_of)}</span>
            ) : null}
          </div>
          <MarkdownNarrative>{agent.summary}</MarkdownNarrative>
          {evidenceByAgent.get(agent.agent_id)?.length ? (
            <ul className="citation-list" aria-label="Sources">
              {evidenceByAgent.get(agent.agent_id)?.map((source) => (
                <li key={source.evidence_id}>
                  <BookOpen aria-hidden="true" size={15} />
                  <a
                    href={source.canonical_url}
                    rel="noreferrer"
                    target="_blank"
                  >
                    {source.title} — {source.publisher}
                  </a>
                </li>
              ))}
            </ul>
          ) : null}
          {supplementalMessagesByAgent.get(agent.agent_id)?.map((warning) => (
            <p className="inline-warning" key={warning}>
              {warning}
            </p>
          ))}
        </section>
      ))}
      {workflowWarnings.map((warning) => (
        <p className="inline-warning" key={warning}>
          {warning}
        </p>
      ))}
      {result.trace_id ? (
        <p className="correlation">Trace available for support correlation.</p>
      ) : null}
    </article>
  );
}

export function AssistantExperience({ sessionId }: { sessionId: string }) {
  const [message, setMessage] = useState("");
  const [recoveryNote, setRecoveryNote] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const runs = useQuery({
    queryKey: ["runs", sessionId],
    queryFn: () => api.listRuns(sessionId),
  });
  const send = useMutation({
    mutationFn: (value: string) => api.createRun(sessionId, value),
    onSuccess: async (run) => {
      setMessage("");
      await queryClient.invalidateQueries({ queryKey: ["runs", sessionId] });
      try {
        const frames = await readRunStream(sessionId, run.execution_id);
        setRecoveryNote(
          frames.length
            ? `Stream synchronized through event ${frames.at(-1)?.id}.`
            : "The authoritative Run result was loaded; no additional stream events were available.",
        );
      } catch {
        setRecoveryNote(
          "Streaming was interrupted. The saved Run result remains available above.",
        );
      }
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = message.trim();
    if (value) send.mutate(value);
  };

  return (
    <>
      <PageHeader
        eyebrow="Six-agent finance workflow"
        title="Ask, explore, decide"
        description="Educational guidance is routed through the backend workflow. Sources, partial results, and unavailable evidence stay visible."
        action={<span className="milestone-chip">Session active</span>}
      />
      <div className="conversation-layout">
        <section className="conversation" aria-label="Conversation history">
          {runs.isPending ? (
            <StateNotice title="Loading saved conversation" />
          ) : null}
          {runs.isError ? (
            <StateNotice tone="error" title="Conversation unavailable">
              <p>
                {runs.error instanceof Error
                  ? runs.error.message
                  : "Try again shortly."}
              </p>
              <button
                className="text-button"
                onClick={() => void runs.refetch()}
                type="button"
              >
                <RefreshCw size={15} /> Retry
              </button>
            </StateNotice>
          ) : null}
          {runs.data?.items.length === 0 ? (
            <div className="welcome-panel">
              <p className="eyebrow">Start here</p>
              <h3>What would you like to understand?</h3>
              <p>
                Try asking about diversification, a financial concept, your
                saved portfolio, or a planning assumption.
              </p>
            </div>
          ) : null}
          {runs.data?.items.map((run, index) => (
            <RunCard key={run.execution_id} run={run} isLatest={index === 0} />
          ))}
          {send.isError ? (
            <StateNotice tone="error" title="Your message was not processed">
              {send.error instanceof ClientApiError
                ? send.error.message
                : "Please try again."}
            </StateNotice>
          ) : null}
          {recoveryNote ? (
            <p className="recovery-note" role="status">
              {recoveryNote}
            </p>
          ) : null}
        </section>
        <form className="composer" onSubmit={submit}>
          <label htmlFor="assistant-message">
            Message the finance assistant
          </label>
          <div>
            <textarea
              id="assistant-message"
              maxLength={20000}
              onChange={(event) => setMessage(event.target.value)}
              placeholder="How should I think about the concentration in my portfolio?"
              rows={3}
              value={message}
            />
            <button
              aria-label="Send message"
              className="send-button"
              disabled={!message.trim() || send.isPending}
              type="submit"
            >
              <ArrowUp aria-hidden="true" size={20} />
            </button>
          </div>
          <p>
            Educational information only. The assistant does not place trades or
            guarantee outcomes.
          </p>
        </form>
      </div>
    </>
  );
}
