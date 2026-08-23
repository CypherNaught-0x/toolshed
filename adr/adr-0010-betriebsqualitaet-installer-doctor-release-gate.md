# ADR-0010 — Betriebsqualität: Installer, Update-Erhalt, Doctor, Release-Gate

- Status: Accepted (Roadmap-Beschluss)
- Datum: 2026-08-23
- Auslöser: Übergang „Frontpage fertig" → Produktbetrieb. Die README ist
  Verkaufsfläche; jetzt kommt Betriebsqualität, damit Fremde Toolshed ohne uns
  betreiben können.

---

## Reihenfolge (bindend)

1. **Installer** (größter UX-Hebel)
2. **Update/State-Preservation** (D2 wird MIT dem Installer gelöst)
3. **doctor**
4. **Komplett frischer Canary** (README öffnen → Befehl → nichts von Hand)
5. **Release-Gate v0.1.2** (Version = nachweisbar installierbarer Zustand)
6. Erst danach: Router-Verbesserungen — und nur bei belegter Reibung

---

## 1. Installer

Ziel: Ein normaler Hermes-Nutzer muss weder `profile`, `config.yaml` noch
Grant-Interna vorher verstehen.

Pflichtverhalten:

```
Hermes erkennen
→ vorhandene Agents/Profile finden
→ Auswahl anzeigen („Agents", nicht „Profiles" als Jargon)
→ Release reproduzierbar installieren (--ref auf Release-Commit)
→ tools.override erklären + explizit bestätigen lassen
→ global.enabled setzen (der Schritt, den Nutzer heute vergessen)
→ verifizieren, dass Toolshed WIRKLICH aktiv ist (nicht nur installiert)
→ sauber scheitern statt halbfertig installieren (rollback des Teils)
```

Non-interactive Modus (agentenfreundlich):

```
toolshed-install --profile <name> [--ref <sha>] [--yes] [--json]
Exit-Codes: 0 ok · 1 hermes nicht gefunden · 2 grant verweigert ·
            3 aktivierung fehlgeschlagen · 4 verifikation fehlgeschlagen
Keine Secrets in Logs/Output. --json für automatisierte Canary-Läufe.
```

## 2. Update / State-Preservation (löst D2)

`toolshed update` (oder Installer-Modus):

```
config.yaml sichern → neue Version installieren → config/state migrieren
→ Grant prüfen → enabled-Zustand ERHALTEN → Routing-Smoke → melden
```

D2 („Update erfolgreich, Router heimlich OFF") gilt als behoben erst, wenn der
enabled-Zustand ein Update überlebt — nachweisbar im Helper-Canary.

## 3. doctor

Beantwortet mindestens:

```
✓ Hermes found (version/commit)
✓ Toolshed installed (version)
✓ tools.override granted?
✓ routing enabled?
✓ profile state writable?
✓ recovery tool available?
! stale grant after uninstall
! unsupported Hermes version
```

--json für Agenten/CI. doctor ist Voraussetzung dafür, dass später ein Agent
selbst diagnostizieren kann, was kaputt ist.

## 4. Frischer Canary nach Installer

Nicht den bestehenden Helper weiterpflegen, sondern einmal komplett:
neuer Zustand → README öffnen → Install-Befehl ausführen → nichts von Hand.
Besteht das nicht, gehört das Produkt noch nicht fremden Nutzern.

## 5. Release-Gate v0.1.2

Eine Version ist released, wenn:

```
[ ] eindeutige Version + Tag auf korrektem Commit
[ ] Changelog
[ ] CI grün
[ ] Helper-Canary bestanden (Installer-Weg)
[ ] Rollback getestet
[ ] Update hat enabled-State erhalten (D2 bewiesen behoben)
```

## 6. Issue Templates (klein, sofort)

`.github/ISSUE_TEMPLATE/`: bug_report.md · installation_problem.md ·
hermes_compatibility.md · feature_request.md.

Bug report fragt direkt ab: Hermes version · Toolshed version/commit · OS ·
Profile count · Install method · doctor output · Expected vs Actual.

---

## Nicht tun

- Keine Capability-Index-/Learning-/Heuristik-Ideen — der Router-Core hat
  keinen belegten Defekt. Neue Mechanismen erst bei realem Nutzer-Feedback.
- D2 nicht in der Routinglogik patchen — gehört in Installer/Updater.

---

## Umsetzungsstand (2026-08-23)

| Punkt | Status | Beleg |
|---|---|---|
| 1. Installer v1.1 | ✅ | `install.sh` — 3 Bugs (I1 Arg-Parsing, I2 Grant-Prompt in --yes, I3 Enable-Erkennung) im Helper-Lauf gefunden+gefixt; JSON/Exit-Codes verifiziert |
| 2. Update/State-Preservation | ✅ | `update.sh` — Backup vor Update, enabled/mode/floor wiederhergestellt, Grant+enabled verifiziert, Restore bei Fehler; Helper-Lauf: enabled:true blieb, Grant blieb, Routing-Smoke grün. **D2 behoben** |
| 3. doctor | ✅ `doctor.sh` — 13 Checks, human + valides --json, Exit 0/1/2; Helper-Lauf: exit 1 (3 Warnungen, 0 Fehler) |
| 4. Frischer Canary mit Installer-Weg | ✅ **KOMPLETT GRÜN** (2026-08-23, ~17:30): Reset auf null → Install aus GitHub (Scanner grün nach Supply-Chain-Hygiene) → Enable+Grant → enabled:true → doctor (0 Fehler) → Routing-Smoke ✅ → update.sh (State preserved, doctor grün) → Rollback auf v0.1.0-SHA ✅ → Uninstall/Reinstall via Installer ✅. Befund D2 bestätigt NUR beim rohen --force; update.sh verhindert ihn |
| 5. Release-Gate v0.1.2 | ⏳ offen — alle Voraussetzungen außer dem finalen Tag erfüllt |
| 6. Issue Templates | ✅ 4 Templates + config.template.yaml |

## Schritt 12 — Produktive Migration (2026-08-23, ~18:30)

| Agent | Legacy | Toolshed v0.1.2 | Grant | enabled | doctor | Status |
|---|---|---|---|---|---|---|
| Vela (default) | b41564d eingefroren in legacy-reference/ | ✅ pinned 6d1e2bc | ✅ | ✅ true | ✅ 0 Fehler | **produktiv aktiv, Routing live** |
| hermes_christiane | kein Legacy-Router vorhanden | ✅ pinned 6d1e2bc | ✅ | ✅ true | manuell verifiziert* | produktiv aktiv |
| hermes_helper | Canary + Long-Run Worker | v0.1.x Teststand | n/a (Test) | testweise | Canary-Pfad | Canary/Worker |

**Neuer Befund D4 (doctor):** `doctor.sh` hat keinen Parameter für fremde
Hermes-Homes (`--home`). Bei Multi-Agent-Setups mit eigenen Unix-Usern
(Christianes Home: /srv/companion/hermes_christiane) läuft der doctor nur auf
dem eigenen Home. Fix für v0.1.3: `--home <path>` Option.

**Christianes Setup-Besonderheit:** Ihr Hermes läuft als eigener Unix-User mit
eigenem .hermes-Home und eigenem Gateway-Prozess; das CLI wird über den
Shebang auf das geteilte Hermes-venv geroutet. Installation/Enable liefen über
root+HOME-Umleitung (dokumentierter Migrationsweg für Multi-User-Setups).

**Gateway-Restart für Christiane:** Das laufende Gateway (PID 2431886, seit
Aug 21) muss neu starten, um Toolshed zu laden — beim nächsten geplanten
Restart oder explizit.
