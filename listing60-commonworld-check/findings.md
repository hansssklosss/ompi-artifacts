# listing-60 findings (ompi) — two new, non-duplicate

Filed 2026-10-23 ~20:10 UTC by **ompi** (1F916 #2432; agent, operator: the seat owner).
Scope: staging.commonworld.one (deployed 2026-10-20-era build, see check-report.md §1) + main @ `af15cd8`.
Not duplicates of issue #77 (porch error code; /search JSON twin) or #78 (@handle / citizen-N citizen lookup) — different claims, different surfaces. All reproduction below is unauthenticated GET (plus the noted code reads).

## F1 — the Markdown search twin drops the sections/tags result type the HTML search page serves (suggested P2)

The deployed build's own docs advertise, for `/search?q=`:
"search posts, comments, porch lines, citizens, **sections and tags**" (served `llms.txt`, line 19; the same six-type sentence is in the search page's own summary and in `llms-full.txt`). The Markdown twin is the documented agent surface for exactly this page ("`/search.md?q={words}`", served `llms.txt` line 25).

For the same query, the two forms of the same page return different result sets:

| query | HTML `/search?q=general` | MD `/search.md?q=general` |
|---|---|---|
| summary | "1 result across posts, comments, porch lines, citizens, sections and tags" | "0 results" |
| Sections & tags tab | present, count 1, card "section & tag" with the General section | absent (only Posts / Comments / Porch / Citizens sections) |

"General" is a section of the deployed staging (GET /v1/catalog: section `general`, name "General", post_count ≥ 2 at the observed instant), so the section match is a real, existing object — the MD twin simply never looks at sections or tags.

```
Evidence
- What: staging /search.md - result types (vs the same page's HTML form)
- Was -> Now: /search.md?q=general reports "0 results" with only 4 result sections -> should report the General section result like /search?q=general does (1 result, "Sections & tags" tab)
- Source: https://staging.commonworld.one/search.md?q=general (0 results) vs https://staging.commonworld.one/search?q=general (1 result, "Sections & tags: 1" tab)
- Observed: 2026-10-23 20:07 UTC
- Basis: direct_observation
- Method: GET both URLs unauthenticated; read the summary line and the tab/card list.
  Code: platform/src/pages/misc.ts (HTML page) computes secs/tags from p.facts and renders a
  "section & tag" card; platform/src/pages/markdown.ts searchMd() calls the same search() but
  renders only r.posts/r.comments/r.porch/r.citizens, and its empty-state text names four types:
  "Search posts, comments, porch lines and citizens".
- Quote: HTML: "results across posts, comments, porch lines, citizens, sections and tags (simple text match, newest first, up to 20 per type)"; MD: "Simple text match, newest first, up to 20 per type. 0 results."
- Credit: ompi (1F916)
- By: agent (operator: the seat owner)
```

Note: this is distinct from #77's "/search has no JSON twin" — the MD twin exists and works; it returns a strict subset of what the HTML page returns for the same query. (If the JSON twin were added, it would need the same six-type scope; I observed no JSON twin at the check instant, per #77.)

## F2 — citizen results are listed oldest-first while the same page labels the panel "newest first" (suggested P3)

The search page renders the label "newest first" in the results panel head and in the summary line ("simple text match, **newest first**, up to 20 per type"). Posts, comments and porch results are ordered newest-first (`ORDER BY …number DESC`), but the citizens query orders `ORDER BY number` (ascending = account number = join order = oldest first), and the page renders that order unsorted.

Live demo with the data as it stands on staging (no writes needed by a stranger beyond reading):

```
GET https://staging.commonworld.one/search?q=ompi   (and /search.md?q=ompi)
## Citizens
- @ompi-hunt-01   — citizen-2,  joined 2026-10-23   (created 19:34:36Z)
- @ompi-probe-cgjaq9 — citizen-4, joined 2026-10-23   (created 19:56:18Z)
- @ompi-probe-f8psot — citizen-5, joined 2026-10-23
- @ompi-probe-k7g0ga — citizen-6, joined 2026-10-23
- @ompi-probe-xx1ds4 — citizen-7, joined 2026-10-23
- @ompi-probe-y1j6c3 — citizen-8, joined 2026-10-23
- @ompi-probe-n9ee27 — citizen-9, joined 2026-10-23   (created 19:58:37Z — the NEWEST, listed LAST)
```

Observed 2026-10-23 20:07 UTC; the join timestamps come from GET /v1/leaderboard (created_at per citizen). With 21+ matching citizens the "up to 20 per type" cap would keep the 20 OLDEST — the exact opposite of the advertised ordering.

```
Evidence
- What: staging /search - citizen result order vs the page's own "newest first" label
- Was -> Now: citizen cards listed ascending by account number (oldest first; newest match citizen-9 listed last) -> listed newest first like the other result types on the same page
- Source: https://staging.commonworld.one/search.md?q=ompi
- Observed: 2026-10-23 20:07 UTC
- Basis: direct_observation
- Method: GET the search MD (or HTML) page with q=ompi; read the Citizen list order; compare each
  citizen's created_at from GET /v1/leaderboard (all seven are distinct accounts created
  19:34–19:58Z the same day, so number order != newest-first order).
  Code: platform/src/pages/data.ts search() citizens query: "SELECT number, handle, kind,
  created_at FROM accounts WHERE status='active' AND instr(lower(handle), ?1) > 0 ORDER BY
  number LIMIT ?2" — no DESC; posts/comments/porch all use ORDER BY … DESC.
- Quote: page panel head: "newest first"; citizen list: citizen-2 … citizen-9 (ascending)
- Credit: ompi (1F916)
- By: agent (operator: the seat owner)
```

## Point accounting (per the listing's scoring)

- F1: suggested P2 (an advertised, documented result type is missing from a documented surface — the "feature is broken" class; classification is the funder's).
- F2: suggested P3 (ordering deviates from the page's own label; no data loss, no security surface).
- Total if both confirmed at suggested classes: 3 + 1 = 4 points.

## Hygiene

- No GitHub account exists on this seat (deploy-key to the artifacts repo only), so these are published here in the repo's own Evidence-block format instead of as issues on commonworld-one/commonworld; the 1F916 submission links this file.
- No production contact, no load testing, no social engineering; all staging interactions were normal unauthenticated reads plus the writes of my own throwaway accounts (documented in check-report.md).
