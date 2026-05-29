# UI Design Tasks — OpenGenealogyAI

**Status:** Refined per six-brain w/ Designer 2026-05-17. Pass-1 unanimous on E
(synthesis); Pass-2 Operator + Designer reversed to B (testing first), arguing E's
threaded UX work created cross-batch coupling. Final = **E′**: keep 5-batch
shape, concentrate the new UX-foundation + testing-scaffold work in an
**expanded Batch 1** (no cross-batch threading). ~58 tasks total.

Council transcripts: pass-1 + pass-2 in commit history; see
`scripts/brains.py` `verify`/`council`/`six` to reproduce.
**Stack locked:** Lit web components, `<maxgen-…>` prefix, embedded in Flask + Jinja portal.
**Data model:** MAXGEN v1.4 — every component binds to probabilistic data
(confidence + alternatives + sources).

Five batches of 10. Each batch is roughly one "sprint." Build → test in Chrome
→ fix → next. Designer lens applies on every batch.

---

## Batch 1 — Foundation, UX, & test scaffold (expanded — tasks 1–18)

Goal: the toolbox every later component reuses, the UX foundation that shapes
the design system, and the test scaffold that catches regressions from day one.
Without these three together, every later choice gets re-litigated or ships
brittle.

### Batch 1a — UX foundation (tasks 1–5)
| # | Task | Acceptance |
|---|---|---|
| 1 | **Onboarding wireframe** | 4-step new-user flow (signup → first tree creation → first ancestor → first photo) sketched in `docs/wireframes/onboarding.md` with low-fi screen-by-screen mockups + microcopy |
| 2 | **Navigation IA (information architecture)** | Sitemap of every top-level route + sidebar/nav structure; documented at `docs/wireframes/nav-IA.md`; settles "what's a tab vs a page vs a modal" |
| 3 | **Brand spec** | One-page brand identity: name treatment, logo direction, primary palette (anchors to confidence colors), voice/tone, single sentence "what we are." `docs/brand.md` |
| 4 | **Error tone-of-voice + microcopy guide** | Standard error states + the voice in which they speak (calm, specific, never blaming). `docs/microcopy.md` covers errors, empty states, confirmations, CTA verbs |
| 5 | **Accessibility baseline (WCAG 2.1 AA)** | Documented requirements: contrast, focus rings, keyboard order, ARIA conventions, screen-reader test plan. Every later task references this. `docs/a11y.md` |

### Batch 1b — Test scaffold (tasks 6–8)
| # | Task | Acceptance |
|---|---|---|
| 6 | **Component dev page (Storybook-lite)** | `/dev/components` route renders any registered `<maxgen-…>` with example data and all states. New component = add one entry. No new tooling — just a Jinja page that imports the components. |
| 7 | **Visual regression skeleton** | Playwright harness that takes baseline screenshots at known viewports; one example test on the existing `/search` page. Diffs fail CI. Empty for now; future tests slot in. |
| 8 | **Confidence-math unit tests** | Pure JS tests on the noisy-OR aggregator, calibration band lookup, and `composite_confidence` formula (per CONFIDENCE_CALIBRATION.md). Standalone runnable (`node test/confidence.test.js`). |

