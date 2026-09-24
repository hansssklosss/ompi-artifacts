#!/usr/bin/env python3
"""Internal control (scratch, not committed): recompute submission 760's published
cohort from this walk's state/ raws, at 760's own boundary rule (1,203 / 13,911 ms).

760 published: n=1,646; arms door 414 / sought 169 / none 1,063;
primary [t0+7d, t0+14d) retained door 91 / sought 82 / none 171.

Reads state/census.ndjson, state/binds.ndjson, state/changes.ndjson (all
fsynced by walk39.py). Stdlib only.
"""
import json, os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state")
D = 86400000

# 760's cohort: derived START (identical on every ompi walk) to 09-08 cut-off
START = 1755022411925  # placeholder, replaced below from census+binds like walk39.py
CUTOFF_760 = int(datetime(2026, 9, 8, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
LO, HI = 1203, 13911  # 760's own rule = funder's original


def ndjson(name):
    out = []
    for line in open(os.path.join(STATE, name)):
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


census = ndjson("census.ndjson")
binds = ndjson("binds.ndjson")
rows = ndjson("changes.ndjson")

reg = {r["handle"]: r["created_at"] for r in census}

first = {}
for b in binds:
    h = b["citizen"]
    if h not in reg:
        continue
    cur = first.get(h)
    if cur is None or (b["created_at"], b["id"]) < (cur["created_at"], cur["id"]):
        first[h] = b

delays = {h: b["created_at"] - reg[h] for h, b in first.items()}

# derived START: chronologically earliest first-bind with delay < 2000 ms
cands = sorted(((b["created_at"], b["id"], h) for h, b in first.items()
                if 0 <= delays[h] < 2000))
start_bind_at, start_bind_id, start_handle = cands[0]
START = reg[start_handle]

cohort = [h for h in reg if START <= reg[h] < CUTOFF_760]

def arm_of(h):
    if h not in delays:
        return "none"
    d = delays[h]
    if d <= LO:
        return "door"
    if d >= HI:
        return "sought"
    return "between"

arms = {h: arm_of(h) for h in cohort}

by_author = {}
for r in rows:
    by_author.setdefault(r["author"], []).append(r["created_at"])

primary = {}
between = []
for h in cohort:
    a = arms[h]
    if a == "between":
        between.append(h)
        continue
    t0 = reg[h]
    ks = by_author.get(h, [])
    ret = any(t0 + 7 * D <= t < t0 + 14 * D for t in ks)
    primary[h] = (a, ret)

arms_n = {a: 0 for a in ("door", "sought", "none")}
ret_n = {a: 0 for a in ("door", "sought", "none")}
for h, (a, ret) in primary.items():
    arms_n[a] += 1
    ret_n[a] += int(ret)

pub = {"n": 1646,
       "arms": {"door": 414, "sought": 169, "none": 1063},
       "primary": {"door": 91, "sought": 82, "none": 171}}

print(json.dumps({
    "start_derived": start_handle, "start_bind": {"at": start_bind_at, "id": start_bind_id, "delay_ms": delays[start_handle]},
    "n_cohort": len(cohort), "between": between,
    "arms_recomputed": arms_n,
    "primary_recomputed": ret_n,
    "published_760": pub,
    "delta_n": len(cohort) - pub["n"],
    "delta_arms": {a: arms_n[a] - pub["arms"][a] for a in arms_n},
    "delta_primary": {a: ret_n[a] - pub["primary"][a] for a in ret_n},
}, indent=1))
