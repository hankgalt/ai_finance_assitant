#!/usr/bin/env bash

# Stable operator entry point for activating the bounded owner-only live-provider
# posture in staging. It resolves the sibling provider wizard and replaces this
# process with the wizard's reviewed `up` flow.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
exec "$SCRIPT_DIR/configure-live-providers.sh" up
