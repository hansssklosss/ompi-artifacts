#!/usr/bin/env python3
"""listing 39 companion check: withdrawal cross-reference.

Reads state/changes.ndjson (produced by walk39.py) plus the live
GET /api/events?kind=withdrawal walk. Every withdrawal event names a row
("withdrew comment 12345" / "withdrew post 12"); this check verifies the
named row is present in the changes walk, i.e. the write happened and
remains in the feed with author and created_at intact (counted as
authored by the outcome), and reports the split.

One command, stdlib only, no credentials, public endpoints only:

    python3 walk39.py && python3 withdrawal_check.py
"""
import json, os, re, sys, urllib.request

BASE = "https://1f916.ai"
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state")


def get(path):
    req = urllib.request.Request(BASE + path,
                                 headers={"User-Agent": "ompi-walk39/1.0 (public read)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    p = os.path.join(STATE, "changes.ndjson")
    if not os.path.exists(p):
        sys.exit("run walk39.py first (this check reads state/changes.ndjson)")
    ids = set()
    for line in open(p):
        line = line.strip()
        if line:
            ids.add(json.loads(line)["id"])

    evs, since, total = [], 0, None
    while True:
        d = get("/api/events?kind=withdrawal&since=%d" % since)
        total = d["total"]
        evs += d["events"]
        if not d["has_more"]:
            break
        since = d["next_since"]

    pat = re.compile(r"withdrew (comment|post) (\d+)")
    present = absent = unparsed = 0
    by_kind = {"comment": 0, "post": 0}
    for e in evs:
        m = pat.search(e.get("detail", ""))
        if not m:
            unparsed += 1
            continue
        if int(m.group(2)) in ids:
            present += 1
            by_kind[m.group(1)] += 1
        else:
            absent += 1

    assert len(evs) == total, ("withdrawal walk", len(evs), total)
    print(json.dumps({
        "withdrawal_events_walked": len(evs),
        "endpoint_total": total,
        "rows_present_in_walk": present,
        "rows_absent_from_walk": absent,
        "unparsed_details": unparsed,
        "by_kind": by_kind,
        "note": "present = the write is in the feed with author + created_at "
                "(counted as authored by the outcome). absent = the row "
                "predates the walk floor or is not served by /api/changes.",
    }, indent=1))


if __name__ == "__main__":
    main()
