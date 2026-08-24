"""Release metadata, manifest capability, and shipped-config consistency tests."""

from __future__ import annotations

import ast
import importlib.util
import sys
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib
import types
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def literal_version(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"No __version__ literal in {path}")


def test_all_shipped_versions_match_pyproject():
    project_version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    root_manifest = yaml.safe_load((ROOT / "plugin.yaml").read_text(encoding="utf-8"))
    package_manifest = yaml.safe_load((ROOT / "src/toolshed/plugin.yaml").read_text(encoding="utf-8"))
    assert project_version == "0.1.5"
    assert root_manifest == package_manifest
    assert root_manifest["version"] == project_version
    assert literal_version(ROOT / "__about__.py") == project_version
    assert literal_version(ROOT / "src/toolshed/__about__.py") == project_version


def test_manifest_declares_current_override_capability():
    manifest = yaml.safe_load((ROOT / "plugin.yaml").read_text(encoding="utf-8"))
    assert manifest["capabilities"] == ["tools.override"]
    assert "provides_middleware" not in manifest  # not part of the current manifest schema
    assert "request_toolset" in manifest["provides_tools"]


def test_config_copies_are_valid_and_semantically_identical():
    paths = [ROOT / "config.yaml", ROOT / "config.template.yaml", ROOT / "src/toolshed/config.yaml"]
    configs = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in paths]
    assert all(isinstance(config, dict) for config in configs)
    assert configs[0] == configs[1] == configs[2]
    global_cfg = configs[0]["global"]
    assert global_cfg["enabled"] is False
    assert global_cfg["classifier"]["enabled"] is False
    assert global_cfg["fail_open"] is True
    assert global_cfg["auto_recover_registered_tools"] is True
    assert global_cfg["excluded_toolsets"] == []
    assert configs[0]["shadow"]["enabled"] is False


def test_flat_directory_loader_imports_root_runtime():
    spec = importlib.util.spec_from_file_location("toolshed_flat_fixture", ROOT / "__init__.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.__version__ == "0.1.5"
    assert module.CONFIG_FILE == ROOT / "config.yaml"
    assert callable(module.register)
    assert callable(module.make_command_handler)


def test_registration_fails_closed_without_override_grant(monkeypatch):
    import toolshed

    calls = []

    class DeniedContext:
        def has_capability(self, capability):
            calls.append(("capability", capability))
            return False

        def __getattr__(self, name):
            calls.append(("unexpected", name))
            raise AssertionError(f"registration continued after denied capability: {name}")

    monkeypatch.setattr(toolshed, "_registration_checked", False)
    toolshed.register(DeniedContext())
    assert calls == [("capability", "tools.override")]
    assert toolshed._registration_checked is True
    assert toolshed._recovery_is_ready() is False


def test_granted_registration_wires_current_hermes_surfaces(monkeypatch):
    import toolshed

    hermes_cli = types.ModuleType("hermes_cli")
    plugins = types.ModuleType("hermes_cli.plugins")
    plugins.VALID_HOOKS = {"pre_llm_call", "post_tool_call", "on_session_end"}
    hermes_cli.plugins = plugins
    monkeypatch.setitem(sys.modules, "hermes_cli", hermes_cli)
    monkeypatch.setitem(sys.modules, "hermes_cli.plugins", plugins)

    class Registry:
        def get_registered_toolset_names(self):
            return ["file", "terminal"]

    tools_module = types.ModuleType("tools")
    registry_module = types.ModuleType("tools.registry")
    registry_module.registry = Registry()
    tools_module.registry = registry_module
    monkeypatch.setitem(sys.modules, "tools", tools_module)
    monkeypatch.setitem(sys.modules, "tools.registry", registry_module)

    class GrantedContext:
        profile_name = "fixture"

        def __init__(self):
            self.hooks = []
            self.middleware = []
            self.commands = []
            self.tools = []

        def has_capability(self, capability):
            return capability == "tools.override"

        def register_hook(self, name, callback):
            self.hooks.append(name)
            return object()

        def register_middleware(self, name, callback):
            self.middleware.append(name)
            return object()

        def register_command(self, name, handler, **metadata):
            self.commands.append(name)
            return object()

        def register_tool(self, **kwargs):
            self.tools.append(kwargs["name"])
            return object()

    ctx = GrantedContext()
    monkeypatch.setattr(toolshed, "_registration_checked", False)
    toolshed.register(ctx)
    assert set(ctx.hooks) == {"pre_llm_call", "post_tool_call", "on_session_end"}
    assert ctx.middleware == ["tool_request"]
    assert ctx.commands == ["toolshed-audit"]
    assert ctx.tools == ["request_toolset"]
    assert toolshed._recovery_is_ready() is True
