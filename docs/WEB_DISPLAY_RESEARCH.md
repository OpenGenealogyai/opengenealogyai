# Genealogy Web Display & Feature Research

**Status:** Research only — for decision, NOT implementation (per Garlon, 2026-05-17).
**Purpose:** Decide how OpenGenealogyAI displays family data on the web, which
features to build, and in what order. Three-brain vetted. Tasks created at the end.

The guiding constraint that makes us different from every program surveyed:
**MAXGEN is probabilistic.** Every other tool forces one answer. Our displays
must show *confidence* and *multiple possibilities* as first-class — that is the
differentiator, not an afterthought.

---

## Part 1 — The 10 best ways to display genealogy data on the web

Surveyed: Ancestry, FamilySearch, MyHeritage, Geni, WikiTree, findmypast,
Gramps (open-source), RootsMagic, Legacy Family Tree, Family Tree Maker.

| # | Display | What it is | Why it matters | MAXGEN twist |
|---|---|---|---|---|
| 1 | **Pedigree chart** | Subject left, ancestors branch right (4–5 gen) | The universal default; what people expect | Uncertain parent shows as a **stack of candidates**, click to expand the 10 leads |
| 2 | **Fan chart** | Radial; subject center, ancestors in arcs | Shows 7–10 generations in one compact, beautiful view | Arc segments **color-coded by confidence** (gold = certain, faded = speculative) |
| 3 | **Family group sheet** | One couple + all their children, full vitals | The classic worksheet (Garlon's mom showed him these) | Each fact carries its confidence + source chip |
| 4 | **Descendant chart** | An ancestor at top, descendants flow down | "Show everyone descended from X" | Collapse/expand branches; confidence on each link |
| 5 | **Hourglass chart** | Subject middle, ancestors up + descendants down | Best single view of a person's full context | — |
| 6 | **Timeline view** | A life's events in chronological order | Humanizes data; pairs events with world history | Events drawn from `event_assertions[]`; confidence shading |
| 7 | **Interactive map / migration** | Births/deaths/residences plotted, paths over time | Reveals migration patterns invisible in charts | Uses `place_registry` gazetteer coords |
| 8 | **Relationship / network graph** | Force-directed graph of all connections | Essential for DNA matches + complex/blended families | DNA-confidence edges; triangulation clusters |
| 9 | **Pan/zoom tree canvas** | Infinite draggable canvas (modern Ancestry style) | How users actually explore large trees today | Lazy-loads; "10 leads" nodes render as a badge you click |
| 10 | **Person profile card** | One person's detail page: facts, sources, photos, timeline | The atomic unit everything links to | Side-by-side conflicting assertions; confidence bars |

**Honorable mentions (defer):** narrative register report (book-style prose
genealogy), statistics dashboard (surname/lifespan/geography), book/PDF export.

**The cross-cutting innovation:** a reusable **confidence chip** and
**"possibilities" expander** that appears in every view. Garlon's "10 leads,
click to open" is exactly this — an unknown ancestor renders as a single node
with a "10 possibilities" badge; clicking expands a ranked, confidence-scored
list. This directly maps to MaxPerson `parent_assertions[]` with multiple
candidates.

---

## Part 2 — 30+ features across the best programs

Catalogued from the surveyed tools. Marked by who does it best.

| # | Feature | Exemplar | Category |
|---|---|---|---|
| 1 | Record hints ("shaky leaf") | Ancestry | Discovery |
| 2 | Cross-tree smart matches | MyHeritage | Discovery |
| 3 | DNA match integration | Ancestry/23andMe | DNA |
| 4 | DNA → tree triangulation | DNA Painter | DNA |
| 5 | Source citation manager | RootsMagic | Evidence |
| 6 | Evidence-to-fact linking | Gramps | Evidence |
| 7 | Conflicting-info handling | (weak everywhere) | Evidence ★ |
| 8 | Photo/document attach + tag | MyHeritage | Media |
| 9 | OCR / handwriting transcription | FamilySearch | Media |
| 10 | Collaborative shared tree | WikiTree/FamilySearch | Collab |
| 11 | Change history / versioning | WikiTree | Collab |
| 12 | Merge / dedup tools | FamilySearch | Data quality |
| 13 | GEDCOM import/export | All | Interop |
| 14 | Relationship calculator | RootsMagic | Navigation |
| 15 | Timeline + historical context | MyHeritage | Display |
| 16 | Map / migration viz | findmypast | Display |
| 17 | Multiple chart types | Legacy | Display |
| 18 | Family group sheets | RootsMagic | Display |
| 19 | Narrative report generation | Legacy | Output |
| 20 | Research to-do / task lists | RootsMagic | Workflow |
| 21 | Place-name standardization | Ancestry | Data quality |
| 22 | Living-person privacy controls | All | Privacy |
| 23 | Full-text record search | Ancestry | Discovery |
| 24 | AI research assistant | MyHeritage (new) | AI ★ |
| 25 | Suggested ancestors | (emerging) | AI ★ |
| 26 | Mobile / responsive | All | Platform |
| 27 | Hint/match notifications | Ancestry | Engagement |
| 28 | Public sharing links | Geni | Sharing |
| 29 | Statistics dashboard | MyHeritage | Insight |
| 30 | Anniversary/calendar reminders | MyHeritage | Engagement |
| 31 | Audio/video memories | MyHeritage | Media |
| 32 | Ancestor color-coding | Ancestry | Display |
| 33 | Multi-language | FamilySearch | Platform |
| 34 | Confidence scoring on facts | (NOBODY does this well) | Evidence ★★ |

★ = where our probabilistic model gives us an unfair advantage.
★★ = the thing literally no competitor does — our core moat.

---

## Part 3 — What OpenGenealogyAI should build (tiered)

### Tier 0 — Differentiators (our moat; build first, nobody else has these)
- **D1. Confidence-aware display layer** — the reusable confidence chip + bar, used in every view (feature 34)
- **D2. Multiple-possibility expander** — "10 leads, click to open" for any unknown ancestor (Garlon's explicit request; features 7, 25)
- **D3. Conflicting-assertion side-by-side** — show both birth years / both fathers, never hide one (feature 7)
- **D4. DNA-confidence boost visualization** — show how DNA chains raised an ancestor's confidence (features 3, 4)

### Tier 1 — Table stakes (any credible genealogy site needs these)
- **T1. Person profile card** (display 10)
- **T2. Pedigree chart** with the possibility-expander (display 1)
- **T3. Family group sheet** (display 3 — Garlon explicitly wants this)
- **T4. Search** (already built — the live search)
- **T5. GEDCOM import/export** (feature 13 — how users get their data in)
- **T6. Source citation display** (feature 5)
- **T7. Living-person privacy gate** (feature 22 — already in schema via is_living)

### Tier 2 — High value, second wave
- **S1. Fan chart** (display 2)
- **S2. Timeline view** (display 6)
- **S3. Map / migration** (display 7 — needs gazetteer population first)
- **S4. Relationship calculator** (feature 14)
- **S5. Merge/dedup UI** (feature 12 — schema ready via merge_history)
- **S6. AI research assistant / suggested ancestors** (features 24, 25)

### Tier 3 — Defer (engagement/scale features, post-launch)
- Collaborative editing, change history, notifications, statistics dashboard,
  audio/video memories, mobile app, multi-language, anniversary reminders.

---

## Part 4 — Three-Brain vet on the tiering

**Judge-GPT (Engineer):** Tier 0 differentiators all read from data the schema
already models (confidence, parent_assertions[], dna_evidence[]). They're
frontend work on existing data — buildable. T5 GEDCOM is the one with hidden
depth (the spec is messy) — budget extra. **PROCEED.**

**Judge-Gemini (Strategist):** The sequencing is right — lead with the moat, not
table stakes. But T3 family group sheet should jump ahead of the pedigree chart:
it's the simplest complete view, Garlon has a personal attachment to it, and it
exercises the confidence-chip layer (D1) on real data. Build D1 + T3 first as
the proving ground, then T1/T2. **PROCEED WITH CAUTION — reorder T3 earlier.**

**Judge-Opus (Operator):** Every Tier-0 item is read-only display — zero risk to
the data layer. The risky one is T5 GEDCOM *import* (writes data, can corrupt the
tree). Gate import behind validation + the Postgres transaction layer. Also: don't
build map/migration (S3) until gazetteer population runs, or it shows empty. **PROCEED.**

**Pam (synthesis):** Consensus PROCEED. One reorder: **D1 (confidence layer) +
T3 (family group sheet) are the first build** — smallest path that proves the
differentiator on a real, beloved format. Then D2 (possibility expander) + T1
(profile) + T2 (pedigree). GEDCOM import is the one to treat carefully
(validation + transactions). Map waits for gazetteer.

```
RECOMMENDED BUILD ORDER:
  1. D1  Confidence display layer (chip + bar component)
  2. T3  Family group sheet (proves D1 on a real format)
  3. D2  Multiple-possibility expander ("10 leads, click to open")
  4. T1  Person profile card
  5. T2  Pedigree chart
  6. D3  Conflicting-assertion side-by-side
  7. T6  Source citation display
  8. T5  GEDCOM import/export (validation + transaction-gated)
  9. D4  DNA-confidence visualization
  10. S1–S6 second wave (fan chart, timeline, map*, relationship calc, merge UI, AI assistant)
       *map waits on gazetteer population
```

---

## Part 5 — Open questions for Garlon (do NOT decide unilaterally)

1. **Framework**: the portal is server-rendered Flask + Jinja today. The Tier-0
   interactive views (pan/zoom, expanders) want client-side JS. Stay
   vanilla-JS-on-Jinja, or introduce a frontend framework (htmx? Alpine? a SPA)?
   This is an architecture decision → six-brain when we get there.
2. **Family group sheet first** vs pedigree first — three-brain says group sheet
   first; confirm.
3. **GEDCOM scope** — import + export both, or export-only for v1 (import is the
   risky, messy one)?

These are flagged in the tasks as needing a decision before that task starts.
