#!/usr/bin/env bash
# Update Toolshed through Hermes' supported, scan-aware plugin updater.
#
# Hermes re-scans the fetched tree and disables a plugin whose update is
# dangerous. Do not bypass Hermes' security and consent state with a custom
# fetcher or direct filesystem writes.
#
# Usage: toolshed-update.sh [--profile <name>]
set -u

PLUGIN_NAME="hermes-token-router"
PROFILE="default"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --profile) [ "$#" -ge 2 ] && PROFILE="$2"; shift 2 ;;
    *) shift ;;
  esac
done

HERMES_BIN="$(command -v hermes || true)"
if [ -z "$HERMES_BIN" ]; then
  printf '%s\n' 'Hermes CLI not found.' >&2
  exit 1
fi

# `plugins update` is the current supported mechanism. It verifies the
# installed git source, re-scans after pulling, and re-consents capabilities.
exec "$HERMES_BIN" -p "$PROFILE" plugins update "$PLUGIN_NAME"
