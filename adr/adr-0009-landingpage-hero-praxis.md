# ADR-0009 — Landingpage-/Hero-Praxis für Toolshed (aus Websearch)

- Status: Accepted (Positionierung für die kommende Frontpage)
- Datum: 2026-08-23
- Kontext: Vor dem Bau der Hero-/Landingpage. Quellen: Evil Martians
  „100+ devtool landing pages 2025“, Web Anatomy „Best Open Source Websites“
  (12 Seiten, Juni 2026), Web Anatomy „Best Developer Tool Websites“ (57 Seiten,
  Aug 2026), Nakora „374 developer landing pages“.
- Zweck: Nur die generalisierbaren Regeln für einen Devtool-/Open-Source-Hero
  festhalten, die Toolsheds tatsächliche Stärken transportieren.

---

## Kernaussage

> Die Hero muss in den ersten 3–5 Wörtern sagen, WAS das Tool ist und FÜR WEN.
> Danach kommt sofort das *Trybare* (Install-Befehl, Code-Snippet), nicht
> Marketingtext. Developer evaluieren durch Ausprobieren, nicht durch Lesen.

## 1. Hero-Formel (Nakora / Evil Martians)

```text
Adjektiv  + Keyword  + ICP/Use-Case
„Open-source, adaptiver Tool-Surface-Proxy für Hermes-Agenten"
(ersetzt „Revolutionary context platform")
```

- Subheadline: 1 Satz was es tut + 2–4 Bullets was es bringt (max. ~10s lesen).
- Zwei CTAs: primär spezifisch („Install Toolshed“), sekundär schwach („View
  docs“ / GitHub). Niemals generisches „Get started“.
- Zentrierte Komposition ist der 2025/26-Default; visuelles Element UNTER der
  Headline (Code-Snippet, Terminal, Diagramm).

## 2. Tryable im Hero — Pflicht für Developer

Quellen konsistent: Seiten, die einen **one-line install / Playground / Code-
Snippet** im Hero zeigen, konvertieren am besten (Strapi, Meilisearch, Supabase,
Neon). Seiten, die Marketing-Copy vor das Trybare stellen, konvertieren am
schlechtesten.

- **Toolshed:** Der Hero-Install-Befehl ist das Kern-Element, kein Text.
  ```bash
  hermes plugins install Huy3ko/toolshed
  hermes plugins enable hermes-token-router --allow-tool-override
  ```
- Kein Signup / keine Karte vor dem Tryen (friction kills adoption).
- Terminal-/CLI-Ästhetik statt Stockphotos-Laptops.

## 3. Trust früh und ehrlich

- **Echte, kontextuelle Benchmarks statt Behauptungen:** „31 % weniger
  Input-Tokens auf frischem Hermes, 32–70 % in gemessenen A/B-Workloads“ —
  mit n und Messbedingungen (Claim-Disziplin aus ADR-0008).
- Vergleichsdaten statt „wir sind besser“: ehrlicher Trade-off (weniger
  Explorationstiefe) MIT nennen — das baut Vertrauen.
- GitHub-Link + Lizenz sichtbar (Open-Source-Status nie verstecken).

## 4. Sections, die bei Devtools überproportional tragen

- **How It Works** (sequenzierter Workflow): höchste durchschnittliche Scores
  aller Section-Typen (88.6). Toolshed: Router-ON → gekürzte Fläche →
  on-demand Recovery.
- **Problem-Section** ist die schwächste (Ø 24) — Toolshed braucht keine lange
  Problem-Erzählung; die Rechnung (55 Tools = 67 KB Schema pro Call) genügt.
- **Feature-Block:** echte Probleme lösen in Plain Language, kein Spec-Sheet.
- **Social Proof:** 1–2 kuratierte, ehrliche Zitate, keine Logo-Wand ohne Kontext
  (wir haben kaum Namen — also Benchmarks + „funktioniert als fremder Install“).

## 5. Pre-Footer-CTA

Letzte Chance, mit messbarem Versprechen (Supabase-Muster „weekend → millions“):
„Install Toolshed und halbiere die Tool-Schema-Last deiner Hermes-Agenten.“

## 6. Anti-Patterns (nicht tun)

- Buzzwords („revolutionary“, „AI-powered“ ohne Substanz).
- Stock-Fotos von lächelnden Leuten mit Laptops.
- Marketing vor Tryable verstecken.
- 90 %-Claims ohne Messbasis (ausdrücklich verboten — ADR-0008).
- Social-Proof-Logos ohne Kontext.

## 7. Konkret für Toolshed v0.1-Landingpage (nächster Schritt)

1. **Headline:** „Adaptive tool-surface proxy for Hermes agents“ (Kategorie +
  ICP).
2. **Subheadline:** 1 Satz + 3 Bullets (weniger Input-Tokens, Recovery, Isolation).
3. **Hero-Code-Block:** der Install-/Enable-/Grant-Weg (tryable).
4. **Trust:** 31 % frisch / 32–70 % A/B, n=…, + GitHub/Lizenz.
5. **How It Works:** 3-Schritt-Flow.
6. **Features:** konkrete Probleme (Schema-Last, Recovery, Multi-Agent).
7. **FAQ** (was passiert bei Fehler → fail-open; ist es sicher → Grant-Modell).
8. **Pre-Footer-CTA.**

Nicht in v0.1-Landing: C/D-Discovery-Features (bewiesen wirkungslos — nicht
bewerben), „90 % garantiert“-Claims.
