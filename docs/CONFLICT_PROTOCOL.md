# Conflict Protocol

When two or more agents produce contradictory assertions about the same Person entity, this protocol governs resolution.

## Definitions

- **Conflict**: two parent_assertions for the same `parent_role` (father or mother) on the same Person, or two birth_assertions with non-overlapping date ranges and gap > 5 years
- **Confidence gap**: absolute difference between the two competing assertion confidence scores
- **Judge threshold**: 0.40 — the minimum confidence gap at which the judge-agent can resolve a conflict autonomously

## Resolution Tiers

### Tier 1 — Automatic (confidence gap >= 0.40)
The judge-agent sets `conflict_flag: true` on the lower-confidence assertion and logs the decision in the task result. No escalation needed.

### Tier 2 — Opus escalation (confidence gap < 0.40)
The judge-agent creates a `resolve_conflict` TaskQueue entry with `priority: 9` and `cost_cap_usd: 5.00`. The Opus conflict resolver reviews all source records, weighs evidence, and selects the winning assertion. Both assertions remain in the Person record permanently — the loser gets `conflict_flag: true`.

### Tier 3 — Human gate (Opus confidence < 0.50 after review)
Opus creates a human-gate notification in `queue/inbox/human-gate-<person_id>.json`. Garlon reviews and approves via HG-7.

## What Never Happens

- No assertion is deleted. Ever. Evidence accumulates; it is never removed.
- No single "correct" parent is forced. Conflicting assertions coexist with explicit confidence scores.
- The system never blocks a tree build due to a conflict — it builds with the highest-confidence path and flags uncertainty in the output.

## Conflict Record Format

When the judge sets `conflict_flag: true`, it appends to the task result:

```json
{
  "conflict_resolved_at": "2026-05-01T14:00:00Z",
  "conflict_resolution_tier": 1,
  "winning_assertion_index": 0,
  "losing_assertion_index": 1,
  "confidence_gap": 0.63,
  "resolution_agent": "judge-agent-sonnet-001"
}
```

## Cost Guardrails

| Resolution tier | Max cost |
|----------------|---------|
| Tier 1 (judge) | $0.10 |
| Tier 2 (Opus) | $5.00 |
| Tier 3 (human gate) | $0 (no API cost) |

If a Tier 2 task exceeds $5.00, it fails and escalates to Tier 3 automatically.
