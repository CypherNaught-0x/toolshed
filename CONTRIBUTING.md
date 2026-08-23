# Contributing

Thanks for your interest in contributing to Toolshed!

## Project roles

- **Owner:** repository decisions, releases, permissions.
- **Maintainer/Author:** development, patches, issue triage.

## How to contribute

1. Open an issue first for anything that changes scope or behavior.
2. Fork, create a feature branch, keep changes small.
3. Run the test suite before pushing:
   ```bash
   python -m venv .venv
   .venv/bin/pip install -e ".[dev]"
   # dev tools (pytest, ruff) come from the [dev] extra
   .venv/bin/pytest tests/ -q
   .venv/bin/ruff check src/
   ```
4. CI must pass (tests + lint + secret/path scan).
5. PRs are reviewed by the maintainer; expect questions about routing
   decisions and evidence.

## Ground rules

- No secrets, tokens, or private paths in commits (CI enforces a scan).
- No new mechanisms without a control run proving they're needed.
  See `adr/adr-0001-0006-foundation.md` and the C/D experiment notes —
  we removed an entire mechanism because its control test showed it wasn't
  causal. Evidence beats elegance.
- Keep the product core small: tool-surface reduction + explicit grant +
  native recovery. Anything else needs an ADR.

## Reporting bugs

Open an issue with:

- Toolshed version,
- Hermes Agent version (`hermes --version`),
- profile setup (single/multi-agent),
- log excerpt showing router behavior
  (`grep "token-router" ~/.hermes/logs/agent.log`).

For security vulnerabilities, see [SECURITY.md](SECURITY.md).
