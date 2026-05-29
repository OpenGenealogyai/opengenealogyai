# Garlon's Big Goals — Building the Program

**Last updated:** 2026-05-17
**Living document.** Garlon's ongoing requests, decisions, and standing
expectations for OpenGenealogyAI's program-build. Pulled up periodically to
check we're still building toward what was asked.

---

## The North Star

Build **the very best genealogy program** — done right the first time, ground-up,
with **confidence ratings throughout** every fact and relationship. Veteran
20-year-engineer discipline: design before code; design the UI and features
first, then the database, then the scrum tasks, then test as we go. Spending
plenty of Claude tokens is acceptable when it improves quality.

---

## Standing expectations (apply to every turn)

1. **Confidence ratings everywhere.** Every fact, every relationship, every
   "lead" — confidence-scored per `docs/CONFIDENCE_CALIBRATION.md`. Multiple
   possibilities coexist. Nothing is ever forced to a single answer.
2. **Six-brain on everything substantial.** Real API calls (verified
   2026-05-17): Claude Sonnet 4.5 + GPT-4o + Gemini 2.5 Pro. Designer lens to
   be added (see open question below). `scripts/brains.py` is the
   infrastructure. Show the panel verdicts when reporting back.
3. **Build → test in Chrome → iterate → next portion.** I open each finished
   slice in a Chrome tab, try the features, fix issues, then advance. No big-
   bang releases.
4. **Plan first, change as we go.** The plan exists from day one and is
   revised as we learn — not invented mid-flight.
5. **Honest uncertainty.** Never fabricate. Hypotheses are clearly labeled.
   MAXGEN's whole premise is uncertainty-as-data; the program must show that.
6. **Family group sheet is a first-class display.** Garlon's mom showed him
   these — they get built early as the proving ground for the confidence
   layer.
7. **10-possibilities cap.** When an ancestor is unknown, generate up to 10
   candidates as `parent_assertions`, never more, expandable on click.
8. **Session ownership.** This session owns `C:\Users\stock\dev\opengenealogyai`
   and is responsible for the PLATFORM (schemas, database, web app).
   Genealogy *research* (the wives' lines, the Scotland push, the lead
   generation) is Deon's lane; the canonical Find A Grave data lives in
   OMEN's `D:\AI\Companies\open-genealogical-ai\family_tree\`.

---

## Locked decisions

