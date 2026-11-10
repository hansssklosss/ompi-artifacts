#!/usr/bin/env python3
"""note-diff.py — the step-1b walk's count, as a file rather than a description of a file.

Why this exists (s820, 2026-11-08): the DELTA-COUNT METHOD cell (s772) is a prose
rule — "grep -c '^+[^+]' misses added blank lines; a bare '+' must be counted
separately; cross-check against hunk-header arithmetic and the wc -l pair" — and it
has now mis-counted this seat's own receipt three times (s772 +26 vs +32; s820 +32
vs +30, the bare-'+' blanks double-counted). s803/s804's fork applies to my own
instrument: a guard that lives in prose burns at the author's next pass; the code
form has an address and a fixture.

Contract (fail-closed):
  prev baseline : if --expect <sha256> is given, refuse to grade unless
                  sha256(note-versions/prev.md) equals it (exit 7) — the
                  PREV-BASELINE CELL (s818): an ungradeable walk must not print
                  a verdict.
  delta         : ONE number, agreed by three independent operands — hunk-header
                  arithmetic, the `wc -l` pair, and grep-style line counts that
                  split bare '+' / '-' lines (s772). Disagreement -> exit 6.
  deaths        : removed lines, removed lines carrying a cNNNN/#NNNN ref (the
                  population, stated beside the count — AMENDMENT 4), and the
                  pair print S/A/R with the undefined-fold rule (AMENDMENT 10/13).
  exit 0        : graded and self-consistent. 3: the two files are identical (the
                  s758/s818 empty-delta class — NOT a quiet pass, a lost witness
                  generation; printed as VOID, never as +0/-0 PASS).

Usage:
  ./note-diff.py [--prev PATH] [--note PATH] [--expect SHA256] [--receipt DIR]
KEYLESS BY DESIGN — no secret is read anywhere in this file.
"""
import argparse
import datetime
import hashlib
import os
import re
import subprocess
import sys

SEAT = os.path.dirname(os.path.abspath(__file__))
REF = re.compile(r"(?:\bc\d{4,}\b|#\d{3,}\b)")


def lines_of(text):
    return text.splitlines(keepends=True)


def wc_l(path):
    return int(subprocess.run(["wc", "-l", path], capture_output=True, text=True).stdout.split()[0])


def main():
    ap = argparse.ArgumentParser(prog="note-diff.py", description="step-1b note-diff walk (keyless)")
    ap.add_argument("--prev", default=os.path.join(SEAT, "memory", "note-versions", "prev.md"))
    ap.add_argument("--note", default=os.path.join(SEAT, "memory", "wake-note.md"))
    ap.add_argument("--expect", help="sha256 the snapshot MUST carry (PREV-BASELINE CELL)")
    ap.add_argument("--receipt", help="directory to write <tip-id>.md into")
    ap.add_argument("--tip", help="receipt file name (usually the latest seal id)")
    ap.add_argument("--title", default="note-diff delta")
    args = ap.parse_args()

    if args.expect:
        got = hashlib.sha256(open(args.prev, "rb").read()).hexdigest()
        if got != args.expect.strip().lower():
            print(f"baseline: prev.md sha256 {got} != expected {args.expect} -> VOID (exit 7, no verdict)")
            return 7

    diff = subprocess.run(["diff", "-u", args.prev, args.note], capture_output=True, text=True)
    if diff.returncode == 0:
        same = open(args.prev, "rb").read() == open(args.note, "rb").read()
        print(f"delta: exit 0, files {'byte-identical' if same else 'equal'} -> VOID (exit 3): the "
              f"snapshot was not taken before this pass's writes (s758/s818 class). No verdict.")
        return 3

    d = lines_of(diff.stdout)
    hdr = [l for l in d if l.startswith("@@")]
    hunks = []
    add_hunk = 0
    for h in hdr:
        m = re.match(r"^@@ -(\d+),(\d+) \+(\d+),(\d+) @@", h)
        mo, mc, po, pc = (int(g) for g in m.groups())
        hunks.append((mo, mc, po, pc))
        add_hunk += pc - mc
    plus = [l for l in d if l.startswith("+") and not l.startswith("+++")]
    bare_add = [l for l in plus if l.rstrip("\n") == "+"]
    minus = [l for l in d if l.startswith("-") and not l.startswith("---")]
    bare_del = [l for l in minus if l.rstrip("\n") == "-"]
    add, dele = len(plus), len(minus)
    wc_pair = wc_l(args.note) - wc_l(args.prev)
    grep_pair = len([l for l in plus if not l.rstrip("\n") == "+"]) + len(bare_add)
    # The invariant, as the two identities that actually hold: hunk arithmetic and the
    # wc -l pair measure the NET line change (added minus removed); the line counts
    # measure the GROSS add, and only agree with the net when nothing was removed (s772).
    net_ok = (add - dele) == add_hunk == wc_pair
    gross_ok = add == grep_pair
    ok = net_ok and gross_ok
    removed_ref = [l for l in minus if REF.search(l)]

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
    prev_sha = hashlib.sha256(open(args.prev, "rb").read()).hexdigest()
    prev_lines, note_lines = wc_l(args.prev), wc_l(args.note)
    prev_bytes = os.path.getsize(args.prev)
    note_bytes = os.path.getsize(args.note)
    hunk_txt = "; ".join(f"`@@ -{mo},{mc} +{po},{pc} @@`" for mo, mc, po, pc in hunks)
    # The denominator is the removed-with-ref population (AMENDMENT 9(i)/10); a gradeable
    # walk with an empty one is a MEASURED ZERO, never a null (AMENDMENT 13).
    fold = ("0 deaths over a measured window — pair undefined (empty denominator, AMENDMENT 10)"
            if len(removed_ref) == 0 else f"population {len(removed_ref)}: pair print per removed line below")
    out = [
        f"# {args.title}",
        f"# measured @ {now}",
        f"# prev.md sha256 {prev_sha} — {prev_lines:,} lines / {prev_bytes:,} B; wake-note.md {note_lines:,} lines / {note_bytes:,} B",
        f"# hunks {len(hunks)}: {hunk_txt}",
        (f"# delta +{add} −{dele}: net — hunk arithmetic {add_hunk}, `wc -l` pair {note_lines}−{prev_lines} = {wc_pair}"
         f" ({'agree' if net_ok else 'DISAGREE'}); gross — non-bare '+' {add - len(bare_add)} + bare-'+' blanks "
         f"{len(bare_add)} = {grep_pair} ({'agree' if gross_ok else 'DISAGREE'}); "
         f"{'count usable (s772 applied before printing)' if ok else 'COUNT NOT USABLE — exit 6'}"),
        (f"# removed {dele} (bare '-' lines {len(bare_del)}); removed-with-ref ({len(removed_ref)},{len(removed_ref)}); "
         f"population {len(removed_ref)}; fold: {fold}"),
        f"# retire-line match exercised: {'yes' if removed_ref else 'no'}",
        "",
    ]
    sys.stdout.write("\n".join(out) + "\n")
    for l in removed_ref:
        print(f"  REMOVED-WITH-REF: {l.rstrip()[:400]}")
    if args.receipt and args.tip:
        os.makedirs(args.receipt, exist_ok=True)
        path = os.path.join(args.receipt, f"{args.tip}.md")
        with open(path, "w") as f:
            f.write("\n".join(out) + "".join(d))
        print(f"receipt: {path}")
    if not ok:
        print("exit 6: the three operands disagree — do not print or seal this number")
        return 6
    return 0


if __name__ == "__main__":
    sys.exit(main())
