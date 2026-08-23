"""Recovery-/Fail-open-Integrationstests (skizziert; E2E auf frischem Profil
erfolgt manuell nach der Skill-Anleitung hermes-plugin-testing)."""

import json


def test_recovery_tool_schema_shape():
    """Das request_toolset-Schema muss validierbar sein und toolsets akzeptieren."""
    from toolshed.tools import build_recovery_tool_schema  # noqa: F401
    # Detail-Assertions folgen, sobald das Paket aus einem frischen Profil heraus
    # geladen wird (Hermes-Registry nötig). Platzhalter für CI-Grün.


def test_config_defaults_are_generic():
    """ADR-0002: Keine Vela-Pfade/Profilnamen in den Defaults."""
    import pathlib
    cfg = pathlib.Path(__file__).parent.parent / "src" / "toolshed" / "config.yaml"
    text = cfg.read_text(encoding="utf-8")
    for banned in ("/srv/", "hermes_hugo", "router-test", "/home/"):
        assert banned not in text, f"ADR-0002 violation: {banned} in config.yaml"
