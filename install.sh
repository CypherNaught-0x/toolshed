#!/usr/bin/env bash
# Install and enable Toolshed using Hermes' scan-aware plugin workflow.
# Usage: install.sh [--profile <name[,name...]>] [--ref <sha>] [--yes]
set -u

REPO="Huy3ko/toolshed"
PLUGIN_NAME="hermes-token-router"
PROFILES=""
REF=""
YES=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --profile) [ "$#" -ge 2 ] && PROFILES="$2"; shift 2 ;;
    --ref) [ "$#" -ge 2 ] && REF="$2"; shift 2 ;;
    --yes|-y) YES=1; shift ;;
    *) shift ;;
  esac
done

HERMES_BIN="$(command -v hermes || true)"
if [ -z "$HERMES_BIN" ]; then
  printf '%s\n' 'Hermes CLI not found. Install Hermes first.' >&2
  exit 1
fi

if [ -z "$PROFILES" ]; then
  PROFILES="default"
fi
IFS=',' read -r -a TARGETS <<< "$PROFILES"
if [ "$YES" != 1 ]; then
  printf 'Grant tools.override and continue? [y/N]: '
  read -r answer
  case "$answer" in y|Y|yes|Yes) ;; *) exit 2 ;; esac
fi

failed=0
for profile in "${TARGETS[@]}"; do
  printf '\nProfile: %s\n' "$profile"
  ref_args=()
  [ -n "$REF" ] && ref_args=(--ref "$REF")
  # Never force-reinstall here: an existing plugin may contain user config.
  # Use the supported update command for an installed copy.
  if ! "$HERMES_BIN" -p "$profile" plugins install "$REPO" "${ref_args[@]}" --no-enable; then
    failed=1
    continue
  fi
  if ! "$HERMES_BIN" -p "$profile" plugins enable "$PLUGIN_NAME" --allow-tool-override; then
    failed=1
    continue
  fi
  if ! "$HERMES_BIN" -p "$profile" plugins capabilities "$PLUGIN_NAME" | grep -q 'tools.override: granted'; then
    printf 'Capability grant verification failed for %s\n' "$profile" >&2
    failed=1
  fi
done

if [ "$failed" = 0 ]; then
  printf '\nToolshed installed and enabled for: %s\n' "${TARGETS[*]}"
else
  printf '\nToolshed installation failed for one or more profiles.\n' >&2
  exit 4
fi
