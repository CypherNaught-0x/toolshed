# ADR-0007: Isolierter Test-Agent `hermes_helper` als dauerhafter Fresh-Install-Kandidat

- Status: Accepted
- Datum: 2026-08-23
- Kontext / Auslöser: Release-Gate für Toolshed v0.1 — „ein anderer Hermes-Agent
  muss das Ding sauber installieren und benutzen können". Hugo-Freigabe: Helper
  bleibt dauerhaft bestehen, wird NICHT nach dem Test gelöscht.

## Entscheidung

1. **Eigener UNIX-User** `hermes_helper` (uid 1003) mit eigenem Home.
   Keine Symlinks, kein Rückgriff auf Velas `~/.hermes`.
2. **Frischer Upstream-Checkout** von Hermes-main (NICHT Velas Fork kopieren):
   - Repository: https://github.com/NousResearch/hermes-agent.git
   - Install-Pfad: `/home/hermes_helper/src/hermes-agent`
   - Version beim Setup: **Hermes Agent v0.20.5 (2026.8.19), upstream commit b766607b**
   - Python: System-Python des Hosts (Debian 13), venv unter `venv/`
   - Installationsweg: `python3 -m venv venv && pip install -e .`
3. **Eigene Modellschiene:** MiniMax-M3-API über den vorgesehenen Secret-Mechanismus
   (.env im Helper-HOME). API-Key wird NIE in Repo, Logs, ADRs oder Testdaten
   geschrieben — nur per Umgebungsvariable referenziert.
4. **Zweck (fest):** Fresh-Install-Kandidat, Plugin-Testagent, Upgrade-Testagent,
   Kompatibilitätsprüfer gegen neues Hermes-Upstream. Vorerst KEINE produktiven
   Aufgaben, KEINE privaten Vela-Daten.

## Fehlerklassifizierung (GPT-Schema, verbindlich für alle Testläufe)

UPSTREAM / PACKAGING / COMPATIBILITY / ROUTING / RECOVERY / PERSISTENCE /
ISOLATION / SECURITY. Nicht jeder Fehler wird am Router repariert.

## Testreihenfolge (verbindlich)

Baseline ohne Toolshed → Plugin-Install wie ein Fremder → Installations-Gate →
erster Funktionslauf mit Rohdaten → Recovery-Test → Persistenzpfad (Session/
Neustart/Gateway-Restart) → zweiter Agent (Isolation) → Update-Test →
Uninstall/Rollback. Kein manuelles Reparieren im Helper-Profil: Jeder Workaround
ist ein Packaging-/Deploy-Bug und wird im Toolshed-Source gefixt + neu installiert.

---

# Testprotokoll: hermes_helper Setup (laufend aktualisiert)

## Schritt 1 — UNIX-User ✅

```
useradd -m -s /bin/bash hermes_helper   → uid=1003(hermes_helper)
```

## Schritt 2 — Frischer Upstream-Checkout ✅

- Clone: `git clone --depth 1 https://github.com/NousResearch/hermes-agent.git`
  nach `/home/hermes_helper/src/hermes-agent` (~10.075 Dateien)
- venv gebaut, `pip install -e .` erfolgreich
- Verifikation: `hermes --version` → **Hermes Agent v0.20.5 (2026.8.19),
  upstream b766607b**

**Abgleich mit unserem Dev-Stand:** Unser produktiver Hermes läuft ebenfalls
v0.20.5, aber auf eigenem Fork-Stand (6 ahead / 123 behind main). Der Helper
testet damit echtes aktuelles main — genau der Sinn des Gate-Tests.

## Schritt 3 — Modellschiene MiniMax M3 ✅ (mit 2 Fehlern)

- `.env` kopiert nach `/home/hermes_helper/.hermes/.env` (600, Eigentümer helper)
  — enthält `MINIMAX_API_KEY` für den **direkten** MiniMax-Provider
  (`https://api.minimax.io/v1`), nicht OpenRouter.
- **Fehler B1 (UPSTREAM/CONFIG):** Erster Versuch lief über `openrouter` →
  „billing/credits exhausted" für minimax/minimax-m3. Ursache: falscher Provider-
  Weg. Fix: direkter Provider `minimax` mit Modell `MiniMax-M3`.
- **Fehler B2 (UPSTREAM/CONFIG):** `.env` lag erst am falschen Ort
  (`~/`, erwartet: `~/.hermes/.env`) → „No LLM provider configured".
  Dokumentierter Konventionsort.

## Schritt 4 — Baseline ohne Toolshed ✅ BESTANDEN

```
Task: "Schreibe das Wort BANANE in die Datei /home/hermes_helper/test_banane.txt"
Ergebnis: Datei geschrieben + verifiziert (6 Bytes = "BANANE")
```

Clean Baseline dokumentiert. Ab hier ist jeder Fehler ein Toolshed-/Packaging-Bug.

## Offene Punkte / gefundene Fehler

| # | Bereich | Befund | Fix | Status |
|---|---|---|---|---|
| F1 | PACKAGING | `pyproject.toml` lag in `src/` und referenzierte `../README.md` → setuptools DistutilsOptionError „Cannot access … outside src" | pyproject ans Repo-Root, package-dir auf src/ | ✅ behoben |
| F2 | PACKAGING | `toolshed.__version__` fehlte (lag nur in `__about__.py`, nicht importiert) | Import in `__init__.py` ergänzt | ✅ behoben |
| F3 | offen | Hermes-Plugin-Loader erwartet `plugin.yaml` + `__init__.py` im selben Verzeichnis (Directory-Scan, flach/kategorie); unser `src/toolshed/`-Layout muss gegen den echten Installer validiert werden | — | ⏳ nächster Schritt |
| B1 | CONFIG | OpenRouter-Weg scheiterte an MiniMax-Credits | Direkter Provider `minimax` + `MiniMax-M3` | ✅ umgangen |
| B2 | CONFIG | `.env` am falschen Ort (`~/` statt `~/.hermes/`) | verschoben | ✅ behoben |
