# Changelog

All notable changes to Toolshed are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [SemVer](https://semver.org/) (0.x = pre-stable).

## [Unreleased]

### Added
- Native `/toolshed-audit` command for metadata-only, profile-local tool-usage reporting,
  host-model tuning suggestions, and explicit backed-up/validated configuration edits.
- Deterministic offline coverage for authorization, routing uncertainty, profile isolation,
  monotonic recovery, configuration loading, manifests, package metadata, and SQLite analysis.

### Changed
- Installation and updates now use Hermes' scan-aware plugin commands; dangerous privileged
  updater behavior and machine-specific paths were removed.
- CI now strictly runs editable installation, Ruff, tests, dependency audit, shipped-code scanning,
  and package-content verification. Plugin/config/version metadata now agree on 0.1.5.
- The plugin declares and fail-closes on `tools.override`; classifier, shadow learning, and routing
  remain opt-in, with privacy and rollback semantics documented.

## [0.1.5] — 2026-08-24

### Fixed
- `update.sh`: Hermes-Binary-Suchkette deckt jetzt beide kanonischen
  Installations-Layouts ab (`~/.hermes/hermes-agent/` git-install und
  `~/src/hermes-agent/` source-install), geordnet nach Layout-Wahrscheinlichkeit.
  Kommentar dokumentiert die Layout-Konvention. Fund: Helper adversarial
  review (2026-08-23), reproduziert von Vela gegen die realen Setups
  hermes_christiane + hermes_helper; zweiter Helper-Review eingearbeitet
  (Suchketten-Reihenfolge, Kommentar-Präzisierung).
- `update.sh`: Erfolgsdetektion des Plugin-Updates präzisiert — matcht auf
  installer-eigene Tokens (`✓ Installed`, `Plugin installed:`) statt breitem
  `Installed`-Substring (falsch-positiv bei "Already installed") und ohne
  Zeilenanfänger-Anker (Installer rahmt Output in Unicode-Boxen, Fund aus
  v0.1.5-Review: `^`-Anker hatte 100% False-Negative-Rate).
- `update.sh`: Multi-User-Bug geschlossen — ohne `--home` wird das Ziel-Home
  jetzt aus dem ZIELUSER (`--user`, via getent) bestimmt statt aus `$HOME`
  des Aufrufers. Bei `root + --user hermes_helper` zeigt TH jetzt korrekt auf
  `/home/hermes_helper/.hermes` statt `/root/.hermes`. Fehlgeschlagene
  Home-Auflösung (unbekannter User, nicht-existierendes Home) führt zu
  hartem Exit 4 mit Hinweis auf `--home` — kein stiller Fallback. Alle 6
  Testfälle der Auflösungsmatrix grün (eigenes Home, root+helper,
  root+christiane, explizites --home gewinnt, unbekannter User, leeres Home).

## [0.1.1] — 2026-08-23

### Fixed
- Root `__about__.py` version synced with `src/toolshed/` (single-source
  versioning pending; pyproject is the source of truth).

### Internal
- ADR-0007 extended: isolation test (2 profiles), uninstall/update findings,
  rollback validated via commit-SHA install.

## [0.1.0] — 2026-08-23

First public-ready release.

### Added
- Adaptive tool-surface routing: first-turn, session-sticky narrowing of
  visible tool schemas (deterministic rules; optional LLM classifier).
- Floor toolsets: critical capabilities (`terminal`, `file`, `skills`,
  `memory`, `web`) are never pruned.
- Dynamic MCP routing: any configured MCP server becomes routable without
  hardcoding (`_build_dynamic_mcp_rules`).
- Monotonic recovery: `request_toolset` re-adds missed capabilities;
  fail-open on router errors.
- Shadow learning bridge: observation → signature → profile store →
  scoring → prediction (never routes; config-gated).
- Profile-scoped state: multi-agent safe by construction.
- Explicit authorization contract: requires
  `hermes plugins enable hermes-token-router --allow-tool-override`.
  Without the grant the plugin stays inactive (fail-closed).

### Validated
- Fresh Hermes upstream install (independent helper agent, different model):
  ~31% input-token reduction on identical tasks vs router-off.
- Earlier controlled paired workloads: 32–70% input reduction.
- Lifecycle: install → enable/grant → routing → persistence → profile
  isolation → update → rollback → uninstall.
- Known limitation: gateway-restart/learning-persistence not yet validated
  in a systemd-user environment.

### Not included (deliberately)
- Capability-index / discovery mechanisms (control runs showed no causal
  benefit over native recovery — see ADR notes and experiment reports).

## [0.1.4] — 2026-08-23

### Added
- `doctor --home <path>` — diagnose foreign Hermes homes (multi-user setups, D4)
- `info` check level in doctor output (neither fail nor warn)
- Robust `.hermes` dir detection via structure markers (plugins/, config.yaml)

### Fixed
- **Multi-user ownership**: update.sh runs all write steps as the target user
  (`--home`/`--user` contract) — root never owns plugin files
- doctor state-dir ownership detection for multi-user installs
- doctor global.enabled consistency check counts only the global block
- doctor plugins-list check uses `--plain` + name-independent matching
- doctor stale-grant check no longer reads the global Hermes config
- Supply-chain hygiene: pinned dev dependencies in CI, unpinned pip refs removed

### Known limitations (unchanged)
- Raw `hermes plugins install --force` can still reset plugin config; use `update.sh`
- Gateway-restart / learning persistence not yet fully validated in systemd-user env

**Validation:** fresh-install canary on upstream Hermes b766607b / v0.20.5 (MiniMax-M3);
multi-user migration on independent runtime (hermes_christiane, own venv + gateway);
all three agents (Vela, Christiane, Helper) productively running v0.1.2→v0.1.4 path.
