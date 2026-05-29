# Brand — OpenGenealogyAI

**Status:** Foundation draft (Batch 1a, task 3). Refines as we ship.

This is the one-page brand identity. Every UI choice — color, voice, copy,
interaction tone — traces back here. When a later decision is tied, the brand
breaks the tie.

---

## What we are (one sentence)

> **OpenGenealogyAI is an open standard and platform for genealogy that treats
> uncertainty as data — every fact carries its confidence and its source, and
> multiple possible ancestors coexist until evidence resolves them.**

If you can only say one thing about us, say that.

---

## Name treatment

- **OpenGenealogyAI** — the platform (web app, search, portal, AI agents)
- **MAXGEN** — the open JSON standard (the four schemas + this document set)
- **Maxwell Genealogy Standard** — the formal name MAXGEN expands to
- Together: "OpenGenealogyAI implements the MAXGEN standard."

The standard outlives the platform. If we were hit by a bus, MAXGEN would still
be adoptable by anyone (CC0). The platform is *an* implementation, not *the*
implementation.

### Capitalization & spelling rules
- Always **OpenGenealogyAI** (one word, two capitals: O and AI). Never
  "Open Genealogy AI" with spaces. Never "openGenealogyAI."
- Always **MAXGEN** in all caps (it's an acronym-flavored mark).
- Always **MaxRecord / MaxPerson / MaxTask / MaxDNA** for the schemas. Never
  the old "MX-" forms.

---

## What we are NOT

| Not this | We are this |
|---|---|
| FamilySearch / Ancestry — single-answer genealogy | Probabilistic — multiple ancestors with confidence |
| 23andMe — find your living cousin | Find your dead ancestor (DNA strengthens historical claims) |
| Gramps (a database tool) | A standard *and* an AI-native platform |
| Wiki-style consensus tree (one shared truth) | Append-only assertion graph (every contributor's claim survives) |
| Hobbyist data dump | Calibrated confidence; gold-set audited |

---

## Voice & tone

Imagine a **careful archivist** — neither breathless ("amazing discovery!") nor
clinical ("query returned 3 results"). Calm, specific, honest about what's
known and what isn't.

### The four voice rules

1. **Never say "is" when "we think" is honest.**
   - ❌ "Richard Maxwell was born in 1796."
   - ✅ "We think Richard Maxwell was born **around 1796** (confidence 0.85,
     based on 2 sources)."

2. **Numbers and dates are sacred.** Use ranges, "around," and confidence
   rather than false precision.
   - ❌ "Born 1843."
   - ✅ "Born 1840–1845." / "Born around 1843."

3. **Never blame the user for an error.** State what happened, what we tried,
   what to do next.
   - ❌ "Invalid input — please try again."
   - ✅ "We couldn't read that GEDCOM file (line 47, unexpected character).
     Try saving it as plain text from your software."

4. **Hands-on language, never corporate.**
   - ❌ "Leverage our platform to facilitate genealogical insights."
   - ✅ "Search 1.5 million records. Find your great-grandmother."

### Tone modulation by surface

| Surface | Tone |
|---|---|
| Marketing / hero pages | Warm, confident, specific. Single line: "Find ancestors. Honestly." |
| Search results, dashboards | Neutral, factual, dense with information. Avoid adjectives. |
| Empty states | Encouraging next step, no apologies. "Add your first ancestor →" |
| Errors | Specific, calm, action-forward. Name what failed and what to try. |
| Confirmations | Quietly factual. "Saved — 3 sources added." Never "Success!" with exclamations. |
| AI assistant replies | Same archivist voice. Says "We think" / "Likely" / "Less certain." |

---

## Color palette

The palette anchors to the **confidence color scale** — gold for certain,
fading toward faded paper / silver for speculative. This is not decorative;
the colors are how confidence becomes legible at a glance.

| Token | Hex | Use |
|---|---|---|
| `--ink` | `#1a1209` | Body text on light, headings |
| `--paper` | `#f7f4ee` | Page background (warm off-white, archival feel) |
| `--gold` | `#d4a843` | Primary brand; high-confidence anchor; CTAs |
| `--gold-dark` | `#b8902d` | Hover for gold elements |
| `--accent` | `#6b3a2a` | Secondary actions, link color |
| `--border` | `#ddd8cc` | Subtle dividers |
| `--muted` | `#6b6458` | Secondary text, metadata, captions |

### Confidence color scale (the cross-cutting visual)
| Token | Hex | Band (per CONFIDENCE_CALIBRATION.md) |
|---|---|---|
| `--conf-near-certain` | `#d4a843` | 0.95–1.00 (gold) |
| `--conf-strong` | `#c19233` | 0.85–0.95 |
| `--conf-good` | `#a17822` | 0.70–0.85 |
| `--conf-moderate` | `#8a7b5e` | 0.50–0.70 (warm silver) |
| `--conf-weak` | `#a8a094` | 0.30–0.50 (silver) |
| `--conf-speculative` | `#c8c2b3` | 0.00–0.30 (faded paper) |

### Semantic colors
| Token | Hex | Use |
|---|---|---|
| `--success` | `#2d6a4f` | Confirmations, valid |
| `--warn` | `#e0a83b` | Conflict, attention needed |
| `--error` | `#a73d3d` | Errors, destructive |
| `--info` | `#3b6cb3` | Notes, neutral information |

### Dark mode
Each token has a `--dark-*` counterpart. Background flips to `--ink-deep`
(`#0e0905`); paper text uses `--paper-text` (`#e6e1d3`). Gold stays gold (it's
on-brand at any background). All semantic colors retest for 4.5:1 contrast on
the dark surface.

---

## Typography

Two type families, no third.

- **Body / archival** — **Georgia** (web-safe serif, evokes printed records).
  All long-form reading, person names, family group sheets, narrative.
- **UI chrome / labels** — system sans (San Francisco / Segoe UI / Roboto via
  the system stack). Buttons, nav, captions, dense data tables.
- **Numeric / IDs** — monospace (system stack). UUIDs, confidence percentages,
  dates inside cards. Optional.

Type scale (6 sizes via tokens):
- `--text-xs` 0.72rem · `--text-sm` 0.85rem · `--text-base` 1rem
- `--text-md` 1.15rem · `--text-lg` 1.4rem · `--text-xl` 1.9rem

Line height 1.55 for body; 1.25 for headings. No display-size text — we're not
a marketing site, even on marketing pages.

---

## Logo direction (not designed yet — direction for a designer)

The logo should evoke:
1. **A tree, but a tree with weighted branches** (some lines bolder than
   others, signaling confidence as a visual primitive).
2. **Open / readable** — not a tight monogram. The name "OpenGenealogyAI" is
   long; the logo lets it breathe.
3. **Archival, not techy** — closer to a library plate than a SaaS startup.
   Serif wordmark + a single small mark (the weighted tree or a single gold
   confidence-arc).

A first sketch direction: serif wordmark **"OpenGenealogyAI"** with a single
gold arc curving over the "O" — the arc thickness varying along its length
(thick = certain, thin = uncertain). The arc is the standard's promise made
visible.

Logo asset work is **deferred** to a real visual designer; this doc gives them
the constraints.

---

## The brand promise (one paragraph for the about page)

> We don't pretend to know things we don't know. When a record disagrees with
> another record, we keep both — labeled with where they came from and how
> confident we are. When you ask who your ancestor's father was and the
> evidence points to three candidates, we'll show you all three, ranked,
> with the reasoning. That's not a bug. That's how genealogy actually is.
