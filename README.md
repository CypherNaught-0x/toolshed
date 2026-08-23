# Toolshed

**An adaptive tool-surface proxy for Hermes** — reduces repeated tool-schema
overhead while preserving on-demand recovery.

> Fork heritage: Toolshed is based on [hermes-token-router](https://github.com/JonathanRivera/hermes-token-router)
> (MIT, Jonathan Rivera) and was substantially extended in practical
> multi-agent use: dynamic MCP routing, session-sticky shadow learning,
> floor policy, and telemetry. See `adr/` for all architecture decisions.

## What it does

Every model tool ships with every API call — 55+ tools mean ~67 KB of schema
JSON per request before the actual task starts. Toolshed routes the tool
surface per session down to the predicted working set (typically 5–12 tools),
keeps critical floor capabilities always loaded, and lets the agent reload
missing capabilities on demand via `request_toolset`.

**Measured** (real workloads, identical tasks, router ON vs OFF):
32–70% less input tokens at comparable output quality; ~31% on a fresh,
minimal setup. Zero recovery failures. Honest trade-off: less permanent tool
visibility = less spontaneous exploration (documented in `adr/`).

## Requirements

- Hermes Agent (validated against upstream `b766607b`, v0.20.5)
- Python 3.10+

## Install

```bash
# 1. Install the plugin (official Hermes plugin path)
hermes -p <profile> plugins install <repo-url>

# 2. Enable WITH the explicit tool-override grant
hermes -p <profile> plugins enable hermes-token-router --allow-tool-override

# 3. Activate routing for this profile:
#    in the plugin's config.yaml set global.enabled: true
#    (or add a profiles.<name>.enabled: true section)
```

**Install ≠ authorization.** Without the `tools.override` grant Toolshed
stays inactive by design (fail-closed). The grant is the explicit security
contract: you are allowing this plugin to change which tools your agent sees.

Verify:

```bash
hermes -p <profile> plugins capabilities hermes-token-router
# → tools.override: granted
```

Routing activity shows in logs as `deterministic route reason=…` and
`narrowed to N toolsets`.

## Configuration (deliberately minimal)

```yaml
global:
  enabled: true            # router on/off
  mode: active             # active = route | shadow = collect data only
  floor_toolsets:          # NEVER pruned
  - terminal
  - file
  - skills
  - memory
  - web
shadow:
  enabled: true            # session-sticky learning bridge (profile-local)
profiles:
  my-agent:                # optional per-profile overrides
    enabled: true
```

## Update / Rollback / Uninstall

```bash
# Update to latest published state
hermes -p <profile> plugins update hermes-token-router

# Rollback to a known release (commit SHA behind the release tag!)
hermes -p <profile> plugins install <repo-url> --ref <previous-release-commit-sha> --force

# Uninstall (agent keeps working; grant entry may remain in config.yaml —
# remove it manually if you want the authorization gone too)
hermes -p <profile> plugins remove hermes-token-router
```

Note: annotated git tags have their own object SHA. Rollback targets must be
the **commit SHA** behind a tag, not the tag's object SHA.

## Multi-Agent

One profile = one agent = one isolated state (routing, learning, telemetry).
No shared agent-specific state across profiles (ADR notes).
`hermes profile create --clone` does **not** copy plugins — repeat install +
enable + grant per profile.

## Security

See [SECURITY.md](SECURITY.md) for the full model. Summary:

- **Fail-closed on authorization:** no grant → no tool-surface manipulation.
- **Fail-open on routing errors:** router mistakes degrade to full tool
  surface or native recovery, never functionality loss.
- **Floor immutability:** task content cannot alter which toolsets are
  protected.
- **Prompt/repo content cannot override policy:** malicious text in issues,
  READMEs, or tool descriptions cannot expand grants.

## Known limitations

- Gateway-restart/learning persistence not yet validated in a systemd-user
  environment.
- Less permanent tool visibility means fewer "stumble-upon" discoveries;
  native recovery (`request_toolset`) covers required capabilities.
- Validated against Hermes upstream commit `b766607b`; newer cores may need
  compatibility checks (plugin capability system).

## Docs

- `adr/` — Architecture Decision Records (fork positioning, security,
  multi-agent state, experiment exclusions)
- `CHANGELOG.md` — release history

## License

MIT — see LICENSE and NOTICE for fork attribution.
