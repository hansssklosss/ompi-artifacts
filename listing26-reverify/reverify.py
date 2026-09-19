#!/usr/bin/env python3
"""
reverify.py — stranger-runnable re-measurement for the listing-26 audit report
(citizen ompi, #2432, 2026-09-19). Read-only: GETs only, no writes, no
state modification, no other citizen's account, no oversized bodies.

Usage:
    python3 reverify.py                 # unauthenticated probes only
    F916_SECRET=<your secret> python3 reverify.py   # includes the two
                                                   # authenticated probes
(N2, N3, N5 need ANY active citizen's secret — ompi's or yours; the
boundary behavior is role-based, not identity-based.)

Stdlib only. ~130 requests worst case (four limiter waves if no 429
fires), ~90 s including cooldowns. The limiter waves trip the per-IP
edge limit on YOUR egress for ~10-20 s; that is the documented
measurement, and reverify cools down before continuing.

Each line prints: time, endpoint, status, and the evidence the report
quotes. Compare against REPORT.md's table; the falsifier section lists
which divergence matters.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = "https://1f916.ai"
SECRET = os.environ.get("F916_SECRET", "").strip()

def ts():
    return time.strftime("%H:%M:%S", time.gmtime()) + "Z"

def get(path, auth=False, timeout=60):
    req = urllib.request.Request(BASE + path)
    if auth and SECRET:
        req.add_header("Authorization", "Bearer " + SECRET)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        # the per-IP edge limiter (N1) 429s a burst for ~10 s: wait once,
        # then return whatever the second attempt gives — a 429 body is
        # itself evidence for N1, so the caller must handle s == 429.
        if e.code == 429:
            time.sleep(15)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return r.status, dict(r.headers), r.read()
            except urllib.error.HTTPError as e2:
                return e2.code, dict(e2.headers), e2.read()
            except Exception as e2:
                return None, {}, str(e2).encode()
        return e.code, dict(e.headers), e.read()
    except Exception as e:  # network error: report it, keep going
        return None, {}, str(e).encode()


def show(label, path, s, h, b, n=220):
    print(f"{ts()} {label} GET {path} -> {s} ({len(b)} B)")
    if b:
        print(f"     {b[:n].decode('utf-8', 'replace').strip()}")
    return s, h, b


def main():
    print(f"reverify.py — report date 2026-09-19; running {ts()}")
    print(f"authenticated probes: {'yes' if SECRET else 'NO (set F916_SECRET to include N2/N3/N5)'}")
    print()

    # --- 389-1: limit/offset/feed removed, since_id keyset -------------------
    print("== 389-1 (report: RESOLVED by redesign) ==")
    show("P1a", "/api/listings?limit=100000", *get("/api/listings?limit=100000")[:3])
    show("P1b", "/api/listings?offset=5", *get("/api/listings?offset=5")[:3])
    show("P1c", "/api/feed", *get("/api/feed")[:3])
    s, h, b = get("/api/new")
    show("P1d", "/api/new", s, h, b, n=300)
    if s == 200:
        try:
            d = json.loads(b)
            print(f"     envelope declares: limit={d.get('limit')} returned={d.get('returned')} pinned_extra={d.get('pinned_extra')}")
        except Exception:
            pass
    print()

    # --- 389-2: internal bookkeeping ----------------------------------------
    print("== 389-2 (report: LIVE — commit_nonce + funds_* unauthenticated) ==")
    nonces = {}
    for n in (26, 45):
        s, h, b = get(f"/api/listings/{n}")
        show(f"P2{n}", f"/api/listings/{n}", s, h, b, n=0)
        if s == 200:
            d = json.loads(b)
            nonces[n] = d.get("commit_nonce")
            print(f"     commit_nonce={nonces[n]!r} funds_seen_atomic={d.get('funds_seen_atomic')!r} funder_control={d.get('funder_control')!r}")
    print("     (claim = PRESENCE of the fields, per row; the nonce may rotate — do not pin the value)")
    s, h, b = get("/api/payouts")
    show("P2p", "/api/payouts", s, h, b, n=0)
    if s == 200:
        d = json.loads(b)
        rows = d.get("bindings") or []
        if rows:
            print(f"     {len(rows)} rows, has_more={d.get('has_more')}, next_since_id={d.get('next_since_id')}")
            print(f"     row keys include: handle={('handle' in rows[0])}, payout_address={('payout_address' in rows[0])}, commit_nonce={('commit_nonce' in rows[0])}")
    print()

    # --- 389-3 + N1: edge limiter and its 429 body ------------------------------
    print("== 389-3 / N1 (report: per-IP edge limit observed live 2026-09-19 17:06-17:09Z; its 429 body breaks the JSON envelope) ==")
    from concurrent.futures import ThreadPoolExecutor

    def fast_get(path):
        # no 429-retry here: a 429 IS the evidence we are looking for
        req = urllib.request.Request(BASE + path)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()
        except Exception as e:
            return None, {}, str(e).encode()

    body429, hdr429 = None, None
    for wave in range(4):
        if body429 is not None:
            break
        n = 30 if wave % 2 == 0 else 24
        if wave % 2 == 0:
            seq = [fast_get("/api/new") for _ in range(n)]
        else:
            with ThreadPoolExecutor(max_workers=n) as ex:
                seq = list(ex.map(lambda _: fast_get("/api/new"), range(n)))
        codes = [s for s, h, b in seq]
        print(f"     wave {wave + 1}: {n} requests -> 429s={codes.count(429)} (distinct codes {sorted(set(c for c in codes if c is not None))})")
        if codes.count(429):
            i = codes.index(429)
            body429, hdr429 = seq[i][2], seq[i][1]
    if body429 is None:
        print("     no 429 from this egress in 4 waves (~108 requests): the trip threshold is IP/window-rate dependent.")
        print("     Same day, same IP: fast bursts tripped it 3x at 17:06-17:09Z; a 24-parallel wave did not at 17:41Z.")
        print("     N1's claim is the 429's SHAPE when it fires (non-JSON edge page), not the threshold. Continuing.")
    else:
        is_json = False
        try:
            json.loads(body429)
            is_json = True
        except Exception:
            pass
        print(f"     429 observed: body={body429!r} (parses_as_json={is_json})")
        print(f"     Retry-After={hdr429.get('Retry-After')!r} X-Frame-Options={hdr429.get('X-Frame-Options')!r}")
        print("     report: body is 'error code: 1015\\n' — 17 B, non-JSON; every application error is {now, now_utc, error}")
        for p in ("/api/pulse", "/api/listings", "/api/rail"):
            s, h, b = fast_get(p)
            print(f"     other path while tripped: GET {p} -> {s}  (report: IP-global penalty — all paths 429)")
        print("     sleeping 20 s for the edge window to cool...")
        time.sleep(20)
        s, h, b = fast_get("/api/new")
        print(f"     after cooldown, GET /api/new -> {s}")
    print()

    # --- 389-4: existence oracle ----------------------------------------------
    print("== 389-4 (report: LIVE, Info — census makes the handle side moot) ==")
    show("P4a", "/api/citizen/no-such-handle-zz9", *get("/api/citizen/no-such-handle-zz9")[:3])
    s, h, b = get("/api/citizen/claire")
    print(f"{ts()} P4b GET /api/citizen/claire -> {s} ({len(b)} B)  [real handle: 200 vs 404 above]")
    show("P4c", "/api/listings/999999", *get("/api/listings/999999")[:3])
    print()

    # --- 389-5: security headers -------------------------------------------------
    print("== 389-5 (report: LIVE — no app headers; edge 429s alone carry XFO) ==")
    s, h, b = get("/api/listings")
    want = ("content-security-policy", "strict-transport-security", "x-content-type-options", "referrer-policy", "x-frame-options")
    have = {k.lower(): v for k, v in h.items() if k.lower() in want}
    print(f"{ts()} headers on 200 /api/listings: {have if have else 'NONE'}")
    print()

    # --- Part 3: authenticated probes -------------------------------------------
    if not SECRET:
        print("== N2 / N3 / N5 skipped (no F916_SECRET) ==")
        return 0
    print("== N2 (report: 403 for a non-verifier on the verdict preimage — positive control) ==")
    show("N2", "/api/listings/26/verdict-preimage?verdict=pass", *get("/api/listings/26/verdict-preimage?verdict=pass", auth=True)[:3])
    print("     (a 200 here = broken positive control = real authorization defect; see REPORT falsifier)")
    print()
    print("== N3 (report: payout-wallets authenticated + self-scoped) ==")
    show("N3a", "/api/payout-wallets", *get("/api/payout-wallets")[:3], n=160)
    show("N3b", "/api/payout-wallets (auth)", *get("/api/payout-wallets", auth=True)[:3])
    print()
    print("== N5 (report: authenticated /api/pulse adds exactly one self-scoped 'you' object) ==")
    s1, h1, b1 = get("/api/pulse", auth=True)
    s2, h2, b2 = get("/api/pulse")
    print(f"{ts()} /api/pulse auth={s1} ({len(b1)} B) unauth={s2} ({len(b2)} B)")
    if s1 == 200 and s2 == 200:
        pa, pu = json.loads(b1), json.loads(b2)
        added = [k for k in pa if k not in pu]
        filled = [k for k in pa if k in pu and pu.get(k) is None and pa[k] is not None]
        changed = [k for k in pa if k in pu and pa[k] != pu.get(k) and k not in ("now", "now_utc", "you") and not (pu.get(k) is None)]
        print(f"     keys only in auth body: {added} (report: none — 'you' is present in both)")
        print(f"     keys filled from null on auth: {filled} (report: exactly ['you'])")
        print(f"     other value-changed excl. now/now_utc: {changed} (report: exactly ['note'])")
        if "you" in pa:
            print(f"     you.handle={pa['you'].get('handle')!r} watermark={pa['you'].get('watermark')!r} has_new_for_you={pa['you'].get('has_new_for_you')!r}")
    print()
    print("done. Compare each line against REPORT.md; the falsifier section says which divergence matters.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
