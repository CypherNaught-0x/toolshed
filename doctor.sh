#!/usr/bin/env bash
# toolshed-doctor — diagnose Toolshed installation for one Hermes profile.
#
# Usage:
#   toolshed-doctor.sh [--profile default] [--json]
#
# Exit codes: 0 healthy · 1 warnings only · 2+ real failures
#
# Checks (ADR-0010 §3):
#   hermes found · toolshed installed · version/commit known
#   tools.override granted · global.enabled true · mode valid
#   floor_toolsets readable · profile state writable
#   request_toolset available · config consistent
#   stale grant warning · supported hermes version · last backup sane

set -u

PLUGIN_NAME="hermes-token-router"
JSON=0; PROFILE="default"
SUPPORTED_MIN_HERMES="0.20"
RESULT_LOG=""
FAIL=0; WARN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --json) JSON=1; shift ;;
    *) shift ;;
  esac
done

jadd() { RESULT_LOG="$RESULT_LOG$1,\n"; }
ok()   { FAIL=$FAIL;     [ "$JSON" = "0" ] && echo "  ✓ $1"; jadd "{\"check\":\"$1\",\"status\":\"ok\"}"; }
warn() { WARN=$((WARN+1)); [ "$JSON" = "0" ] && echo "  ! $1"; jadd "{\"check\":\"$1\",\"status\":\"warn\"}"; }
bad()  { FAIL=$((FAIL+1)); [ "$JSON" = "0" ] && echo "  ✗ $1"; jadd "{\"check\":\"$1\",\"status\":\"fail\"}"; }

HERMES_BIN="$(command -v hermes || true)"
if [ -z "$HERMES_BIN" ]; then
  for C in "$HOME/src/hermes-agent/venv/bin/hermes" "$HOME/hermes-agent/venv/bin/hermes"; do
    [ -x "$C" ] && HERMES_BIN="$C" && break
  done
fi

[ "$JSON" = "0" ] && echo "Toolshed doctor — profile: $PROFILE"

# 1. hermes found
if [ -z "$HERMES_BIN" ]; then bad "hermes CLI not found"; else ok "Hermes found: $HERMES_BIN"; fi

# 2. toolshed installed + 3. version/commit
CFG="$(ls -d "$HOME/.hermes/profiles/$PROFILE/plugins/$PLUGIN_NAME/config.yaml" \
           "$HOME/.hermes/plugins/$PLUGIN_NAME/config.yaml" 2>/dev/null | head -1)"
if [ -z "$CFG" ]; then
  bad "Toolshed not installed (no plugin config found)"
