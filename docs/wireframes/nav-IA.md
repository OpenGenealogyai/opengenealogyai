# Navigation & Information Architecture

**Status:** Foundation draft (Batch 1a, task 2). The sitemap that every other
view honors.

This doc answers: where does a feature *live* on the site? When does a thing
become a tab vs a page vs a modal? What's the route shape? When ambiguous, we
re-read this.

---

## Top-level sitemap

```
/                                marketing landing (logged out)
                                  → dashboard (logged in)

/auth/sign-up                     account creation
/auth/sign-in                     sign in
/auth/sign-out                    sign out (POST)
/auth/reset                       password reset

/dashboard                        logged-in home: trees, photos, leads, activity

/search                           live semantic search (existing route)
/search?q=...                     results page

/trees                            list of user's trees
/tree/<tree-id>                   tree view (default = pedigree)
/tree/<tree-id>/pedigree          pedigree explicitly
/tree/<tree-id>/fan               fan chart
/tree/<tree-id>/descendant        descendant chart
/tree/<tree-id>/hourglass         hourglass chart
/tree/<tree-id>/group-sheet/<person-id>   family group sheet
/tree/<tree-id>/map               migration / place map
/tree/<tree-id>/timeline          tree-wide timeline
/tree/<tree-id>/leads             ancestor leads queued for verification

/person/<person-id>               person profile (universal entry point)
/person/<person-id>/facts         → tab on profile
/person/<person-id>/family        → tab
/person/<person-id>/photos        → tab
/person/<person-id>/dna           → tab (if user has DNA permission)
/person/<person-id>/sources       → tab

/photos                           media library across all trees
/photos/<photo-id>                lightbox view
/photos/upload                    photo upload entry

/documents                        document (MaxRecord) library
/documents/<record-id>            single document detail

/dna                              DNA dashboard (if any kits linked)
/dna/<dna-id>                     specific kit + matches

/community                        public directory (contributors, shared trees)

/account                          settings: profile, password, subscription
/account/billing                  subscription + payment (paying tier)
/account/api-keys                 personal API keys (advanced users)

/dev/tokens                       color/typography tokens demo (Batch 1c)
/dev/colors                       color swatches + contrast (Batch 1c)
/dev/components                   Storybook-lite for all <maxgen-…> (Batch 1b)

/api/v1/...                       JSON API (mirrors page routes)
```

---

## Page vs tab vs modal vs panel — the rules

Decision rule for new UI:

