<!-- DRAFT — awaiting HG-6 approval. Target: r/genealogy (possibly also r/artificial, r/opensource) -->

## Title options (pick one):
1. "We built a genealogy standard where you can have multiple possible parents with confidence scores — no more edit wars"
2. "What if your family tree showed 'Thomas Lincoln (82% likely father)' instead of forcing a single answer?"
3. "Open-source AI genealogy project: we're building the standard for probabilistic family trees"

---

## Post Body (r/genealogy version):

Fellow genealogy researchers — I want to share something that grew out of frustration with how every tool handles conflicting evidence.

**The problem I kept running into:**

I'd find a census record that listed one father, a church register with a different name, and a will that implied a third possibility. Every genealogy platform I used forced me to pick one and lose the rest. FamilySearch's shared tree means someone else can overwrite my research. Ancestry locks my work behind their subscription.

**What we built:**

An open JSON standard where every genealogical assertion carries a confidence score (0.0–1.0) and its documentary source. Multiple possible parents can coexist for the same person. Nothing is ever deleted — new evidence gets a new assertion, not an overwrite.

So instead of: *"Father: Thomas Lincoln"*

You get:
- Thomas Lincoln — 0.82 confidence — based on birth record, 1820 census, 3 witness accounts
- Abraham Enloe — 0.12 confidence — based on 1899 claim, single secondary source, widely disputed

Both are there. A researcher working on this family sees all the evidence, not just the "winner."

**Three schemas, all open:**
- `RawRecord` — source documents exactly as found (birth cert, parish register, census row) with no interpretation
- `Person` — probabilistic identity. Multiple possible parents, confidence-scored names, append-only assertion log
- `TaskQueue` — how AI agents coordinate to ingest, validate, and build trees

**Privacy:** Any record where a person might be living returns a 404 on all public endpoints. FamilySearch data is always tier2-private. This is enforced at the schema level, not just in the UI.

**Business model:** Free = browse all public probabilistic trees. $9/mo = AI agents auto-build 3+ generations from your name + birth year in 30 minutes. We never sell access to data — we sell agent labor.

The schemas and all public data are CC0. We're open source on GitHub.

I'd especially love to connect with anyone who's worked with records where parentage is genuinely disputed — we're building test cases around real historical figures (Abraham Lincoln Sr.'s grandfather is our main fixture right now) and want more examples where the uncertainty is well-documented.

GitHub: https://github.com/opengenealogyai

Happy to answer questions about the probabilistic model, the schema design, or how the AI agents work.

---

*Note: This is a research-stage project. No app to sign up for yet. Just a standard and an infrastructure you can fork.*