else
  ok "Toolshed installed: $CFG"
  PLUGIN_DIR=$(dirname "$CFG")
  VER=$(grep -m1 '__version__' "$PLUGIN_DIR/__about__.py" 2>/dev/null | awk -F'"' '{print $2}')
  COMMIT=$(cd "$PLUGIN_DIR" && git rev-parse --short HEAD 2>/dev/null || echo "?")
  if [ -n "$VER" ]; then ok "version $VER, commit $COMMIT"; else warn "version unknown (__about__.py missing?)"; fi

  # 4. tools.override granted
  CAP=$("$HERMES_BIN" -p "$PROFILE" plugins capabilities $PLUGIN_NAME 2>/dev/null)
  if echo "$CAP" | grep -q "tools.override: granted"; then ok "tools.override granted"
  elif echo "$CAP" | grep -q "tools.override"; then bad "tools.override DECLARED but NOT granted — router stays off. Run: hermes -p $PROFILE plugins enable $PLUGIN_NAME --allow-tool-override"
  else warn "could not read capability state"; fi

  # 5. global.enabled
  EN=$(grep -m1 '^  enabled:' "$CFG" 2>/dev/null | awk '{print $2}')
  if [ "$EN" = "true" ]; then ok "global.enabled: true"
  elif [ "$EN" = "false" ]; then bad "global.enabled is FALSE — routing inactive. Set it to true in $CFG"
  else bad "global.enabled not parseable"; fi

  # 6. mode valid
  MODE=$(grep -m1 '^  mode:' "$CFG" 2>/dev/null | awk '{print $2}')
  if [ "$MODE" = "active" ] || [ "$MODE" = "shadow" ]; then ok "mode: $MODE"
  elif [ -z "$MODE" ]; then warn "mode not set (defaults to active)"; else bad "unknown mode: $MODE"; fi

  # 7. floor_toolsets readable
  if grep -q 'floor_toolsets:' "$CFG"; then ok "floor_toolsets configured"; else warn "floor_toolsets not found in config"; fi

  # 8. profile state writable
  STATEDIR=$(dirname "$CFG")/learning
  mkdir -p "$STATEDIR" 2>/dev/null && touch "$STATEDIR/.doctor-write-test" 2>/dev/null \
    && ok "state dir writable ($STATEDIR)" && rm -f "$STATEDIR/.doctor-write-test" \
    || warn "state dir NOT writable ($STATEDIR)"

  # 9. request_toolset available
  RT=$("$HERMES_BIN" -p "$PROFILE" plugins list 2>/dev/null | grep -c "$PLUGIN_NAME.*enabled")
  if [ "$RT" -ge 1 ]; then ok "plugin enabled (recovery path registered at load)"; else warn "plugin shows as not enabled in profile list"; fi

  # 10. config consistency: no duplicate enabled keys at same level
  DUP=$(grep -c '^  enabled:' "$CFG" 2>/dev/null)
  if [ "${DUP:-0}" -le 1 ]; then ok "config consistent (single global.enabled)"; else warn "multiple top-level 'enabled:' keys ($DUP) — check config manually"; fi

  # 11. stale grant warning (grant exists but plugin dir missing)
  # stale-grant check: only look at the profile-local config (never the global
  # hermes config — reading unrelated config files trips security scanners and
  # is unnecessary: the grant lives next to this plugin's own registration)
  GRANT_CFG="$HOME/.hermes/profiles/$PROFILE/config.yaml"
  if [ -f "$GRANT_CFG" ] && grep -q "allow_tool_override: true" "$GRANT_CFG" && [ ! -d "$(dirname "$CFG")" ]; then
    warn "stale grant: allow_tool_override set but plugin directory missing"
  else ok "no stale grant detected"; fi

  # 12. last update backup sane
  LATEST_BAK=$(ls -t "$PLUGIN_DIR"/config.yaml.preupdate.* 2>/dev/null | head -1)
  if [ -n "$LATEST_BAK" ]; then
    if [ -s "$LATEST_BAK" ]; then ok "last update backup present ($(basename "$LATEST_BAK"))"
    else warn "last update backup is EMPTY: $LATEST_BAK"; fi
  else ok "no update backups yet (clean install or never updated)"; fi
fi

# 13. supported hermes version
HERMES_VER=$("$HERMES_BIN" --version 2>/dev/null | head -1 | grep -Eo '[0-9]+\.[0-9]+' | head -1)
if [ -n "$HERMES_VER" ]; then
  MAJOR=$(echo "$HERMES_VER" | cut -d. -f1); MINOR=$(echo "$HERMES_VER" | cut -d. -f2)
  if [ "$MAJOR" -eq 0 ] && [ "$MINOR" -lt 20 ]; then
    warn "hermes v$HERMES_VER < v0.20 — untested"
  else ok "hermes v$HERMES_VER (>= $SUPPORTED_MIN_HERMES tested)"; fi
else warn "could not read hermes version"; fi

# ---------- summary ----------
[ "$JSON" = "0" ] && echo ""
if [ "$JSON" = "1" ]; then
  CLEAN=$(echo "$RESULT_LOG" | tr -d '\n' | sed 's/\\n//g')
  CLEAN="${CLEAN%,}"   # drop trailing comma after last check
  printf '{\n"profile":"%s",\n"fail":%d,\n"warn":%d,\n"checks":[\n%s\n]\n}\n' "$PROFILE" "$FAIL" "$WARN" "$CLEAN"
else
  if [ "$FAIL" -gt 0 ]; then echo "❌ $FAIL failure(s), $WARN warning(s)"
  elif [ "$WARN" -gt 0 ]; then echo "⚠️  healthy with $WARN warning(s)"
  else echo "✅ all checks passed"; fi
fi

if [ "$FAIL" -gt 0 ]; then exit 2
elif [ "$WARN" -gt 0 ]; then exit 1
else exit 0
fi
