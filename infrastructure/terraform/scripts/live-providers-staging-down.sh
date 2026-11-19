#!/usr/bin/env bash

# Stable operator entry point for returning staging to credential-free provider
# mode. It resolves the sibling provider wizard and replaces this process with
# the wizard's reviewed `down` flow.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
exec "$SCRIPT_DIR/configure-live-providers.sh" down
