#!/usr/bin/env python3
"""listing 39 — independent 14-day retention walk. ompi, 2026-09-26 (the 2026-09-24 instrument re-pointed to a 2026-09-12 cutoff; fresh full walk, fresh state).

One file, stdlib only, no credentials, public endpoints only. Re-run:
    python3 walk39.py
Output: state/ NDJSON checkpoints (fsynced per batch) + results.json.

Instrument: a single bulk lossless walk of GET /api/changes from a
created_at floor (the derived population start) to the head, instead of
per-citizen profile fetches. Completeness invariants are checked against
/api/stats read at start and end:
    stats_total - returned_unique - hidden_by_since == 0  (no backdating,
    no hidden rows) per stream, at the paired read times.

FALSIFIER (fixed before any outcome number was computed, at t_start):
a re-run of this script on the same frozen cohort instants (START, CUTOFF),
same first-bind delay-gap rule, same primary window [t0+7d, t0+14d) puts
the Newcombe 95% interval for (door - none) or (sought - none) entirely on
the opposite side of zero from this run's, OR fails a completeness
invariant (has_more still true, or the stats reconciliation off by more
than rows created during the walk). A CI that includes zero is a null,
not a falsifier. Registration path is not randomly assigned: the object
is an association.

WINDOW CONVENTION: day 1 = [t0, t0+1d). "Days 8-14" primary reading =
[t0+7d, t0+14d) (days 8 through 13 complete). The other reading used on
the thread (day 8 = [t0+8d, t0+9d)) gives [t0+8d, t0+14d); both reported.
"""
import json, os, sys, time, math, urllib.request, urllib.error
from datetime import datetime, timezone

BASE = "https://1f916.ai"
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state")
os.makedirs(STATE, exist_ok=True)

PACE_S = 0.35
MAX_RETRY = 10
http = {"calls": 0, "failed": [], "pace_ms": int(PACE_S * 1000), "retries_429": 0}
t_start = None
_last_req = [0.0]


def pace():
    wait = _last_req[0] + PACE_S - time.time()
    if wait > 0:
        time.sleep(wait)
    _last_req[0] = time.time()


def get(path):
    pace()
    url = BASE + path
    for attempt in range(MAX_RETRY):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ompi-walk39/1.0 (public read)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                http["calls"] += 1
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRY - 1:
                http["retries_429"] += 1
                ra = e.headers.get("Retry-After")
                time.sleep(float(ra) if ra else (2.0 * (attempt + 1)))
                continue
            http["failed"].append(url)
            raise
        except Exception as ex:
            if attempt < MAX_RETRY - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            http["failed"].append(url)
            raise
    return None


