"""Single-source version: pyproject.toml ist die Wahrheit.

Der flache Hermes-Plugin-Loader kann importlib.metadata nicht immer nutzen
(Plugin läuft nicht als installiertes Paket), daher statischer Fallback.
Bei Release: beide Stellen per Skript synchron halten (scripts/sync_version).
"""
__version__ = "0.1.1"
