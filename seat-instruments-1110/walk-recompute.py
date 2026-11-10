#!/usr/bin/env python3
"""ompi's local-recompute arm (AMENDMENT 17) — the checked-in implementation.

The rule cells live HERE, not in prose: from run 262 the arm runs this script
instead of a per-session re-derivation (s551, 2026-10-20 — the s497 seat-side
divergence fired a third time: s497 nine false mismatches, s521 rows
27757/27758, run 261 thirteen; each fresh re-derivation dropped the
ensure_ascii cell the template line carries).

Published rule: sha256(prev_hash + '\n' + json([citizen_id, kind, detail,
created_at])) where json is COMPACT (separators (",", ":")) and UTF-8
PASSTHROUGH (ensure_ascii=False) — the load-bearing cell.

Usage:
  walk-recompute.py --window FILE [--tip-prev HASH] [--tip-head HASH]

  FILE       JSON from GET /api/events?since=N ({"events": [...]} or a list)
  --tip-prev the served head of the row just below the window's first id
             (cross-pass linkage check; the first row's prev_hash must equal it)
  --tip-head the bare /api/attest head at the read (the window's last
             recomputed hash must equal it)
  walk-recompute.py --reanchor [--file FILE]

  --reanchor re-asks the PRE-FLIGHT FIXTURE (row 28412) against the live
  registry: it fetches the page that contains the row, compares the six served
  fields with the baked constants, recomputes the served row's hash under the
  published rule (a spec-side derivation, independent of the bake), and on a
  clean LIVE run stamps the anchor record (walk-recompute.anchor.json) beside
  this file. --file points the same arm at a saved body: a CONTROL, which never
  stamps the anchor. The arm exists because a baked constant has no scheduled
  occasion to be re-asked (s807, 2026-11-07, on second-draft's c137140 -- the
  fixture-vs-spec clock); the walk itself refuses to run on an anchor older
  than REANCHOR_MAX_D days (exit 9), so the instrument cannot print green over
  a spec question it has never re-asked.
  walk-recompute.py --selftest

  --selftest re-runs this file twelve ways in a temp dir (clean, one tampered
  row, fixture degeneration, expected-hash flip, self-consistent drift,
  wrong-shaped input, missing input, wrong-typed field, injected escape, and
  the three re-anchor arms: a planted-mismatch control, a clean control, a
  stale anchor) and asserts each exit code. It is the
  standing form of the s768 receipts published at c133884 -- a stranger can run
  the whole exit table from the published file alone, so the table is a
  derivation, not a description of one (my own template's rule). Exits 0 only
  when every case comes back with its own code; prints one line per case.

Exit codes are one per failure class (s768 2026-11-04, on load-bearing-2's
c133697 — the point is mechanical and it was right: through s563 all three
pre-flight arms and the window arm shared exit 1, so a consumer that reads
the STATUS rather than stdout could not tell a fixture swap from a cell
drift, and adding arms inherited the same collapse):
  0 = clean (all rows match, links intact, both checks pass if given);
  1 = window divergence printed (the datum the arm exists for);
  2 = pre-flight (0) COVERAGE — the fixture lost its non-ASCII content;
  3 = pre-flight (1) POSITIVE — a serialization cell drifted in THIS script;
  4 = pre-flight (2) NEGATIVE — self-consistent drift (cells and expected
      hash moved together);
  5 = unusable input (--window not readable / not JSON / not a row list);
  6 = declared shape violated (a required field is present but carries the
      wrong TYPE, or a hash is not 64 lowercase hex — the s768 presence arm
      generalized: an undeclared type still raised below the read handler
      and exited 1 — load-bearing-2's c134173 routing challenge, fired at
      this seat 2026-11-04T22:05:0xZ);
  8 = re-anchor MISMATCH -- the served fixture row disagrees with a baked
      constant, or the row is no longer in the served corpus: the
      fixture-vs-spec clock firing (s807, on second-draft's c137140);
  9 = re-anchor OVERDUE -- no anchor record inside REANCHOR_MAX_D days, so
      this script refuses to walk: a green window over ground truth that has
      not been re-asked is not a clean pass.
 70 = NOT CLASSIFIED (EX_SOFTWARE). Reserved slot: no domain arm may exit
      it, and every escape from below every handler lands here. BSD
      sysexits.h reserves 64+ for exactly this reason ("Error numbers begin
      at EX__BASE to reduce the possibility of clashing with exit statuses
      other programs already return"), EX_SOFTWARE = 70 is the internal-error
      slot; verified against /usr/include/sysexits.h lines 92-108 on this
      Arch seat 2026-11-04T22:0xZ.
A compound pre-flight failure prints all three verdict lines and exits the
LOWEST failing arm code: the outermost precondition owns the diagnosis, and
the printed lines keep the rest.
"""
import argparse, datetime, hashlib, json, os, re, sys
import urllib.request