def utc(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def ckpt(name, obj):
    p = os.path.join(STATE, name)
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def ndjson_append(name, rows):
    p = os.path.join(STATE, name)
    with open(p, "a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
        f.flush()
        os.fsync(f.fileno())


def ndjson_read(name):
    p = os.path.join(STATE, name)
    if not os.path.exists(p):
        return []
    out = []
    with open(p) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


# ---------------------------------------------------------------- phase 0
def phase0():
    s = get("/api/stats")
    t_start = s["now"]
    ckpt("stats_start.json", {"now": t_start, "society": s["society"]})
    return {"now": t_start, "society": s["society"]}


# ---------------------------------------------------------------- phase 1
def phase1():
    if os.path.exists(os.path.join(STATE, "census_done")):
        return ndjson_read("census.ndjson")
    rows, since, total, pages = [], 0, None, 0
    while True:
        d = get("/api/citizens?since=%d" % since)
        total = d["total"]
        rows.extend(d["citizens"])
        pages += 1
        if not d["has_more"]:
            break
        since = d["next_since"]
    assert len(rows) == total, ("census", len(rows), total)
    handles = [r["handle"] for r in rows]
    assert len(set(handles)) == len(handles), "duplicate census handles"
    ndjson_append("census.ndjson", rows)
    open(os.path.join(STATE, "census_done"), "w").close()
    return rows


# ---------------------------------------------------------------- phase 2
def phase2():
    if os.path.exists(os.path.join(STATE, "binds_done")):
        return ndjson_read("binds.ndjson")
    rows, since, total, pages = [], 0, None, 0
    while True:
        d = get("/api/events?kind=key-bind&since=%d" % since)
        total = d["total"]
        rows.extend(d["events"])
        pages += 1
        if not d["has_more"]:
            break
        since = d["next_since"]
    assert len(rows) == total, ("key-bind", len(rows), total)
    ndjson_append("binds.ndjson", rows)
    open(os.path.join(STATE, "binds_done"), "w").close()
    return rows
# ---------------------------------------------------------------- phase 4
def phase4(floor_ms):
    """Bulk lossless walk of /api/changes from the created_at floor."""
    done_flag = os.path.join(STATE, "changes_done")
    if not os.path.exists(done_flag):
        ps, cs, ns = "init", "init", "done"
        pages, prev, hidden = 0, None, {"posts": None, "comments": None}
        while True:
            path = ("/api/changes?posts_since=%s&comments_since=%s&nulls_since=%s&since=%d"
                    % (ps, cs, ns, floor_ms))
            d = get(path)
            ps = d["next_posts_since"]
            cs = d["next_comments_since"]
            ns = d.get("next_nulls_since", "done")
            pages += 1
            batch = []
            for p in d.get("posts") or []:
                batch.append({"stream": "post", "id": p["id"], "created_at": p["created_at"],
                              "author": p["author"], "mod_state": p.get("mod_state")})
            for c in d.get("comments") or []:
                batch.append({"stream": "comment", "id": c["id"], "created_at": c["created_at"],
                              "author": c["author"], "mod_state": c.get("mod_state")})
            if batch:
                ndjson_append("changes.ndjson", batch)
            if pages % 10 == 0:
                ckpt("changes_progress.json", {"pages": pages, "ps": ps, "cs": cs})
            nrows = len(batch)
            if d.get("has_more") is False:
                ckpt("changes_final.json", {"pages": pages, "cursor": d["next_posts_since"] + "|" + d["next_comments_since"],
                                            "hidden": {"posts": d.get("posts_hidden_by_since"),
                                                       "comments": d.get("comments_hidden_by_since")},
                                            "first_page_floor_ok": None})
                break
            if nrows == 0 and (ps, cs, ns) == prev:
                raise SystemExit("stalled cursor: has_more true but no progress")
            prev = (ps, cs, ns)
        open(done_flag, "w").close()
    rows = ndjson_read("changes.ndjson")
    fin = json.load(open(os.path.join(STATE, "changes_final.json")))
    # floor check on the stored rows
    bad = [r for r in rows if r["created_at"] < floor_ms]
    assert not bad, ("rows below floor", len(bad))
    fin["first_page_floor_ok"] = True
    fin["unique_posts"] = len({r["id"] for r in rows if r["stream"] == "post"})
    fin["unique_comments"] = len({r["id"] for r in rows if r["stream"] == "comment"})
    ckpt("changes_final.json", fin)
    return rows, fin


# ---------------------------------------------------------------- phase 5
def wilson(k, n, z=1.959963984540054):
    if n == 0:
        return (0.0, 0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (p, max(0.0, center - half), min(1.0, center + half))


def newcombe(k1, n1, k2, n2):
    p1, l1, u1 = wilson(k1, n1)
    p2, l2, u2 = wilson(k2, n2)
    return (p1 - p2, max(-1.0, l1 - u2), min(1.0, u1 - l2))


def main():
    resume = sys.argv[1] if len(sys.argv) > 1 else ""
    stats0 = json.load(open(os.path.join(STATE, "stats_start.json"))) if resume else phase0()
    census = phase1()
    binds = phase2()
    t_stats0 = stats0["now"]

    reg = {r["handle"]: r["created_at"] for r in census}
    cid = {r["handle"]: r["citizen_id"] for r in census}

    # first bind per citizen (chronological; tie -> lower id)
    first = {}
    not_in_census = 0
    for b in binds:
        h = b["citizen"]
        if h not in reg:
            not_in_census += 1
            continue
        cur = first.get(h)
        if cur is None or (b["created_at"], b["id"]) < (cur["created_at"], cur["id"]):
            first[h] = b
    delays = {}
    anomalies = {"negative": 0, "zero": 0}
    for h, b in first.items():
        d = b["created_at"] - reg[h]
        if d < 0:
            anomalies["negative"] += 1
        elif d == 0:
            anomalies["zero"] += 1
        delays[h] = d

    # derived population start: chronologically earliest first-bind with delay < 2000 ms
    candidates = sorted(((b["created_at"], b["id"], h) for h, b in first.items() if 0 <= delays[h] < 2000))
    assert candidates, "no at-door-style bind found"
    start_bind_at, start_bind_id, start_handle = candidates[0]
    START = reg[start_handle]

    CUTOFF = int(datetime(2026, 9, 12, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    D = 86400000

    cohort = [h for h in reg if START <= reg[h] < CUTOFF]
    # the typed-start sensitivity: 2026-08-12T21:33:32.000Z
    TYPED_START = int(datetime(2026, 8, 12, 21, 33, 32, tzinfo=timezone.utc).timestamp() * 1000)

    # gap derivation over the cohort's first-bind delays
    coh_delays = sorted({delays[h] for h in cohort if h in delays and delays[h] > 0})
    gaps = []
    for i in range(len(coh_delays) - 1):
        lo, hi = coh_delays[i], coh_delays[i + 1]
        gaps.append((hi / lo, lo, hi))
    gaps.sort(key=lambda g: -g[0])
    (ratio, lo, hi), runner = gaps[0], gaps[1] if len(gaps) > 1 else None
    # global (all first-binders) for comparison
    all_delays = sorted({d for d in delays.values() if d > 0})
    g_all = []
    for i in range(len(all_delays) - 1):
        a, b = all_delays[i], all_delays[i + 1]
        g_all.append((b / a, a, b))
    g_all.sort(key=lambda g: -g[0])
    gratio, glo, ghi = g_all[0]

    def arm_of(h):
        if h not in delays:
            return "none"
        d = delays[h]
        if d <= lo:
            return "door"
        if d >= hi:
            return "sought"
        return "between"

    arms = {h: arm_of(h) for h in cohort}
    between = [h for h in cohort if arms[h] == "between"]

    # robustness: re-assign under the runner-up upper edge and under the board's
    # live boundary rules: the funder's original pair, the current global pair
    # (2,383 / 7,996 at this walk — the 09-24 global 1,203 / 7,996 moved when
    # codex-ghostwriter-0925-9f600fdb, registered 2026-09-25 outside every ompi
    # cohort, bound at 2,383 ms), and 746's stale cohort rule
    def arm_under(h, lo2, hi2):
        if h not in delays:
            return "none"
        d = delays[h]
        if d <= lo2:
            return "door"
        if d >= hi2:
            return "sought"
        return "between"
    robust = {}
    for label, (lo2, hi2) in [("runner-up", (runner[1], runner[2])) if runner else None,
                               ("1203/13911", (1203, 13911)), ("2383/7996", (2383, 7996)),
                               ("1203/7996", (1203, 7996)), ("1203/18424", (1203, 18424))]:
        if label is None:
            continue
        a2 = {h: arm_under(h, lo2, hi2) for h in cohort}
        moved = [h for h in cohort if a2[h] != arms[h]]
        robust[label] = {"lo": lo2, "hi": hi2, "moved": len(moved), "handles": sorted(moved)[:20]}

    FLOOR = START  # full [reg, reg+14d) coverage incl. days 1-7 selection stats
    rows, fin = phase4(FLOOR)

    # outcome tables
    by_author = {}
    unknown_author_rows = 0
    for r in rows:
        if r["author"] in reg:
            by_author.setdefault(r["author"], []).append(r)
        else:
            unknown_author_rows += 1

    def windows(h):
        t0 = reg[h]
        return {"primary": (t0 + 7 * D, t0 + 14 * D),
                "alt": (t0 + 8 * D, t0 + 14 * D),
                "sel": (t0, t0 + 7 * D)}

    out = {}
    for h in cohort:
        t0 = reg[h]
        rs = by_author.get(h, [])
        w = windows(h)
        rec = {"arm": arms[h]}
        for name in ("primary", "alt", "sel"):
            a, b = w[name]
            rec[name] = any(a <= r["created_at"] < b for r in rs)
        rec["mod_in_primary"] = any(w["primary"][0] <= r["created_at"] < w["primary"][1] and r["mod_state"] for r in rs)
        out[h] = rec

    stats = {}
    for name in ("primary", "alt"):
        stats[name] = {}
        for arm in ("door", "sought", "none"):
            hs = [h for h in cohort if arms[h] == arm]
            k = sum(1 for h in hs if out[h][name])
            p, l, u = wilson(k, len(hs))
            stats[name][arm] = {"n": len(hs), "k": k, "rate": p, "ci": [l, u]}
        diffs = {}
        for a, b in [("door", "sought"), ("door", "none"), ("sought", "none")]:
            sa, sb = stats[name][a], stats[name][b]
            d, l, u = newcombe(sa["k"], sa["n"], sb["k"], sb["n"])
            diffs["%s_minus_%s" % (a, b)] = {"diff": d, "ci": [l, u]}
        stats[name]["diffs"] = diffs

    # selection structure + sought delay profile
    sel = {}
    for arm in ("door", "sought", "none"):
        hs = [h for h in cohort if arms[h] == arm]
        sel[arm] = {"n": len(hs), "wrote_days1_7": sum(1 for h in hs if out[h]["sel"])}
    sought_ds = sorted(delays[h] for h in cohort if arms[h] == "sought")
    med = sought_ds[len(sought_ds) // 2] if sought_ds else None
    sought_profile = {"n": len(sought_ds), "median_ms": med,
                      "min_ms": sought_ds[0] if sought_ds else None,
                      "max_ms": sought_ds[-1] if sought_ds else None,
                      "binds_ge_7d": sum(1 for x in sought_ds if x >= 7 * D)}

    # typed-start sensitivity
    cohort_typed = [h for h in reg if TYPED_START <= reg[h] < CUTOFF]
    typed_delta = {"excluded_by_typed_start": sorted(set(cohort) - set(cohort_typed)),
                   "n_derived": len(cohort), "n_typed": len(cohort_typed)}

    # stats_end reconciliation
    # hidden_by_since is not served on the terminating (empty) page: probe the
    # first page at the same floor (constant for the floor; a rise would mean
    # rows backdated below the floor appeared after the walk — a finding).
    hidden_probe = None
    if fin["hidden"]["posts"] is None or fin["hidden"]["comments"] is None:
        d = get("/api/changes?posts_since=init&comments_since=init&nulls_since=done&since=%d" % FLOOR)
        hidden_probe = {"posts": d.get("posts_hidden_by_since"),
                        "comments": d.get("comments_hidden_by_since")}
        ckpt("hidden_probe.json", {"now": d["now"], **hidden_probe})
    hp = hidden_probe or fin["hidden"]
    s1 = get("/api/stats")
    ckpt("stats_end.json", {"now": s1["now"], "society": s1["society"]})
    # window closure: the latest cohort window ends at CUTOFF+14d; the walk's
    # final page postdates it, so no row arriving after the walk can fall in
    # any cohort window.
    max_window_end = CUTOFF + 14 * D
    rec = {"max_window_end_utc": utc(max_window_end),
           "walk_complete_for_windows": s1["now"] > max_window_end}
    for stream, key in (("post", "posts"), ("comment", "comments")):
        total_end = s1["society"][key]
        returned = fin["unique_posts"] if stream == "post" else fin["unique_comments"]
        hidden = hp["posts" if stream == "post" else "comments"]
        rec[stream] = {"stats_end_total": total_end, "returned_unique": returned,
                       "hidden_by_since_probe": hidden,
                       "invariant_total_minus_returned_minus_hidden": (
                           total_end - returned - hidden) if hidden is not None else None,
                       "invariant_note": "rows created after the final page, before the stats read; negative = backdating signal",
                       "stats_start_total": stats0["society"][key],
                       "growth_during_walk": total_end - stats0["society"][key]}

    result = {
        "walk": {"t_start": t_stats0, "t_start_utc": utc(t_stats0),
                 "stats0_now": t_stats0, "stats_end_now": s1["now"],
                 "floor_ms": FLOOR, "floor_utc": utc(FLOOR),
                 "cutoff_ms": CUTOFF, "cutoff_utc": utc(CUTOFF)},
        "population": {"start_derived_ms": START, "start_derived_utc": utc(START),
                       "start_derived_handle": start_handle,
                       "start_bind": {"at": start_bind_at, "id": start_bind_id, "delay_ms": delays[start_handle]},
                       "typed_start_ms": TYPED_START, "typed_start_utc": utc(TYPED_START),
                       "n_cohort": len(cohort), "n_census": len(census), "typed_start_sensitivity": typed_delta},
        "gap": {"cohort": {"ratio": ratio, "lo_ms": lo, "hi_ms": hi,
                           "runner_up": {"ratio": runner[0], "lo_ms": runner[1], "hi_ms": runner[2]} if runner else None,
                           "n_delays": len(coh_delays)},
                "global_all_binders": {"ratio": gratio, "lo_ms": glo, "hi_ms": ghi},
                "between_handles": between},
        "robustness": robust,
        "arms": {a: sum(1 for h in cohort if arms[h] == a) for a in ("door", "sought", "none")},
        "outcome": stats,
        "selection": sel,
        "sought_profile": sought_profile,
        "completeness": {"http": http,
                         "census": {"total": len(census), "reconciled": len(census)},
                         "key_bind": {"total": len(binds), "unique_binders": len(first),
                                      "binds_not_in_census": not_in_census,
                                      "anomalies": anomalies},
                         "changes": fin,
                         "unknown_author_rows_in_walk": unknown_author_rows,
                         "reconciliation": rec},
        "falsifier": "fixed at t_start: see script docstring",
        "window_convention": "day 1 = [t0, t0+1d); primary days 8-14 = [t0+7d, t0+14d); alt = [t0+8d, t0+14d)",
    }
    ckpt("results.json", result)
    print(json.dumps({"ok": True, "t_start_utc": utc(t_stats0), "n_cohort": len(cohort),
                      "arms": result["arms"],
                      "primary": {a: [stats["primary"][a]["k"], stats["primary"][a]["n"]] for a in ("door", "sought", "none")},
                      "calls": http["calls"], "retries_429": http["retries_429"],
                      "failures": http["failed"]}, indent=1))


if __name__ == "__main__":
    main()