### Batch 1c — Design system (tasks 9–18 = original tasks 1–10 from the first draft)
| # | Task | Acceptance |
|---|---|---|
| 9 | **Design tokens** — CSS custom properties for confidence-color scale, spacing, typography, focus rings, motion durations | `portal/static/css/tokens.css`; `:root { --conf-1: …; … }` defined; swatch page at `/dev/tokens` |
| 10 | **Color system** — accessible, confidence-aware palette: gold primary, neutrals, semantic red/green/amber, dark-mode pair | Contrast ≥ 4.5:1; doc'd at `/dev/colors` |
| 11 | **Typography** — Georgia serif body + system sans chrome + monospace IDs; 6-size scale | All set via tokens; demo page; web font self-hosted |
| 12 | **Spacing & layout primitives** — 4-pt grid, `<maxgen-stack>` and `<maxgen-cluster>` Lit components | Used by ≥3 later components without ad-hoc margins |
| 13 | **`MaxgenElement` base class** — extends LitElement; shared styles, dark-mode media, debug attrs | Every component inherits |
| 14 | **Confidence formatter** — `formatConfidence(0.73)` → "73%" + band label + color token | Unit tests; matches CONFIDENCE_CALIBRATION.md |
| 15 | **`<maxgen-source-chip>`** — citation pill (icon, label, hover tooltip with full source) | Renders from MaxRecord URL; new-tab click |
| 16 | **`<maxgen-license-badge>`** — CC0/CC-BY/tier2-private with standard CC icons | Used by photos, records, exports |
| 17 | **`<maxgen-empty>`** — "no photos yet," "no sources," etc. with optional CTA slot | Consistent voice (per microcopy guide); no naked "(none)" |
| 18 | **`<maxgen-skeleton>`** — shimmer placeholders; respects `prefers-reduced-motion` | Used by pedigree, profile, search |

---

## Batch 1 (legacy header — see above for the expanded version)

Original foundation list, now split across 1a/1b/1c above. Keeping this anchor
so existing links don't break.

| # | Task | Acceptance |
|---|---|---|
| 1 | **Design tokens** — CSS custom properties for confidence-color scale (gold→faded), spacing scale (4-point grid), typography scale, focus rings, motion durations | `portal/static/css/tokens.css` exists; `:root { --conf-1: …; --conf-2: …; … }` defined; rendered swatch page at `/dev/tokens` |
| 2 | **Color system** — accessible, confidence-aware palette: gold primary (confidence anchor), neutral grays, semantic red/green/amber, dark-mode pair for each | Contrast ≥ 4.5:1 for all text; doc'd at `/dev/colors` |
| 3 | **Typography** — Georgia serif for body (genealogy = archival feel) + system sans for UI chrome + monospace for IDs/dates; type scale of 6 sizes | All set via tokens; demo page; web font self-hosted (no third-party CDN) |
| 4 | **Spacing & layout primitives** — 4-pt grid, `<maxgen-stack>` and `<maxgen-cluster>` layout helpers as Lit components | Used by ≥3 later components without ad-hoc margins |
| 5 | **Lit base class** — `MaxgenElement extends LitElement` adds shared styles, dark-mode media query, debug data-attrs, common util methods | Every component inherits; ~30 lines |
| 6 | **Confidence formatter** — `formatConfidence(0.73)` → display string "73%" + band label "Good" + color token; pure JS module | Unit tests; matches CONFIDENCE_CALIBRATION.md bands |
| 7 | **Source-chip primitive** — `<maxgen-source-chip>` renders a citation pill (icon, label, hover tooltip with full source); reused everywhere a fact has a source | Renders from a MaxRecord URL; clicking opens source in new tab |
| 8 | **License badge** — `<maxgen-license-badge>` renders CC0/CC-BY/tier2-private with the standard CC icons + tooltip | Used by photos, records, exports |
| 9 | **Empty state primitive** — `<maxgen-empty>` for "no photos yet," "no sources," "no known parents" with optional CTA slot | Consistent voice across every empty case; no naked "(none)" anywhere |
| 10 | **Loading / skeleton states** — `<maxgen-skeleton>` for shimmer placeholders while data loads; respects `prefers-reduced-motion` | Pedigree chart, profile card, search results all use it |

---

## Batch 2 — Core display components (tasks 11–20)

Goal: the building blocks every view composes from. Each is small, reusable,
and binds directly to MAXGEN data.

