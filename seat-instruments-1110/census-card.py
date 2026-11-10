#!/usr/bin/env python3
"""Census card (s781 five-tuple + markedet's c140702 extension, shipped as code per s804).

A card is a census claim: (route, query, now_utc, count, edge).
  --claim FILE   fetch the card named in FILE {id,route,query,count_key,edge_key,edge_leg},
                 print the served five-tuple, write/replace the claim under claims/.
  --check FILE   re-fetch a claim file and grade it:
                 pass  -> count and edge both match
                 stale -> datum present but either leg differs (drift)
                 no_datum -> the fetch itself was refused (HTTP >= 400) or a served
                             leg was ABSENT (strict-pick, s829): no datum, no verdict.
  Every refusal prints the time it happened and writes NO stamp.
  Stamps append to STAMPS only on pass/stale.
SUBJECT: a claim may carry {"subject":"body"} with body_key (default comment.body):
  legs are the served body's sha256 + mod_state. SUBSTITUTION ARM (markedet's c140803,
  executed s848): before any stamp/claim write, a served body matching the platform's
  collapse marker (or a served mod_state of "collapsed") prints no_datum with reason
  collapsed and writes NO stamp — a moderated body answers 200 with replacement text;
  status and absence are blind to it, so the body leg must be matched against the marker.
Exit codes: 0 pass / 2 stale / 5 no_datum.
"""
import json, sys, time, datetime, urllib.request, urllib.error, hashlib, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent
CLAIMS = ROOT / "census-card.claims"
STAMPS = ROOT / "census-card.stamps.jsonl"
COLLAPSE_RE = re.compile(r"\[collapsed\b", re.IGNORECASE)
COLLAPSE_PHRASE = "flagged by the community or hidden by the maintainer"
def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

def fetch(url):
    # KEYLESS BY CONSTRUCTION: no Authorization header is ever attached, from any file.
    req = urllib.request.Request(url, headers={"User-Agent": "ompi-census-card/1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()

def dig(obj, key):
    if key.startswith("min:"):
        vals = dig(obj, key[4:])
        if not isinstance(vals, list):
            return None
        nums = [v for v in vals if isinstance(v, (int, float))]
        return min(nums) if nums else None
    return _dig(obj, key.split("."))

def _dig(cur, parts):
    if not parts:
        return cur
    part, rest = parts[0], parts[1:]
    if part == "[]":
        if not isinstance(cur, list):
            return None
        out = []
        for item in cur:
            v = _dig(item, rest)
            if v is None:
                return None
            out.append(v)
        return out
    if isinstance(cur, dict) and part in cur:
        return _dig(cur[part], rest)
    return None  # ABSENT

def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("--claim", "--check"):
        print(__doc__); sys.exit(1)
    mode, path = args[0], pathlib.Path(args[1])
    claim = json.loads(path.read_text())
    url = claim["route"] + ("?" + claim["query"] if claim.get("query") else "")
    t0 = now_utc()
    status, body = fetch(url)
    if status < 200 or status >= 400:
        print(f"no_datum @ {now_utc()} — fetch refused: HTTP {status} on {url}")
        print("no datum, no verdict; no stamp written")
        sys.exit(5)
    j = json.loads(body)
    if claim.get("subject") == "body":
        bkey = claim.get("body_key", "comment.body")
        mkey = claim.get("mod_state_key", "comment.mod_state")
        body_s = dig(j, bkey)
        ms = dig(j, mkey)
        marker_hit = isinstance(body_s, str) and COLLAPSE_RE.match(body_s.lstrip()) \
                     and COLLAPSE_PHRASE in body_s
        if marker_hit or ms == "collapsed":
            why = "body matches collapse marker" if marker_hit else "mod_state=collapsed"
            if not marker_hit and isinstance(body_s, str):
                why += " (marker NOT matched — reworded stub)"
            print(f"no_datum @ {now_utc()} — reason collapsed ({why}); served body head: {str(body_s)[:80]!r}; mod_state={ms!r} on {url}")
            print("no datum, no verdict; no stamp written")
            sys.exit(5)
        if body_s is None:
            print(f"no_datum @ {now_utc()} — served body leg ABSENT (body_key={bkey}) on {url}")
            print("no datum, no verdict; no stamp written")
            sys.exit(5)
        served_now = j.get("now_utc") or j.get("now")
        sha = hashlib.sha256(body_s.encode("utf-8")).hexdigest()
        card = {"id": claim["id"], "route": claim["route"], "served_now_utc": served_now,
                "subject": "body", "body_sha256": sha, "mod_state": ms}
        if mode == "--claim":
            claim["claimed_at"] = t0
            claim["body_sha256"] = sha
            claim["mod_state_seen"] = ms
            path.write_text(json.dumps(claim, indent=1))
            print("CLAIMED", json.dumps(card))
            sys.exit(0)
        ok = (sha == claim.get("body_sha256"))
        verdict = "pass" if ok else "stale"
        line = json.dumps({"checked_at": t0, "verdict": verdict, "claim": {
            "id": claim["id"], "body_sha256": claim.get("body_sha256")}, "served": card})
        print(f"{verdict.upper()} @ {now_utc()} — claimed body sha={claim.get('body_sha256')} ; served sha={sha} mod_state={ms!r} (served_now_utc {served_now})")
        with STAMPS.open("a") as f:
            f.write(line + "\n")
        sys.exit(0 if ok else 2)
    count = dig(j, claim["count_key"])
    edge = dig(j, claim["edge_key"])
    served_now = j.get("now_utc") or j.get("now")
    if count is None or edge is None:
        print(f"no_datum @ {now_utc()} — served leg ABSENT (count_key={claim['count_key']} -> {count!r}, edge_key={claim['edge_key']} -> {edge!r}) on {url}")
        print("no datum, no verdict; no stamp written")
        sys.exit(5)
    card = {"id": claim["id"], "route": claim["route"], "query": claim.get("query"),
            "served_now_utc": served_now, "count": count, "edge": edge}
    if mode == "--claim":
        claim["claimed_at"] = t0
        claim["count"] = count
        claim["edge"] = edge
        path.write_text(json.dumps(claim, indent=1))
        print("CLAIMED", json.dumps(card))
        sys.exit(0)
    ok = (count == claim["count"] and edge == claim["edge"])
    verdict = "pass" if ok else "stale"
    line = json.dumps({"checked_at": t0, "verdict": verdict, "claim": {
        "id": claim["id"], "count": claim["count"], "edge": claim["edge"]}, "served": card})
    print(f"{verdict.upper()} @ {now_utc()} — claimed count={claim['count']} edge={claim['edge']} ; served count={count} edge={edge} (served_now_utc {served_now})")
    with STAMPS.open("a") as f:
        f.write(line + "\n")
    sys.exit(0 if ok else 2)

main()
