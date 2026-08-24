"""Profile-local Hermes tool-usage analysis and safe tuning helpers.

The analyzer reads only tool-call metadata from Hermes' SQLite history. It never
selects message content or reasoning columns.
"""

from __future__ import annotations

import argparse
import collections
import contextlib
import datetime as dt
import difflib
import json
import os
import shlex
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_RARE_MAX = 2
DEFAULT_FREQUENT_MIN = 5
RECOVERY_LOG_NAME = "recovery-events.jsonl"


@dataclass(frozen=True)
class AuditOptions:
    days: int = DEFAULT_LOOKBACK_DAYS
    report_only: bool = False
    json_output: bool = False
    apply_floor: tuple[str, ...] = ()
    apply_exclude: tuple[str, ...] = ()
    approved: bool = False


@dataclass(frozen=True)
class HistoryCounts:
    counts: collections.Counter[str]
    complete: bool
    error: str = ""


def profile_home() -> Path:
    """Return the active Hermes profile home without inspecting other profiles."""
    configured = os.environ.get("HERMES_HOME", "").strip()
    return Path(configured).expanduser() if configured else Path.home() / ".hermes"


def profile_state_db() -> Path:
    return profile_home() / "state.db"


def profile_data_dir() -> Path:
    return profile_home() / "toolshed"


def _normalize_names(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip().lower() for value in values if str(value).strip()}))


def parse_options(raw_args: str) -> AuditOptions:
    parser = argparse.ArgumentParser(prog="/toolshed-audit", add_help=False)
    parser.add_argument("--days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--report", "--no-llm", dest="report_only", action="store_true")
    parser.add_argument("--json", dest="json_output", action="store_true")
    parser.add_argument("--apply-floor", default="")
    parser.add_argument("--apply-exclude", default="")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--help", action="store_true")
    try:
        args = parser.parse_args(shlex.split(raw_args or ""))
    except (SystemExit, ValueError) as exc:
        raise ValueError(
            "Usage: /toolshed-audit [--days N] [--report] [--json] "
            "[--apply-floor a,b --apply-exclude c,d --approve]"
        ) from exc
    if args.help:
        raise ValueError(
            "Usage: /toolshed-audit [--days N] [--report] [--json] "
            "[--apply-floor a,b --apply-exclude c,d --approve]\n"
            "Default: deterministic report plus model suggestions. --report makes no LLM call. "
            "Configuration is changed only when --apply-* and --approve are both present."
        )
    if args.days < 1 or args.days > 3650:
        raise ValueError("--days must be between 1 and 3650")
    floor = _normalize_names(args.apply_floor.split(",")) if args.apply_floor else ()
    excluded = _normalize_names(args.apply_exclude.split(",")) if args.apply_exclude else ()
    return AuditOptions(
        days=args.days,
        report_only=args.report_only,
        json_output=args.json_output,
        apply_floor=floor,
        apply_exclude=excluded,
        approved=bool(args.approve),
    )


def _tool_names_from_payload(raw: Any) -> list[str]:
    """Extract tool names from a tool_calls JSON value, never message content."""
    if not raw:
        return []
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(value, dict):
        value = value.get("tool_calls", value.get("calls", [value]))
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for call in value:
        if not isinstance(call, dict):
            continue
        function = call.get("function")
        name = function.get("name") if isinstance(function, dict) else call.get("name")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return names


def _connect_history(db_path: Path, uri: str) -> sqlite3.Connection:
    """Open history through Hermes' tracked connection API when available."""
    try:
        from hermes_cli.sqlite_safe_read import connect_tracked
    except ImportError:  # Offline fixtures do not install Hermes.
        return sqlite3.connect(uri, uri=True)
    return connect_tracked(uri, tracking_path=db_path, uri=True)


def read_tool_call_counts(db_path: Path, *, since: float) -> HistoryCounts:
    """Count calls from metadata, reporting any incomplete history source."""
    counts: collections.Counter[str] = collections.Counter()
    if not db_path.is_file():
        return HistoryCounts(counts, False, "Hermes state.db was not found for this profile")
    uri = f"file:{db_path.resolve()}?mode=ro"
    try:
        with contextlib.closing(_connect_history(db_path, uri)) as conn:
            columns = {
                str(row[1]) for row in conn.execute("PRAGMA table_info(messages)").fetchall()
            }
            required = {"role", "timestamp", "tool_calls", "tool_name"}
            missing = sorted(required - columns)
            if missing:
                return HistoryCounts(
                    counts,
                    False,
                    "Hermes messages schema is missing metadata columns: " + ", ".join(missing),
                )
            rows = conn.execute(
                "SELECT role, tool_calls, tool_name FROM messages "
                "WHERE timestamp >= ? AND (tool_calls IS NOT NULL OR tool_name IS NOT NULL)",
                (since,),
            )
            for role, raw_calls, tool_name in rows:
                names = _tool_names_from_payload(raw_calls)
                if names:
                    counts.update(names)
                elif (
                    str(role).lower() not in {"tool", "function"}
                    and isinstance(tool_name, str)
                    and tool_name.strip()
                ):
                    counts[tool_name.strip()] += 1
    except (OSError, sqlite3.Error) as exc:
        return HistoryCounts(counts, False, f"History metadata read failed: {type(exc).__name__}")
    return HistoryCounts(counts, True)


