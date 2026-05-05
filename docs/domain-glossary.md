# OpenGenealogyAI Domain Glossary

Every agent, contributor, and tool must use these definitions exactly.
Each term: one-sentence definition, one example, one anti-example.

---

## Core Data Types

**RawRecord**
A single original source document exactly as found, with no interpretation added.
*Example:* A scanned 1887 Virginia death certificate with handwritten entries for "Abram Lincoln, age 43."
*Anti-example:* A summary that says "Abraham Lincoln died in 1887" with no source citation.

**Person**
A probabilistic identity record aggregating multiple RawRecord assertions about one individual, with confidence scores on every field.
*Example:* Person ID p-001 with name_canonical="Abraham Lincoln Sr.", birth_year_min=1742, birth_year_max=1746, confidence=0.82.
*Anti-example:* A single definitive record stating "Abraham Lincoln Sr., born 1744" with no confidence score or source.

**Assertion**
A single claimed fact about a Person derived from one or more RawRecords, with a confidence score and source list.
*Example:* Assertion: "Person p-001 has_parent Person p-002, confidence=0.74, sources=[r-019, r-023]."
*Anti-example:* An unsourced note saying "probably the son of Mordecai Lincoln."

**Confidence Score**
A decimal from 0.0 to 1.0 representing the system's certainty that an assertion is correct, based on source quality and corroboration.
*Example:* confidence=0.91 means two independent primary sources agree on the same fact.
*Anti-example:* confidence=1.0 — reserved only for mathematically certain facts (e.g., a person cannot be their own parent).

**Redistribution License**
A machine-readable field on every fact indicating whether it can be shared publicly.
*Example:* redistribution_license="CC0" means anyone can republish the fact without restriction.
*Anti-example:* Omitting the field and assuming all data is public — FamilySearch data is never redistributable.

---

## Source Tiers

**Tier 1 (Open Dataset)**
Records that can be freely stored, searched, and redistributed. Sources: Internet Archive CC/public-domain, Wikidata CC0, US Census pre-1927, user-contributed CC-BY-SA 4.0.
*Example:* A pre-1927 Illinois death record downloaded from Internet Archive with license=CC0.
*Anti-example:* Any record from FamilySearch — even if technically accessible, it cannot be redistributed.

**Tier 2 (Private Augment)**
Records fetched on behalf of a specific consenting user that cannot be merged into the open dataset.
*Example:* A FamilySearch ancestry hint fetched using the user's own OAuth token, stored only in their private partition.
*Anti-example:* Copying a FamilySearch record into the public Qdrant collection.

---

## Agent Roles

**Orchestrator**
The top-level Sonnet-class agent that receives a user request, decomposes it into tasks, dispatches to worker agents, and collects results.
*Example:* Orchestrator receives "build tree for Abraham Lincoln Sr." and dispatches three parallel extractor agents.
*Anti-example:* An agent that both extracts records AND approves writes — no agent does two roles.

**Extractor (Haiku worker)**
A low-cost parallel agent that fetches and converts raw records from a single source into RawRecord JSON format.
*Example:* Extractor claims one Internet Archive collection task, fetches 200 records, converts to RawRecord JSON, terminates.
*Anti-example:* An extractor that decides which records are relevant — that is the critic's job.

**Validator**
An agent that checks extracted RawRecord JSON against the schema before passing it forward.
*Example:* Validator confirms all required fields are present and redistribution_license is set.
*Anti-example:* A validator that also scores confidence — that is the critic's job.

**Critic**
An agent that scores the quality of extracted records and proposes confidence scores for assertions.
*Example:* Critic compares two records about the same person and assigns confidence=0.68 due to conflicting birth years.
*Anti-example:* A critic that writes to the database — only the integrator does that.

**Judge**
The sole gatekeeper between all producer agents and the persistent databases. Approves or blocks every proposed write.
*Example:* Judge receives a proposed Person record, verifies schema compliance and confidence threshold, returns APPROVED.
*Anti-example:* A judge that generates new data — it only evaluates what producers submit.

**Integrator**
An agent that commits judge-approved records to SQLite and Qdrant.
*Example:* Integrator receives APPROVED assertion, writes to assertions table, indexes in Qdrant, logs cost.
*Anti-example:* An integrator that modifies the record before writing — write exactly what judge approved.

---

## Data Model Terms

**date_range**
A pair of integers (year_min, year_max) representing uncertain dates. Never store a single "exact" year unless absolutely certain.
*Example:* birth year of a person from an 1880 census listing age 36 → birth_year_min=1843, birth_year_max=1845.
*Anti-example:* birth_year=1844 with no range — false precision.

**is_living**
A boolean flag (true/false) that triggers privacy protection. Set true if birth_year > (current_year - 110) OR if any source indicates the person may be alive.
*Example:* Person born 1990 → is_living=true → returns 404 on all open dataset endpoints.
*Anti-example:* Omitting is_living and exposing a living person's data publicly.

**source**
A reference to a specific RawRecord that supports an assertion. Every assertion must have at least one source.
*Example:* source: {record_id: "r-019", page: 42, confidence_contribution: 0.4}
*Anti-example:* source: "Internet Archive" — too vague, must reference a specific record ID.

**evidence**
The collection of all assertions about a Person from all sources, never deleted, only superseded by newer assertions.
*Example:* Two conflicting assertions about birth year both exist in evidence, each with their own confidence score.
*Anti-example:* Deleting an old assertion when new evidence arrives — always preserve the full history.

---

## System Terms

**Task Queue**
A file-based directory system (inbox/processing/done/failed) where agents claim and complete discrete units of work atomically.
*Example:* An extractor claims `inbox/ia-illinois-1890-001.json` by renaming it to `processing/ia-illinois-1890-001.json`.
*Anti-example:* Two agents reading the same task file without atomic claiming — causes duplicate work.

**Context Isolation**
The requirement that the judge agent never sees the reasoning of the producer agents, only their output.
*Example:* Judge receives only the proposed JSON record, not the extractor's chain-of-thought.
*Anti-example:* Passing the full conversation history to the judge — would bias its evaluation.

**Escalation**
The process of routing a decision to a higher-capability model when confidence is insufficient.
*Example:* Conflicting assertions with delta < 0.2 escalate from Sonnet judge to Opus for resolution.
*Anti-example:* Escalating every decision to Opus — defeats cost discipline.

**Human Gate (HG)**
A numbered action that requires Garlon Maxwell's personal involvement. All other actions are agent-autonomous.
*Example:* HG-1: Create GitHub org and PAT. HG-6: Post to Hacker News.
*Anti-example:* Any routine data processing step — agents handle all of those.

---

## Business Terms

**Free Tier**
Access to the public genealogy registry: browse trees, view probabilistic relationships, download schemas, contribute records.

**Paid Tier**
Instant Tree Build ($9/mo): submit your name and birth year, agents auto-populate 3+ generations within 30 minutes using Tier-1 public-domain sources, with every fact cited.

**Adopt a Collection**
A contributor program where community members claim an Internet Archive genealogy collection, extract records using the provided tools, and submit validated RawRecord JSON via pull request.
*Example:* Contributor claims the 1890 Illinois death register collection, processes 500 records, submits PR.
*Anti-example:* Uploading records without running the schema validator first.
