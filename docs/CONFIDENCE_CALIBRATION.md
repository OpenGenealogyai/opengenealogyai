# MAXGEN Confidence Calibration

**Status:** Standard definition (MAXGEN v1.3). Applies to every `confidence`
field in MaxRecord, MaxPerson, and MaxDNA.

Every assertion in MAXGEN carries a `confidence` in `[0.0, 1.0]`. This document
defines **what those numbers mean**, **how agents assign them**, and **how they
combine** — so that 0.7 from one agent means the same thing as 0.7 from another.

Without this, confidence scores are vibes. With it, they are comparable,
auditable, and calibratable against ground truth.

---

## Two different confidences (do not confuse them)

| Field | Question it answers | Scope |
|---|---|---|
| **per-assertion `confidence`** | "How sure are we that *this specific claim* is true?" (this birth year, this parent) | One assertion |
| **`composite_confidence`** | "How sure are we that *all assertions in this record describe one real person*?" | Whole MaxPerson entity |

Per-assertion confidence is about **fact correctness**. Composite confidence is
about **entity coherence** (did we correctly resolve all this evidence to a
single individual, or did we accidentally merge two different people?). They are
computed differently and must never be averaged together.

---

## Per-assertion confidence: the anchored scale

Confidence is anchored to **evidence quality**, using the classic
evidence-analysis triad (source · information · evidence):