def record_recovery_event(
    toolset: str,
    *,
    source: str,
    session_id: str = "",
    timestamp: Optional[float] = None,
    path: Optional[Path] = None,
) -> None:
    """Append capability metadata for one recovery; failures are fail-open."""
    clean_toolset = str(toolset).strip().lower()
    if not clean_toolset:
        return
    event = {
        "timestamp": float(
            timestamp if timestamp is not None else dt.datetime.now(tz=dt.timezone.utc).timestamp()
        ),
        "toolset": clean_toolset,
        "source": str(source).strip()[:40],
        "session_id": str(session_id).strip()[:160],
    }
    target = path or (profile_data_dir() / RECOVERY_LOG_NAME)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
    except OSError:
        return


def read_recovery_counts(path: Path, *, since: float) -> collections.Counter[str]:
    counts: collections.Counter[str] = collections.Counter()
    if not path.is_file():
        return counts
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
                if float(event.get("timestamp", 0)) < since:
                    continue
                toolset = str(event.get("toolset") or "").strip().lower()
                if toolset:
                    counts[toolset] += 1
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
    except OSError:
        return collections.Counter()
    return counts


def build_report(
    *,
    db_path: Path,
    tool_to_toolset: Mapping[str, str],
    eligible_toolsets: Iterable[str],
    floor_toolsets: Iterable[str],
    excluded_toolsets: Iterable[str] = (),
    routed_toolsets: Iterable[str] = (),
    recovery_log: Optional[Path] = None,
    days: int = DEFAULT_LOOKBACK_DAYS,
    rare_max: int = DEFAULT_RARE_MAX,
    frequent_min: int = DEFAULT_FREQUENT_MIN,
    now: Optional[float] = None,
    profile_name: str = "default",
) -> dict[str, Any]:
    """Build a deterministic capability report from metadata-only sources."""
    current_time = float(
        now if now is not None else dt.datetime.now(tz=dt.timezone.utc).timestamp()
    )
    since = current_time - (days * 86400)
    history = read_tool_call_counts(db_path, since=since)
    call_counts = history.counts
    recovery_counts = read_recovery_counts(
        recovery_log or (db_path.parent / "toolshed" / RECOVERY_LOG_NAME), since=since
    )
    mapping = {str(k): str(v).strip().lower() for k, v in tool_to_toolset.items() if str(v).strip()}
    eligible = set(_normalize_names(eligible_toolsets))
    floor = set(_normalize_names(floor_toolsets))
    excluded = set(_normalize_names(excluded_toolsets)) - floor
    routed = set(_normalize_names(routed_toolsets))
    all_toolsets = eligible | floor | excluded | routed | set(mapping.values()) | set(recovery_counts)
    toolset_counts: collections.Counter[str] = collections.Counter()
    unknown_tools: collections.Counter[str] = collections.Counter()
    for tool_name, count in sorted(call_counts.items()):
        toolset = mapping.get(tool_name)
        if toolset:
            toolset_counts[toolset] += count
        else:
            unknown_tools[tool_name] += count

    rows = []
    for toolset in sorted(all_toolsets):
        count = int(toolset_counts.get(toolset, 0))
        if count == 0 and not history.complete:
            frequency = "unknown"
        elif count == 0:
            frequency = "never-used"
        elif count <= rare_max:
            frequency = "rarely-used"
        elif count >= frequent_min:
            frequency = "frequently-used"
        else:
            frequency = "used"
        rows.append({
            "toolset": toolset,
            "tool_calls": count,
            "frequency": frequency,
            "recovery_added": int(recovery_counts.get(toolset, 0)),
            "floor": toolset in floor,
            "eligible": toolset in eligible and toolset not in excluded,
            "routed": toolset in routed,
            "excluded": toolset in excluded,
            "tools": [
                {"name": name, "calls": int(call_counts.get(name, 0))}
                for name, owner in sorted(mapping.items())
                if owner == toolset
            ],
        })
    return {
        "profile": profile_name,
        "lookback_days": days,
        "window_start": dt.datetime.fromtimestamp(since, tz=dt.timezone.utc).isoformat(),
        "total_tool_calls": int(sum(call_counts.values())),
        "history_complete": history.complete,
        "history_error": history.error,
        "toolsets": rows,
        "unknown_tools": [
            {"name": name, "calls": int(count)} for name, count in sorted(unknown_tools.items())
        ],
        "privacy": "Tool names, toolset metadata, counts, and timestamps only; message content is not queried.",
    }


