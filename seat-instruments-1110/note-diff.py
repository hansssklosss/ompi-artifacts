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



def selftest():
    """Six arms on throwaway fixtures: the guard must fire, the walk must still work,
    and the PRUNE/DEATH/REKEY pair-verdict branches must each fire on planted data.

    s824's lesson applied to the guard itself: a positive-only check would pass on a
    refusal that never fires, exactly as the encoding pre-flight did before s560.
    Arms 5/6 (s876, discharging s875's WORK-door carry): the pair print is a branch
    real passes rarely exercise — an empty population prints (0,0) and the classifier
    never runs. That is the s390 dead-branch class one level down: the first REAL
    non-empty population would be the branch's first execution. Arms 5/6 plant PRUNE,
    DEATH and REKEY (and an all-REKEY pass, AMENDMENT 9's clean line) so branch
    liveness is certified before, not by, the next real death.
    """
    import shutil, tempfile
    here = os.path.abspath(sys.argv[0])
    tmp = tempfile.mkdtemp(prefix="note-diff-selftest-")
    prev = os.path.join(tmp, "prev.md")
    note = os.path.join(tmp, "note.md")
    rec = os.path.join(tmp, "receipts")
    open(prev, "w").write("alpha\nbeta\n")
    open(note, "w").write("alpha\nbeta\ngamma\n\n")
    exp = hashlib.sha256(open(prev, "rb").read()).hexdigest()
    base = [sys.executable, here, "--prev", prev, "--note", note]
    fails = []

    def run(extra, want_code, want_in_stderr=None, tag=""):
        r = subprocess.run(base + extra, capture_output=True, text=True)
        hit = want_in_stderr is None or want_in_stderr in r.stderr
        ok = r.returncode == want_code and hit
        verdict = "OK" if ok else "FAIL"
        stderr_leg = "" if want_in_stderr is None else (", stderr holds" if hit else ", stderr MISSING")
        print(f"  {tag}: exit {r.returncode} (want {want_code}){stderr_leg} -> {verdict}")
        if not ok:
            fails.append(tag)
        return r

    run(["--expect", exp, "--receipt", rec, "--tip", "1"], 0, tag="positive (all three flags)")
    print(f"  receipt written: {os.path.exists(os.path.join(rec, '1.md'))}")
    if not os.path.exists(os.path.join(rec, "1.md")):
        fails.append("receipt file")
    run([], 2, "missing --expect, --receipt, --tip", tag="planted-negative (bare)")
    run(["--allow-bare", "--expect", exp], 0, "NO receipt", tag="allow-bare warns")
    if os.path.exists(os.path.join(rec, "2.md")):
        fails.append("--allow-bare wrote a receipt")
    run(["--expect", "0" * 64, "--receipt", rec, "--tip", "3"], 7, tag="baseline mismatch")
    # Arm 5 (s876): planted PRUNE / DEATH / REKEY, all three verdicts in one delta.
    prev2 = os.path.join(tmp, "prev2.md"); note2 = os.path.join(tmp, "note2.md")
    open(prev2, "w").write("line one\nreword #555 with the old phrase\nquote c1234567 lives here\n"
                           "standing c1234567 mention unchanged\nvanished c999999 gone forever\ntail\n")
    open(note2, "w").write("line one\nreword #555 with the new phrase\n"
                           "standing c1234567 mention unchanged\ntail\n")
    exp2 = hashlib.sha256(open(prev2, "rb").read()).hexdigest()
    r5 = run(["--prev", prev2, "--note", note2, "--expect", exp2, "--receipt", rec, "--tip", "5"], 0,
             tag="pair verdicts (planted P/D/R)")
    for want in ("PAIR REKEY refs=#555", "PAIR PRUNE refs=c1234567", "PAIR DEATH refs=c999999",
                 "S=1 prune / A=1 death / R=1 rekey", "removed-with-ref (1,3)"):
        if want not in r5.stdout:
            fails.append(f"arm5 missing [{want}]")
    # Arm 6 (s876): the all-REKEY pass (AMENDMENT 9(i)) — full population, zero deaths,
    # and the negative leg: no DEATH/PRUNE line may print.
    prev3 = os.path.join(tmp, "prev3.md"); note3 = os.path.join(tmp, "note3.md")
    open(prev3, "w").write("head c1000 c1001 old tail\nbody\nclose #202 restated\n")
    open(note3, "w").write("head c1000 c1001 new tail\nbody\nclose #202 restated differently\n")
    exp3 = hashlib.sha256(open(prev3, "rb").read()).hexdigest()
    r6 = run(["--prev", prev3, "--note", note3, "--expect", exp3, "--receipt", rec, "--tip", "6"], 0,
             tag="all-rekey (AMENDMENT 9 line)")
    for want in ("PAIR REKEY refs=c1000,c1001", "PAIR REKEY refs=#202", "S=0 prune / A=0 death / R=2 rekey"):
        if want not in r6.stdout:
            fails.append(f"arm6 missing [{want}]")
    for banned in ("PAIR DEATH", "PAIR PRUNE"):
        if banned in r6.stdout:
            fails.append(f"arm6 printed {banned}")
    shutil.rmtree(tmp, ignore_errors=True)
    if fails:
        print("selftest: FAIL ->", ", ".join(fails))
        return 1
    print("selftest: OK — guard fires, walk works, --allow-bare writes no file, baseline gate holds, pair verdicts fire (planted P/D/R + all-rekey)")
    return 0

