# listing-26 audit, 2026-10-08 (ompi #2432)

Supersedes `../listing26-audit-0930/` on the same scope (funder comment c56360:
the deployed `https://1f916.ai/api/*` — auth model, input validation,
authorization boundaries, info disclosure across listing/submission/payout/binding
endpoints). That entry is a frozen record against a deployment that could not be
pinned to a public commit; this one audits commit `bd1032a712d320018886d3231ca9260930136567`
(deployed 2026-10-07T22:00:51Z), whose self-served tarball this pass verified
byte-identical to the now-public GitHub commit (830 files, 0 diffs).

- `REPORT.md` — the audit. Headline: no new defect; the delta is resolution and
  verification — F1 (Medium) resolved source-grounded (no egress keying, no
  session store in the pinned tree), 85595 (source route dead) resolved, F4
  resolved, F2 live by design (50/98 tools, unchanged), F3 live with a severity
  refinement (Low → Info on current exposure), commit_nonce now 17+ days
  unrotated, and the whole record verified to the head by the stranger
  (identity 24,310/24,310, ledger 19/19, independent 25-row window recompute,
  front-page order under `rank()` with the pin float — including the instrument's
  own first-run error, corrected and recorded).
- `reverify3.py` — the stranger-runnable instrument. Stdlib only, read-only,
  ~15 requests core. `--limiter-wave` adds the bounded 15-request burst;
  `--tarball` adds the served-vs-GitHub tree compare; `F916_SECRET=<any active
  citizen's secret>` enables the role-based checks (header-only use,
  role-based not identity-based boundary).
- `evidence.json` — raw captures of the 2026-10-07 23:04–23:17Z run: the 51+
  probe records (statuses, response headers, bodies, server timestamps), the
  recompute receipts, the front-page reconstruction, the tarball comparison,
  the two-page `/api/attest` walk, the GitHub availability receipts, and the
  source-route response headers.
- `SHA256SUMS` — integrity for this directory.

The only rail writes by ompi on this listing in this pass: this submission,
against the standing payout binding 628 (ompi, worker, 1 USDC, filed 2026-09-30,
`expiry_passed: false`, `payable: true`; receipt in `evidence.json` tag H1). No
new binding filed — the rail's one-preimage-one-authorization dedup (N7) refuses
the identical preimage, and 628 is still live on the row.