def format_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Toolshed tool-usage audit",
        (
            f"Profile: {report.get('profile', 'default')} | "
            f"Lookback: {report.get('lookback_days')} days | "
            f"Calls: {report.get('total_tool_calls', 0)}"
        ),
    ]
    if not report.get("history_complete", False):
        lines.extend([
            "",
            "WARNING: history is incomplete; zero counts are unknown, not never-used. "
            + str(report.get("history_error", "")),
        ])
    lines.extend([
        "",
        "| Toolset | Calls | Frequency | Recovery | Floor | Eligible | Routed | Excluded |",
        "| --- | ---: | --- | ---: | :---: | :---: | :---: | :---: |",
    ])
    for row in report.get("toolsets", []):
        display = dict(row)
        display.update({
            "floor": "yes" if row["floor"] else "",
            "eligible": "yes" if row["eligible"] else "",
            "routed": "yes" if row["routed"] else "",
            "excluded": "yes" if row["excluded"] else "",
        })
        lines.append(
            "| {toolset} | {tool_calls} | {frequency} | {recovery_added} | {floor} | "
            "{eligible} | {routed} | {excluded} |".format(**display)
        )
    unknown = report.get("unknown_tools", [])
    if unknown:
        lines.extend(["", "Unmapped historical tools: " + ", ".join(
            f"{item['name']} ({item['calls']})" for item in unknown
        )])
    lines.extend(["", str(report.get("privacy", ""))])
    return "\n".join(lines)


def suggestion_prompt(report: Mapping[str, Any]) -> list[dict[str, str]]:
    """Create a metadata-only prompt for the host-owned model."""
    payload = json.dumps(report, sort_keys=True, separators=(",", ":"))
    return [{
        "role": "user",
        "content": (
            "Interpret this deterministic Hermes tool-usage report. Suggest three explicit lists: "
            "(1) toolsets that should remain in the protected floor, (2) toolsets that should remain "
            "eligible/on-demand, and (3) toolsets that might be excluded from initial routing. "
            "Treat never-used data as weak evidence, keep recovery and fail-open safety, and do not "
            "claim that any change was applied. The payload contains metadata only.\n\n" + payload
        ),
    }]


