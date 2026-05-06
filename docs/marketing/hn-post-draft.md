<!-- DRAFT — awaiting HG-6 approval before posting -->

# Show HN: OpenGenealogyAI — probabilistic genealogy standard where every fact has a confidence score

I've been thinking about why genealogy research tools are so frustrating: they all force a single answer. Two records disagree about who someone's father was? One gets deleted. Researchers fight, the loudest voice wins, and the uncertainty — the most honest part of historical research — disappears.

So I built an open JSON schema standard where every assertion about a person carries:
- A confidence score (0.0–1.0)
- The source record that produced it
- Which agent or contributor asserted it
- A timestamp (assertions are append-only, never deleted)

Example: Abraham Lincoln's (b. 1809) father might be Thomas Lincoln (confidence: 0.82) AND Abraham Enloe (confidence: 0.12). Both assertions coexist. A researcher can cite either. No one's work gets overwritten.

**Three schemas define the standard:**
- `RawRecord` — a source document exactly as found (census row, parish register, death certificate) with no interpretation added
- `Person` — probabilistic identity with multiple possible parents, each with a relationship_type (biological/adoptive/step), confidence score, and source citation
- `TaskQueue` — distributed work queue so AI agents can ingest, judge, and build trees without coordinating directly

**What we built so far:**
- JSON Schema 2020-12 specs with AJV validation and 60+ test fixtures
- Judge agent (Python) that runs 5 checks on every assertion: schema conformance, confidence validity, source credibility, privacy gate (living persons), relationship consistency
- Internet Archive fetcher that converts 22 curated genealogy collections to RawRecord format
- Qdrant vector DB setup with Soundex + character 3-gram hybrid search (for historical name variants like Lincoln/Linkhorn)
- Conflict resolution protocol with 3 tiers: auto-approve (gap ≥0.40), Opus review (gap <0.40), human gate
- Privacy middleware that returns 404 (not 403) on any living or tier2-private record

**Tech stack:** JSON Schema 2020-12, Python, SQLite (append-only assertions), Qdrant on Docker, Internet Archive as free document storage.

**Business model:** Free tier = browse all public probabilistic trees. Paid tier ($9/mo) = AI agents auto-build 3+ ancestral generations in 30 minutes. The data is CC0 forever. You pay for agent labor.

**Status:** Core infrastructure done. Looking for genealogical researchers who want to help validate the probabilistic model — especially anyone who's worked with records where parentage is genuinely disputed.

GitHub: https://github.com/opengenealogyai
Schema docs: https://opengenealogyai.org/schemas/v0.1/

The core insight: genealogy is fundamentally probabilistic. We should stop pretending otherwise.
