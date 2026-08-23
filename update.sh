#!/usr/bin/env bash
# toolshed-update — update Toolshed WITHOUT silently changing user state (fixes D2).
#
# Usage:
#   toolshed-update.sh --profile default [--ref <sha>] [--json]
#
# Contract (ADR-0010 §2):
#   capture state → update → restore config/state → verify grant+enabled+routing
#   on ANY failure: restore the pre-update config, exit non-zero. No half-states.
#
# Exit codes: 0 ok · 1 hermes not found · 5 update failed · 6 verification failed

set -u

REPO="Huy3ko/toolshed"
PLUGIN_NAME="hermes-token-router"
JSON=0; REF=""; PROFILES=""; TARGET_USER=""; TARGET_HOME=""
RESULT_LOG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --profile) PROFILES="$2"; shift 2 ;;
    --ref) REF="$2"; shift 2 ;;
    --json) JSON=1; shift ;;
    # D2/Multi-User contract: update a FOREIGN agent's home. The updater derives
    # the target user from the home owner and runs every write step as that user
    # (sudo -u) — root never owns plugin files (v0.1.4 ownership fix).
    --home) TARGET_HOME="$2"; shift 2 ;;
    --user) TARGET_USER="$2"; shift 2 ;;
    *) shift ;;
  esac
done

# Resolve target user/home. Fail closed when ambiguous (ADR-0010 §Updater-Vertrag).
if [ -n "$TARGET_HOME" ]; then
  [ -d "$TARGET_HOME" ] || { echo "✗ target home not found: $TARGET_HOME" >&2; exit 4; }
  if [ -z "$TARGET_USER" ]; then
    TARGET_USER="$(stat -c '%U' "$TARGET_HOME")"
    [ -n "$TARGET_USER" ] || { echo "✗ cannot derive owner of $TARGET_HOME — pass --user explicitly" >&2; exit 4; }
  fi
fi
# Run-as wrapper: identity = target user when updating a foreign home, else current user
AS_USER() {
  if [ -n "$TARGET_USER" ] && [ "$(id -un)" != "$TARGET_USER" ]; then sudo -u "$TARGET_USER" env HOME="$TARGET_HOME" "$@"; else env HOME="${TARGET_HOME:-$HOME}" "$@"; fi
}

say() { [ "$JSON" = "0" ] && echo "$@"; return 0; }
jadd() { RESULT_LOG="$RESULT_LOG$1\n"; }

HERMES_BIN="$(AS_USER command -v hermes || true)"
if [ -z "$HERMES_BIN" ]; then
  for C in "${TARGET_HOME:+$TARGET_HOME}/src/hermes-agent/venv/bin/hermes" "${TARGET_HOME:+$TARGET_HOME}/hermes-agent/venv/bin/hermes" "$HOME/src/hermes-agent/venv/bin/hermes"; do
    [ -x "$C" ] && HERMES_BIN="$C" && break
  done
fi
[ -n "$TARGET_HOME" ] && case "$HERMES_BIN" in "$HOME"*) HERMES_BIN="${HERMES_BIN/$HOME/$TARGET_HOME}" ;; esac
[ -z "$HERMES_BIN" ] && say "✗ hermes not found" && jadd '{"ok":false,"reason":"no hermes"}' && [ "$JSON" = "1" ] && printf "%b" "$RESULT_LOG" && exit 1

TH="${TARGET_HOME:-$HOME}"
[ -z "$PROFILES" ] && PROFILES="default"
IFS=',' read -r -a TARGETS <<< "$PROFILES"

