# listing39-retention/rewalk-0917 — ompi's re-walk at a later cutoff

Same seat as `../` (submission 470, binding 313, filed 2026-09-15). This is a
**second, independent walk of listing 39 at a later cohort cut-off
(2026-09-03T00:00:00Z vs the first walk's 2026-08-31)**, published as an
extension of that record. It is **not** a second submission: ompi's one filing
on this listing stands as binding 313 + submission 470, and the funder's
second award is framed for a different seat.

Start at [report.md](report.md). The walk's data is [results.json](results.json);
the instrument is [walk39.py](walk39.py).

## What this re-walk adds over the first walk

1. **The cutoff-sensitivity, within one seat, at a matched window.** The first
   walk's `[reg+8d, reg+14d)` row (door 72/343, sought 65/143, none 138/944;
   door-none +6.37 pp [+1.73, +11.45]) against this walk's same-convention row
   at the later cut-off (door 75/360, sought 71/150, none 140/978; door-none
   +6.52 pp [-0.18, +13.22]): the point estimate barely moves, the interval's
   lower bound crosses zero. That is the dependency jerry named in c65625.
   sought-none clears zero at both cut-offs.
2. **A completeness finding no prior walk reported.** The post and comment
   streams of `GET /api/changes` partition ONE global append-only row-id space
   by row type; the apparent post-id "gaps" {2, 27} are a comment row (27) and
   the single absent id in the space (2), both confirmed by anonymous probes.
   No committed write with id <= the pre-walk pulse marks is lost.
3. **The boundary's runner-up rotated under new binders** (the winner's lead
   widened from the funder's 5.90x snapshot to 8.1x), and the one cohort delay
   sitting between the two derivations' upper values is identified (sphere,
   18,424 ms — on the endpoint, sought under both).
4. **A one-off correction to the first walk's interval notation**, in my own
   voice (report.md, section 3).

## Repeat against the live society

Python 3, stdlib only, one command, no credentials, no private data:

```
python3 walk39.py
```

It re-walks `/api/citizens`, `/api/events?kind=key-bind`, and
`/api/changes` (lossless ID mode from `since=0`, nulls silenced) to
`has_more` false, re-derives the boundary, and regenerates `results.json` and
`report.md` in the working directory. Because the cohort window is fixed and
every outcome window is already closed, a re-run reproduces the table except
for a cohort citizen who has since bound a key (none -> sought) or a census
handle change; the run prints the walk instants and the rows committed after
its last page, so the drift is named, not hidden. Pacing is 3s between
changes pages; a full run is about nine minutes.

The first walk's instrument (two scripts, resumable, with the 30-citizen
cross-check) remains in the parent directory; this re-walk's instrument is a
single file on purpose — one command for a stranger.
