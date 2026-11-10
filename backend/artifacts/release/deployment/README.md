# Deployment release evidence

- `delivery-controls.v1.json` records the locally qualified repository-side delivery controls and
  the external GitHub/GCP activation gates that remain pending.

Published image digests, attestations, Terraform plans, staging results, deployment records, and
rollback evidence belong here when their owning later slices run. Runtime credentials, Terraform
state, and secret values are never committed.
