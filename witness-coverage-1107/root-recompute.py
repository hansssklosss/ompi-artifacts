#!/usr/bin/env python3
"""Independent recomputation of the identity_events Merkle root from the public
log, under GET /api/checkpoint's own published spec:
  leaves_are : the sealed rows' `hash` column values (lowercase hex, as UTF-8 bytes), in id order
  tree       : RFC 6962: leaf = SHA-256(0x00 || leaf), node = SHA-256(0x01 || l || r)
The recomputed root is compared with the registry-signed root at that checkpoint's tree_size.
"""
import hashlib
import json
import time
import urllib.error
import urllib.request

BASE = "https://1f916.ai"


def get(url):
    """Keyless read with a seat pause and a 429 backoff (a rate refusal is not a missing row)."""
    for attempt in range(10):
        req = urllib.request.Request(url, headers={"User-Agent": "ompi-seat-recompute"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = json.load(r)
            time.sleep(0.30)
            return body
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(3.0 * (attempt + 1))
                continue
            raise
    raise RuntimeError("rate-limited out on %s" % url)


def leaf(b):
    return hashlib.sha256(b"\x00" + b).digest()


def node(l, r):
    return hashlib.sha256(b"\x01" + l + r).digest()


def mth(hashes):
    ls = [leaf(h.encode("utf-8")) for h in hashes]

    def rec(a):
        n = len(a)
        if n == 1:
            return a[0]
        k = 1
        while k * 2 < n:
            k *= 2
        return node(rec(a[:k]), rec(a[k:]))

    return rec(ls).hex()


cp = get(BASE + "/api/checkpoint")
tgt = [c for c in cp["checkpoints"] if c["log"] == "identity_events"][0]
T = int(tgt["tree_size"])
R = tgt["root"]
print("checkpoint id %s tree_size %d root %s created_at %s" % (tgt["id"], T, R, tgt["created_at"]))
print("read now_utc", cp["now_utc"])

since = 0
leaves, nulls, seen, pages, stamps = [], [], [], 0, []
while len(leaves) < T:
    d = get("%s/api/events?since=%d" % (BASE, since))
    ev = d.get("events")
    if ev is None:
        print("page at since=%d served no events array; keys=%s" % (since, sorted(d.keys())))
        break
    pages += 1
    if not ev:
        break
    for r in ev:
        seen.append((r["id"], r["hash"]))
        (nulls if r["hash"] is None else leaves).append((r["id"], r["hash"]))
    since = d.get("next_since", ev[-1]["id"])
    stamps.append(d.get("now_utc"))
    if not d.get("has_more", False) or len(leaves) >= T:
        break

ids = [i for i, _ in seen]
print("pages %d rows fetched %d id range %d .. %d" % (pages, len(seen), ids[0], ids[-1]))
print("server stamps on this read: first %s last %s" % (stamps[0], stamps[-1]))
print("null-hash (unsealed) rows %d ids %s" % (len(nulls), nulls[:20]))
print("strictly increasing across pages:", all(b > a for a, b in zip(ids, ids[1:])))
print("contiguous ids:", ids == list(range(ids[0], ids[-1] + 1)))
sealed_ids = [i for i, _ in leaves]
print("sealed count %d, dense from %d:" % (len(sealed_ids), sealed_ids[0]),
      sealed_ids == list(range(sealed_ids[0], sealed_ids[0] + len(sealed_ids))))

took = [h for _, h in leaves[:T]]
print("leaves used %d target %d (sealed collected %d)" % (len(took), T, len(leaves)))
c = mth(took)
print("recomputed root", c)
print("served    root", R)
print("VERDICT", "MATCH" if c == R else "MISMATCH")
