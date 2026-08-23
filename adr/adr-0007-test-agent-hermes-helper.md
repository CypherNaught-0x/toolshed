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

| F4 | COMPATIBILITY | Frischer Core lädt Plugin mit `enabled=False` — Ursache: generische Config hat `global.enabled:false` (Safe-Default) und keinen Profileintrag; `_get_profile_config` fällt auf global zurück | User setzt `global.enabled:true` ODER legt Profilsektion an — als offizieller Setup-Schritt dokumentiert (README) | ✅ geklärt |
| F5 | COMPATIBILITY | Frischer Core: `capability_check tools.override decision=deny evidence=not granted` — neue Plugin-Capability-Policy | Offizieller Weg: `hermes plugins enable <name> --allow-tool-override`; Grant landet als `plugins.entries.<id>.allow_tool_override:true` und wird verifizierbar erlaubt (`decision=allow`) | ✅ gelöst |
| B1 | CONFIG | OpenRouter-Weg scheiterte an MiniMax-Credits | Direkter Provider `minimax` + `MiniMax-M3` | ✅ umgangen |
| B2 | CONFIG | `.env` am falschen Ort (`~/` statt `~/.hermes/`) | verschoben | ✅ behoben |

## Schritt 5 — Installations-/Lifecycle-Gate ✅ BESTANDEN (2026-08-23, ~13:50)

Offizieller User-Flow, von null, auf frischem Upstream b766607b:

```
1. hermes plugins install file://<toolshed-repo>
2. hermes plugins enable hermes-token-router --allow-tool-override
   → "✓ Granted … permission to override built-in tools"
3. plugins.entries.<id>.allow_tool_override:true wird gesetzt (verifiziert,
   Log: decision=allow)
4. global.enabled:true in der Plugin-config.yaml (oder Profilsektion)
5. Routing-Lauf + Verifikation über --usage-file
```

**A/B-Beweis auf dem Helper (identischer Task):**

| Bedingung | Input-Tokens | Total |
|---|---|---|
| Router ON | 10.448 | 21.015 |
| Router OFF | 15.120 | 34.513 |
| **Ersparnis** | **31 %** | **39 %** |

31 % liegt in unserer bewiesenen Spanne (32–70 %) — Toolshed funktioniert als
fremdes Paket auf aktuellem Hermes-main mit einem Modell (MiniMax-M3), das im
Entwicklungsprototyp nie getestet wurde.

## Offizielles Install-/Grant-Modell (verifiziert am Upstream b766607b)

1. **Enable-State:** `plugins.enabled` Allow-Liste in config.yaml
   (`_get_enabled_plugins`). Plugins sind opt-in; `plugins.enable <name>` ist
   der offizielle CLI-Weg.
2. **tools.override Grant:** Consent-basiert via
   `plugins.entries.<id>.granted_capabilities` ODER Legacy-Key
   `plugins.entries.<id>.allow_tool_override:true` (#64228-Migration).
   CLI: `--allow-tool-override` / `--no-allow-tool-override`.
   Bundled Plugins sind automatisch trusted; Drittanbieter müssen den Grant
   explizit bekommen (fail-closed).
3. **Install ≠ Enable:** Der Installer installiert ohne Auto-Enable;
   Aktivierung ist ein separater, bewusster Schritt.
4. **Multi-Agent:** Grants liegen profilbezogen im jeweiligen Plugin-Home
   (#65593: ein Prozess konsultiert NUR sein eigenes Home) — kein Cross-Agent-Leak.

## Produktkonsequenzen für v0.1

1. README-Quickstart:
   ```
   hermes plugins install <repo-url>
   hermes plugins enable hermes-token-router --allow-tool-override
   # dann global.enabled:true (oder Profilsektion) in der Plugin-config.yaml
   ```
2. Security-Kapitel: Grant ist notwendig und transparent — kein stilles Sonderrecht.
   Ohne Grant bleibt Toolshed deaktiviert (fail-closed), absichtlich.
3. `diagnostics.py` sollte den Grant-Status prüfen und melden ("tools.override:
   not granted — router will stay inactive").

## Schritt 6 — Persistenz-/Lifecycle-Befund (2026-08-23, ~14:00)

| Prüfung | Ergebnis | Beleg |
|---|---|---|
| Funktionspersistenz | ✅ | 4+ unabhängige `-z`-Prozesse (je frischer Interpreter) routen konstant auf ~10k Input statt 15k (OFF) |
| Autorisierungspersistenz | ✅ | `plugins.entries.hermes-token-router.allow_tool_override:true` bleibt über alle Prozesszyklen; `plugins capabilities` zeigt `tools.override: granted` |
| Config-Persistenz | ✅ | `global.enabled:true` + Shadow-Pfade bleiben erhalten |
| Learning-/Reuse-Persistenz | ⚠️ NICHT VALIDIERBAR im `-z`-Modus | Shadow schreibt keine `profiles.json`/`events.jsonl` in `-z`-Läufen → braucht Gateway-Betrieb |
| Cold-vs-Warm | ✅ (Routing-Teil) | Session1 10.448 → Session2 10.235 (konstant); OFF-Baseline 15.120 |

**Gateway-Limit (Umgebungs-, nicht Produkt-):** `hermes gateway install/start`
scheitert am Helper mit `systemctl --user` Fehler (kein laufender user-systemd
für den Test-User). Der frische Helper ist damit reiner `-z`/CLI-Betrieb. Für
die volle Learning- und Gateway-Restart-Persistenz braucht es eine Umgebung mit
user-systemd ODER den produktiven Gateway-Host.

**Damit ist die Release-Gate-Matrix (GPT):**
- Install ✅ / Enable+Grant ✅ / Routing ✅ / Persistenz (Funktion+Auth+Config) ✅
- **Offen:** Learning-/Reuse-Persistenz + echter Gateway-Restart (braucht
  systemd-Umgebung); zweiter Agent/Isolation; Update/Rollback/Uninstall.

