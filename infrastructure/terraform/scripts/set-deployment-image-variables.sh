#!/usr/bin/env bash

# Publish the mirrored merged-main image references as non-secret GitHub
# environment variables. Existing matching values are verified and left
# untouched so an identical repeated run performs no GitHub writes.

set -euo pipefail

readonly REPOSITORY="hankgalt/ai_finance_assitant"
readonly PROJECT_ID="comfforts-369117"
readonly AR_ROOT="us-west1-docker.pkg.dev/$PROJECT_ID/aifa-containers"

# Keep operator output explicit and send failures to stderr with a nonzero exit.
info() {
  printf 'INFO: %s\n' "$1"
}

fail() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

# Require authenticated-CLI dependencies before reading external state.
require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "$1 is required but is not available on PATH."
}

# Resolve a revision tag through Artifact Registry and accept only a sha256
# digest suitable for an immutable Terraform image reference.
resolve_artifact_digest() {
  local reference="$1"
  local digest

  digest=$(gcloud artifacts docker images describe "$reference" \
    --project="$PROJECT_ID" \
    --format='value(image_summary.digest)' 2>/dev/null) || return 1
  [[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]] || return 1
  printf '%s' "$digest"
}

# Read before writing: matching values are already verified and skipped;
# missing or changed values are written once and then read back exactly.
set_and_verify_variable() {
  local name="$1"
  local value="$2"
  local actual

  actual=$(gh variable list \
    --repo "$REPOSITORY" \
    --env "$ENVIRONMENT" \
    --json name,value \
    --jq ".[] | select(.name == \"$name\") | .value" 2>/dev/null) || \
    fail "Failed to inspect $name in the $ENVIRONMENT GitHub environment."
  if [[ "$actual" == "$value" ]]; then
    info "$name is already correct in the $ENVIRONMENT GitHub environment; skipping update."
    return
  fi

  gh variable set "$name" \
    --repo "$REPOSITORY" \
    --env "$ENVIRONMENT" \
    --body "$value" >/dev/null || \
    fail "Failed to set $name in the $ENVIRONMENT GitHub environment."
  actual=$(gh variable get "$name" \
    --repo "$REPOSITORY" \
    --env "$ENVIRONMENT" 2>/dev/null) || \
    fail "Failed to read back $name from the $ENVIRONMENT GitHub environment."
  [[ "$actual" == "$value" ]] || \
    fail "$name readback did not match the value written to the $ENVIRONMENT environment."
  info "Set and verified $name in the $ENVIRONMENT GitHub environment."
}

# Step 1: validate the optional environment selector and both authenticated CLIs.
[[ $# -le 1 ]] || fail "Usage: ${0##*/} [environment]"
ENVIRONMENT="${1:-staging}"
case "$ENVIRONMENT" in
  staging | production) ;;
  *) fail "Environment must be either staging or production." ;;
esac

for tool in gh gcloud; do
  require_command "$tool"
done
gh auth status >/dev/null 2>&1 || fail "GitHub CLI is installed but is not authenticated."
ACTIVE_GCLOUD_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null) || \
  fail "Could not inspect the active gcloud account."
[[ -n "$ACTIVE_GCLOUD_ACCOUNT" ]] || fail "gcloud has no active authenticated account."

# Step 2: resolve the authoritative merged-main revision from GitHub.
MAIN_SHA=$(gh api "repos/$REPOSITORY/commits/main" --jq .sha 2>/dev/null) || \
  fail "GitHub CLI could not resolve the current main commit."
[[ "$MAIN_SHA" =~ ^[0-9a-f]{40}$ ]] || fail "GitHub returned an invalid main commit SHA."

BACKEND_AR_REPOSITORY="$AR_ROOT/finance-assistant-backend"
FRONTEND_AR_REPOSITORY="$AR_ROOT/finance-assistant-frontend"

# Step 3: require both main-SHA tags to exist before changing either variable.
BACKEND_DIGEST=$(resolve_artifact_digest "$BACKEND_AR_REPOSITORY:$MAIN_SHA") || \
  fail "The merged-main backend image is not available in Artifact Registry; run mirror-merged-main-images.sh first."
FRONTEND_DIGEST=$(resolve_artifact_digest "$FRONTEND_AR_REPOSITORY:$MAIN_SHA") || \
  fail "The merged-main frontend image is not available in Artifact Registry; run mirror-merged-main-images.sh first."

GCP_BACKEND_IMAGE="$BACKEND_AR_REPOSITORY@$BACKEND_DIGEST"
GCP_FRONTEND_IMAGE="$FRONTEND_AR_REPOSITORY@$FRONTEND_DIGEST"

# Step 4: converge both GitHub variables on the immutable digest references.
set_and_verify_variable "GCP_BACKEND_IMAGE" "$GCP_BACKEND_IMAGE"
set_and_verify_variable "GCP_FRONTEND_IMAGE" "$GCP_FRONTEND_IMAGE"

# Step 5: print the verified non-secret values for operator review.
printf '\nGitHub environment image variables now reference merged main %s:\n' "$MAIN_SHA"
printf 'GCP_BACKEND_IMAGE=%s\n' "$GCP_BACKEND_IMAGE"
printf 'GCP_FRONTEND_IMAGE=%s\n' "$GCP_FRONTEND_IMAGE"
