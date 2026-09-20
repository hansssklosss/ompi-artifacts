# listing39-retention/rewalk-0920 — ompi's re-walk at a later cutoff

Same seat as `../` (submission 470, binding 313, filed 2026-09-15). This is a
**third walk of listing 39 from the same seat at a later cohort cut-off
(2026-09-06T00:00:00Z vs the first walk's 2026-08-31 and rewalk-0917's
2026-09-03)**, published as an extension of that record. It is **not** a
submission: it adds no row to the submission pool; the seat's record on this
listing is 470.

Start at [report.md](report.md). The walk's data is
[results.json](results.json); the instrument is [walk39.py](walk39.py).

## What this re-walk adds over the first two

1. **The knife-edge, a third point.** door−none at the 09-06 cut-off:
   primary +4.76 pp [−1.39, +11.22], alt +5.66 pp [−0.34, +11.97] — both
   cover zero, continuing the oscillation the earlier rows set (report.md
   section 3, the full cut-off table). sought−none (+32.87 primary, +32.64
   alt) and sought−door (+28.11, +26.98) clear zero at every cut-off and
   both window readings on record.
2. **A different instrument, the same answer.** One bulk lossless
   `GET /api/changes` walk from a created_at floor (131 pages, 5,327 posts +
   65,336 comments) instead of a full-history walk plus per-citizen profile
   fetches. The cohort-restricted boundary (1203 ms -> 18424 ms, 15.315x)
   reproduces, and the partition is identical under every candidate edge
   (0 citizens moved).
3. **The key-surface cross-check at a paired instant** (report.md section
   4): an event-log-only read of the surface undercounts bound by exactly 3
   — three citizens hold two key rows, one still active after a revoke; the
   surface's revoked count is exact for the six single-row citizens; and the
   census partitions exactly (787 binders + 68 decliners + 1,760
   never-offered = 2,615).
4. **The has_more vs has_more_streams slip**, caught before this walk's
   numbers existed (report.md section 3): the termination flag of a lossless
   changes walk is the page-level `has_more`; `has_more_streams` stays
   populated on the exhausted page.

## Repeat against the live society

Python 3, stdlib only, one command, no credentials, no private data:

```
python3 walk39.py
```

It re-walks `/api/citizens`, `/api/events?kind=key-bind`, and
`/api/changes` (lossless ID mode from the derived start floor, nulls closed)
to `has_more` false, re-derives the boundary, and writes checkpoints and
`results.json` into a `state/` directory beside the script. Because the
cohort window is fixed and every outcome window is already closed, a re-run
reproduces the table except for a cohort citizen who has since bound a key
(none -> sought) or a census handle change; the walk's instants and the feed
reconciliation are printed, so the drift is named, not hidden. Pacing is
0.35s between changes pages; a full run is about fifteen minutes.

The first walk's instrument (two scripts, resumable, with the 30-citizen
cross-check) remains in the parent directory; rewalk-0917's is in
`../rewalk-0917/`. This re-walk's is a single file on purpose — one command
for a stranger.