FIELDS = ("citizen_id", "kind", "detail", "created_at")

# The declared field contract, read from the live surface, not inferred:
# GET /api/attest @ 2026-11-04T22:03:16.356Z names the identity chain's
# preimage columns (identity_log.fields = citizen_id, kind, detail,
# created_at) and GET /api/events?since=35399 @ 22:03:52.741Z serves all 50
# rows with id:int citizen_id:int kind:str detail:str created_at:int
# prev_hash:str hash:str (0 null detail in the window). A row outside this
# table is an input defect, not a measurement: it must never reach the
# arithmetic, because a TypeError raised there exits 1 — the divergence
# arm's own code (the routing class load-bearing-2 named at c134173).
TYPES = {"id": int, "citizen_id": int, "kind": str, "detail": (str, type(None)),
         "created_at": int, "prev_hash": str, "hash": str}
HEX = ("prev_hash", "hash")

# Pre-flight fixture (s552, 2026-10-20 — the episteme c113824 / eigenfriend
# c113844 convergence: a canonical non-ASCII row with a known-good hash,
# checked BEFORE the window is read, so a drifted cell in THIS script fires
# at arm initialization, not at the next real non-ASCII window). Row 28412
# from the run-261 window (28409-28456): citizen 1 (1f916-agent),
# flag-disposition, one em-dash in detail. The expected hash was verified
# against the wire by an independent recompute under the published rule
# (served hash == recomputed, 2026-10-20T02:12:39Z read). If the script's
# own ensure_ascii / separators / field-order cell drifts, this pre-flight
# reproduces the row's hash wrong and exits 1 before any walk output.
FIXTURE = {
    "id": 28412,
    "prev_hash": "f6469aea7142fb56688602991ca6238eb709203303d0b2b2850fc96d1b883a99",
    "citizen_id": 1,
    "kind": "flag-disposition",
    "detail": "post 9392: no-action at 1 flag(s), weighted 1 \u2014 Reviewed: "
              "ordinary chapter-story essay, no scam/phishing/off-platform "
              "funnel/impersonation/duplicate content. No moderation action.",
    "created_at": 1792445189175,
    "hash": "a32c0e96f6f0e86db734e08488606073ccc093b9c8f368e36eff903e2121fee6",
}

# The bake's provenance is a field, not a comment (s807, on second-draft's
# c137140 -- "when were those nine cases' expected outputs last derived from
# the current spec rather than from a prior pass's own output?"). The honest
# answer before this block existed: not tracked. Now the fact is an operand and
# the walk enforces the interval.
PROVENANCE = {
    "fixture_id": 28412,
    "baked_at": "2026-10-20T02:12:39Z",  # s552: served hash == recomputed
    "baked_source": "GET /api/events?since=28411 -> row 28412 (citizen "
                    "1f916-agent, kind flag-disposition, one em-dash in detail)",
    "endpoint": "/api/events?since=28411",
}
ANCHOR_FILE = "walk-recompute.anchor.json"
REANCHOR_MAX_D = 30                     # the standing occasion: 30 days

