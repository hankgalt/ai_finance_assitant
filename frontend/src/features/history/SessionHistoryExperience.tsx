import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, Eye, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "../../components/PageHeader";
import { StateNotice } from "../../components/StateNotice";
import { RunCard } from "../chat/AssistantExperience";
import { api, ClientApiError } from "../../lib/api";
import { formatDateTime } from "../../lib/format";

export function SessionHistoryExperience() {
  const queryClient = useQueryClient();
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(
    null,
  );
  const [deleteSessionId, setDeleteSessionId] = useState<string | null>(null);
  const sessions = useQuery({
    queryKey: ["archived-sessions"],
    queryFn: () => api.listSessions("archived"),
  });
  const runs = useQuery({
    queryKey: ["runs", selectedSessionId],
    queryFn: () => api.listRuns(selectedSessionId ?? ""),
    enabled: selectedSessionId !== null,
  });
  const remove = useMutation({
    mutationFn: (sessionId: string) => api.deleteSession(sessionId),
    onSuccess: async (_, sessionId) => {
      queryClient.removeQueries({ queryKey: ["runs", sessionId] });
      if (selectedSessionId === sessionId) setSelectedSessionId(null);
      setDeleteSessionId(null);
      await queryClient.invalidateQueries({ queryKey: ["archived-sessions"] });
    },
  });

  return (
    <>
      <PageHeader
        eyebrow="Session lifecycle"
        title="Session history"
        description="Archived Sessions are read-only and retain their saved conversation until you permanently delete them or local retention expires."
        action={<span className="milestone-chip">Archived only</span>}
      />

      {sessions.isPending ? (
        <StateNotice title="Loading archived Sessions" />
      ) : null}
      {sessions.isError ? (
        <StateNotice tone="error" title="Session history unavailable">
          <p>
            {sessions.error instanceof Error
              ? sessions.error.message
              : "Try again shortly."}
          </p>
          <button
            className="text-button"
            onClick={() => void sessions.refetch()}
            type="button"
          >
            <RefreshCw aria-hidden="true" size={15} /> Retry
          </button>
        </StateNotice>
      ) : null}
      {sessions.data?.items.length === 0 ? (
        <section className="empty-state" aria-labelledby="history-empty-title">
          <Archive aria-hidden="true" size={32} />
          <h3 id="history-empty-title">No archived Sessions</h3>
          <p>
            Clearing the active Session archives it here and opens a new empty
            Session.
          </p>
        </section>
      ) : null}
      {sessions.data?.items.length ? (
        <div className="history-layout">
          <section className="panel" aria-labelledby="archived-sessions-title">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Saved locally</p>
                <h3 id="archived-sessions-title">Archived Sessions</h3>
              </div>
            </div>
            <div className="history-list">
              {sessions.data.items.map((archived) => (
                <article key={archived.session_id}>
                  <div>
                    <strong>{archived.label ?? "Untitled Session"}</strong>
                    <span>
                      Archived{" "}
                      {formatDateTime(
                        archived.archived_at ?? archived.updated_at,
                      )}
                    </span>
                  </div>
                  {deleteSessionId === archived.session_id ? (
                    <div
                      aria-labelledby={`delete-${archived.session_id}`}
                      className="history-delete-confirmation"
                      role="group"
                    >
                      <strong id={`delete-${archived.session_id}`}>
                        Permanently delete this Session?
                      </strong>
                      <p>
                        Its runs, saved artifacts, and checkpoint cannot be
                        recovered.
                      </p>
                      {remove.isError ? (
                        <p className="clear-session-error" role="alert">
                          {remove.error instanceof ClientApiError
                            ? remove.error.message
                            : "The archived Session could not be deleted."}
                        </p>
                      ) : null}
                      <div className="history-actions">
                        <button
                          autoFocus
                          className="danger-button"
                          disabled={remove.isPending}
                          onClick={() => remove.mutate(archived.session_id)}
                          type="button"
                        >
                          {remove.isPending
                            ? "Deleting…"
                            : "Delete permanently"}
                        </button>
                        <button
                          className="text-button"
                          disabled={remove.isPending}
                          onClick={() => {
                            remove.reset();
                            setDeleteSessionId(null);
                          }}
                          type="button"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="history-actions">
                      <button
                        className="secondary-button"
                        onClick={() =>
                          setSelectedSessionId(archived.session_id)
                        }
                        type="button"
                      >
                        <Eye aria-hidden="true" size={15} /> View conversation
                      </button>
                      <button
                        className="history-delete-button"
                        onClick={() => {
                          remove.reset();
                          setDeleteSessionId(archived.session_id);
                        }}
                        type="button"
                      >
                        <Trash2 aria-hidden="true" size={15} /> Delete
                      </button>
                    </div>
                  )}
                </article>
              ))}
            </div>
          </section>

          {selectedSessionId ? (
            <section
              className="history-conversation"
              aria-labelledby="archived-conversation-title"
            >
              <div className="results-heading">
                <div>
                  <p className="eyebrow">Read-only</p>
                  <h3 id="archived-conversation-title">
                    Archived conversation
                  </h3>
                </div>
              </div>
              {runs.isPending ? (
                <StateNotice title="Loading conversation" />
              ) : null}
              {runs.isError ? (
                <StateNotice tone="error" title="Conversation unavailable">
                  <p>
                    {runs.error instanceof Error
                      ? runs.error.message
                      : "Try again."}
                  </p>
                </StateNotice>
              ) : null}
              {runs.data?.items.length === 0 ? (
                <StateNotice title="This Session has no saved Runs" />
              ) : null}
              {runs.data?.items.map((run, index) => (
                <RunCard
                  key={run.execution_id}
                  run={run}
                  isLatest={index === 0}
                />
              ))}
            </section>
          ) : null}
        </div>
      ) : null}
    </>
  );
}
