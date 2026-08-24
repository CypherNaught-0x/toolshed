"""Deterministic, offline tests for profile-local tool-usage analysis."""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
import sys
import types
from pathlib import Path

import pytest
import yaml

from toolshed.usage_audit import (
    apply_profile_tuning,
    build_report,
    format_report,
    parse_options,
    read_tool_call_counts,
    record_recovery_event,
    suggestion_prompt,
)


def make_history(path: Path, now: float) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE messages ("
            "id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, "
            "tool_calls TEXT, tool_name TEXT, timestamp REAL)"
        )
        conn.executemany(
            "INSERT INTO messages(session_id, role, content, tool_calls, tool_name, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    "s1",
                    "assistant",
                    "SECRET prompt body must never enter the report",
                    json.dumps([{"function": {"name": "read_file", "arguments": "{}"}}]),
                    None,
                    now - 60,
                ),
                ("s1", "tool", "SECRET tool output", None, "read_file", now - 59),
                (
                    "s1",
                    "assistant",
                    "more SECRET text",
                    json.dumps({"tool_calls": [{"function": {"name": "shell_exec"}}]}),
                    None,
                    now - 58,
                ),
                ("old", "tool", "old", None, "web_search", now - 40 * 86400),
            ],
        )


def test_metadata_only_history_counts_do_not_read_content(tmp_path):
    now = 2_000_000_000.0
    db = tmp_path / "state.db"
    make_history(db, now)
    history = read_tool_call_counts(db, since=now - 30 * 86400)
    assert history.complete is True
    assert history.counts == {"read_file": 1, "shell_exec": 1}
    assert "SECRET" not in repr(history.counts)


def test_history_uses_hermes_tracked_connection_when_available(tmp_path, monkeypatch):
    now = 2_000_000_000.0
    db = tmp_path / "state.db"
    make_history(db, now)
    calls = []
    hermes_cli = types.ModuleType("hermes_cli")
    safe_read = types.ModuleType("hermes_cli.sqlite_safe_read")

    def connect_tracked(path, **kwargs):
        calls.append((path, kwargs))
        return sqlite3.connect(path, uri=kwargs.get("uri", False))

    safe_read.connect_tracked = connect_tracked
    hermes_cli.sqlite_safe_read = safe_read
    monkeypatch.setitem(sys.modules, "hermes_cli", hermes_cli)
    monkeypatch.setitem(sys.modules, "hermes_cli.sqlite_safe_read", safe_read)
    history = read_tool_call_counts(db, since=now - 30 * 86400)
    assert history.complete is True
    assert calls[0][1]["tracking_path"] == db
    assert calls[0][1]["uri"] is True


def test_report_distinguishes_usage_surface_and_recovery(tmp_path):
    now = 2_000_000_000.0
    db = tmp_path / "state.db"
    make_history(db, now)
    recovery = tmp_path / "recovery-events.jsonl"
    record_recovery_event("web", source="middleware", timestamp=now - 20, path=recovery)
    report = build_report(
        db_path=db,
        tool_to_toolset={"read_file": "file", "shell_exec": "terminal", "web_search": "web"},
        eligible_toolsets={"file", "terminal", "web", "vision"},
        floor_toolsets={"file", "terminal"},
        excluded_toolsets={"vision", "file"},
        routed_toolsets={"file"},
        recovery_log=recovery,
        days=30,
        now=now,
        profile_name="audit-fixture",
    )
    rows = {row["toolset"]: row for row in report["toolsets"]}
    assert rows["file"] == {
        "toolset": "file",
        "tool_calls": 1,
        "frequency": "rarely-used",
        "recovery_added": 0,
        "floor": True,
        "eligible": True,
        "routed": True,
        "excluded": False,
        "tools": [{"name": "read_file", "calls": 1}],
    }
    assert rows["web"]["frequency"] == "never-used"
    assert rows["web"]["recovery_added"] == 1
    assert rows["vision"]["excluded"] is True
    rendered = format_report(report)
    prompt = json.dumps(suggestion_prompt(report))
    assert "SECRET" not in rendered
    assert "SECRET" not in prompt
    assert "message content is not queried" in rendered


