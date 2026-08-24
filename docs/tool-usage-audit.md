# Tool-usage audit and tuning

Current Hermes exposes plugin-provided slash commands, so Toolshed uses the native
`/toolshed-audit` command rather than installing a separate flat skill.

## Data sources and privacy

The command resolves the active profile from Hermes and opens that profile's `state.db` read-only.
Its SQL selects only `messages.tool_calls`, `messages.tool_name`, and `messages.timestamp`; message
content, API content, reasoning, system prompts, and tool outputs are never selected. Toolshed also
keeps a profile-local JSONL record of recovery events containing only timestamp, session identifier,
recovery source, and toolset name.

The deterministic report combines those metadata sources with the live Hermes registry and current
Toolshed configuration. It labels toolsets as:

- **never-used** — no calls in the lookback window;
- **rarely-used** — one or two calls by default;
- **frequently-used** — five or more calls by default;
- **recovery-added** — loaded through `request_toolset`, request middleware, or post-call recovery;
- **floor**, **eligible**, **routed**, or **excluded** — current surface/configuration state.

Thresholds are configurable under `global.audit` or a profile override. The lookback is selected with
`--days` and defaults to 30 days.

## Report modes

```text
/toolshed-audit
/toolshed-audit --days 90
/toolshed-audit --days 30 --report
/toolshed-audit --days 30 --report --json
```

The default sends only the deterministic report to Hermes' host-owned active model and asks it to
suggest floor, eligible/on-demand, and possible exclusion lists. `--report` (alias `--no-llm`) is
fully deterministic and offline. A model response is advice only; it cannot modify configuration.
Never-used data alone is weak evidence because the lookback may not represent future work.

## Explicit, reversible edits

No edit occurs unless the invocation includes at least one `--apply-*` option and the explicit
`--approve` token:

```text
/toolshed-audit --report \
  --apply-floor file,terminal,skills \
  --apply-exclude image_gen,video_gen \
  --approve
```

An approved edit:

1. targets `profiles.<active-profile>` rather than another agent;
2. refuses to run when global fail-open or automatic recovery safety is disabled;
3. makes floor membership win over exclusion;
4. validates the generated YAML;
5. writes a timestamped backup beside the config;
6. uses an atomic replacement; and
7. returns a unified diff.

Exclusion removes a toolset only from the initial candidate set. The complete registry remains cached,
`request_toolset` can add an excluded toolset, request middleware can recover it, and uncertainty or
errors still restore the full tool surface. To roll back, restore the displayed backup and restart the
profile's Hermes process.

## Classifier privacy

The audit's optional model sees metadata only. This is separate from Toolshed's optional routing
classifier. The classifier is disabled by default; when explicitly enabled, it can send up to the
first 1,500 characters of a user message to the configured classifier provider.
