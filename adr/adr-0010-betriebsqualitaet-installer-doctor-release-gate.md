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
| 3. doctor | ⏳ offen |
| 4. Frischer Canary mit Installer-Weg | ⏳ offen |
| 5. Release-Gate v0.1.2 | ⏳ offen |
| 6. Issue Templates | ✅ 4 Templates + config.template.yaml |