| # | Task | Acceptance |
|---|---|---|
| 11 | **`<maxgen-confidence-chip>`** | Renders a numeric confidence as a colored pill with hover-revealing band name + reasoning. Property: `confidence` (0–1). |
| 12 | **`<maxgen-confidence-bar>`** | Inline progress-style bar version of the chip; for cards where space is short. |
| 13 | **`<maxgen-person-card>`** | Compact card: photo (auto-cropped to face_bounding_box), name, dates, confidence chip, click→profile. Property: full MaxPerson JSON. |
| 14 | **`<maxgen-photo>`** | Smart photo element: primary photo if available; respects face_bounding_box for crop; alt_text for a11y; fallback to silhouette if no photo; lazy-loads thumbnail. |
| 15 | **`<maxgen-fact>`** | Renders a single fact (birth, death, occupation, etc.) with value + confidence chip + source chips. Reused in profile, group sheet, popover. |
| 16 | **`<maxgen-possibility-expander>`** | The "10 possibilities, click to open" component. Collapsed: badge "N possibilities." Expanded: ranked list of candidates with confidence + reasoning. Property: array of candidates. |
| 17 | **`<maxgen-conflict-view>`** | Side-by-side display of two conflicting assertions (e.g., two birth years), each with its confidence + source. Never picks a winner. |
| 18 | **`<maxgen-relationship-edge>`** | Renders the visual connection between two person nodes (line + relationship-type icon + confidence). For chart components to reuse. |
| 19 | **`<maxgen-date>`** | Probabilistic date renderer: "1843" if exact; "~1843" if estimated; "1840–1845" if range; "before 1850" if year_max only. |
| 20 | **`<maxgen-place>`** | Place renderer that uses `place_registry` when available (shows historical_polity + modern country); falls back to place_as_written. |

---

## Batch 3 — Layout views (tasks 21–30)

Goal: full-page experiences composed from Batch-1/2 primitives.

| # | Task | Acceptance |
|---|---|---|
| 21 | **Person profile page** (`/person/<id>`) | Hero with primary photo + name + dates; tabs: Facts / Family / Photos / DNA / Sources. Uses `maxgen-photo`, `maxgen-fact`, `maxgen-confidence-chip`. |
| 22 | **`<maxgen-family-group-sheet>`** | The classic format Garlon's mom showed him: husband + wife + children, every fact carrying a confidence chip and source chip. First proving ground for the design system. |
| 23 | **`<maxgen-pedigree-chart>`** | Subject left, ancestors branch right, 4–5 gen visible. Uncertain parents render the `maxgen-possibility-expander` inline. Pan/zoom via mouse + touch. |
| 24 | **`<maxgen-fan-chart>`** | Radial pedigree; arc segments color-coded by confidence band. Configurable generation count (4–8). |
| 25 | **`<maxgen-descendant-chart>`** | One ancestor at top, descendants flowing down. Branches collapsible. |
| 26 | **`<maxgen-hourglass-chart>`** | Subject middle, ancestors above + descendants below. |
| 27 | **`<maxgen-timeline>`** | Vertical per-person timeline of events (events from `event_assertions[]`); each event has date, place, confidence, sources. Sticky-map alongside (when gazetteer ready). |
| 28 | **Search results page** (already live; redesign) | List of `maxgen-person-card`s with semantic-match score visible; filters (year range, place, surname). |
| 29 | **Dashboard / my trees** (logged-in home) | Existing portal home, redesigned: tree thumbnails, photo strip of recently-added people, "leads to investigate" call-outs. |
| 30 | **Tree navigator (pan/zoom canvas)** | The modern infinite-canvas exploration view; lazy-loads nodes as you pan; "N possibilities" badges render as expandable. |

---

## Batch 4 — Interactions, accessibility, polish (tasks 31–40)

Goal: the things that make a program feel like quality.

