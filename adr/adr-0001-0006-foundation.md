# ADR-0001: Toolshed ist ein Hermes-Plugin-Fork mit eigenständiger Identität

- Status: Accepted
- Datum: 2026-08-23
- Kontext / Auslöser: Release-Entscheidung des Vela Tool-Proxy Projekts

## Kontext

Toolshed entstand als Fork/Erweiterung des Hermes-Token-Routers (hermes-token-router,
MIT, Jonathan Rivera) und wurde im praktischen Einsatz (Vela/Hugo, Multi-Agent-VPS)
weiterentwickelt. Die Frage: Wie positionieren wir das Projekt — Fork, Plugin,
eigenständiges Produkt?

## Entscheidung

1. Toolshed ist ein **Hermes-Plugin** (kein eigener Agent-Stack, kein Netzwerk-Proxy).
   Es sitzt zwischen Agent-Core und Tool-Surface.
2. Die **Fork-Herkunft wird prominent dokumentiert** (README + NOTICE): Basis war
   hermes-token-router; die wesentlichen Erweiterungen sind dynamisches MCP-Routing,
   Shadow-Learning-Bridge (Multi-Agent, session-sticky Signatures), Floor-Policy und
   Telemetrie.
3. Positionierung: *"an adaptive tool-surface proxy for Hermes"* — Differenzierung zu
   Context-Compression-Proxys (Headroom AI, Paritok): Toolshed arbeitet auf der
   Tool-Schema-Ebene IM Agenten, nicht als Netzwerk-Layer.

## Konsequenzen

+ Ehrliche Herkunft schützt vor Community-Konflikt und erfüllt Fork-Etikette.
+ Plugin-Form bedeutet: Installation per `hermes plugins install`, kein Core-Fork.
− Wir erben die Hook-Grenzen des Hermes-Plugin-Systems (dokumentierte Kompromisse).

# ADR-0002: Keine Nutzerdaten, keine Umgebungsannahmen im Build

- Status: Accepted
- Datum: 2026-08-23

## Kontext

Der Entwicklungsprototyp enthielt harte Pfade (`/srv/companion/hermes_hugo/...`),
Testprofil-Referenzen und Learning-Daten aus der Vela-Umgebung.

## Entscheidung

Der öffentliche Build enthält:
- keine absoluten Pfade außerhalb des jeweiligen Hermes-Profils (`~/.hermes/profiles/<name>/`)
- keine Learning-/Telemetrie-Daten aus der Entwicklungsumgebung
- keine Namen/IDs realer Agents, Server oder Dienste
- Config ausschließlich über `config.yaml` des Profils (Defaults im Repo, Overrides lokal)

Verifiziert vor jedem Release durch den Secret-/Path-Scan in CI (ADR-0004).

# ADR-0003: Multi-Agent-State-Trennung ohne globale Registrierung

- Status: Accepted
- Datum: 2026-08-23

## Kontext

Hermes-Nutzer betreiben mehrere Agents (bei uns: 5). Routing-State und
Learning-Daten dürfen nicht zwischen Agents fluten.

## Entscheidung

- Jedes Profil hält seinen eigenen State unter seinem eigenen Profilpfad.
  Es gibt KEINEN globalen Shared-State in v0.1.
- Optionale spätere Erweiterung (v0.2+): anonymisiertes, opt-in geteiltes
  Tool-Metadaten-Wissen. Nicht Bestandteil von v0.1.
- Sessions innerhalb eines Profils teilen bewusst das Working-Set-Learning
  (das ist der Warm-Start-Zweck), getrennt per Session-ID.

# ADR-0004: Sicherheit — das Plugin manipuliert Tool-Schemas, daher Fail-open + Scan-Gate

- Status: Accepted
- Datum: 2026-08-23

## Kontext

Ein Fehler im Router könnte dem Agent Tools entziehen oder bösartige
Toolbeschreibungen könnten Routing-Policies beeinflussen.

## Entscheidung

1. **Fail-open Invariante:** Jeder Router-Fehler führt zur vollen Toolfläche,
   nie zu weniger. Recovery (request_toolset) muss nach jedem Eingriff
   registriert sein, sonst wird nicht gekürzt.
2. **Floor unveränderlich durch Task-Inhalte:** floor_toolsets kommen nur aus
   der lokalen config.yaml. Toolbeschreibungen/Repo-Inhalte können die Policy
   nicht erweitern oder überschreiben.
3. **CI-Gate:** GitHub Actions führt bei jedem PR aus: pytest (inkl. der
   Headroom-spezifischen Szenarien: Recovery, Restart-Isolation, Multi-Agent-
   Trennung, stale Routes), ruff, pip-audit und einen Pfad-/Secret-Scan
   (kein `/srv/`, kein `/home/<user>`, keine Profilnamen).
4. **Read/Write-Grenze:** Das Plugin selbst hat keine Write-Rechte auf
   Nutzerdaten außerhalb seines Profilpfads; Tests müssen belegen, dass ein
   Read-only-Task nie Schreibrechte eskaliert.

# ADR-0005: Experimente C/D werden NICHT ausgeliefert

- Status: Accepted
- Datum: 2026-08-23

## Kontext

Die Capability-Index-Experimente (passiver Index C-v1, Entscheidungsregel D-v1)
ergaben: Aktivierung hängt vom Aufgabenzwang ab, nicht vom Hinweis; die
B-Kontrolle leistete dasselbe ohne Mechanismus.

## Entscheidung

Capability-Index und Aktivierungsregel sind **nicht Teil von Toolshed v0.1**.
Dokumentiert bleiben sie als Forschungsanhang (Experiment-Log), um den
Explorationstrade-off ehrlich zu erklären. Wiederaufnahme nur mit neuem
kausalem Nachweis gegen eine B-Kontrolle.

# ADR-0006: Benennung — „Toolshed", bewusst NICHT „Headroom"

- Status: Accepted
- Datum: 2026-08-23

## Kontext

„Headroom" ist bereits etabliert (headroom-ai, ~29k Stars, gleiche Nische:
Kontext-/Token-Optimierung für Agenten) — Namenskollision würde Verwirrung und
SEO-Verlust bedeuten.

## Entscheidung

Produktname: **Toolshed**. Metapher: die Werkbank bleibt klein (geroutetes
Working Set), der Schuppen kennt den Rest (Recovery + Learning). Getestet auf
Eindeutigkeit gegenüber bekannten Hermes-/LLM-Infrastrukturprojekten.