def test_parse_options_requires_bounded_lookback_and_explicit_approval():
    options = parse_options("--days 45 --report --apply-floor file,terminal --approve")
    assert options.days == 45
    assert options.report_only is True
    assert options.apply_floor == ("file", "terminal")
    assert options.approved is True
    with pytest.raises(ValueError, match="between 1 and 3650"):
        parse_options("--days 0")


def test_apply_tuning_requires_approval_backs_up_validates_and_shows_diff(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text(
        "global:\n"
        "  enabled: false\n"
        "  fail_open: true\n"
        "  auto_recover_registered_tools: true\n"
        "profiles: {}\n",
        encoding="utf-8",
    )
    with pytest.raises(PermissionError, match="--approve"):
        apply_profile_tuning(
            config,
            profile_name="alpha",
            floor_toolsets=["file"],
            excluded_toolsets=["vision"],
            approved=False,
        )
    backup, diff = apply_profile_tuning(
        config,
        profile_name="alpha",
        floor_toolsets=["file", "terminal"],
        excluded_toolsets=["vision", "file"],
        approved=True,
        now=dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.timezone.utc),
    )
    assert backup.name == "config.yaml.backup-20260102T030405Z"
    assert backup.is_file()
    parsed = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert parsed["profiles"]["alpha"]["floor_toolsets"] == ["file", "terminal"]
    assert parsed["profiles"]["alpha"]["excluded_toolsets"] == ["vision"]
    assert "+    - vision" in diff


def test_apply_tuning_refuses_to_weaken_fail_open(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text(
        "global:\n"
        "  fail_open: true\n"
        "  auto_recover_registered_tools: true\n"
        "profiles:\n"
        "  alpha:\n"
        "    fail_open: false\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="fail-open"):
        apply_profile_tuning(
            config,
            profile_name="alpha",
            floor_toolsets=["file"],
            excluded_toolsets=[],
            approved=True,
        )


def test_history_schema_failure_is_not_reported_as_never_used(tmp_path):
    db = tmp_path / "state.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, content TEXT)")
    report = build_report(
        db_path=db,
        tool_to_toolset={"read_file": "file"},
        eligible_toolsets={"file"},
        floor_toolsets={"file"},
        now=2_000_000_000.0,
    )
    assert report["history_complete"] is False
    assert "missing metadata columns" in report["history_error"]
    assert report["toolsets"][0]["frequency"] == "unknown"
    assert "history is incomplete" in format_report(report)


def test_same_second_backups_never_overwrite_and_preserve_mode(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text(
        "global:\n  fail_open: true\n  auto_recover_registered_tools: true\nprofiles: {}\n",
        encoding="utf-8",
    )
    config.chmod(0o640)
    fixed = dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.timezone.utc)
    first, _ = apply_profile_tuning(
        config,
        profile_name="alpha",
        floor_toolsets=["file"],
        excluded_toolsets=[],
        approved=True,
        now=fixed,
    )
    first_contents = first.read_text(encoding="utf-8")
    second, _ = apply_profile_tuning(
        config,
        profile_name="alpha",
        floor_toolsets=["file", "terminal"],
        excluded_toolsets=[],
        approved=True,
        now=fixed,
    )
    assert first != second
    assert second.name.endswith("-1")
    assert first.read_text(encoding="utf-8") == first_contents
    assert first.stat().st_mode & 0o777 == 0o640
    assert config.stat().st_mode & 0o777 == 0o640


def test_incomplete_history_suppresses_model_and_edits(tmp_path, monkeypatch):
    import toolshed.usage_audit as audit

    config = tmp_path / "config.yaml"
    original = (
        "global:\n  fail_open: true\n  auto_recover_registered_tools: true\n"
        "profiles: {}\n"
    )
    config.write_text(original, encoding="utf-8")

    class Context:
        profile_name = "alpha"

        @property
        def llm(self):
            raise AssertionError("LLM must not be called for incomplete history")

    monkeypatch.setattr(audit, "profile_state_db", lambda: tmp_path / "missing.db")
    monkeypatch.setattr(audit, "runtime_surface", lambda: ({"read_file": "file"}, {"file"}))
    handler = audit.make_command_handler(Context(), config)
    output = handler("--apply-floor file --approve")
    assert "history is incomplete" in output
    assert "suggestions and configuration edits are disabled" in output.lower()
    assert config.read_text(encoding="utf-8") == original
    assert not list(tmp_path.glob("*.backup-*"))
