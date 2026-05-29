# Gramps Web — Deep Research

**Status:** Research only (Garlon, 2026-05-17). For decision, not implementation.
**Goal:** Decide how heavily OpenGenealogyAI should lean on / copy Gramps Web.

Gramps Web is the open-source web genealogy app. It is the single most relevant
reference for us — but there is a **license catch** (AGPL-3.0) that must be
decided before any code is copied. See §4.

---

## 1. What Gramps Web is, and its architecture

Two separate repositories:

| Repo | Role | Stack |
|---|---|---|
| **gramps-web** (Gramps.js) | Frontend | **Lit web components** (vanilla JS, no React/Vue), **MapLibre GL** for maps, **Graphviz (graphvizlib.wasm)** for relationship graphs |
| **gramps-web-api** | Backend | **Python Flask** REST API over the Gramps database |
| **gramps** | Core | The desktop app's data model + logic, reused by the API |

**Why this matters for us:** their backend is **Flask** — *the same framework our
portal already uses*. Their frontend is framework-agnostic web components (Lit),
which can be embedded into any page. The architecture is strikingly close to
what we already have.

Data flows: Gramps.js → REST calls (e.g. `/api/people/{handle}/timeline`) →
Flask API → Gramps DB → JSON back. Clean REST, well-documented endpoints.

---

## 2. Full feature inventory

### Record types (the data model)
people · families · events · places · repositories · sources · citations ·
media objects · notes. (Same model as Gramps Desktop — battle-tested over 20 yrs.)

### Charts & visualizations
- **Ancestor chart** (pedigree)
- **Descendant chart**
- **Hourglass chart** (ancestors up + descendants down)
- **Fan chart** — circular, expanding arcs per generation, **color-coded by
  birth year / death year / surname / etc.**
- **Relationship graph** (Graphviz-rendered)
- All with **configurable generation count** and interactive graphics

### Maps (MapLibre GL)
- All places on an interactive, searchable map
- **Historical map overlays** from a stored media image
- **OpenHistoricalMap integration** with a **time slider** to watch places
  evolve over the years (e.g. shifting borders)
- Pin-drop + Nominatim geocoding to set lat/long

### Timeline & person view
- Per-person `/timeline` endpoint → life events with **date + age at event**,
  labels, roles, places
- **Sticky map beside the event list** that auto-fits to geocoded events;
  hovering an event highlights its map marker
- Hover/click raises event marker opacity (focus interaction)

### Search
- **Full-text search across ALL object types**, including note text
- Wildcards + logical operators
- **External search** (v25.12, 2026): one click searches the same person on
  CompGen, FamilySearch, Ancestry, MyHeritage, Geneanet, WikiTree, Find a Grave
  via template-URL string substitution

### DNA tools
- **Interactive chromosome browser** for DNA matches
- Store match data in a "future-proof" format
- *(Note: this is exactly the territory our MaxDNA + dna_evidence model covers —
  we go further with confidence-boost-to-ancestors; they stop at visualization.)*

### Collaboration & privacy
- **Multi-user with roles**: owner / editor / contributor / member, granular
  view/add/edit permissions
- **Private record flag** with database-layer filtering by role
- **Bi-directional sync** with Gramps Desktop (the Sync add-on)

### Media
- Web upload of photos/documents from any device
- **Automated face detection** + two-click ancestor tagging

### Research workflow
- **Integrated task manager** (tasks stored as sources in the DB)
- **Blog / stories** — narrative research write-ups with pictures
- **Reports**: relationship graphs, **book reports as PDF**, generated in-browser

### Data portability
- **Import/export GEDCOM and Gramps XML**
- Full data download (tree + media + user accounts) for backup/migration

### AI
- **AI chat assistant** — natural-language conversation with your tree data

### Platform
- **40+ languages**, community-translated
- Multi-device / responsive (PWA-style access from any browser)

---

## 3. How it maps to what we already have

