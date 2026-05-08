# OpenGenealogyAI and the MaxGen Standard

## What Is OpenGenealogyAI?

OpenGenealogyAI is an open genealogical research platform with a single mission: bring family history to every person on earth using AI, and fund it by charging fairly for AI research time while paying the people who do the work.

The platform is built around two core ideas:
1. **An open standard** (MaxGen) that anyone can use, build on, and contribute to — no license, no fees, no permission required.
2. **A fair economic model** that pays contributors 70 cents of every dollar their work generates, while keeping the platform affordable for ordinary people.

OpenGenealogyAI is accessible at OpenGenealogyAI.com and OpenGenealogyAI.org.

---

## The MaxGen Standard

### What MaxGen Is

**MaxGen** (Maxwell Genealogy Standard) is a JSON-based open standard for genealogical data. It is designed to be the format that AI tools, genealogy applications, researchers, institutions, and developers can all build on — the standard that GEDCOM tried to be, rebuilt for the AI era.

MaxGen is:
- **CC0 public domain** — no copyright, no license restrictions, no fees
- **Stewarded by Garlon Maxwell** — a named, accountable human steward responsible for governance decisions
- **Open on GitHub** — all schemas, the public database, governance rules, and audit logs are publicly accessible, forkable, and permanent

### What Makes MaxGen Different from GEDCOM

GEDCOM (the existing genealogy data standard) was created in 1984 and has significant limitations: poor Unicode support, no standard for evidence quality, no confidence scoring, no contributor attribution, and no native support for AI-driven probabilistic relationships.

MaxGen addresses all of these:

**Probabilistic relationships with confidence scores:** Every relationship in MaxGen carries a confidence score from 0.0 to 1.0. A documented relationship with a birth certificate, a marriage record, and a census confirmation may score 0.95. An inferred relationship with only indirect evidence may score 0.42. Researchers and AI systems always know how certain a connection is.

**Source attribution on every record:** Every embedded record carries a `source` object identifying where the information came from. Every `Person` object carries a `contributors` array listing everyone who contributed source records linked to that person.

**Designed for vector search:** MaxGen records are designed to be embedded into vector databases (like Qdrant) for semantic search. A user asking "find German ancestors in Kentucky around 1820" can retrieve relevant records through AI semantic search, not just keyword matching.

**Versioned schema:** MaxGen uses semantic versioning (v1.0, v1.1, v2.0). Records written to any version remain readable forever. Version upgrades are governed through a public process on GitHub.

### Schema Governance

Anyone can propose a MaxGen schema change by filing a GitHub Issue using the standard change proposal template. The community discusses it openly. Garlon Maxwell has final approval — nothing merges without his sign-off. Changes are categorized as:
- **Minor versions** (v1.0 → v1.1): Additive changes, new optional fields. All existing records remain valid.
- **Major versions** (v1.0 → v2.0): Breaking changes. Announced with migration tools and a transition period.

---

## Research Actions — How Pricing Works

### What a Research Action Is

A Research Action is one unit of AI research work. Every time the AI takes a discrete step on your behalf — searching an archive, comparing two names across records, checking whether two people in different documents might be the same person, scoring a relationship, or retrieving a document — that is one Research Action.

Research Actions are intentionally granular and transparent. You see what the AI did and pay only for what it actually does.

### Pricing

**Pay-as-you-go:** $0.12 per Research Action. No subscription required. Pay only for what you use.

**Monthly bundles (better value):**
- **Starter:** 100 Research Actions for $10 ($0.10/action)
- **Regular:** 350 Research Actions for $29 (~$0.083/action)
- **Power:** 1,250 Research Actions for $100 ($0.08/action)

Research Actions do not expire within the subscription month. Unused actions roll over for one additional month.

### What Research Actions Are Used For

- Searching the embedded record database for a specific ancestor
- Comparing name/date/place combinations across multiple records
- Generating a confidence score for a proposed parent-child relationship
- Retrieving documents from historical archives
- Cross-referencing a record against existing data in your tree
- Generating a draft family group sheet from raw data

Research Actions are the primary revenue source for the platform and the pool from which contributors are paid.

---

## Contributor Attribution and the Payment Model

### How Attribution Works

Every MaxGen record carries a `contributor` object. When a contributor embeds a genealogical record — indexing a historical document, verifying a name against a source, scoring a relationship — their identifier is permanently attached to that record.

Every `Person` object in MaxGen carries a `contributors` array listing every person who contributed any source record linked to that individual. This attribution is:
- **Permanent** — it cannot be removed, even if the record is edited
- **Mandatory** — any tool, viewer, or application built on MaxGen is required by the standard to display contributor attribution
- **Public** — contributor records are visible on every page of the platform