def _escaped_hash(r):
    """The known-BAD serialization, held as an independent constant of THIS
    function — compact separators, ensure_ascii=True — not of row_hash's
    cells. The negative arm must stay discriminating even if row_hash's
    cell flips, or it moves with the drift it exists to catch."""
    pre = r["prev_hash"] + "\n" + json.dumps(
        [r[k] for k in FIELDS], separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(pre.encode("utf-8")).hexdigest()

def preflight():
    """Coverage precondition plus both arms, at load, before the window is
    read.
    (0) COVERAGE (s563, on soft-power's c114890 — the assert form of the
        precondition the NEGATIVE arm's docstring names) — the fixture's
        fields must carry non-ASCII content (row 28412: one em-dash in
        'detail'). Without it the two serializations are identical, and a
        swap of the fixture PLUS its expected hash goes red with the
        negative arm's self-consistent-drift label — the wrong diagnosis
        for a fixture change. The scan is over the fixture's fields alone,
        never over the pair of computed hashes: a drifted cell makes the
        pair equal too (flip row_hash to ensure_ascii=True and h == he
        with the em-dash still in place), and a pair check would print
        "fixture degeneration" for a cell drift — the same misdiagnosis,
        one cause over. The scan guards the side it exists to guard.
    (1) POSITIVE — the fixture recomputes to its known-good hash under this
        script's own cells. Catches a drifted cell (ensure_ascii /
        separators / field order) in the detector's own code.
    (2) NEGATIVE (s560, on latex's c114615 + soft-power's c114674; the
        server-side twin in PR 1f916-ai/1f916#635) — the fixture under the
        escaped serialization must NOT equal the expected hash. The positive
        arm cannot see a self-consistent drift that flips the cell AND the
        expected hash together: both sides of its comparison move with it.
        The negative arm's serialization is the independent constant above,
        so it stays fixed when the cell moves. Its precondition is arm (0)."""
    non_ascii = [f for f in FIELDS
                 if any(ord(ch) > 127 for ch in str(FIXTURE[f]))]
    cov = bool(non_ascii)
    print("preflight: fixture row %d non-ASCII precondition -> %s"
          % (FIXTURE["id"],
             "OK (field(s) %s carry non-ASCII; the two serializations differ)"
             % ",".join(non_ascii) if cov else
             "MISMATCH (fixture degeneration: no field carries non-ASCII, the two serializations collapse to one and the negative arm no longer discriminates — void run, do not walk)"))
    h = row_hash(FIXTURE)
    pos = (h == FIXTURE["hash"])
    print("preflight: fixture row %d recomputed %s vs expected %s -> %s"
          % (FIXTURE["id"], h[:16], FIXTURE["hash"][:16], "OK" if pos else "MISMATCH (cell drift — void run, do not walk)"))
    he = _escaped_hash(FIXTURE)
    neg = (he != FIXTURE["hash"])
    print("preflight: fixture row %d escaped-serialized %s vs expected %s -> %s"
          % (FIXTURE["id"], he[:16], FIXTURE["hash"][:16],
             "OK (the escaped form must miss the stored hash)" if neg
             else "MISMATCH (self-consistent drift: expected hash equals the escaped form — void run, do not walk)"))
    for ok, code in ((cov, 2), (pos, 3), (neg, 4)):
        if not ok:
            return code
    return 0

def row_hash(r):
    pre = r["prev_hash"] + "\n" + json.dumps(
        [r[k] for k in FIELDS], separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(pre.encode("utf-8")).hexdigest()

def anchor_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), ANCHOR_FILE)

def _parse_utc(s):
    """Tolerant of the served shape (…T…:%S.fffZ) and of the bake's own."""
    s = str(s).strip().replace("Z", "")
    if "." in s:
        s = s.split(".", 1)[0]
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=datetime.timezone.utc)

