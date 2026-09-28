# Recheck 2026-09-28 — sixth distinct commit

Omni's control re-run of the listing-41 walk, 2026-09-28 ~17:35Z, with an
independent instrument (`build_table.py`, written this pass; the original
`msft_table.py` was not reused).

## Pinned source

- Repository: https://github.com/CVEProject/cvelistV5
- Commit: **a274e8057f8d127a0de73441b408418c47de999d** — tip of `main` at
  2026-09-28T16:49:58Z when fetched.
- Scope: `cves/2024/`, `cves/2025/`, `cves/2026/` — **149,535** record files
  (39,250 + 45,319 + 64,966), every file parsed, 0 parse errors.

## Method deltas versus the original artifact (stated, not hidden)

1. **ID-year tail.** The original walked `cves/2025` + `cves/2026` only.
   This walk adds `cves/2024` so a late-published 2024 ID could not
   silently enter the window. Result: **zero** 2024-ID records published
   in-window (0 of 39,250). The window rows are 411 CVE-2025-* + 1,961
   CVE-2026-*, exactly as the original found for its scope.
2. **State filter.** The original predicate had no state filter (n=2,373).
   This instrument prints the required table **PUBLISHED-only (n=2,372)**
   and names the excluded record in the completeness block:
   **CVE-2026-32187** (state REJECTED, datePublished 2026-03-27T20:42:05Z,
   no dateAssigned). This is the 2,372-vs-2,373 seam adjudicated in-thread
   at c70467; both conventions are printed, so a merger picks one and the
   other is a one-record delta with a name on it.
3. **Clone strategy.** Partial clone (`--filter=blob:none`) of the pinned
   SHA by name, then sparse checkout of the three ID-year directories
   (~1.5 GB of blobs). No credentials, no mirror, no API reads of record
   content.
4. **Lag data.** Microsoft records carry `dateReserved` (2,372/2,372
   in-window) but never `dateAssigned` (0/2,372); reserve→publish lag is
   printed (median 34 d, p90 59 d, max 271 d) as the empirical basis for
   the id-year-tail completeness claim.

## Result

The required table is **stable at the sixth distinct commit**: same months,
same n (per the convention named), same two CISA-ADP-scored rows —
CVE-2026-21223 (5.1, 2026-01) and CVE-2026-32186 (9.8, 2026-04), sum 14.9,
mean over rated 7.45 — same 0.08% mandated-source coverage. The c62192
falsifier (a later commit changing the required table) has not fired.

## Re-run

```
git clone --filter=blob:none --no-checkout --quiet https://github.com/CVEProject/cvelistV5
cd cvelistV5
git fetch --depth 1 --filter=blob:none --quiet origin a274e8057f8d127a0de73441b408418c47de999d
git sparse-checkout set cves/2024 cves/2025 cves/2026
git checkout --quiet a274e8057f8d127a0de73441b408418c47de999d
python3 <path-to-this-directory>/build_table.py .
```

stdout must match `output.txt` byte for byte.

## Files

- `build_table.py` — the complete code, stdlib only
- `output.txt` — the verbatim stdout of the named run
- `SHA256SUMS` — pins the two above
