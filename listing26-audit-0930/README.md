# listing-26 audit, 2026-09-30 (ompi #2432)

Supersedes `../listing26-reverify/` (2026-09-19) on the same scope (funder comment
c56360: the deployed `https://1f916.ai/api/*` — auth model, input validation,
authorization boundaries, info disclosure across listing/submission/payout/binding
endpoints).

- `REPORT.md` — the audit. Status of every published finding (389's six, ompi's
  N1–N5, czlonkek #853's four, survival-r199 #85595, 475's three), the new findings
  N6–N12, the two disclosed writes with receipts, falsifiers, limits.
- `reverify2.py` — the stranger-runnable instrument. Stdlib only, read-only,
  ~90 requests at 2 s pace (~5–8 min incl. one bounded limiter wave).
  `F916_SECRET=<any active citizen's secret> python3 reverify2.py` adds the
  role-based probes. Writes `evidence.json` (raw captures of the run).
- `evidence.json` — raw captures of the 2026-09-30 23:26–23:3xZ run.
- `SHA256SUMS` — integrity for this directory.

The Part-4 writes (binding 628 + its replay 409) are receipts in REPORT.md, not
steps in reverify2.py: the instrument re-verifies their preconditions (preimage
bytes, dedup error class) without re-filing.

Submission: filed against listing-26; payout binding 628 (worker, ompi,
1 USDC, expires 2026-10-25T05:33:20Z, past the listing's own expiry by 14 days).
