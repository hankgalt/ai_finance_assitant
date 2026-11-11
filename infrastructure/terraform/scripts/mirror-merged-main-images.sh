#!/usr/bin/env bash

# Mirror the two images built from the current merged main commit from GHCR to
# Artifact Registry. Repeated runs against identical state perform read-only
# verification and skip every repository, Docker-config, and registry write.

set -euo pipefail

readonly REPOSITORY="hankgalt/ai_finance_assitant"
readonly PROJECT_ID="comfforts-369117"
readonly AR_HOST="us-west1-docker.pkg.dev"
readonly GHCR_ROOT="ghcr.io/hankgalt"
readonly AR_ROOT="$AR_HOST/$PROJECT_ID/aifa-containers"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(cd -- "$SCRIPT_DIR/../../.." && pwd)"

# Keep operator output explicit and send failures to stderr with a nonzero exit.
info() {
  printf 'INFO: %s\n' "$1"
}

fail() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

# Require every local dependency before attempting an authenticated operation.
require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "$1 is required but is not available on PATH."
}

# Return success only when Docker already delegates this registry to gcloud.
# This read-before-write check prevents configure-docker from touching the
# Docker configuration on an identical second run.
docker_auth_is_configured() {
  local config_root config_file

  if [[ -n "${DOCKER_CONFIG:-}" ]]; then
    config_root="$DOCKER_CONFIG"
  elif [[ -n "${HOME:-}" ]]; then
    config_root="$HOME/.docker"
  else
    return 1
  fi
  config_file="$config_root/config.json"
  [[ -r "$config_file" ]] || return 1
  jq -e --arg host "$AR_HOST" '.credHelpers[$host] == "gcloud"' \
    "$config_file" >/dev/null 2>&1
}

# Resolve and validate the immutable digest behind a registry tag or reference.
resolve_manifest_digest() {
  local reference="$1"
  local manifest digest

  manifest=$(docker buildx imagetools inspect "$reference" \
    --format '{{json .Manifest}}' 2>/dev/null) || return 1
  digest=$(printf '%s\n' "$manifest" | jq -er \
    '.digest | strings | select(test("^sha256:[0-9a-f]{64}$"))' 2>/dev/null) || return 1
  printf '%s' "$digest"
}

# Add the merged-main tag only when absent. A matching tag is a no-op, while a
# conflicting tag fails closed because revision tags are treated as immutable.
copy_manifest_if_needed() {
  local label="$1"
  local source_repository="$2"
  local source_digest="$3"
  local target_repository="$4"
  local target_tag existing_digest

  target_tag="$target_repository:$MAIN_SHA"
  if existing_digest=$(resolve_manifest_digest "$target_tag"); then
    if [[ "$existing_digest" == "$source_digest" ]]; then
      info "$label manifest is already mirrored at $target_tag; skipping copy."
      return
    fi
    fail "$target_tag already exists with $existing_digest; refusing to replace it with $source_digest."
  fi

  info "Copying $label manifest to $target_tag."
  docker buildx imagetools create --prefer-index=false \
    --tag "$target_tag" \
    "$source_repository@$source_digest" >/dev/null || \
    fail "Failed to copy the $label manifest into Artifact Registry."
}

# Independently confirm that the Artifact Registry API resolves the expected
# digest, rather than relying only on Docker's registry view.
verify_gcloud_digest() {
  local label="$1"
  local reference="$2"
  local expected_digest="$3"
  local resolved_digest

  resolved_digest=$(gcloud artifacts docker images describe "$reference" \
    --project="$PROJECT_ID" \
    --format='value(image_summary.digest)' 2>/dev/null) || \
    fail "gcloud could not resolve the mirrored $label image $reference."
  [[ "$resolved_digest" == "$expected_digest" ]] || \
    fail "gcloud resolved $label as $resolved_digest instead of $expected_digest."
  info "gcloud resolved the $label image at $expected_digest."
}

# Step 1: validate local tooling without changing repository or cloud state.
for tool in git gh gcloud docker jq; do
  require_command "$tool"
done
docker buildx version >/dev/null 2>&1 || fail "Docker Buildx is required but is not usable."

# Step 2: move to a clean main checkout only when necessary. Dirty work is
# never carried across branches or hidden by the operator workflow.
CURRENT_BRANCH=$(git -C "$REPO_ROOT" branch --show-current) || \
  fail "Could not resolve the current Git branch."
if [[ "$CURRENT_BRANCH" != "main" ]]; then
  if [[ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]]; then
    fail "The working tree is not clean; commit, stash, or remove local changes before switching to main."
  fi
  git -C "$REPO_ROOT" switch main >/dev/null || fail "Could not switch the repository to main."
else
  info "The repository is already on main; skipping branch switch."
fi
if [[ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]]; then
  fail "The main working tree is not clean; commit, stash, or remove local changes before mirroring images."
fi

# Step 3: verify authenticated CLIs and resolve GitHub's authoritative main SHA.
gh auth status >/dev/null 2>&1 || fail "GitHub CLI is installed but is not authenticated."
ACTIVE_GCLOUD_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null) || \
  fail "Could not inspect the active gcloud account."
[[ -n "$ACTIVE_GCLOUD_ACCOUNT" ]] || fail "gcloud has no active authenticated account."

