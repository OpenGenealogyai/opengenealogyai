# Decision: Frontend Framework for OpenGenealogyAI

**Date:** 2026-05-17
**Method:** Six-brain (real API calls — Anthropic Sonnet 4.5 + OpenAI GPT-4o + Gemini 2.5 Pro)
**Status:** Pending Garlon confirmation

## The question

Pick the frontend approach for the web interface, given an existing Flask +
Jinja2 server-rendered portal and a need to build interactive features
(confidence chips, possibility expanders, pedigree/fan/family-group-sheet
charts, map, conflicting-assertion views, profile cards) that bind to a
probabilistic data model.

## Options

| | Approach |
|---|---|
| A | Vanilla JS on Jinja + d3/MapLibre. No build pipeline. |
| B | htmx + Alpine.js on Flask+Jinja. Partial HTML over the wire. |
| C | Lit web components (our own, MIT — not Gramps's AGPL). Embedded in Jinja. |
| D | Separate SPA (React/Svelte) + JSON API. Build pipeline. |

## Pass 1 — Open council

- **Engineer (GPT-4o) → B** "Pragmatic, leverages existing Flask+Jinja, lightweight."
- **Strategist (Gemini 2.5 Pro) → C** "Web components are a browser standard; lowest lock-in; encapsulated; reusable in any future SPA."
- **Operator (Claude Sonnet 4.5) → B** "Smallest blast radius; rollback = delete two script tags."

Pass-1 tally: **B = 2, C = 1.**

## Pass 2 — Adversarial (each judge argues against own Pass-1 view)

- **Engineer → A** (reversed away from B) "htmx+Alpine adds dependency surface; vanilla JS is simpler."
- **Strategist → C** (consistent; Pass-2 reply truncated on token budget but Pass-1 reasoning stands).
- **Operator → C** (REVERSED). Self-quote: *"I was wrong to prize 'rollback ease' over 'right tool for the job.' htmx is great for CRUD forms but terrible for the stateful, nested components you need: a pedigree chart with 200+ nodes where clicking a person loads their profile card while preserving chart zoom state while updating the confidence legend while syncing to the URL. That's not partial HTML over the wire — that's coordinated client-side state htmx actively fights against. Alpine.js doesn't scale to component libraries — you'll write `x-data="{open: false, selected: null}"` 47 times across templates, with no encapsulation. The 'no build pipeline' badge is a trap: Lit also has no build pipeline for development (native ES modules), but gives you actual components with lifecycle hooks, scoped styles, and testability."*

Pass-2 tally: **C = 2, A = 1.** Verdict flipped from B to C.

## Verdict

**Option C — Lit web components.** Three reasons:

1. **Right tool for the data model.** Our nodes carry confidence + alternatives
   + DNA chains + conflicts. That's stateful, nested, coordinated UI — exactly
   what web components handle well and htmx/Alpine handle poorly.
2. **Browser-standard, no lock-in.** Custom Elements + Shadow DOM + ES Modules
   are W3C standards. If we later want React or Svelte, the components port
   over (web components consume cleanly from any framework). htmx is a bet on
   one maintainer's philosophy.
3. **No build pipeline required during dev.** Native ES modules in modern
   browsers mean we can `<script type="module">` Lit components directly from
   Jinja pages. Build pipeline only needed if/when we minify for production.

## What this changes

- **Confidence chip / bar (task #1)** is a `<og-confidence-chip>` component.
- **Possibility expander (task #3)** is `<og-possibility-expander>`.
- **Family group sheet (task #2)** is `<og-family-group-sheet>` composed from
  smaller components.
- All MIT-licensed, our own code — no Gramps Web component reuse.

## What doesn't change

- The Flask portal stays. Jinja templates stay. The server-rendered base + the
  semantic search at `/search` stay live.
- Postgres + Qdrant data layer untouched.
- The portal continues to deliver HTML pages; pages embed our Lit components
  for interactive bits.

## Risks (flagged by Engineer in Pass 2)

- Slight learning-curve cost vs. vanilla JS.
- Shadow DOM debugging is different from regular DOM debugging (manageable —
  modern devtools handle it).

## Implementation notes (for when we build)

- Place components at `portal/static/components/og-*.js`.
- Use Lit's `import { LitElement, html, css } from 'https://cdn.skypack.dev/lit'`
  (or self-host the Lit ESM bundle once we want to pin a version).
- Each component takes a single MaxPerson JSON blob as a property; renders by
  reading the probabilistic fields directly.
- Components dispatch CustomEvents up; pages handle navigation.

## Status

⏳ Awaiting Garlon's explicit confirmation before this becomes locked.
