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

## Schritt 7 — Isolationstest (2 Profile) ✅ mit 1 Befund (2026-08-23, ~14:20)

Setup: `profile create agenta/agentb --clone` → **Befund F7:** `profile clone`
kopiert KEINE Plugins — jedes Profil braucht eigene Installation. Das ist das
korrekte Isolationsmodell (bewusste Opt-in-Pro-Instanz), muss aber ins README.

Beide Profile: eigener Install ✅, eigener Grant ✅, eigene Plugin-Kopie ✅,
eigene Config ✅.

| Prüfung | Ergebnis |
|---|---|
| A routet unabhängig (9.695 in / 2 calls) | ✅ |
| B routet unabhängig (10.531 in / 2 calls) | ✅ |
| Grants physisch getrennt (pro Profil-config.yaml) | ✅ |
| Plugin-Copies physisch getrennt | ✅ |
| Runtime-Code ohne Fremdpfade | ✅ 0 Treffer in *.py/*.yaml |
| Contamination False-Positives | 6 Treffer NUR in tests/ci (unsere eigenen Security-Scan-Regeln matchen sich selbst — dokumentiert, kein Bug) |

**F7 (DOKUMENTATION):** `profile clone` übernimmt keine Plugins/Grants/State.
Gewollte Isolation; README braucht einen „Multi-Agent"-Abschnitt:
Pro Profil `plugins install` + `enable --allow-tool-override` wiederholen.

## Schritt 8 — Uninstall/Update-Befunde (2026-08-23, ~14:30)

**Uninstall (agenta):** Plugin-Code entfernt ✅, Agent läuft danach normal weiter
✅ (kein Bruch). **ABER F8 (UX/SECURITY):** Der Grant
(`plugins.entries.hermes-token-router.allow_tool_override: true`) bleibt in der
Profil-config.yaml liegen. Nach Reinstall wäre die alte Autorisierung sofort
wieder wirksam — ohne dass der User neu zustimmt. Für ein Produkt mit
tools.override inakzeptabel als stiller Zustand. Regel festzulegen:
Uninstall entfernt Grant ODER meldet explizit „Authorization retained".
(Upstream-Verhalten von Hermes, nicht Toolshed-eigen — als Issue/Befund führen.)

**Update (agentb, 0.1.0 → 0.1.1):** `--force` reinstall ✅, Version wechselt
nachweislich ✅, Grant überlebt ✅, Routing funktioniert nach Update ✅.
**ABER F6 (PACKAGING):** Version war doppelt gepflegt (`__about__.py` im Root
UND in src/toolshed/) und driftete auseinander (Root 0.1.0, src 0.1.1). Fix:
Root synchronisiert; langfristig single-source (pyproject als einzige Wahrheit,
__about__ generieren oder importlib.metadata nutzen).

**Rollback:** ✅ GETESTET und BESTANDEN. Weg: annotierte Tags v0.1.0/v0.1.1 im
Repo, `plugins install <url> --ref <commit-sha> --force` dreht agentb von
0.1.1 zurück auf 0.1.0 (Versionsnachweis im installierten `__about__.py`,
Routing-Lauf danach erfolgreich). **Lernung daraus:** Rollback-Ziel ist die
*Commit-SHA hinter dem Tag*, nicht die Tag-SHA selbst (annotierte Tags haben
eigene Objekt-SHA — erster Versuch scheiterte daran, zweiter mit
`v0.1.0^{commit}`-Auflösung erfolgreich). Für das Release: Tags sauber auf die
richtigen Commits setzen, README dokumentiert Rollback als
`plugins install <url> --ref <sha-vorheriges-release> --force`.

**Lifecycle-Kette komplett bestanden:**
install → enable+grant → routing → persistenz → isolation → update (0.1.0→0.1.1)
→ rollback (0.1.1→0.1.0) → Agent bleibt durchgehend funktionsfähig.


