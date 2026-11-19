#!/usr/bin/env bash

# Stable operator entry point for removing the M11 private HTTPS/IAP edge. It
# resolves the sibling edge wizard and replaces this process with its reviewed
# `down` flow, forwarding any additional arguments.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
exec "$SCRIPT_DIR/configure-private-edge.sh" down "$@"
