# Microcopy & Error Tone-of-Voice

**Status:** Foundation draft (Batch 1a, task 4). All UI strings honor this.

Every component that shows text routes through these patterns. New text gets
added to this doc, not invented case-by-case. The point: the *system* sounds
consistent — calm archivist, never breathless, never blaming.

Anchored to `docs/brand.md`. Read that first.

---

## The five universal rules

1. **State what is, not what we wish.** Avoid hedges like "should be," "might
   be," "could possibly." Either we know with confidence or we say "we think"
   with the score.
2. **Numbers in ranges, not points.** "1840–1845" over "around 1843."
3. **Verb-first CTAs.** "Add a photo," not "Photo upload."
4. **Errors name the cause + the next step.** Never "Something went wrong."
5. **Specific confirmations.** "Saved — 3 sources added to William Maxwell" — never "Success!"

---

## Error message pattern

Every error answers three questions in this order:

```
[What happened]. [Why, if we know]. [What to do next].
```

### Examples

| ❌ Avoid | ✅ Prefer |
|---|---|
| "Oops! Something went wrong." | "We couldn't load the photo. The file may be moved or you may be offline. Reload, or try again in a minute." |
| "Invalid input." | "We need a year between 1000 and 2100 in the birth field. You typed '184' — did you mean 1840?" |
| "Permission denied." | "This record is marked private. Sign in as the owner to view." |
| "404 — Not Found." | "We can't find person `8a3f-…` in your tree. They may have been merged or removed. See your recent changes." |
| "GEDCOM parse error: line 47." | "We couldn't read your GEDCOM file at line 47 (unexpected character `™`). Try saving it as plain text from your software, then re-upload." |

### Never in error copy

- "Oops" / "Yikes" / "Uh-oh" — undignified
- "Failed" as a verb pointed at the user
- Exclamation marks. Errors are calm
- "Please try again" without telling them *what* to change
- Stack traces, internal IDs, codes the user can't act on (log those for us — show them a UUID only if they need to quote it to support)

---

## Empty state pattern

```
[Plain-English description of the void]. [Single clear next step as a CTA].
```

### Catalog

| Surface | Copy |
|---|---|
| New user dashboard | "No trees yet. **Create your first tree →** or **Import a GEDCOM →**" |
| Tree with no people | "This tree is empty. **Add yourself or a starting ancestor →**" |
| Person with no facts | "No facts recorded yet. **Add a birth, death, or other event →**" |
| Person with no photos | "No photos of this person yet. **Add a photo →**" |
| Person with unknown father | "Father unknown. **See 10 candidate fathers →**" (links to possibility-expander) |
| Person with no sources | "No sources cited yet. **Cite a record →**" |
| Search returned nothing | "Nothing matched **"Jonas Mxwell."** Try fewer words, or check the spelling." |
| DNA matches list (empty) | "No DNA matches yet. **Connect a kit →**" |

**Never use the literal string "(none)" or "N/A"** — both are voids in
disguise. Either name the next step or render an honest dash with context.

---

## Confirmation pattern

After any save / write / send action:

```
[Past-tense verb] — [specific noun + count]. [Optional undo link].
```

### Examples

- "Saved — 3 sources added to William Maxwell."
- "Photo uploaded — set as primary. **Undo →**"
- "Merge complete — Mary Hodge merged into Ruthey Hodge. **Undo this merge →**"
- "GEDCOM exported — 1,247 people, 318 marriages. **Download →**"

### Never

- "Success!" / "Done!" — both lose specificity
- "It worked!" — patronizing
- Confirmation modals that say "Are you sure?" without telling the user what
  they're about to do. Always restate the action and its scope.

---

## Confirmation modal pattern (destructive actions)

```
Title:      [Action verb] [specific thing]?
Body:       [What will happen]. [How much / how many]. [Reversibility].
Primary:    [Same action verb] — [thing]
Secondary:  Cancel
```

### Example — deleting a person

```
Title:      Remove William Maxwell from this tree?
Body:       This will remove 1 person and the 14 facts attached to him.
            Their sources stay in your library. You can undo this for 30 days.
Primary:    Remove William
Secondary:  Cancel
```

Never just **"Are you sure? Yes / No"** — the user has to scroll back to
remember what they clicked.

