# Changelog

All notable changes to Toolshed are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [SemVer](https://semver.org/) (0.x = pre-stable).

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
