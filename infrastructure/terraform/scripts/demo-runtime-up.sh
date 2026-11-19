#!/usr/bin/env bash

# Stable operator entry point for creating the disposable M11 staging demo
# runtime. It resolves the sibling lifecycle wizard and replaces this process
# with its reviewed `up` flow, forwarding any additional arguments.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
exec "$SCRIPT_DIR/bootstrap-staging.sh" up "$@"