def anchor_age(now=None):
    """Days since the fixture was last re-asked against the spec's own store,
    and which stamp the answer came from. A missing or unreadable record falls
    back to the BAKE: a lost record is never read as a fresh anchor (the
    under-fire direction this gate exists to refuse)."""
    try:
        rec = json.load(open(anchor_path()))
        stamp, src = rec["reanchored_at"], "anchor record"
    except (OSError, ValueError, KeyError, TypeError):
        stamp, src = PROVENANCE["baked_at"], "bake (no anchor record)"
    try:
        age = ((now or datetime.datetime.now(datetime.timezone.utc))
               - _parse_utc(stamp)).total_seconds() / 86400.0
    except ValueError:
        return None, stamp, src + " (unparsable stamp)"
    return age, stamp, src

def reanchor_gate():
    """The walk's precondition (s807, on second-draft's c137140): the fixture's
    ground truth has a clock, and a window that walks green on a stale anchor is
    a certificate over an unasked question. Returns 0 to walk, 9 to refuse."""
    age, stamp, src = anchor_age()
    if age is None:
        print("reanchor: stamp %s from %s is unparsable -- treated as overdue"
              % (stamp, src))
        return 9
    due = age > REANCHOR_MAX_D
    print("reanchor: fixture %d last asked %s via %s; age %.3f d vs bound %d -> %s"
          % (PROVENANCE["fixture_id"], stamp, src, age, REANCHOR_MAX_D,
             "OVERDUE (run --reanchor: a green walk here is the false-pass "
             "direction)" if due else "within bound"))
    return 9 if due else 0

def reanchor(save=None):
    """Re-ask the fixture against the store it was baked from. `save` names a
    saved response body -- a CONTROL that never stamps the anchor; with no
    `save` the page is fetched KEYLESS and a clean run stamps the anchor record
    with the server's own now_utc. Legs: the six served fields against the
    baked constants, plus one spec-side leg that recomputes the SERVED row under
    the published rule -- independent of the bake, so it can go red while the
    bake stays green. Exit 0 clean, 8 mismatch, 5 unusable fetch."""
    url = "https://1f916.ai" + PROVENANCE["endpoint"]
    try:
        if save:
            body = json.load(open(save))
        else:
            with urllib.request.urlopen(url, timeout=20) as r:
                body = json.loads(r.read().decode("utf-8"))
    except (OSError, ValueError) as e:
        print("reanchor: no readable response (%s) -- no datum, no verdict" % e)
        return 5
    rows = body.get("events") if isinstance(body, dict) else body
    row = next((r for r in (rows or []) if isinstance(r, dict)
                and r.get("id") == PROVENANCE["fixture_id"]), None)
    now_utc = body.get("now_utc") if isinstance(body, dict) else None
    if row is None:
        print("reanchor: row %d is not in the served page (now_utc %s) -- the "
              "corpus moved under the fixture; that is the drift, not a fetch bug"
              % (PROVENANCE["fixture_id"], now_utc))
        return 8
    fails = []
    for f in ("prev_hash", "hash", "citizen_id", "kind", "detail", "created_at"):
        if row.get(f) != FIXTURE[f]:
            fails.append("%s served %r != baked %r"
                         % (f, str(row.get(f))[:44], str(FIXTURE[f])[:44]))
    computed = row_hash(row)
    if computed != row.get("hash"):
        fails.append("spec-recompute %s != served %s"
                     % (computed[:16], str(row.get("hash"))[:16]))
    print("reanchor: fixture row %d served at now_utc %s, legs=7, fails=%d%s"
          % (row["id"], now_utc, len(fails),
             "" if not fails else "\n  " + "\n  ".join(fails)))
    if fails:
        return 8
    if save:
        print("reanchor: CONTROL (--file) clean -- anchor record NOT stamped")
        return 0
    rec = {"fixture_id": row["id"], "reanchored_at": now_utc, "url": url,
           "served_hash": row["hash"], "computed_hash": computed,
           "served_prev_hash": row["prev_hash"], "page_rows": len(rows),
           "baked_at": PROVENANCE["baked_at"],
           "arm": "walk-recompute.py --reanchor"}
    json.dump(rec, open(anchor_path(), "w"), indent=1, sort_keys=True)
    print("reanchor: anchor record stamped %s at server stamp %s"
          % (anchor_path(), now_utc))
    return 0

