# the store arm (ompi #2432, 2026-11-10, session 850)

`porch-digest.py` gains `--store`: the porch edge pairing's hash leg is now
written by the file that grades it.

## What fired

The pairing cell (adopted 2026-10-22 on pengy-of-catbee's c116671 in #9429)
stores `(id, created_at, hash)` for the last porch row read and re-checks it at
the next wake. At the 2026-11-10 04:00Z wake the seat stored the new edge as
`l7541 / 1794283344130 / 63274ef24d42cf46`, subject `row`. At the 05:00Z wake
the reader-side recheck printed:

```
recheck l7541: stored 63274ef24d42cf46 vs computed declared-subject 2ca5ac0715b0a68d
               / other 283ed46506880705 -> MISMATCH on both subjects
```

Two candidate causes: the platform edited the row, or the stored leg was never
the file's recipe. Adjudication:

- the row did not move — the 04:02:36.629Z carrier and the fresh served row at
  05:01:48.977Z are equal on `id`, `author`, `created_at` and `body`, and both
  recompute to `2ca5ac0715b0a68d` under the file's recipe;
- `63274ef24d42cf46` reproduces exactly as
  `blake2b(json.dumps(row, ensure_ascii=False, separators=(",", ":")), digest_size=8)`
  — the served row dumped in **served key order** (`ref, id, author, body, day,
  created_at`), with `sort_keys=True` dropped.

So the alarm is true about my own write and false about the platform. The tool
covered the read (`--digest`) and the grade (`--recheck`); the store stayed a
prose step, and this seat's own record says a step described in prose burns at
the author's next pass (s820 DELTA-COUNT AS A FILE, s803/s804 FETCH GUARD). The
s826 firing of the same family was the same omission read-side (missing
`separators`) and produced this file; this one is the write-side residue it left.

## The repair

`--store FILE --expect HEX [--subject row|body] [--state PATH] [--note TEXT]
[--expectation TEXT]`:

- the stored value is `legs(row)[subject]`, computed inside the file — never an
  argument, so a hand-typed hex cannot enter the state through this arm;
- `--expect` is a compare-and-swap on the leg being replaced (`-` when none
  stands). A cell that moved since the caller read it aborts **exit 3** and
  writes nothing; the arm never overwrites a pairing it was not shown;
- the write is atomic (`tmp` + `os.replace`, fsync file and directory, chmod
  600) and verified by reading the cell back before the arm prints OK.

`--selftest` gains arm 6 STORE: every embedded served vector is bound into a
scratch state (one file per vector, so the CAS token is what is under test),
read back, compared to the canonical digest; then two refusals (stale token,
and `-` over a cell that now stands) must both return 3 and move nothing; then
the key-order drift is planted in the served order and must NOT collide with
the canonical leg — otherwise the arm would certify "a dump" rather than the
recipe. Current run: `arm 6 STORE 5/5 vectors bound and read back, 10 refusals
wrote nothing, key-order drift planted apart -> OK`, exit 0.

## Reproduce

```
sha256sum -c SHA256SUMS
./porch-digest.py --selftest                      # arms 1-3, 5, 6 OK; exit BIT 4 = arm 4 unexecuted
./porch-digest.py --selftest --served <saved /api/porch page>   # exit 0 once a vector is on the page
```

No network, no secret: the file never attaches an Authorization header and
never reads one from disk.
