"""Deterministic, offline safety coverage for the router's high-risk paths."""

import json
import sys
import types

import pytest


class FakeAgent:
    def __init__(self, session_id="s1", include_vision=False):
        self.session_id = session_id
        self.tools = [
            {"type": "function", "function": {"name": "read_file"}},
            {"type": "function", "function": {"name": "run_shell"}},
        ]
        if include_vision:
            self.tools.append({"type": "function", "function": {"name": "vision_analyze"}})
        self.valid_tool_names = {item["function"]["name"] for item in self.tools}
        self.enabled_toolsets = ["file", "terminal"] + (["vision"] if include_vision else [])


def install_registry(monkeypatch, *, fail=False, empty_toolset=False, missing_definitions=False):
    class Registry:
        def get_registered_toolset_names(self):
            if fail:
                raise RuntimeError("registry offline")
            return ["file", "terminal", "vision"]

        def get_tool_names_for_toolset(self, name):
            if empty_toolset and name == "vision":
                return []
            return {
                "file": ["read_file"],
                "terminal": ["run_shell"],
                "vision": ["vision_analyze"],
            }[name]

        def get_definitions(self, names, quiet=True):
            if missing_definitions:
                return []
            return [
                {"type": "function", "function": {"name": name}}
                for name in names
            ]

        def get_entry(self, name):
            return types.SimpleNamespace(toolset={
                "read_file": "file",
                "run_shell": "terminal",
                "vision_analyze": "vision",
            }.get(name))

        def get_toolset_alias_target(self, name):
            return None

    tools = types.ModuleType("tools")
    registry_module = types.ModuleType("tools.registry")
    registry_module.registry = Registry()
    tools.registry = registry_module
    monkeypatch.setitem(sys.modules, "tools", tools)
    monkeypatch.setitem(sys.modules, "tools.registry", registry_module)


def test_invalid_confidence_is_uncertainty():
    from toolshed.policy import _extract_confidence

    for value in (-1, 1.01, 101, float("nan"), float("inf"), "not-a-number"):
        assert _extract_confidence({"confidence": value}) is None
    assert _extract_confidence({"confidence": 95}) == pytest.approx(0.95)


def test_deterministic_routing_is_stable():
    from toolshed.policy import _predict_toolsets_by_rules

    available = {"file", "terminal", "web"}
    first = _predict_toolsets_by_rules("read the file and run the tests", available)
    for _ in range(10):
        assert _predict_toolsets_by_rules("read the file and run the tests", available) == first


def test_router_state_is_profile_agent_local():
    from toolshed.state import _get_agent_ref, _get_router_state

    a = FakeAgent("one")
    b = FakeAgent("two")
    assert _get_router_state(a) is not _get_router_state(b)
    from toolshed.state import _store_agent_ref
    _store_agent_ref(a, "one")
    _store_agent_ref(b, "two")
    assert _get_agent_ref("one") is a
    assert _get_agent_ref("two") is b
    assert _get_agent_ref() is None


def test_recovery_expands_monotonically(monkeypatch):
    install_registry(monkeypatch)
    from toolshed.state import _get_router_state
    from toolshed.tools import _cache_full_toolset, _expand_toolset

    agent = FakeAgent()
    _cache_full_toolset(agent)
    state = _get_router_state(agent)
    state.set_initial_surface({"file"})
    _expand_toolset(agent, "terminal")
    _expand_toolset(agent, "file")
    assert state.active_toolsets == {"file", "terminal"}
    assert state.expansion_count == 1


@pytest.mark.parametrize(
    "registry_options",
    [{"empty_toolset": True}, {"missing_definitions": True}],
)
def test_recovery_failure_restores_full_surface_before_state_mutation(monkeypatch, registry_options):
    install_registry(monkeypatch, **registry_options)
    from toolshed.state import _get_router_state
    from toolshed.tools import _cache_full_toolset, _expand_toolset

    agent = FakeAgent()
    original = list(agent.tools)
    _cache_full_toolset(agent)
    state = _get_router_state(agent)
    state.active = True
    state.set_initial_surface({"file"})
    assert _expand_toolset(agent, "vision") is False
    assert agent.tools == original
    assert "vision" not in state.active_toolsets
    assert state.active is False