MAIN_SHA=$(gh api "repos/$REPOSITORY/commits/main" --jq .sha 2>/dev/null) || \
  fail "GitHub CLI could not resolve the current main commit."
[[ "$MAIN_SHA" =~ ^[0-9a-f]{40}$ ]] || fail "GitHub returned an invalid main commit SHA."
LOCAL_SHA=$(git -C "$REPO_ROOT" rev-parse HEAD) || fail "Could not resolve the local main commit."
if [[ "$LOCAL_SHA" != "$MAIN_SHA" ]]; then
  info "Fast-forwarding local main from $LOCAL_SHA to $MAIN_SHA."
  git -C "$REPO_ROOT" pull --ff-only origin main >/dev/null || \
    fail "Could not fast-forward local main from origin/main."
  LOCAL_SHA=$(git -C "$REPO_ROOT" rev-parse HEAD) || \
    fail "Could not resolve local main after the fast-forward."
else
  info "Local main already matches GitHub main; skipping pull."
fi
# A pull is accepted only when it lands on the exact SHA returned by GitHub.
[[ "$LOCAL_SHA" == "$MAIN_SHA" ]] || \
  fail "Local main is $LOCAL_SHA but GitHub main is $MAIN_SHA; synchronize the checkout and retry."

info "Using merged main commit $MAIN_SHA."
info "GHCR root: $GHCR_ROOT"
info "Artifact Registry root: $AR_ROOT"
# Step 4: configure the Artifact Registry credential helper only when missing.
if docker_auth_is_configured; then
  info "Docker authentication for $AR_HOST is already configured; skipping update."
else
  gcloud auth configure-docker "$AR_HOST" --quiet >/dev/null || \
    fail "Failed to configure Docker authentication for $AR_HOST."
  docker_auth_is_configured || \
    fail "Docker authentication configuration for $AR_HOST was not persisted as expected."
fi

BACKEND_GHCR_REPOSITORY="$GHCR_ROOT/ai-finance-assitant-backend"
FRONTEND_GHCR_REPOSITORY="$GHCR_ROOT/ai-finance-assitant-frontend"
BACKEND_AR_REPOSITORY="$AR_ROOT/finance-assistant-backend"
FRONTEND_AR_REPOSITORY="$AR_ROOT/finance-assistant-frontend"

# Step 5: resolve both source digests before attempting either manifest copy.
BACKEND_DIGEST=$(resolve_manifest_digest "$BACKEND_GHCR_REPOSITORY:$MAIN_SHA") || \
  fail "Could not resolve the merged-main backend digest from GHCR."
FRONTEND_DIGEST=$(resolve_manifest_digest "$FRONTEND_GHCR_REPOSITORY:$MAIN_SHA") || \
  fail "Could not resolve the merged-main frontend digest from GHCR."
info "Backend GHCR digest: $BACKEND_DIGEST"
info "Frontend GHCR digest: $FRONTEND_DIGEST"

# Step 6: copy only missing revision tags; this is safe to resume after a
# partial run because an already-copied image is detected and skipped.
copy_manifest_if_needed \
  "backend" "$BACKEND_GHCR_REPOSITORY" "$BACKEND_DIGEST" "$BACKEND_AR_REPOSITORY"
copy_manifest_if_needed \
  "frontend" "$FRONTEND_GHCR_REPOSITORY" "$FRONTEND_DIGEST" "$FRONTEND_AR_REPOSITORY"

# Step 7: require digest equality through both Docker and the gcloud API.
BACKEND_AR_DIGEST=$(resolve_manifest_digest "$BACKEND_AR_REPOSITORY:$MAIN_SHA") || \
  fail "Could not resolve the backend digest from Artifact Registry after mirroring."
FRONTEND_AR_DIGEST=$(resolve_manifest_digest "$FRONTEND_AR_REPOSITORY:$MAIN_SHA") || \
  fail "Could not resolve the frontend digest from Artifact Registry after mirroring."
[[ "$BACKEND_AR_DIGEST" == "$BACKEND_DIGEST" ]] || \
  fail "Backend digest changed during mirroring: $BACKEND_DIGEST became $BACKEND_AR_DIGEST."
[[ "$FRONTEND_AR_DIGEST" == "$FRONTEND_DIGEST" ]] || \
  fail "Frontend digest changed during mirroring: $FRONTEND_DIGEST became $FRONTEND_AR_DIGEST."
info "Artifact Registry preserved both source manifest digests."

GCP_BACKEND_IMAGE="$BACKEND_AR_REPOSITORY@$BACKEND_AR_DIGEST"
GCP_FRONTEND_IMAGE="$FRONTEND_AR_REPOSITORY@$FRONTEND_AR_DIGEST"
verify_gcloud_digest "backend" "$GCP_BACKEND_IMAGE" "$BACKEND_AR_DIGEST"
verify_gcloud_digest "frontend" "$GCP_FRONTEND_IMAGE" "$FRONTEND_AR_DIGEST"

# Step 8: print copyable, non-secret digest references for local deployment.
printf '\nMirrored merged-main image references:\n'
printf "export GCP_BACKEND_IMAGE='%s'\n" "$GCP_BACKEND_IMAGE"
printf "export GCP_FRONTEND_IMAGE='%s'\n" "$GCP_FRONTEND_IMAGE"
