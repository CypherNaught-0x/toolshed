# Toolshed

**An adaptive tool-surface proxy for Hermes** — reduces repeated tool-schema
overhead while preserving on-demand recovery.

> Fork-Herkunft: Toolshed basiert auf dem [hermes-token-router](https://github.com/JonathanRivera/hermes-token-router)
> (MIT, Jonathan Rivera) und wurde im praktischen Multi-Agent-Einsatz wesentlich
> weiterentwickelt: dynamisches MCP-Routing, session-sticky Shadow-Learning,
> Floor-Policy und Telemetrie. Siehe `adr/` für alle Architekturentscheidungen.

## Was es tut

Jedes Modell-Tool wird bei jedem API-Call mitgeschickt — 55+ Tools bedeuten
~67 KB Schema-JSON pro Request, bevor die eigentliche Aufgabe beginnt. Toolshed
routet die Toolfläche pro Session auf das vorhergesagte Working Set (typisch
5–12 Tools), hält kritische Floor-Fähigkeiten immer geladen und erlaubt dem
Agenten, fehlende Capabilities per `request_toolset` on-demand nachzuladen.

**Gemessen (reale Arbeitsläufe, identische Aufgaben, Router ON vs OFF):**
32–70 % weniger Input-Tokens bei vergleichbarer Ergebnisqualität, 0 Recovery-
Ausfälle. Ehrlicher Trade-off: weniger permanente Tool-Sicht = weniger
spontane Exploration (dokumentiert in `adr/adr-0001-0006-foundation.md`).

## Install

```bash
hermes -p <profil> plugins install <repo-url> --enable
```

Danach Routing prüfen:

```bash
headroom doctor   # bzw. python diagnostics.py aus dem Plugin-Verzeichnis
```

Logs zeigen pro Session: `deterministic route reason=…`, `narrowed to N toolsets`.

## Konfiguration (bewusst minimal)

```yaml
enabled: true            # Router an/aus (Profil-Level überschreibt global)
mode: active             # active = routet | shadow = sammelt nur Vergleichsdaten
floor_toolsets:          # werden NIE weggeprunt
  - terminal
  - file
  - skills
  - memory
  - web
learning: true           # Shadow-Learning-Bridge (session-sticky, profil-lokal)
```

## Multi-Agent

Ein Profil = ein Agent = eigener State. Kein globaler Shared-State (ADR-0003).
Mehrere Agents auf derselben Maschine konfigurieren nichts gegenseitig um.

## Sicherheit (ADR-0004)

- **Fail-open:** jeder Router-Fehler → volle Toolfläche, nie weniger.
- **Floor unveränderlich durch Task-Inhalte** — nur lokale config.yaml bestimmt ihn.
- CI-Gate: pytest-Szenarien (Recovery, Restart-Isolation, Multi-Agent-Trennung,
  stale Routes), ruff, pip-audit, Pfad-/Secret-Scan.

## Docs

- `adr/` — Architecture Decision Records (Fork-Positionierung, Security,
  Multi-Agent-State, Experiment-Ausschlüsse)
- `docs/benchmarks.md` — Messaufbau und Zahlen

## License

MIT
