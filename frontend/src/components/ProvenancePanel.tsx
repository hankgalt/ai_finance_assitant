import type { ProviderEnvelope } from "../types/contracts";
import { formatDateTime } from "../lib/format";

export function ProvenancePanel({
  provenance,
}: {
  provenance: ProviderEnvelope;
}) {
  return (
    <section className="provenance" aria-label="Data provenance and freshness">
      <div>
        <span>Source</span>
        <strong>{provenance.provider}</strong>
      </div>
      <div>
        <span>Data as of</span>
        <strong>{formatDateTime(provenance.data_as_of)}</strong>
      </div>
      <div>
        <span>Coverage</span>
        <strong>{provenance.cache_coverage.replaceAll("_", " ")}</strong>
      </div>
      <div>
        <span>Delivery</span>
        <strong>
          {provenance.is_synthetic
            ? "Synthetic demo data"
            : provenance.is_stale
              ? "Stale cached data"
              : provenance.cache_status.replaceAll("_", " ")}
        </strong>
      </div>
    </section>
  );
}