| Date | Decision | Result |
|---|---|---|
| 2026-05-15 | MAXGEN v1.2 amendments (six-brain) | ✅ Applied (9 amendments to MaxDNA + MaxPerson) |
| 2026-05-15 | Postgres storage layer (six-brain) | ✅ DDL drafted + executed; persons mirror + 5 DNA tables |
| 2026-05-15 | Phase-0 operator gates | ✅ All 3 closed (encryption, localhost-only, backup) |
| 2026-05-17 | MAXGEN v1.3 additive batch | ✅ Merge model, events, places, lockstep versioning, extensions |
| 2026-05-17 | `CONFIDENCE_CALIBRATION.md` standard | ✅ Anchored bands, noisy-OR, composite formula, gold-set calibration |
| 2026-05-17 | **Gramps reuse** | **A — design-only copy; build fresh; stay MIT/CC0** |
| 2026-05-17 | **Lead-research routing** | **A — Deon does leads (wives' lines + Scotland); OMEN keeps canonical data; this session builds the platform** |

---

## The 4-phase plan (the 20-year-vet sequence)

### Phase 1 — UI / feature design (current)
- 10 best display methods identified (see `docs/WEB_DISPLAY_RESEARCH.md`)
- 30+ features surveyed across competitors
- 207-line deep dive on Gramps Web (see `docs/GRAMPS_WEB_RESEARCH.md`)
- **Next:** 50 specific UI design tasks, six-brain-vetted, including a
  Designer-lens review
- **Open framing decisions** below must close first

### Phase 2 — Database design
- MAXGEN schemas already at v1.3 (lockstep)
- Postgres DDL `001_init.sql` already deployed
- **Next when Phase 1 closes:** ingest agent design (FAG JSON → MaxRecord →
  Postgres + Qdrant), merge/dedup engine, place_registry population plan,
  chain-inference worker for DNA evidence

### Phase 3 — Scrum tasks in order
- 13 tasks already in tracker covering display features (#1–#10, #13)
- **Next:** expand to the full ordered task list (1000+ may emerge per
  Garlon's note) once Phase 1 + Phase 2 designs are firm, with each task
  having: acceptance criteria, test plan, dependencies, owner

### Phase 4 — Build → test → iterate loop
- Per-task: implement → open in Chrome → exercise → fix → commit → next
- Continuous: nightly backup runs, schema validation script, regression on
  fixtures (62 currently pass)

---

## Roles and ownership

| Lane | Owner | What they do |
|---|---|---|
| **Platform** (web app, schemas, DB, search, AI) | THIS session (opengenealogyai) | Builds the program. Owns `C:\Users\stock\dev\opengenealogyai\`. |
| **Genealogy research** (leads, hypotheses, verification) | Deon | Researches dead ends, generates parent-candidate hypotheses with sources. Owns `C:\Users\stock\Documents\maxwell_genealogy\`. |
| **Canonical Find A Grave data** | OMEN pipeline session | Human-in-the-loop FAG extraction. Owns `D:\AI\Companies\open-genealogical-ai\family_tree\`. |
| **Approvals + irreversible actions** | Garlon | Six-brain decisions, vendor/financial calls, anything > $500 or that can't be undone. |

---

## API keys — verified live 2026-05-17

| Provider | Model | Latency | Status |
|---|---|---|---|
| Anthropic | claude-sonnet-4-5 | 0.96s | ✅ |
| OpenAI | gpt-4o | 0.74s | ✅ |
| Gemini | gemini-2.5-pro | 2.26s | ✅ |

Real calls confirmed in `scripts/brains.py verify`. Council protocol now uses
actual external models, not internal synthesis.

---

## Open framing decisions (need closure before 50 UI tasks)

1. **Frontend framework** — vanilla JS on the current Flask+Jinja portal, or
   introduce htmx / Alpine.js / Lit / a SPA framework? Shapes every UI task.
   Six-brain candidate.
2. **Designer lens in council** — formally add Judge-Designer to the panel
   (making four-brain), or run UX as a separate review pass? Three-brain
   candidate.
3. **GEDCOM scope for v1** — import + export, or export-only?
4. **Map provider** — MapLibre GL (what Gramps uses), Leaflet, or defer
   entirely until gazetteer integration?

---

## Pending / open requests (in flight)

| Item | Status |
|---|---|
| 50 UI design tasks, six-brain-vetted | Waiting on framing decisions above |
| Designer-perspective review | Pending decision #2 above |
| Family group sheet for Garlon's tree | ✅ Delivered (3 sheets, in chat) |
| 10 leads per dead end | Routed to Deon (handoff drafted) |
| Build in portions, test each in Chrome | Will start once Phase 1 framing closes |
| Track everything in this file | ✅ This file |

---

## History — recent activity (newest first)

- 2026-05-17 — API keys verified, brains.py shipped, this file created.
- 2026-05-17 — Gramps Web research; license catch flagged; decision A locked.
- 2026-05-17 — Web display methods + feature survey; 13 platform tasks created.
- 2026-05-17 — MAXGEN v1.3 (merge model, events, places, lockstep).
- 2026-05-17 — CONFIDENCE_CALIBRATION.md.
- 2026-05-15 — Spouse bidirectional sync; six-brain on storage layer; DDL.
- 2026-05-15 — MAXGEN v1.2 amendments (DNA layer, Max* rename, dna_evidence).
- (earlier) — Initial schemas, portal, search.

Every commit lands on `main` and is pushed to GitHub. Run
`git log --oneline -20` for the verifiable trail.