FAILED=()
for P in "${TARGETS[@]}"; do
  CFG="$(ls -d "${TH}/profiles/$P/plugins/$PLUGIN_NAME/config.yaml" \
             "${TH}/plugins/$PLUGIN_NAME/config.yaml" 2>/dev/null | head -1)"
  if [ -z "$CFG" ] || [ ! -f "$CFG" ]; then
    FAILED+=("$P:no-config"); jadd "{\"profile\":\"$P\",\"step\":\"find-config\",\"ok\":false}"; continue
  fi

  # ---------- 1. CAPTURE STATE ----------
  BACKUP="$CFG.preupdate.$(date +%s)"
  cp "$CFG" "$BACKUP"

  OLD_ENABLED=$(grep -m1 '^  enabled:' "$CFG" | awk '{print $2}')
  OLD_MODE=$(grep -m1 '^  mode:' "$CFG" | awk '{print $2}')
  OLD_FLOOR=$(grep -A6 'floor_toolsets:' "$CFG" | head -7)
  GRANT_BEFORE=$("$HERMES_BIN" -p "$P" plugins capabilities $PLUGIN_NAME 2>/dev/null | grep -c "tools.override: granted")
  OLD_COMMIT=$(cd "$(dirname "$CFG")" && git rev-parse --short HEAD 2>/dev/null || echo "?")

  say "── Profile: $P ────────────────────────────────────────────"
  say "  before: commit=$OLD_COMMIT enabled=$OLD_ENABLED mode=${OLD_MODE:-active} grant=$GRANT_BEFORE"
  jadd "{\"profile\":\"$P\",\"before\":{\"commit\":\"$OLD_COMMIT\",\"enabled\":\"$OLD_ENABLED\",\"grant\":$GRANT_BEFORE}}"

  # ---------- 2. UPDATE ----------
  REFARG=(); [ -n "$REF" ] && REFARG=(--ref "$REF")
  UPD_OUT=$(AS_USER "$HERMES_BIN" -p "$P" plugins install "$REPO" "${REFARG[@]+${REFARG[@]}}" --force 2>&1)
  if ! echo "$UPD_OUT" | grep -qE "✓ Installed|Installed"; then
    say "  ✗ update failed — restoring config from backup"
    cp "$BACKUP" "$CFG"
    FAILED+=("$P:update"); jadd "{\"profile\":\"$P\",\"step\":\"update\",\"ok\":false}"; continue
  fi

  # ---------- 3. RESTORE USER CONFIG ----------
  NEW_CFG="$(ls -d "${TH}/profiles/$P/plugins/$PLUGIN_NAME/config.yaml" \
                 "${TH}/plugins/$PLUGIN_NAME/config.yaml" 2>/dev/null | head -1)"
  if [ -z "$NEW_CFG" ] || [ ! -f "$NEW_CFG" ]; then
    cp "$BACKUP" "$NEW_CFG" 2>/dev/null || { FAILED+=("$P:restore"); jadd "{\"profile\":\"$P\",\"step\":\"restore\",\"ok\":false}"; continue; }
  fi
  # merge: keep new defaults, but restore user's enabled/mode/floor
  sed -i "s|^  enabled:.*|  enabled: $OLD_ENABLED|" "$NEW_CFG"
  if [ -n "$OLD_MODE" ]; then sed -i "s|^  mode:.*|  mode: $OLD_MODE|" "$NEW_CFG"; fi

  # ---------- 4. VERIFY ----------
  GRANT_AFTER=$(AS_USER "$HERMES_BIN" -p "$P" plugins capabilities $PLUGIN_NAME 2>/dev/null | grep -c "tools.override: granted")
  EN_AFTER=$(grep -m1 '^  enabled:' "$NEW_CFG" | awk '{print $2}')
  NEW_COMMIT=$(cd "$(dirname "$NEW_CFG")" && git rev-parse --short HEAD 2>/dev/null || echo "?")

  if [ "$EN_AFTER" != "$OLD_ENABLED" ]; then
    say "  ✗ enabled-state lost ($OLD_ENABLED → $EN_AFTER) — restoring backup"
    cp "$BACKUP" "$NEW_CFG"
    FAILED+=("$P:enabled-lost"); jadd "{\"profile\":\"$P\",\"step\":\"verify-enabled\",\"ok\":false}"; continue
  fi
  if [ "$GRANT_BEFORE" = "1" ] && [ "$GRANT_AFTER" = "0" ]; then
    say "  ✗ grant lost during update — restoring backup"
    cp "$BACKUP" "$NEW_CFG"
    FAILED+=("$P:grant-lost"); jadd "{\"profile\":\"$P\",\"step\":\"verify-grant\",\"ok\":false}"; continue
  fi

  say "  after: commit=$NEW_COMMIT enabled=$EN_AFTER grant=$GRANT_AFTER"
  jadd "{\"profile\":\"$P\",\"after\":{\"commit\":\"$NEW_COMMIT\",\"enabled\":\"$EN_AFTER\",\"grant\":$GRANT_AFTER},\"ok\":true}"
done

FAILCOUNT=${#FAILED[@]}
if [ "$FAILCOUNT" -eq 0 ]; then
  say ""
  say "✅ Update complete — config, enabled-state and grants preserved."
  jadd '{"summary":"ok"}'
  [ "$JSON" = "1" ] && printf "%b" "{\n$RESULT_LOG}"
  exit 0
else
  say ""
  say "❌ Update had failures: ${FAILED[*]}"
  jadd "{\"summary\":\"failed\"}"
  [ "$JSON" = "1" ] && printf "%b" "{\n$RESULT_LOG}"
  exit 6
fi