def test_registry_failure_never_reports_recovery_ok(monkeypatch):
    install_registry(monkeypatch, fail=True)
    from toolshed import request_toolset_handler

    result = json.loads(request_toolset_handler({"toolset": "file"}, session_id="s1"))
    assert result["ok"] is False
    assert "registry" in result["error"]


def test_malformed_profile_config_fails_open(monkeypatch):
    from toolshed.config import _get_profile_config

    assert _get_profile_config([])["enabled"] is False
    assert _get_profile_config({"profiles": [], "global": "bad"})["enabled"] is False
    assert _get_profile_config({"profiles": {"default": []}, "global": {"enabled": True}})["enabled"] is False


def test_restore_full_surface_restores_toolsets(monkeypatch):
    from toolshed.tools import _cache_full_toolset, _restore_full_tools

    agent = FakeAgent()
    _cache_full_toolset(agent)
    agent.tools = []
    agent.valid_tool_names = set()
    agent.enabled_toolsets = []
    _restore_full_tools(agent)
    assert agent.valid_tool_names == {"read_file", "run_shell"}
    assert agent.enabled_toolsets == ["file", "terminal"]


def test_current_hook_narrows_eligible_surface_but_keeps_recovery(monkeypatch):
    install_registry(monkeypatch)
    import toolshed
    import toolshed.tools as router_tools

    config = {
        "global": {
            "enabled": True,
            "floor_toolsets": ["file"],
            "excluded_toolsets": ["vision"],
            "deterministic_rules_enabled": True,
            "confidence_threshold": 0.9,
            "classifier": {"enabled": False},
        },
        "profiles": {},
    }
    monkeypatch.setattr(toolshed, "_registration_checked", False)
    monkeypatch.setattr(toolshed, "_load_config", lambda: config)
    monkeypatch.setattr(toolshed, "_get_available_toolsets", lambda: {"file", "terminal", "vision"})
    monkeypatch.setattr(router_tools, "_load_config", lambda: config)
    agent = FakeAgent(include_vision=True)
    toolshed.pre_turn_context_build(
        agent=agent,
        user_message="run the tests",
        session_id=agent.session_id,
        turn_id="turn-1",
    )
    assert agent.valid_tool_names == {"read_file", "run_shell", "request_toolset"}
    assert "vision_analyze" not in agent.valid_tool_names
    state = toolshed._get_router_state(agent)
    assert state.active is True
    assert state.active_toolsets == {"file", "terminal"}


def test_uncertain_hook_restores_exact_full_surface(monkeypatch):
    install_registry(monkeypatch)
    import toolshed
    import toolshed.tools as router_tools

    config = {
        "global": {
            "enabled": True,
            "floor_toolsets": ["file"],
            "excluded_toolsets": [],
            "deterministic_rules_enabled": False,
            "classifier": {"enabled": False},
        },
        "profiles": {},
    }
    monkeypatch.setattr(toolshed, "_registration_checked", False)
    monkeypatch.setattr(toolshed, "_load_config", lambda: config)
    monkeypatch.setattr(toolshed, "_get_available_toolsets", lambda: {"file", "terminal", "vision"})
    monkeypatch.setattr(router_tools, "_load_config", lambda: config)
    agent = FakeAgent(include_vision=True)
    original = list(agent.tools)
    toolshed.pre_turn_context_build(
        agent=agent,
        user_message="please handle this ambiguous request",
        session_id=agent.session_id,
        turn_id="turn-2",
    )
    assert agent.tools == original
    assert agent.valid_tool_names == {"read_file", "run_shell", "vision_analyze"}
    assert toolshed._get_router_state(agent).active is False