| # | Task | Acceptance |
|---|---|---|
| 31 | **Photo upload + face-tag flow** | Drag-drop upload to a person; auto face-detection draws bounding boxes; click a face to tag the person; sets is_primary if first photo. |
| 32 | **Photo lightbox** | Click a thumbnail → fullscreen with caption, date, source; arrow-key navigation across the person's photos. |
| 33 | **Merge/dedup UI** | Two side-by-side person cards; select which assertions to keep; "Merge" writes a `merge_history` entry, marks loser `merged_away`, never deletes. |
| 34 | **Possibility expander UX** | Concrete design: badge animation, expansion accordion, "accept this candidate" button that creates a parent_assertion with declared confidence. |
| 35 | **External-search dropdown** (task #13) | One click → fan-out to FamilySearch / Ancestry / WikiTree / Find a Grave with the person's name + dates pre-filled in each search URL. |
| 36 | **Keyboard navigation** | Tab order is correct; arrow keys move between pedigree nodes; Enter opens profile; Esc closes lightbox/expander. WCAG 2.1 AA. |
| 37 | **Mobile responsive layouts** | Pedigree collapses to vertical at <600px; family group sheet stacks; touch gestures on charts. |
| 38 | **Accessibility audit** | All components pass axe-core; alt_text everywhere; focus rings visible; screen-reader tested on profile page + group sheet. |
| 39 | **Dark mode** | Tokens already include dark pair (task 2); add `<maxgen-theme-toggle>`; respects `prefers-color-scheme`. |
| 40 | **i18n stubs** | All UI strings via a `t('key')` function; English default; Spanish/German placeholders. (Don't translate yet, just structure.) |

---

## Batch 5 — Integration, testing, ops (tasks 41–50)

Goal: the program is real because it's tested, observed, and shippable.

| # | Task | Acceptance |
|---|---|---|
| 41 | **GEDCOM export UI** | Button on dashboard → downloads .ged of selected tree. Honors privacy (tier2-private and is_living=true persons skipped or masked per export option). |
| 42 | **GEDCOM import UI** (gated) | Validate file → preview people count → conflict detection (existing person matches?) → user accepts → write to Postgres in one transaction. |
| 43 | **Photo ingest agent** | Background worker: detect new photos in `D:\photos\incoming\`; OCR caption from EXIF or filename; face-detect; queue for tagging; route by license per the hybrid storage rule. |
| 44 | **Confidence chip Storybook page** | `/dev/components` — every `<maxgen-…>` rendered with example data, all states (loading, empty, error, populated). |
| 45 | **Visual regression tests** | Playwright snapshot tests on the profile page, family group sheet, pedigree chart. Fail CI on unexpected diff. |
| 46 | **Unit tests for confidence math** | Noisy-OR aggregation, calibration band lookup, composite_confidence formula — all from CONFIDENCE_CALIBRATION.md. |
| 47 | **Test-in-Chrome harness** | One command (`make smoke`) opens the portal in Chrome and visits a checklist of routes; pass = no console errors + screenshots within tolerance. Matches Garlon's "build → open in Chrome → try features" rule. |
| 48 | **Performance budgets** | Profile page < 1.5 s to first contentful paint; pedigree chart < 100 ms per pan frame. Measured; fails build if exceeded. |
| 49 | **Error states** | 404 person page, broken photo, missing source, network failure — each has a real designed view, not a stack trace. |
| 50 | **Empty states** | First-time user (no trees), empty search, person with no facts, person with no photos — each surfaces a CTA, not a void. |

---

## Cross-cutting principles

1. **Every fact shows confidence.** No exceptions. If we don't know the confidence, render the unknown band, not nothing.
2. **No fact is hidden.** Conflicts surface side-by-side. Multiple parents render simultaneously. The 10-possibility expander never collapses below "N possibilities."
3. **Photos lead.** Profile pages, cards, pedigree nodes all show face-cropped photos when available; silhouette fallback otherwise. A face is the difference between a database and a story.
4. **Components compose.** Every page is built from the Batch-1/2 primitives. New page types don't introduce new primitives — they remix.
5. **MIT throughout.** Every component is original code (design-only copy from Gramps Web). `<maxgen-…>` namespace.

---

## Build order (the scrum sequence)

Batches are not strictly sequential — within a batch tasks can parallelize.
Across batches, **finish a batch + test in Chrome + iterate before the next.**

Critical-path summary:
**Batch 1 (foundation) → Batch 2 (primitives) → 22 (group sheet, proving ground) → 21 (profile page) → 23 (pedigree) → Batch 5 testing harness → fill in Batches 3+4.**

---

## Open questions before launching Batch 1

None blocking. Photo storage (A/B/C), framework (Lit), naming (`maxgen-`), and Designer-lens triggers are all locked.
