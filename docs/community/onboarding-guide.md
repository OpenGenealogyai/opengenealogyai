# OpenGenealogyAI — Contributor Onboarding Guide

**Version:** 0.1 | **Status:** Draft — awaiting HG-6 approval

Welcome to OpenGenealogyAI. This guide gets you from zero to your first merged contribution.

---

## What We're Building

An open standard and platform for probabilistic genealogy. Every assertion about a person carries:
- A **confidence score** (0.0–1.0)
- A **source citation** (the document that produced it)
- An **agent or contributor ID** (who asserted it)
- A **timestamp** (append-only — nothing is ever deleted)

Multiple possible parents can coexist. Uncertainty is a feature, not a bug.

---

## Ways to Contribute

### 1. Validate Confidence Scores (No coding required)
Review AI-extracted assertions against the source documents. Tell us whether our confidence scores feel right based on the evidence. Especially valuable if you have genealogical research experience.

**How:** Pick a record from the `needs-human-review` label on GitHub Issues. Download the source document. Fill in the review form linked in the issue.

**Time:** 15-30 minutes per record set.

### 2. Adopt a Collection (Intermediate)
Take ownership of getting a historical document collection indexed.

**How:**
1. Pick an unassigned collection from `docs/community/adopt-a-collection-tasks.md`
2. Comment on the GitHub Issue to claim it
3. Use `agents/ia-fetcher/ia_fetcher.py` to fetch items from Internet Archive
4. Run `agents/ia-fetcher/ia_to_rawrecord.py` to convert to RawRecord format
5. Validate with `schemas/validators/validate-raw-record.js`
6. Open a PR with the extracted records in `data/raw-records/{collection-id}/`

**Time:** 2-4 hours per collection.

### 3. Write Extraction Rules (Technical)
Some record types need custom parsing — German church records, Freedmen's Bureau files, Italian civil records. If you know a record type well, help us build keyword maps and field extractors.

**How:** See `agents/ia-fetcher/ia_to_rawrecord.py` → `RECORD_TYPE_HINTS` dict. Open a PR adding new keywords with a test fixture.

### 4. Fix Bugs / Add Features (Coding)
Standard open-source contribution. See the Issues tab on GitHub.

**Stack:** Python 3.12, Node.js (AJV validator only), JSON Schema 2020-12.

---

## Setup

```bash
git clone https://github.com/opengenealogyai/opengenealogyai
cd opengenealogyai

# Python dependencies
pip install qdrant-client openai ajv

# Node.js (for schema validator only)
npm install

# Run all tests
python test/test_ia_fetcher.py
python test/test_privacy_middleware.py
python test/test_tree_builder.py
python test/test_integration_pipeline.py
```

---

## Code Standards

- No comments that explain WHAT code does (names should do that)
- Add comments only for non-obvious WHY (a hidden constraint, a privacy invariant)
- Every new assertion must have `source_record_id` — empty string is rejected
- `is_living_flag: true` records never go into public Qdrant — enforced in `privacy_middleware.py`
- Confidence scores: 0.0 = no evidence (rejected by judge), 1.0 = absolute certainty (rare)
- Append-only: never delete or modify existing assertions, only add new ones

---

## Privacy Rules (Non-Negotiable)

1. Any person whose birth year is > (current year - 110) is potentially living — `is_living_flag: true`
2. Living persons: 404 on all open endpoints, never in Qdrant, never in public datasets
3. FamilySearch data is always `redistribution_license: tier2-private` — never in open data
4. When in doubt: living flag ON, license tier2-private

Violating these rules will block your PR.

---

## Your First Contribution

The easiest first step:
1. Go to GitHub Issues → filter by `good-first-issue`
2. Or open `docs/community/adopt-a-collection-tasks.md` → pick an unclaimed collection
3. Comment "I'm claiming [collection name]" on the issue
4. Follow the Adopt a Collection steps above

Questions: open a GitHub Discussion. We'll respond within 48 hours.