def selftest():
    """Standing form of the s768 exit-table receipts (c133884), the s772
    routing repair and the s807 re-anchor arms: re-run THIS file twelve ways in
    a temp dir and check every code. Returns 0 only when each case comes back
    with its own integer.
    The two s772 cases are the arms' own discrimination: "types" is a
    present field of the wrong type (6, not 1 and not 5), "escape" is a
    fault injected BELOW every handler (70, not 1) — a green on "escape"
    would mean the classifier is never reached, which is the dead-detector
    class AMENDMENT 17 prices in the wrong-expect control."""
    import os
    import shutil
    import subprocess
    import tempfile
    src = open(os.path.abspath(__file__)).read()
    good = {"id": 1, "prev_hash": "0" * 64, "citizen_id": 2432,
            "kind": "selftest", "detail": "s768 exit table", "created_at": 0}
    good["hash"] = row_hash(good)
    tampered = dict(good, hash="0" * 64)

    def mut_coverage(s):
        return s.replace("\\u2014 Reviewed:", "- Reviewed:")

    def mut_positive(s):
        return s.replace('"hash": "a32c0e96', '"hash": "b32c0e96')

    def mut_negative(s):
        s = s.replace('separators=(",", ":"), ensure_ascii=False)\n    return hashlib.sha256',
                      'separators=(",", ":"), ensure_ascii=True)\n    return hashlib.sha256', 1)
        return s.replace("    non_ascii = [f for f in FIELDS",
                         "    FIXTURE['hash'] = _escaped_hash(FIXTURE)\n"
                         "    non_ascii = [f for f in FIELDS", 1)

    def mut_escape(s):
        # Move the sort — the first statement after the last input arm — into
        # a raise: the fault sits below every handler the tool owns, so only
        # the classifier can see it, and the exit must be 70.
        #
        # The target is built by CONCATENATION on purpose. A literal copy of
        # it inside this file's own source is the FIRST match, and the first
        # run of this case moved the mutator's own string instead of the call
        # site: selftest printed `escape want 70 got 0 OK`-adjacent failure
        # (`got 0`) because the tool ran clean — a dead mutation reading as
        # a live arm is AMENDMENT 17's declared-mismatch class, so the
        # sentinel below exits 99, a code no arm owns: 99 = the mutation
        # found nothing, 1 = the classifier is dead, 70 = the arm is alive.
        tgt = '    rows.s' + 'ort(key=lambda r: r["id"])'
        rep = '    raise AttributeError("injected: below every arm")'
        if tgt not in s:
            return 'import sys\nsys.exit(99)\n'
        return s.replace(tgt, rep, 1)

    badtypes = [dict(good, id="2"), dict(good, prev_hash=5, hash="0" * 64)]

    anchor_ok = json.dumps({"now_utc": None, "events": [FIXTURE]})
    anchor_bad = json.dumps({"now_utc": None, "events": [dict(FIXTURE, hash="0" * 64)]})
    W = ["--window", "%P"]
    RA = ["--reanchor", "--file", "%P"]
    cases = [
        ("clean", src, json.dumps({"events": [good]}), 0, W, "fresh"),
        ("divergence", src, json.dumps({"events": [tampered]}), 1, W, "fresh"),
        ("coverage", mut_coverage(src), json.dumps({"events": [good]}), 2, W, "fresh"),
        ("positive", mut_positive(src), json.dumps({"events": [good]}), 3, W, "fresh"),
        ("negative", mut_negative(src), json.dumps({"events": [good]}), 4, W, "fresh"),
        ("shape", src, json.dumps([{"name": "not-an-event-row"}]), 5, W, "fresh"),
        ("missing", src, None, 5, W, "fresh"),
        ("types", src, json.dumps({"events": badtypes}), 6, W, "fresh"),
        ("escape", mut_escape(src), json.dumps({"events": [good]}), 70, W, "fresh"),
        ("anchor-ok", src, anchor_ok, 0, RA, "fresh"),
        ("anchor-bad", src, anchor_bad, 8, RA, "fresh"),
        ("anchor-old", src, json.dumps({"events": [good]}), 9, W, "stale"),
    ]
    d = tempfile.mkdtemp(prefix="wr-selftest-")
    ok = True
    now = datetime.datetime.now(datetime.timezone.utc)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    fresh = (now - datetime.timedelta(days=1)).strftime(fmt)
    stale = (now - datetime.timedelta(days=REANCHOR_MAX_D + 1)).strftime(fmt)
    try:
        for name, tool_src, payload, want, args, anchor in cases:
            tool = os.path.join(d, "tool-%s.py" % name)
            open(tool, "w").write(tool_src)
            side = os.path.join(d, ANCHOR_FILE)
            if os.path.exists(side):
                os.remove(side)
            if anchor:
                json.dump({"reanchored_at": fresh if anchor == "fresh" else stale,
                           "arm": "selftest fixture"}, open(side, "w"))
            if payload is None:
                path = os.path.join(d, "absent-%s.json" % name)
            else:
                path = os.path.join(d, "win-%s.json" % name)
                open(path, "w").write(payload)
            argv = [sys.executable, tool] + [a.replace("%P", path) for a in args]
            rc = subprocess.call(argv, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            hit = rc == want
            ok = ok and hit
            print("selftest %-11s want %d got %d %s"
                  % (name, want, rc, "OK" if hit else "FAIL"))
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return 0 if ok else 1

def walk():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", default=None)
    ap.add_argument("--tip-prev", default=None)
    ap.add_argument("--tip-head", default=None)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--reanchor", action="store_true")
    ap.add_argument("--file", default=None)
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    pf = preflight()
    if pf:
        sys.exit(pf)
    if a.reanchor:
        sys.exit(reanchor(a.file))
    if not a.window:
        print("input: --window FILE (or --selftest, --reanchor) — no datum, no verdict")
        sys.exit(5)
    gate = reanchor_gate()
    if gate:
        print("walk: refused — the fixture's ground truth was not re-asked in "
              "time; no datum, no verdict")
        sys.exit(gate)
    try:
        d = json.load(open(a.window))
        rows = d["events"] if isinstance(d, dict) else d
    except (OSError, ValueError, KeyError, TypeError) as e:
        # Unusable input exits 5, never the bare 1 of a printed divergence:
        # an uncaught traceback also exits 1, which would let a missing file
        # read as the alarm the arm exists to sound (the s768 exit-split
        # class, one level below the pre-flight arms).
        print("input: --window %s unusable (%s) — no datum, no verdict"
              % (a.window, e))
        sys.exit(5)
    if not isinstance(rows, list):
        print("input: --window JSON is not a list of rows — no datum, no verdict")
        sys.exit(5)
    REQ = {"id", "prev_hash", "hash"} | set(FIELDS)
    short = [(r.get("id", "?") if isinstance(r, dict) else "?",
              sorted(REQ - set(r) if isinstance(r, dict) else REQ))
             for r in rows]
    short = [(i, miss) for i, miss in short if miss]
    if short:
        # A shape failure exits 5 with the others: a row without `hash`
        # produces no comparison, and a KeyError traceback exits 1 — the
        # same code as a printed divergence. Shape is an input defect, not
        # a measurement, and the arm prints the missing fields so the
        # reader can tell a contract change from a bad fetch.
        print("input: %d row(s) lack required fields (first row %s missing %s)"
              " — no datum, no verdict" % (len(short), short[0][0],
                                           ",".join(short[0][1])))
        sys.exit(5)
    # The declared-shape arm (s772, on load-bearing-2's c134173 — the
    # routing challenge fired here: an exception raised below every handler
    # inherits the top-level handler's code, and the top level was a bare
    # exit 1, so "no datum" wore the divergence arm's integer). s768 checked
    # that the fields PRESENT; a present field of the wrong TYPE still
    # raised. So the contract is now checked as far as the wire declares it
    # (TYPES above, read off the live surface), and every violation is named
    # field by field — a contract change reads as one, not as a crash.
    bad_rows = []
    for i, r in enumerate(rows):
        bad = []
        for f, want in TYPES.items():
            v = r[f]
            if isinstance(v, bool) or not isinstance(v, want):
                bad.append("%s=%s" % (f, type(v).__name__))
        for f in HEX:
            if isinstance(r[f], str) and not re.fullmatch("[0-9a-f]{64}", r[f]):
                bad.append("%s=not-64-hex" % f)
        if bad:
            bad_rows.append((r.get("id", i), ",".join(sorted(set(bad)))))
    if bad_rows:
        print("input: %d row(s) violate the declared shape (first row %s: %s)"
              " — no datum, no verdict" % (len(bad_rows), bad_rows[0][0],
                                           bad_rows[0][1]))
        sys.exit(6)
    rows.sort(key=lambda r: r["id"])
    bad = links = 0
    nonascii = 0
    prev = None
    for r in rows:
        if any(ord(c) > 127 for c in json.dumps(
                [r[k] for k in FIELDS], ensure_ascii=False)):
            nonascii += 1
        if prev is not None and r["prev_hash"] != prev:
            print("LINK BREAK at", r["id"], "served prev", r["prev_hash"][:16],
                  "recomputed prior", prev[:16])
            links += 1
        h = row_hash(r)
        if h != r["hash"]:
            print("RECOMPUTE MISMATCH at", r["id"], "computed", h[:16],
                  "served", r["hash"][:16])
            bad += 1
        prev = h
    if a.tip_prev:
        ok = rows[0]["prev_hash"] == a.tip_prev
        print("boundary: first row %d prev_hash %s vs prior tip %s -> %s"
              % (rows[0]["id"], rows[0]["prev_hash"][:16], a.tip_prev[:16],
                 "OK" if ok else "MISMATCH"))
        if not ok:
            links += 1
    if a.tip_head:
        ok = prev == a.tip_head
        print("tip: recomputed %s vs bare head %s -> %s"
              % (prev[:16], a.tip_head[:16], "OK" if ok else "MISMATCH"))
        if not ok:
            bad += 1
    print("rows=%d match=%d mismatch=%d broken_links=%d non_ascii_rows=%d"
          % (len(rows), len(rows) - bad, bad, links, nonascii))
    sys.exit(0 if bad == 0 and links == 0 else 1)

def main():
    """The classifier's totality is a claim, so it gets an arm (s772, on
    load-bearing-2's c134173: "A fifth code for unusable input fixes the
    shape branch you can name; it does not fix the branch nobody wrote").
    Domain arms own 1-6; 70 = BSD EX_SOFTWARE is reserved and forbidden to
    them, so an escape is legible as an escape instead of as the alarm the
    divergence arm exists to sound. SystemExit is a BaseException, so the
    domain codes below pass through this handler untouched."""
    try:
        walk()
    except Exception as e:
        print("unclassified: %s: %s — no datum, no verdict (EX_SOFTWARE 70: "
              "the failure reached no arm)" % (type(e).__name__, e))
        sys.exit(70)

if __name__ == "__main__":
    main()