def apply_profile_tuning(
    config_path: Path,
    *,
    profile_name: str,
    floor_toolsets: Iterable[str],
    excluded_toolsets: Iterable[str],
    approved: bool,
    now: Optional[dt.datetime] = None,
) -> tuple[Path, str]:
    """Apply explicitly approved profile tuning with backup, validation, and diff."""
    if not approved:
        raise PermissionError("No configuration changed: repeat with --approve after reviewing the report.")
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - Hermes ships PyYAML
        raise RuntimeError("PyYAML is required to edit Toolshed configuration") from exc
    before = config_path.read_text(encoding="utf-8")
    data = yaml.safe_load(before)
    if not isinstance(data, dict):
        raise TypeError("Toolshed config must contain a YAML mapping")
    global_cfg = data.get("global")
    if not isinstance(global_cfg, dict):
        raise TypeError("Toolshed config global section must be a mapping")
    profiles = data.setdefault("profiles", {})
    if not isinstance(profiles, dict):
        raise TypeError("Toolshed config profiles section must be a mapping")
    profile_cfg = profiles.setdefault(profile_name, {})
    if not isinstance(profile_cfg, dict):
        raise TypeError(f"Profile {profile_name!r} config must be a mapping")
    effective = dict(global_cfg)
    effective.update(profile_cfg)
    if (
        effective.get("fail_open", True) is not True
        or effective.get("auto_recover_registered_tools", True) is not True
    ):
        raise ValueError("Refusing tuning while fail-open or automatic recovery safety is disabled")
    floor = set(_normalize_names(floor_toolsets))
    excluded = set(_normalize_names(excluded_toolsets)) - floor
    profile_cfg["floor_toolsets"] = sorted(floor)
    profile_cfg["excluded_toolsets"] = sorted(excluded)
    after = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    reparsed = yaml.safe_load(after)
    if not isinstance(reparsed, dict):
        raise TypeError("Generated configuration did not validate as YAML")
    stamp = (now or dt.datetime.now(tz=dt.timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    source_mode = config_path.stat().st_mode & 0o777
    backup: Optional[Path] = None
    for counter in range(1000):
        suffix = "" if counter == 0 else f"-{counter}"
        candidate = config_path.with_name(f"{config_path.name}.backup-{stamp}{suffix}")
        try:
            with candidate.open("x", encoding="utf-8") as handle:
                handle.write(before)
            os.chmod(candidate, source_mode)
            backup = candidate
            break
        except FileExistsError:
            continue
    if backup is None:  # pragma: no cover - requires 1000 same-second collisions
        raise RuntimeError("Could not create a unique configuration backup")
    fd, temp_name = tempfile.mkstemp(prefix=f".{config_path.name}.", dir=str(config_path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(after)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, source_mode)
        Path(temp_name).replace(config_path)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise
    diff = "".join(difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=str(config_path),
        tofile=str(config_path),
    ))
    return backup, diff


def runtime_surface() -> tuple[dict[str, str], set[str]]:
    """Return live tool→toolset metadata and registered toolsets, if available."""
    mapping: dict[str, str] = {}
    eligible: set[str] = set()
    try:
        from tools.registry import registry
        eligible = set(registry.get_registered_toolset_names() or [])
        for toolset in sorted(eligible):
            for tool_name in registry.get_tool_names_for_toolset(toolset) or []:
                mapping[str(tool_name)] = str(toolset)
    except Exception:
        pass
    return mapping, eligible


def make_command_handler(ctx: Any, config_path: Path, state_resolver: Any = None):
    """Create the native ``/toolshed-audit`` command handler."""
    def handle(raw_args: str) -> str:
        try:
            options = parse_options(raw_args)
        except ValueError as exc:
            return str(exc)
        try:
            import yaml
            cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            return f"Toolshed audit could not load config: {exc}"
        global_cfg = cfg.get("global") if isinstance(cfg, dict) else {}
        profiles = cfg.get("profiles") if isinstance(cfg, dict) else {}
        global_cfg = global_cfg if isinstance(global_cfg, dict) else {}
        profiles = profiles if isinstance(profiles, dict) else {}
        profile_name = str(getattr(ctx, "profile_name", "default") or "default")
        profile_cfg = profiles.get(profile_name)
        profile_cfg = profile_cfg if isinstance(profile_cfg, dict) else {}
        effective = dict(global_cfg)
        effective.update(profile_cfg)
        floor = effective.get("floor_toolsets") or []
        excluded = set(effective.get("excluded_toolsets") or []) - set(floor)
        mapping, registered = runtime_surface()
        eligible = registered - excluded
        routed: set[str] = set()
        try:
            if state_resolver is not None:
                resolved = state_resolver()
                if resolved is not None:
                    routed = set(resolved.active_toolsets)
            else:
                from .state import _get_agent_ref, _get_router_state
                agent = _get_agent_ref()
                if agent is not None:
                    routed = set(_get_router_state(agent).active_toolsets)
        except Exception:
            pass
        audit_cfg = effective.get("audit") if isinstance(effective.get("audit"), dict) else {}
        report = build_report(
            db_path=profile_state_db(),
            tool_to_toolset=mapping,
            eligible_toolsets=eligible,
            floor_toolsets=floor,
            excluded_toolsets=excluded,
            routed_toolsets=routed,
            days=options.days,
            rare_max=int(audit_cfg.get("rare_max", DEFAULT_RARE_MAX)),
            frequent_min=int(audit_cfg.get("frequent_min", DEFAULT_FREQUENT_MIN)),
            profile_name=profile_name,
        )
        rendered = json.dumps(report, indent=2, sort_keys=True) if options.json_output else format_report(report)
        wants_change = bool(options.apply_floor or options.apply_exclude)
        if not report["history_complete"]:
            return (
                rendered
                + "\n\nModel suggestions and configuration edits are disabled until history metadata "
                "can be read completely."
            )
        if wants_change:
            try:
                backup, diff = apply_profile_tuning(
                    config_path,
                    profile_name=profile_name,
                    floor_toolsets=options.apply_floor or floor,
                    excluded_toolsets=options.apply_exclude or excluded,
                    approved=options.approved,
                )
            except (OSError, RuntimeError, TypeError, ValueError, PermissionError) as exc:
                return rendered + f"\n\nNo configuration changed: {exc}"
            return rendered + f"\n\nBackup: {backup}\n\n```diff\n{diff}```"
        if options.report_only:
            return rendered
        try:
            result = ctx.llm.complete(
                suggestion_prompt(report),
                temperature=0.0,
                max_tokens=700,
                timeout=30.0,
                purpose="toolshed tool-usage tuning suggestions",
            )
            suggestion = str(getattr(result, "text", "") or "").strip()
        except Exception as exc:
            suggestion = f"Model suggestions unavailable ({exc}). The deterministic report is still valid."
        return rendered + "\n\n## Model suggestions (not applied)\n" + suggestion

    return handle