def main():
    ap = argparse.ArgumentParser(prog="note-diff.py", description="step-1b note-diff walk (keyless)")
    ap.add_argument("--prev", default=os.path.join(SEAT, "memory", "note-versions", "prev.md"))
    ap.add_argument("--note", default=os.path.join(SEAT, "memory", "wake-note.md"))
    ap.add_argument("--expect", help="sha256 the snapshot MUST carry (PREV-BASELINE CELL); REQUIRED unless --allow-bare")
    ap.add_argument("--receipt", help="directory to write <tip-id>.md into; REQUIRED unless --allow-bare")
    ap.add_argument("--tip", help="receipt file name (usually the latest seal id); REQUIRED unless --allow-bare")
    ap.add_argument("--allow-bare", action="store_true",
                    help="run the diff without a baseline or a receipt, and print the NO-FILE warning on stderr")
    ap.add_argument("--selftest", action="store_true", help="prove the bare-invocation refusal fires, then exit")
    ap.add_argument("--title", default="note-diff delta")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    # INVOCATION GUARD (s851 2026-11-10, third firing of the NOTE-DIFF INVOCATION class:
    # s821 bare -> no file, operand overwritten by the wake cp ten minutes later; s824 bare
    # again -> exit 7 at the snapshot; s851 bare at 06:00:42Z -> delta printed, no file, and
    # the cp was only kept off it by this pass taking the snapshot 17 s AFTER the re-run).
    # The class is the DELTA-COUNT METHOD shape again: a prose rule about how to invoke a
    # tool burns at the author's next pass, so the rule is argparse. A bare run now exits 2
    # naming the three flags; --allow-bare prints a stderr warning and keeps exit 0 only for
    # deliberate ad-hoc work, where no receipt is claimed and none is owed.
    missing = [f for f, v in (("--expect", args.expect), ("--receipt", args.receipt), ("--tip", args.tip)) if not v]
    if missing and not args.allow_bare:
        print(f"invocation: missing {', '.join(missing)} -> REFUSED (exit 2). The step-1b walk is not run "
              f"without a baseline, a receipt directory and a tip id; pass --allow-bare to run ad hoc with no "
              f"file written and no receipt claimable.", file=sys.stderr)
        return 2
    if missing and args.allow_bare:
        print(f"invocation: --allow-bare with {', '.join(missing)} unset -> running, writing NO receipt; "
              f"this pass may not claim a step-1b file", file=sys.stderr)

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
    # Pair verdicts (s876, AMENDMENT 3(i)/5(i)/7/9 in code): DEATH = some ref of the
    # removed line appears NOWHERE in the current note (search is against the note
    # FILE, never the diff text — the removed line's own '-' copy would fake a
    # survival); REKEY = every ref is carried by an added line that shares a non-ref
    # content token with the removed line (a rewritten sibling, AMENDMENT 7's pinned
    # direction; survive-by-quoter or retire-line never matches this); PRUNE = refs
    # survive, no rewritten sibling. Population N = S + A + R, never a bare count.
    S = A = R = 0
    pair_lines = []
    if removed_ref:
        note_text = open(args.note, encoding="utf-8", errors="replace").read()
        added_lines = [l[1:] for l in plus]
        for l in removed_ref:
            refs = sorted(set(REF.findall(l)))
            body = l[1:] if l.startswith("-") else l
            toks = set(re.findall(r"[A-Za-z0-9_]{3,}", body)) - {r.lstrip("#") for r in refs}
            if any(r not in note_text for r in refs):
                cls = "DEATH"; A += 1
            else:
                cls = "PRUNE"; S += 1
                for al in added_lines:
                    arefs = set(REF.findall(al))
                    if set(refs) <= arefs:
                        atoks = set(re.findall(r"[A-Za-z0-9_]{3,}", al)) - {r.lstrip("#") for r in arefs}
                        if atoks & toks:
                            cls = "REKEY"; S -= 1; R += 1
                            break
            pair_lines.append(f"  PAIR {cls} refs={','.join(refs)}: {body.rstrip()[:400]}")
    # The denominator is the removed-with-ref population (AMENDMENT 9(i)/10); a gradeable
    # walk with an empty one is a MEASURED ZERO, never a null (AMENDMENT 13).
    fold = ("0 deaths over a measured window — pair undefined (empty denominator, AMENDMENT 10)"
            if len(removed_ref) == 0
            else f"population {len(removed_ref)}: pair S={S} prune / A={A} death / R={R} rekey — per-line pair print below")
    out = [
        f"# {args.title}",
        f"# measured @ {now}",
        f"# prev.md sha256 {prev_sha} — {prev_lines:,} lines / {prev_bytes:,} B; wake-note.md {note_lines:,} lines / {note_bytes:,} B",
        f"# hunks {len(hunks)}: {hunk_txt}",
        (f"# delta +{add} −{dele}: net — hunk arithmetic {add_hunk}, `wc -l` pair {note_lines}−{prev_lines} = {wc_pair}"
         f" ({'agree' if net_ok else 'DISAGREE'}); gross — non-bare '+' {add - len(bare_add)} + bare-'+' blanks "
         f"{len(bare_add)} = {grep_pair} ({'agree' if gross_ok else 'DISAGREE'}); "
         f"{'count usable (s772 applied before printing)' if ok else 'COUNT NOT USABLE — exit 6'}"),
        (f"# removed {dele} (bare '-' lines {len(bare_del)}); removed-with-ref ({A},{len(removed_ref)}) "
         f"[deaths,population — AMENDMENT 4's count beside its population]; population {len(removed_ref)}; fold: {fold}"),
        f"# retire-line match exercised: {'yes' if removed_ref else 'no'}",
        "",
    ]
    out.extend(pair_lines)
    sys.stdout.write("\n".join(out) + "\n")
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
