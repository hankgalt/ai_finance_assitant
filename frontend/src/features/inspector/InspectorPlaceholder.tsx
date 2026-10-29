import { Crosshair } from "lucide-react";

import { PageHeader } from "../../components/PageHeader";
import { StateNotice } from "../../components/StateNotice";

export function InspectorPlaceholder() {
  return (
    <>
      <PageHeader
        eyebrow="Measured execution evidence"
        title="Agent execution inspector"
        description="The Inspector will render persisted RunEvents as the source of truth. It will never infer execution from an answer."
        action={<span className="milestone-chip">Scheduled for M7</span>}
      />
      <section
        className="empty-state"
        aria-labelledby="inspector-status-heading"
      >
        <Crosshair aria-hidden="true" size={34} />
        <h3 id="inspector-status-heading">Inspector not implemented yet</h3>
        <p>
          M6 supplies the shared product interface. Run selection, event
          timelines, and measured graph paths remain explicitly unavailable
          until M7 acceptance is complete.
        </p>
        <StateNotice title="No synthetic execution is shown">
          Use the Assistant for completed workflow results. This view does not
          imply that an Inspector trace exists.
        </StateNotice>
      </section>
    </>
  );
}
