# Onboarding Flow — New User

**Status:** Foundation draft (Batch 1a, task 1). Wireframes are low-fi text
mockups; the visual designer translates these into pixels later.

A new user lands on OpenGenealogyAI from a search result, a friend's share
link, or marketing. The first 5 minutes decide whether they come back. Goal:
get them to **see one ancestor + one photo + one confidence chip** before they
abandon. That is the "aha" moment for this product.

Honors `brand.md` (archivist voice, never breathless), `microcopy.md`
(verb-first CTAs, specific copy), and `a11y.md` (every step keyboard-navigable).

---

## The 4-step flow

```
[Landing] → [Sign up] → [Welcome — Path choice] → [First ancestor] → [First photo or first parent]
                                                                  ↓
                                                          [Dashboard with 1 person]
```

Time budget: ≤ 5 minutes from landing to first "aha."

---

## Step 0 — Landing (logged out)

Existing marketing page. Two CTAs:

```
┌──────────────────────────────────────────────────────────────┐
│  OpenGenealogyAI                                Sign in     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│    Find ancestors. Honestly.                                 │
│                                                              │
│    Genealogy that shows every fact's confidence,             │
│    every source it came from, and every other possibility    │
│    the evidence allows.                                      │
│                                                              │
│    [  Get started — free  ]   [  See how it works  ]         │
│                                                              │
│    Free tier: 1 tree, public-domain records, photo links.    │
│    Paid tier: unlimited photos stored on our servers,        │
│    private trees, DNA tools. $X/mo.                          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

Both CTAs are equal weight (gold, large). "Get started — free" goes to
sign-up; "See how it works" scrolls to a 90-second explainer below.

**A11y:** skip-to-content link first; h1 = "Find ancestors. Honestly."

---

## Step 1 — Sign up

```
┌──────────────────────────────────────────────────────────────┐
│  Create your account                                         │
│                                                              │
│  Name *                                                      │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  Email *                                                     │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  Password *  (12+ characters)                                │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  [  Create account  ]                                        │
│                                                              │
│  By creating an account you agree to our Terms (CC0 for the  │
│  open standard) and Privacy (we never sell your data).       │
│                                                              │
│  Already have one?  Sign in →                                │
└──────────────────────────────────────────────────────────────┘
```

- Three fields, no more. We do NOT ask for: phone number, birthday, "how did
  you hear about us," surname interest, marketing opt-in. Each extra field
  drops sign-up completion ~5-10%.
- Password rule: 12+ chars. Show strength meter, no other restrictions.
- "Verb-first CTA": "Create account" not "Submit."
- Privacy / Terms linked, not modal-trapped.

**Error states** (per `microcopy.md`):
- Email taken: "An account already uses that email. **Sign in instead →** or
  **reset your password →**"
- Weak password: "Password needs at least 12 characters. Mixing letters,
  numbers, and symbols makes it stronger."

---

## Step 2 — Welcome (path choice)

Three paths, one short screen:

```
┌──────────────────────────────────────────────────────────────┐
│  Welcome, Garlon.                                            │
│                                                              │
│  Where would you like to start?                              │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────┐ │
│  │ ▦ Start a tree   │  │ ⇪ Import GEDCOM  │  │ ⊕ Search   │ │
│  │                  │  │                  │  │   records  │ │
│  │ Add ancestors    │  │ Have a file from │  │ Look around │ │
│  │ one at a time.   │  │ Ancestry or      │  │ first; add  │ │
│  │ Best if you're   │  │ another tool?    │  │ a tree later│ │
│  │ starting fresh.  │  │ Bring it in.     │  │             │ │
│  │                  │  │                  │  │             │ │
│  │ Recommended for  │  │ Available in v1. │  │             │ │
│  │ first-time users │  │                  │  │             │ │
│  └──────────────────┘  └──────────────────┘  └────────────┘ │
│                                                              │
│  Skip for now →                                              │
└──────────────────────────────────────────────────────────────┘
```

- Three cards, ordered by what we think most users want first.
- "Start a tree" recommended (default focus). Big card, prominent verb.
- "Import GEDCOM" gated on Batch 5 task 42 being shipped. Until then, show
  this card with "Coming soon" badge and disable the click.
- "Skip for now" → goes straight to dashboard with empty state.
- Picking any of the three drops the user into Step 3 with the appropriate
  context. "Start a tree" → Step 3a. "Import GEDCOM" → Step 3b.

---

## Step 3a — First ancestor (chose "Start a tree")

```
┌──────────────────────────────────────────────────────────────┐
│  ← Back                            Step 1 of 2               │
│                                                              │
│  Who would you like to add first?                            │
│                                                              │
│  You can start with yourself or with a known ancestor. Either│
│  way, you can add more people, photos, and records later.    │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                  │
│  │ Add yourself     │  │ Add an ancestor  │                  │
│  │                  │  │                  │                  │
│  │ Anchor your tree │  │ A grandparent,   │                  │
│  │ to you.          │  │ great-grandfather│                  │
│  │                  │  │ — anyone you can │                  │
│  │ Your details     │  │ name.            │                  │
│  │ stay private.    │  │                  │                  │
│  └──────────────────┘  └──────────────────┘                  │
└──────────────────────────────────────────────────────────────┘
```

Then a single-screen form:

```
┌──────────────────────────────────────────────────────────────┐
│  ← Back                            Step 2 of 2               │
│                                                              │
│  Tell us about this person.                                  │
│                                                              │
│  Given name(s)                                               │
│  ┌──────────────────────────┐                                │
│  │  Horace William          │                                │
│  └──────────────────────────┘                                │
│                                                              │
│  Surname                                                     │
│  ┌──────────────────────────┐                                │
│  │  Maxwell                 │                                │
│  └──────────────────────────┘                                │
│                                                              │
│  Born — approximate is fine                                  │
│  ┌──────────┐  to  ┌──────────┐                              │
│  │  1898    │      │  1898    │      (leave blank if unsure) │
│  └──────────┘      └──────────┘                              │
│                                                              │
│  Born where? (free text — we'll resolve places later)        │
│  ┌──────────────────────────────────────────┐                │
│  │  Glendale, Utah                          │                │
│  └──────────────────────────────────────────┘                │
│                                                              │
│  Still living?  ○ Yes   ● No                                 │
│                                                              │
│  [  Add to tree  ]                                           │
│                                                              │
│  No need to be precise. Every fact you add carries its own   │
│  confidence; you can refine later.                           │
└──────────────────────────────────────────────────────────────┘
```

Five fields, all optional except given+surname. The range-style date input
*teaches* the user that this product takes ranges (key brand value); they
won't be confused later when fan-chart segments shows ranges.

**On submit:** the person is created with confidence 0.85 (self-reported,
strong but not verified), redirected to the person's profile page (Step 4).

---

## Step 3b — Import GEDCOM (chose "Import GEDCOM")

Deferred until Batch 5 task 42. Until then, show "Coming soon" and bounce to
3a.

---

## Step 4 — First photo OR first parent (the "aha")

The person's profile page, with two **prominent prompts** in empty-state
positions:

```
┌──────────────────────────────────────────────────────────────┐
│  Horace William Maxwell                                      │
│  1898 – 1898   ✦ Strong  (85%)                               │
│  Glendale, Utah                                              │
│                                                              │
│  ┌──── Facts ── Family ── Photos ── DNA ── Sources ────────┐ │
│                                                              │
│  ◉  Add a photo of Horace →                                  │
│  ◉  Add Horace's parents →                                   │
│  ◉  Search records for Horace →                              │
│                                                              │
│  Each step here is what makes a tree real. A face. A         │
│  generation back. A source citation.                         │
└──────────────────────────────────────────────────────────────┘
```

The three CTAs are equal weight, ordered by emotional payoff (photo first —
the "aha" moment per `brand.md`). Each is a single click that opens the right
sub-flow (photo upload modal, add-parent form, search prefilled with the
person's details).

**On adding a photo:** the photo replaces the silhouette in the hero, the
confirmation reads (per `microcopy.md`):
> "Photo added — set as primary. **Undo →**"

That moment — seeing the face in the card — is what we're optimizing the
entire onboarding flow for. Everything before is in service of it.

---

## Step 5 — Dashboard (post-onboarding)

The user lands on `/dashboard` with one person, one photo, and a friendly
prompt for the next step:

```
┌──────────────────────────────────────────────────────────────┐
│  Your trees                                                  │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ ▦ Maxwell line                                          │ │
│  │   1 person  •  1 photo                                  │ │
│  │   [PHOTO]   Horace William Maxwell                      │ │
│  │             1898 – 1898  •  Glendale, Utah              │ │
│  │                                                         │ │
│  │   Next:  Add Horace's father →                          │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  Leads to investigate                                        │
│  (Once you add a generation, we'll suggest possibilities)    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

The "Next" prompt is contextual — the system picks the highest-value next step
based on what's missing.

---

## Drop-off recovery

For users who abandon mid-flow, send a single follow-up email 24 hours later
(no more — we are not a spam shop):

> Subject: Your tree at OpenGenealogyAI
>
> You started a tree but didn't finish. It's still here when you want to come
> back. **Continue your tree →**
>
> If you'd rather we forget your account, **delete it here** — no questions
> asked.

That's the entire email funnel. No drip campaigns.

---

## Accessibility notes

- Every step has clear progress indication ("Step 2 of 2").
- Back link is always present and goes one step back, not to the dashboard.
- Form errors appear next to fields (per `a11y.md`), and the live region
  announces them.
- Skip-to-content link first; h1 matches the visible page title; tab order
  matches visual order.

---

## Open questions for refinement

- [ ] **Free tier vs paid tier** split at sign-up — show pricing during
      onboarding, or post-onboarding? (Three-brain candidate.)
- [ ] **Verify email** — gate the tree creation on email verification, or
      let them play first and verify later?
- [ ] **Sample tree** — offer to populate with the Lincoln demo so the user
      can see what a populated tree looks like before committing their own
      data?
- [ ] **Mobile-first onboarding** — the screens above assume desktop. Mobile
      layouts may want fewer optional fields per screen.
