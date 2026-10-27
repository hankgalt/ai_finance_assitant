import { syntheticRunEvents } from "./synthetic-events";

export function InspectorPlaceholder() {
  return (
    <section aria-labelledby="inspector-heading">
      <div className="notice" role="note">
        <strong>Synthetic fixture · M0 contract preview</strong>
        <span>
          These events are test data. LangGraph execution and live streaming
          begin in later milestones.
        </span>
      </div>

      <div className="section-heading">
        <div>
          <p className="eyebrow">Agent Execution Inspector</p>
          <h2 id="inspector-heading">Readable event timeline</h2>
        </div>
        <span className="schema-chip">RunEvent v1</span>
      </div>

      <ol className="timeline" aria-label="Synthetic run events">
        {syntheticRunEvents.map((event) => (
          <li key={event.event_id}>
            <div className="timeline-marker" aria-hidden="true" />
            <article>
              <div className="event-meta">
                <span>#{event.sequence}</span>
                <span>{event.event_type.replaceAll("_", " ")}</span>
                <span>{event.status}</span>
              </div>
              <h3>{event.summary}</h3>
              <dl>
                <div>
                  <dt>Node</dt>
                  <dd>{event.node_id}</dd>
                </div>
                <div>
                  <dt>Duration</dt>
                  <dd>
                    {event.duration_ms === null
                      ? "Not available"
                      : event.duration_ms + " ms"}
                  </dd>
                </div>
                <div>
                  <dt>Trace</dt>
                  <dd>{event.trace_id ?? "Not available"}</dd>
                </div>
              </dl>
            </article>
          </li>
        ))}
      </ol>
    </section>
  );
}
