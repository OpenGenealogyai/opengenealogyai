# PROJECT_CHARTER.md — OpenGenealogyAI

## Vision

An open standard for genealogy that treats uncertainty as a first-class feature.
Every relationship, date, and name carries a confidence score and source attribution.
Multiple possible parents are the norm. No fact is ever overwritten.

## What This Is

- An open JSON standard for probabilistic genealogy records
- A public registry of Tier-1 (redistributable) genealogy facts
- A working AI agent pipeline that builds family trees from public-domain sources
- A contributor platform (Adopt a Collection) for growing the dataset

## What This Is NOT

- A replacement for Ancestry, FamilySearch, or GEDCOM
- A database of living persons (is_living=true returns 404 always)
- A tool for storing or redistributing FamilySearch or Ancestry data

## Product Tiers

### Free Tier
- Browse the public genealogy registry
- View probabilistic family trees with confidence scores
- Download the JSON schemas and build tools
- Contribute records via Adopt a Collection program
- Query the API for public Tier-1 records

### Paid Tier ($9/month — "Instant Tree Build")
- Submit your name, birth year, and country
- Agents automatically build 3+ ancestral generations within 30 minutes
- Every fact is cited with a Tier-1 source
- Results delivered as downloadable JSON + viewable web tree
- Private Tier-2 augment available: connect FamilySearch for additional hints (your data only, never redistributed)

## Core Differentiator

No other genealogy platform models uncertainty natively. FamilySearch and Ancestry force
a single "correct" answer for every relationship. Our system allows:
- Multiple possible parents with confidence scores
- Assertions that conflict are preserved (never deleted, only superseded)
- Every fact traceable to its source record

## Versioning Policy

- Schema versions use semantic versioning: MAJOR.MINOR.PATCH
- Breaking schema changes require a new MAJOR version
- Old schema versions remain valid indefinitely (no forced migration)
- Schema $id URLs are permanent once published (human gate HG-6 required to change)

## Open Questions Log

| # | Question | Owner | Status |
|---|----------|-------|--------|
| 1 | GitHub org name: opengenealogyai vs open-genealogy-ai? | Agents research, Garlon decides | Resolved: opengenealogyai |
| 2 | Qdrant local vs cloud? | Agents | Resolved: local on Omen, cloud fallback if GPU contention |
| 3 | GEDCOM import tool? | Agents | Deferred to v2 |
| 4 | FindAGrave redistribution ToS? | Agents verify | Open |
| 5 | Stripe or LemonSqueezy for paid tier? | Agents research | Open |