---

## CTA button text rules

- **Verb-first, then noun.** "Add a photo," "Create tree," "Cite source."
- **No "Click here," "Submit," "OK."** These mean nothing.
- **Length: 2–4 words.** Longer = the page is wrong, not the button.
- **Confirmations use the original verb.** If the user clicked "Add a photo,"
  the success message says "Photo added," not "Upload complete."

| ❌ Avoid | ✅ Prefer |
|---|---|
| Submit | Save changes / Add ancestor / Send invite |
| OK | Got it / Continue (with context) |
| Cancel | Cancel / Discard changes / Keep editing |
| Click here to learn more | Read the data model → |
| Yes / No | (the verb itself: Delete William / Keep William) |

---

## Confidence display copy

A confidence number is rendered with **percentage + band label** when there's
room for both; just the band label for chips; the full sentence for tooltips.

| Score | Percentage | Band label | Tooltip |
|---|---|---|---|
| 0.95–1.00 | 95–100% | **Near-certain** | "Direct primary source. Filed at the event by an informed witness." |
| 0.85–0.95 | 85–95% | **Strong** | "Direct evidence with a minor caveat (e.g. informant slightly removed from the event)." |
| 0.70–0.85 | 70–85% | **Good** | "Consistent secondary sources, or one solid derivative." |
| 0.50–0.70 | 50–70% | **Moderate** | "Single secondary source, or indirect inference." |
| 0.30–0.50 | 30–50% | **Weak** | "Uncorroborated late or derivative source." |
| 0.00–0.30 | 0–30% | **Speculative** | "Guess, placeholder, or actively conflicting." |

Pattern in prose: *"We think Richard Maxwell was born around 1796 (**Strong**,
89% — death certificate + 1820 census)."* The confidence chip is hover-clickable
to expand the reasoning.

---

## Date display copy

Per `brand.md` rule 2 (numbers in ranges, not points):

| Source data | UI text |
|---|---|
| `{year_min: 1843, year_max: 1843, date_type: "exact", month: 8, day: 30}` | "30 Aug 1843" |
| `{year_min: 1843, year_max: 1843, date_type: "exact"}` | "1843" |
| `{year_min: 1843, year_max: 1843, date_type: "estimated"}` | "around 1843" |
| `{year_min: 1840, year_max: 1845, date_type: "range"}` | "1840–1845" |
| `{year_min: null, year_max: 1850}` | "before 1850" |
| `{year_min: 1850, year_max: null}` | "after 1850" |
| all null | (render nothing; not "Unknown") |

---

## Conflict-display copy

Two assertions disagreeing — never hide the smaller one.

```
[Higher-confidence value]  •  [Confidence chip]
[Lower-confidence value]   •  [Confidence chip]
Both kept — see sources.
```

Never label one "wrong" or "correct." MAXGEN keeps both.

---

## "Unknown ancestor" copy (the 10-possibilities expander)

```
Collapsed:   "Father — 10 possibilities"  [chip showing best candidate's confidence]
Expanded:    "10 candidate fathers, ranked by confidence:
              1. Joseph Maxwell (1775–1845)  — 0.42  Strong reasoning: …
              2. Thomas Maxwell (1780–1851)  — 0.31  …
              … "
```

Never "Unknown" by itself. Always **"N possibilities"** with the badge.

---

## Living-person privacy copy

```
"This person may be living. Their details are private — sign in as the
person or their tree owner to view."
```

Never show a 404 stack trace for a privacy-gated person. Render this calm
explanation.

---

## AI assistant copy

When an AI agent (Deon, the research agent, the embedding agent, etc.)
contributes an assertion, surface it explicitly:

> "Suggested by Deon (genealogy researcher agent), 2026-05-17. Sources cited
> below. Confidence: 0.65. **Accept** / **Reject** / **Investigate** →"

Never let AI-generated content look indistinguishable from human-cited
content. Always badge + dateline + sources.

---

## What needs to be written next (this doc evolves)

- [ ] Sign-up + sign-in flow copy
- [ ] Photo upload feedback copy
- [ ] GEDCOM import/export feedback
- [ ] Sharing & permissions copy
- [ ] Subscription / billing copy (when we add tiers)