| If the user… | Use a… |
|---|---|
| Navigates to a distinct concept (a person, a tree, the dashboard) | **Page** with its own URL |
| Switches between facets of the *same* concept (a person's facts vs photos) | **Tab** within the page |
| Opens a focused detail without losing context (a photo, a source) | **Lightbox / modal** |
| Reviews supplementary data alongside primary content (event details next to timeline) | **Side panel** |
| Performs a quick action that doesn't deserve its own page (rename tree, change permissions) | **Dialog** |
| Receives transient feedback (saved, error) | **Toast** with `aria-live` |

### Tabs

Tabs are for **facets of one thing**, never for unrelated nav. A person page
has tabs (Facts / Family / Photos / DNA / Sources) because they're all aspects
of one person. A dashboard does NOT have tabs for Trees / Photos / Documents —
those are separate top-level pages.

### Modals

Modals only for:
- Confirmations of destructive actions (per `microcopy.md` confirmation pattern)
- Quick add forms (add a fact, add a source) when staying on the current view matters
- Lightboxes for media

Modals must:
- Trap focus while open
- Return focus on close
- Close on Esc
- Have an explicit close button (X)
- Render `<dialog>` semantics or equivalent ARIA

---

## Sidebar (logged-in chrome — left rail, 220px)

Top-level nav, persistent on every logged-in page:

```
┌─────────────────────────────┐
│  OpenGenealogyAI            │  ← brand + tagline
│  Portal                     │
├─────────────────────────────┤
│  ⊕ Search Records           │  /search
│  ▦ Dashboard                │  /dashboard
│  ❖ My Trees                 │  /trees
│       └─ Maxwell line       │   (recent / pinned tree)
│  📷 Photos                  │  /photos
│  📜 Documents               │  /documents
│  🧬 DNA                     │  /dna
│  👥 Community               │  /community
│                              │
│  ○ Account                  │  /account
│  ↗ Upgrade Plan             │  /account/billing
├─────────────────────────────┤
│  Signed in as Garlon        │  ← footer
│  Sign out                   │
└─────────────────────────────┘
```

Notes:
- Order = frequency-of-use (research first; account last).
- Active item gets a gold left border + lighter background (current portal pattern).
- "My Trees" is expandable to show the user's trees (most-recent 3 listed inline; rest under "See all").
- Mobile (< 700px): sidebar collapses behind a hamburger; bottom-bar shows the 4 most-used items.

---

## Topbar (every logged-in page)

```
┌────────────────────────────────────────────────────────────────────┐
│  [Page title]                                Garlon · Account · Sign out │
└────────────────────────────────────────────────────────────────────┘
```

- Page title on the left
- User name + Account link + Sign out on the right
- Sticky on scroll (current portal pattern; keep it)

---

## Logged-out chrome

Simpler. No sidebar. A header with: logo, "Sign in," "Get started." Marketing
copy is the main content. Same Georgia + gold treatment so logged-out and
logged-in feel like one product.

---

## Person profile — the most-visited page

```
┌──────────────────────────────────────────────────────────────────┐
│  ← Back to tree                                                  │
│                                                                  │
│  [PHOTO]    William Bailey Maxwell                               │
│  (200x200)  1821 – 1895   ✦ Strong  (89%)                        │
│             Shawneetown, IL → Mesa, AZ                           │
│             Father: Richard Maxwell  •  Mother: Ruthey Hodge      │
│                                                                  │
│  ┌──── Facts ──── Family ──── Photos ──── DNA ──── Sources ───┐ │
│  │                                                              │ │
│  │  (tab content here)                                          │ │
│  │                                                              │ │
│  └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

The hero has the **primary photo** (or silhouette fallback), name, dates,
overall confidence chip, and the two most-recent parent assertions inline.
Tabs underneath. Mobile: hero stacks vertically, tabs scroll horizontally.

---

## Tree view — the second-most-visited page

Default view = **pedigree chart**. Switcher at top right:

```
┌──────────────────────────────────────────────────────────────────┐
│  Maxwell Line — 1,247 people  •  back to 8th gen                 │
│                                                                  │
│  [ Pedigree  Fan  Descendant  Hourglass  Group Sheet  Map  Timeline ] │
│                                                                  │
│  (chart canvas — pan, zoom, click)                               │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

The chart switcher is a segmented control (not tabs — tabs are for facets of
one entity, the tree has facets at this level). URL updates as the user
switches so the view is shareable.

---

## Dashboard — the logged-in landing

Three rails stacked:

1. **Your trees** — cards with photo strips + last activity
2. **Leads to investigate** — possibilities the system surfaced (uses the
   10-possibilities expander pattern)
3. **Recent activity** — sources added, photos uploaded, matches confirmed

CTAs at top: **Create tree** / **Import GEDCOM** / **Connect DNA kit**.

---

## URL conventions

- **UUIDs in URLs** for canonical entity references (`/person/8a3f-…`). They
  are stable and shareable.
- **Slugs in optional `?q=` for human readability** when relevant (search).
- **Query params for view state** (e.g. `/tree/abc?gen=8&zoom=1.4`). Lets
  users share a specific view.
- **Trailing slashes: no.** `/person/abc`, not `/person/abc/`.
- **Action verbs as path suffixes when read-only doesn't fit**:
  `/person/<id>/merge?into=<other-id>` for a merge UI invocation.

---

## What this doc does NOT cover (deferred)

- **API endpoints** beyond the trivial mirror — the JSON API spec is a
  separate doc when Batch 5 starts.
- **Detailed wireframes** of each page — those go in
  `docs/wireframes/<page-name>.md` as we build them. This doc is the map.
- **Permissions / roles** — Gramps Web has 4 roles; we'll lift the model when
  collaborative editing arrives. Defer.
