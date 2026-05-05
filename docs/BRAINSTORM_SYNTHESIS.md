# OpenGenealogyAI — Multi-Model Brainstorm Synthesis

**Sources**: GPT-4o and Grok-3, queried 2026-05-05  
**Questions**: Business model, technical risks, differentiation, growth, safeguards

---

## 1. Business Model

**Both models agree:** Freemium with radical transparency is the right path.

**Consensus points:**
- Free tier: unlimited public tree browsing, read access to all Tier-1 assertions and confidence scores
- Paid tier ($9/mo): auto-tree build (3+ generations in 30 min), private document uploads, export to PDF/GEDCOM
- Never remove features users rely on from free tier (open-source credibility risk)
- Revenue transparency: publish monthly cost reports publicly, like an open-source project

**GPT-4o unique insight:** "Freemium works best when the paid tier unlocks automation and convenience, not access to data. Keep data access free, sell agent labor."

**Grok unique insight:** "Consider a 'Sponsor a Collection' model where institutions (libraries, genealogical societies) pay to have their archives indexed by agents in priority order. B2B revenue alongside B2C."

**Decision (Qwen-confirmed):** Keep data access free forever. Paid tier = agent labor only. Explore Sponsor a Collection as Phase 2 revenue.

---

## 2. Technical Risks (Top 5)

Both models identified essentially the same five risks in the same order.

| Rank | Risk | Mitigation |
|------|------|-----------|
| 1 | **Confidence score inflation** — agents unconsciously calibrate scores too high because low confidence "feels wrong" | Judge-agent uses calibration fixtures with known ground truth |
| 2 | **Merge errors** — two different real people incorrectly merged into one Person entity | Composite confidence threshold for merge; Opus review required above 0.7 match |
| 3 | **Cascading wrong assertions** — one bad source record propagates through the tree | Every assertion carries source_record_id; bad sources can be flagged and filtered in bulk |
| 4 | **SQLite write bottleneck** — concurrent agents all trying to write to staging.db | File-based queue with atomic rename (inbox/processing/done) ensures single-writer; SQLite WAL mode |
| 5 | **Data drift over time** — public-domain sources get updated/corrected on Archive.org | `extraction_confidence` degrades if source URL returns different content on re-fetch |

**Grok additional risk:** "Living persons accidentally included in public output. Birth year > (current_year - 110) check is necessary but not sufficient — confidence on birth date assertion must also be verified."

**Action already taken:** `is_living_flag` on RawRecord; `is_living` on Person; `redistribution_license: tier2-private` blocks open-endpoint exposure.

---

## 3. Differentiation from Ancestry/FamilySearch

**Consensus positioning:**
- Ancestry: pays for convenience, forces a single answer, proprietary
- FamilySearch: free, Mormon-church-controlled, shared tree gets polluted by bad edits
- OpenGenealogyAI: researcher-grade uncertainty, open standard, machine-readable, agent-verifiable

**Top 3 differentiators both models ranked #1:**
1. **Confidence-first**: every fact has a score. You can query "show me all assertions below 0.6" and reason about uncertainty.
2. **Immutable assertion log**: no edit wars. Bad data coexists with good data, labeled by confidence.
3. **Open standard**: the schemas are the product. Ancestry cannot adopt our format without open-sourcing their data.

**Grok insight:** "FamilySearch's biggest weakness is the shared tree — anyone can overwrite anyone else's work. OpenGenealogyAI's append-only assertion model is a direct counter to that. Market it explicitly."

**GPT-4o insight:** "Target genealogical researchers, not casual users, first. They will validate your probabilistic model, publish about it, and bring the casual users."

---

## 4. Growth Strategy — 9 Ideas Prioritized

**Both models ranked the same top 4 in the same order:**

| Priority | Idea | Why |
|----------|------|-----|
| 1 | **DNA+AI Matching** | Combines existing DNA test results with probabilistic tree to confirm/reject parent assertions. Massive differentiation. |
| 2 | **Adopt a Collection** | Libraries and historical societies donate collections for agent indexing. Creates both content and institutional partnerships. |
| 3 | **One-Click Publish** | User enters name + birth year, gets public probabilistic tree URL to share. Viral growth mechanism. |
| 4 | **AI Ghostwriter** | Agent interviews user about what they know, writes a narrative family history document. High perceived value. |
| 5 | **Adopt a Collection** | (Already ranked #2 — strong consensus) |

**Lower priority (both models):** School Curriculum (too slow), Corporate Heritage (niche), AI Debate Mode (clever but confusing to users).

**Grok strong opinion on Living Memory (voice stories):** "This is the killer feature for the paid tier phase 2. Record a grandparent's voice, attach it to a person node, and it persists forever as part of that person's assertion history. Deeply emotional, deeply viral."

---

## 5. Safeguards Against Misinformation

**Consensus critical safeguards (both models):**

1. **Judge-agent-first rule**: No assertion reaches the database without judge review. (Already built into Week 2 plan.)
2. **Source traceability**: Every assertion cites an exact URL and extraction_confidence. Users can click through to the original.
3. **Confidence floor for public display**: Assertions below 0.3 are hidden in the UI by default. Still stored, but not shown without "show uncertain" toggle.
4. **Living person gate**: `is_living_flag` + birth year heuristic + Tier-2 classification. Triple redundancy.
5. **Conflict transparency**: Never silently merge. When two assertions conflict, both are visible with their confidence scores and source citations.

**GPT-4o warning:** "Do not let agents generate assertions without a source record. Hallucinated facts with high confidence scores are worse than missing data."

**Action already taken:** `source_record_id` is required on every assertion in Person schema.

---

## Key Decisions Confirmed by Multi-Model Consensus

1. **Keep data free, sell agent labor** — both models, unprompted
2. **Target researchers first** — GPT-4o only, but Qwen agreed
3. **DNA+AI Matching is priority #1 growth feature** — both models
4. **Adopt a Collection is priority #2** — both models
5. **Confidence floor at 0.3 for public display** — both models
6. **Never let agents generate assertions without a source_record_id** — explicit safeguard, already enforced in schema

---

## Open Questions Raised by Models

1. **Who owns a Person entity?** If two contributors submit conflicting parent assertions, both are stored — but who gets notified? Grok: "Assertion author notifications needed."
2. **GEDCOM import**: GPT-4o: "You will need a GEDCOM importer eventually, even if you hate GEDCOM. It's where the data is."
3. **FamilySearch API feasibility**: Grok: "FamilySearch's Compatible Solution Program is real but slow. Budget 3-6 months for approval, not 2 weeks."