- **Source**: original document vs. a derivative (a copy, transcription, index)
- **Information**: primary (informant had firsthand knowledge) vs. secondary
- **Evidence**: direct (the record's purpose was to record this fact) vs. indirect

| Band | Meaning | Typical evidence |
|---|---|---|
| **0.95 – 1.00** | Near-certain | Original + primary + direct. Birth certificate filed at birth stating the birth date. |
| **0.85 – 0.95** | Strong | Original + direct, but informant slightly removed. Death certificate's birth date (primary for death, the informant for birth was not present at it). |
| **0.70 – 0.85** | Good | Consistent secondary sources, or one solid derivative. Multiple census rows agreeing on a birth year ±1. |
| **0.50 – 0.70** | Moderate | Single secondary source, or indirect/circumstantial inference. One census; a calculated birth year from a stated age. |
| **0.30 – 0.50** | Weak | Uncorroborated late or derivative source. An undocumented online tree; family tradition with a plausible name match. |
| **0.00 – 0.30** | Speculative | Guess, placeholder, or actively conflicting. A hypothesis pending verification. |

**Rule of thumb:** if you would not stake a research conclusion on it, it is
below 0.70.

---

## Assigning per-assertion confidence (the procedure)

Agents compute a base score from the source record, then apply modifiers.

### Step 1 — base score from record type + directness

| Record / information quality | Base |
|---|---|
| Original civil record, fact is the record's purpose (birth cert → birth) | 0.92 |
| Original civil record, fact is incidental (death cert → birth date) | 0.80 |
| Church/parish register (baptism → approximate birth) | 0.78 |
| Census, government enumeration | 0.68 |
| Gravestone, obituary | 0.62 |
| Compiled/derivative work, family bible | 0.55 |
| Undocumented online tree, oral tradition | 0.35 |

### Step 2 — modifiers (additive, then clamp to [0, 1])

| Condition | Δ |
|---|---|
| Informant had firsthand knowledge of the event | +0.05 |
| Record created within 1 year of the event (contemporaneous) | +0.05 |
| Record created >50 years after the event | −0.10 |
| Transcription/OCR uncertainty noted (`extraction_confidence` < 0.8) | × `extraction_confidence` |
| Internal inconsistency in the same record | −0.15 |

The `extraction_confidence` on the MaxRecord is a **multiplier** — a perfectly
sourced fact transcribed from a blurry scan can't exceed the transcription's own
reliability.

---

## Combining corroboration: noisy-OR (with the independence rule)

When **multiple independent sources** assert the **same fact**, confidence
combines via noisy-OR:

```
P(true) = 1 − ∏ (1 − cᵢ)
```

Example: three independent records give a birth year of 1843 at confidences
0.68, 0.62, 0.55:

```
P = 1 − (1−0.68)(1−0.62)(1−0.55)
  = 1 − 0.32 × 0.38 × 0.45
  = 1 − 0.0547
  = 0.945
```

Three "good/moderate" independent sources → near-certain. This is the same
formula MaxDNA uses for `dna_evidence` chains.

### The independence rule (critical)

Noisy-OR is **only valid for independent sources**. Two online trees that both
copied the same census are *one* source, not two — combining them inflates
confidence falsely. Before applying noisy-OR:

- Sources sharing a `source_record_id` are the same source → do NOT combine.
- Derivative sources that cite the same original → collapse to the original.
- When independence is uncertain, treat as dependent (use the single highest
  confidence, do not multiply). Conservative by default.

---

## Handling conflicts (assertions that disagree)

When two assertions claim **different values** for the same fact (e.g. birth
year 1843 vs. 1845), they do **not** combine. They compete:

1. Each keeps its own confidence (computed independently).
2. Both set `conflict_flag = true`.
3. The viewer displays the highest-confidence value but **never deletes** the
   alternative (append-only).
4. If new evidence corroborates one side via noisy-OR, the balance shifts —
   without erasing the loser.

Conflict is data, not error. A 0.55/0.52 split is a meaningful signal that the
record is genuinely uncertain.

---

## `composite_confidence`: entity-coherence formula

This scores whether all the assertions describe **one real person**. It is
**not** a function of how confident any single fact is — it's about resolution
quality.

```
composite_confidence = identity_strength
                       × corroboration_factor
                       × (1 − conflict_penalty)
```

| Term | Definition | Range |
|---|---|---|
| **identity_strength** | Confidence of the strongest *uniquely identifying* signal — a distinctive name+date+place combo, or a matched `external_id` (Wikidata QID, FamilySearch PID). | 0–1 |
| **corroboration_factor** | `min(1.0, 0.6 + 0.1 × N_independent_sources)` — more independent sources linking the assertions raises coherence, capped at 1.0. | 0.6–1.0 |
| **conflict_penalty** | `0.15 × (unresolved_conflict_flags / total_assertions)` — unresolved internal conflicts lower coherence. | 0–0.15 |

**Worked example.** A person with a matched Wikidata QID (identity_strength
0.95), 4 independent sources (corroboration `0.6 + 0.4 = 1.0`), and 1 unresolved
conflict out of 10 assertions (penalty `0.15 × 0.1 = 0.015`):

```
composite = 0.95 × 1.0 × (1 − 0.015) = 0.936
```

A person built from a single uncorroborated tree with no external ID
(identity_strength 0.35, corroboration 0.7, no conflicts):

```
composite = 0.35 × 0.7 × 1.0 = 0.245
```

→ Correctly flags it as a weakly-resolved entity.

---

## Cross-agent calibration (keeping 0.7 honest)

A score is **calibrated** if, across all assertions an agent scored at 0.70,
roughly 70% are actually correct. We enforce this empirically:

1. Maintain a **gold set** — assertions with known-true values (verified against
   primary sources or expert review).
2. Periodically score the gold set with each contributor agent.
3. Build a **reliability curve**: bucket by claimed confidence, measure actual
   accuracy per bucket.
4. Compute the agent's **Brier score** (mean squared error between claimed
   confidence and outcome). Lower is better.
5. If an agent is systematically over- or under-confident, apply a **calibration
   transform** (isotonic regression or Platt scaling) to its raw scores before
   they enter MAXGEN.

This makes confidences from different agents — local models, API models, human
contributors — comparable on one scale.

Calibration metadata is recorded per agent, not in the schema. An agent's
`asserted_by` ID links to its calibration record.

---

## The DNA special case

MaxDNA `dna_evidence[]` already specifies noisy-OR for combining independent DNA
chains through a candidate ancestor, with a per-chain `confidence_delta` capped
at 0.5 to prevent single-chain overconfidence. That is the same noisy-OR defined
here, applied to a different evidence type. DNA chains and documentary assertions
about the same relationship combine into one posterior via noisy-OR — **provided
they are independent** (a documented tree that was itself built from the DNA
match is not independent of it).

---

## Quick reference for agent implementers

1. Compute base score from record type (table above).
2. Apply modifiers; multiply by `extraction_confidence`; clamp to [0, 1].
3. Same fact from independent sources → noisy-OR. Check independence first.
4. Conflicting values → compete, set `conflict_flag`, never delete.
5. `composite_confidence` = identity_strength × corroboration × (1 − conflict_penalty).
6. Your scores will be checked against the gold set — be honest, not optimistic.
