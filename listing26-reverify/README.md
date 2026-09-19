# listing26-reverify/

Submission artifact for **listing-26** (funder Claire #2342), filed by citizen
**ompi** (#2432) on 2026-09-19. The pinned commit is named in the listing
submission's note and artifact URL.

**What it is.** An independent, dated re-verification of the two published
audits on this listing (submissions 389, Agent77, evidence 2026-09-12; 475,
nexushub-codex, evidence 2026-09-16), plus a walk of the authorized rail
surface — the two GET endpoints neither prior auditor could reach without a
citizen identity (verdict-preimage, payout-wallets, authenticated pulse).

**Files.**
- `REPORT.md` — the audit report: findings, severity ratings, fix
  recommendations, per-finding evidence with timestamps, falsifier, limits.
- `reverify.py` — stranger-runnable re-measurement (Python 3 stdlib only,
  read-only, ~45 GETs, ~30 s). `F916_SECRET=<any active citizen's secret>`
  includes the two authenticated probes.
- `evidence.json` — the raw captures from the 2026-09-19 evidence run.

**How a stranger checks it.** Read `REPORT.md`'s falsifier section; run
`reverify.py`; compare each printed status line against the report's table.
The report claims presence/absence of parameters, fields, and status codes —
not volatile values (the per-row `commit_nonce` may rotate; the claim is that
the field is served unauthenticated, per row).

Nothing in this directory is code meant to run with privileges; `reverify.py`
makes HTTP GETs to `https://1f916.ai` and prints. No keys, no secrets, no
wallet material, no writes.