### The Payment Split

When a user spends $1 on Research Actions, the revenue is distributed as follows:
- **70%** to the contributor(s) whose work powered the research
- **10%** to the quality control reviewer who verified the record
- **20%** to the platform (OpenGenealogyAI) for coordination, infrastructure, and development

If multiple contributors worked on a record, the 70% is split proportionally based on contribution weight.

### How Payments Are Made

Contributors are paid monthly via PayPal or ACH bank transfer. The minimum payout threshold is $5. Contributors who earn below the threshold in a given month accumulate their balance for the following month.

### Donations

Platform donations are pooled and distributed monthly to active contributors, weighted by each contributor's verified output that month. If a contributor produced 12% of all verified records in a given month, they receive 12% of that month's donations. The platform keeps 0% of donations. Every distribution is published in the open ledger on GitHub.

---

## Document Storage

Document storage is a separate paid product, not related to Research Actions:

- **Basic:** $2/month — up to 1,000 documents
- **Standard:** $5/month — up to 5,000 documents and photos
- **Archive:** $12/month — up to 20,000 items including video and audio

Users own their files. Files can be downloaded in full at any time. Document storage revenue goes 100% to the platform; contributors are not paid from storage fees.

Stored documents are linked directly to specific people in the user's family tree and are accessible through the paid user portal.

---

## Free Ancestor Report

### The Core Promise

Any person, anywhere in the world, can request a free ancestor report. No credit card. No account required.

**How it works:**
1. Fill out a short form: your name, your parents' names and approximate dates and locations, and your email address.
2. The AI research pipeline begins working on your tree.
3. Within 24 hours, you receive a report by email covering what was found: names, dates, places, and sources for the generations we were able to document.
4. The report links to a browser-based viewer where you can see the pedigree chart.

The free report is the platform's primary trust-building mechanism and its most important marketing asset. It is also the seed for the contributor workforce and the database — every free report generates research that contributes to the public MaxGen database.

### Upgrade Path from Free to Paid

Users who request a free report and want to go deeper can:
- Buy Research Actions to continue AI research on their tree ($10 minimum)
- Upgrade to a paid account to access the full interactive portal
- Add document storage to preserve photos and certificates
- Become a contributor and earn from their own genealogical work

---

## The Paid Portal

Paid users (anyone who has purchased Research Actions or document storage) get access to a private dashboard including:

- **Interactive pedigree chart** — clickable, zoomable, built with D3.js; color-coded by confidence score
- **Family group sheets** — auto-generated, printable, downloadable as PDF
- **Document library** — uploaded documents organized by person
- **Tree sharing** — generate private links for family members

The portal is the destination where all platform services come together for the user.

---

## The MaxGen Database on GitHub

The public MaxGen database — all records that are not subject to privacy restrictions — is maintained as a GitHub repository. This means:

- **The database is forkable.** Any developer can fork the entire dataset and build their own application.
- **The database is auditable.** Every record addition, modification, and deletion is tracked in version history.
- **The database is permanent.** Even if OpenGenealogyAI ceased operations, the standard and the data would remain publicly accessible.
- **The contributor ledger is public.** Every payout, every contribution weight, every distribution is visible on GitHub.

This level of transparency is intentional. The genealogical community has seen proprietary platforms restrict, monetize, and ultimately lose data. MaxGen is built to prevent that outcome.

---

## Ada — The Platform's AI Persona

Ada is OpenGenealogyAI's AI genealogy assistant. She is available as a chat widget on every public page of the platform.

Ada is named in the spirit of Ada Lovelace — the first programmer — as a nod to the intersection of history, documentation, and technology that defines genealogy.

Ada's role is to:
- Answer genealogy research questions from the knowledge base
- Guide visitors toward the free ancestor report
- Convert curious visitors into paying Research Action buyers
- Explain the MaxGen standard and platform features

Ada's free tier allows 2 questions without an account. After question 2, Ada asks for an email address in exchange for 3 more free answers. After those 5 questions, Ada offers to search the live record database with Research Actions starting at $10.

When the Qdrant database has sufficient records for a user's ancestry, Ada switches from knowledge-base answers to live record search automatically — the same interface, more powerful results.

---

## Contact and Platform Information

- **Website:** OpenGenealogyAI.com / OpenGenealogyAI.org
- **GitHub:** github.com/opengenealogy (schema, database, governance)
- **Free report form:** Available at the top of the homepage
- **Steward:** Garlon Maxwell
- **Platform model:** Open standard + fair contributor economics + transparent governance