| Capability | Gramps Web | OpenGenealogyAI today | Gap |
|---|---|---|---|
| Backend framework | Flask | **Flask (portal)** | ✅ same |
| Data model | Gramps DB (fixed schema) | **MAXGEN (probabilistic, confidence-scored)** | We're richer — but incompatible shape |
| Search | full-text | **semantic vector search (live)** | Different strength; ours is fuzzier/smarter |
| Charts | 5 chart types | none yet | Build (tasks #2,#5,#10) |
| Maps | MapLibre + historical | none; `place_registry` field ready | Build (task #10) after gazetteer |
| DNA | chromosome browser | **MaxDNA + confidence boost (deeper)** | We go further conceptually |
| GEDCOM | import+export | none | Build (task #8) |
| Multi-user roles | yes | portal has accounts, no roles | Build later |
| AI assistant | chat with tree | (we have agents + search) | Aligns with our strengths |

**The fundamental divergence:** Gramps uses a **single-answer** data model. We
use a **probabilistic** one. Their charts show one father; ours must show the
"10 possibilities" expander. So we can copy their *layouts and UX*, but the
*data binding* is ours — every node carries confidence + alternatives.

---

## 4. ⚠️ THE LICENSE CATCH — read before copying anything

| Component | License | Implication |
|---|---|---|
| gramps-web (Gramps.js frontend) | **AGPL-3.0** | Strong network copyleft |
| gramps-web-api (backend) | **AGPL-3.0** | Strong network copyleft |
| gramps (core) | GPL-2.0+ | Copyleft |

**AGPL-3.0 is the strongest common copyleft.** Its key clause: if you run
modified AGPL code as a *network service* (which a website is), you must offer
your **entire** corresponding source — including server-side — to all users
under AGPL-3.0. There is no "it's just on our server" loophole; that's the whole
point of the *A* in AGPL.

What this means for "lean heavily on copying Gramps":

| Approach | License effect |
|---|---|
| **Copy their feature/UX ideas** (what charts, what views, what flows) | ✅ Free — ideas/look-and-feel aren't copyrightable |
| **Mirror their REST API shape** (endpoint design) | ✅ Free — API designs aren't copyrightable (Google v. Oracle) |
| **Fork/embed Gramps.js components** into our frontend | ⚠️ Our frontend becomes AGPL-3.0 |
| **Fork gramps-web-api** as our backend | ⚠️ Our **entire** server stack becomes AGPL-3.0 |

Our current repo is **MIT** (per README badge) with **CC0** data. AGPL is
incompatible with keeping an MIT codebase. **This is a foundational licensing
decision and an architecture decision → six-brain before any Gramps code is
copied.**

---

## 5. Recommendation (pre-six-brain draft)

**Copy the design, not the code.** Gramps Web is the gold-standard reference for
*what* to build and *how the UX should feel*. Use it as the spec for our chart
types, map behavior, timeline interaction, and external-search feature. But
**build our own implementation** against the MAXGEN probabilistic model, keeping
our MIT/CC0 licensing intact.

Three reasons this is right, not just license-driven:
1. **Data model mismatch** — Gramps.js is hard-wired to the single-answer Gramps
   DB. Our confidence/alternatives model needs different components anyway.
2. **License freedom** — staying MIT keeps the standard maximally adoptable
   (companies can build on it; AGPL scares commercial adopters away).
3. **Backend parity** — their Flask API patterns are copyable as *design*; we
   already run Flask, so we mirror the endpoint shapes without taking the code.

**Specific things to copy as design:**
- Their 5 chart types + configurable generations (feeds tasks #2, #5, #10)
- The per-person `/timeline` endpoint shape (event + age + place + map marker)
- Sticky-map-beside-timeline interaction
- External-search template-URL trick (cheap, high-value, add to our roadmap)
- Role model (owner/editor/contributor/member) for when we add collaboration
- "Tasks stored as sources" pattern ↔ maps to our MaxTask

**One thing they do that we should add to the roadmap:** the **external-search
one-click** (search this person on FamilySearch/Ancestry/WikiTree/etc.) — it's
trivial (template URLs) and immediately useful. Proposed as a new task.

---

## 6. Open decision for Garlon / six-brain

The big one: **license + reuse strategy.** Options sketched (full six-brain when
you're ready to decide):

- **A. Design-only copy, build fresh, stay MIT** (recommended above) — keeps
  licensing clean and commercially adoptable; more build work.
- **B. Fork Gramps Web wholesale, go AGPL** — fastest to a feature-rich app, but
  relicenses the whole project AGPL and forces the data model toward Gramps' (we
  lose the probabilistic core, or fight the framework).
- **C. Hybrid: our MIT frontend, but run gramps-web-api AGPL as a separate
  service** — possible but the AGPL service still triggers source-offer
  obligations and couples us to Gramps' data model.

My read: A. But this is a licensing + architecture decision and explicitly a
six-brain trigger — not mine to lock.

---

Sources:
- [Features — Gramps Web](https://www.grampsweb.org/features/)
- [gramps-web GitHub (Gramps.js frontend, AGPL-3.0)](https://github.com/gramps-project/gramps-web)
- [Gramps Web Charts / Timeline implementation (DeepWiki)](https://deepwiki.com/gramps-project/gramps-web/6.2-charts)
- [External Search in Gramps Web (Grampshub, 2026)](https://www.grampshub.com/blog/en/2026/01/06/external-search-in-gramps-web.html)
- [Gramps Web home](https://www.grampsweb.org/)
