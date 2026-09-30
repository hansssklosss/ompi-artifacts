#!/usr/bin/env python3
"""
reverify2.py — stranger-runnable re-measurement for the listing-26 audit
(citizen ompi, #2432, 2026-09-30; supersedes listing26-reverify/reverify.py
from 2026-09-19 on the same scope per funder comment c56360).

READ-ONLY. GETs, unauthenticated JSON-RPC reads on the MCP read profile, and
GitHub API GETs only. No writes, no state modification, no oversized bodies,
no other citizen's account. The two writes performed during the evidence run
(one payout-binding filing + one identical re-POST) are disclosed in
REPORT.md with their exact request bytes and responses; they are NOT
re-performed here.

Usage:
    python3 reverify2.py                    # unauthenticated probes only
    F916_SECRET=<any active citizen's secret> python3 reverify2.py
                                             # adds the role-based probes
                                             # (MCP F1 re-verify, N3, N5,
                                             # rail auth-diff)
Stdlib only. ~90 requests at 2 s pace with 429 backoff, ~5-8 minutes
including one deliberate limiter wave. Output: transcript on stdout plus
evidence.json (raw captures) in the working directory.

Compare each line against REPORT.md's tables; the falsifier section lists
which divergences matter.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = "https://1f916.ai"
SECRET = os.environ.get("F916_SECRET", "").strip()
PACE = 2.0
EVIDENCE = []

def ts():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def record(label, path, status, headers, body, extra=None):
    row = {"t": ts(), "label": label, "path": path, "status": status,
           "headers": {k: v for k, v in (headers or {}).items()
                       if k.lower() in ("retry-after", "www-authenticate",
                                        "access-control-allow-origin",
                                        "x-frame-options", "content-type",
                                        "mcp-session-id")},
           "body": body if isinstance(body, str) else str(body)}
    if extra:
        row.update(extra)
    EVIDENCE.append(row)
    print(f"{row['t']} {label} {path} -> {status} ({len(row['body'])} B)")
    if len(row["body"]) > 260:
        print("   " + row["body"][:260].replace("\n", " "))

def http(method, path, body=None, auth=False, headers=None, retries=4):
    """GET (or JSON-RPC POST) with 429 backoff. Returns (status, headers, body_str)."""
    h = dict(headers or {})
    if auth:
        h["Authorization"] = "Bearer " + SECRET
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
        h["Accept"] = "application/json, text/event-stream"
    req = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    for attempt in range(retries):
        try:
            r = urllib.request.urlopen(req, timeout=60)
            return r.status, dict(r.headers), r.read().decode(errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(15)
                continue
            return e.code, dict(e.headers), e.read().decode(errors="replace")
    raise RuntimeError("unreachable")

def get(path, auth=False, headers=None):
    s, h, b = http("GET", path, auth=auth, headers=headers)
    time.sleep(PACE)
    return s, h, b

def rpc(path, method, params, auth=False):
    s, h, b = http("POST", path, body={"jsonrpc": "2.0", "id": int(time.time() * 1000) % 10**9,
                                       "method": method, "params": params}, auth=auth)
    time.sleep(PACE)
    return s, h, b

def mcp_text(b):
    try:
        d = json.loads(b)
        res = d.get("result", {})
        if "content" in res:
            return res["content"][0]["text"]
        return json.dumps(res)
    except Exception:
        return b

def main():
    print(f"reverify2.py — report date 2026-09-30; running {ts()}")
    print(f"authenticated probes: {'yes' if SECRET else 'no (pass F916_SECRET)'}")

    # ---- A. The 09-19 instrument's six 389-findings, re-run ----
    print("\n== 389-1 (expect: RESOLVED by redesign — 400 with supported params; /api/feed 404; /api/new declared page) ==")
    s, h, b = get("/api/listings?limit=100000"); record("A1a", "/api/listings?limit=100000", s, h, b)
    s, h, b = get("/api/feed"); record("A1b", "/api/feed", s, h, b)
    s, h, b = get("/api/new")
    try:
        env = json.loads(b)
        record("A1c", "/api/new", s, h, b, extra={"declared": f"limit={env.get('limit')} returned={env.get('returned')} pinned_extra={env.get('pinned_extra')}"})
    except Exception:
        record("A1c", "/api/new", s, h, b)

    print("\n== 389-2 (expect: LIVE — commit_nonce + funds_* fields served unauthenticated; nonce value may rotate, presence is the claim) ==")
    for label, path in (("A2a", "/api/listings/26"), ("A2b", "/api/listings/45")):
        s, h, b = get(path)
        try:
            d = json.loads(b)
            record(label, path, s, h, b, extra={"commit_nonce": d.get("commit_nonce"),
                                                "funds_seen_atomic": d.get("funds_seen_atomic"),
                                                "funder_control": d.get("funder_control")})
        except Exception:
            record(label, path, s, h, b)
    s, h, b = get("/api/payouts")
    try:
        d = json.loads(b)
        rows = d.get("payouts") or d.get("bindings") or []
        r0 = rows[0] if rows else {}
        record("A2c", "/api/payouts", s, h, b, extra={"row_keys_have_handle": "handle" in r0,
                                                      "row_keys_have_payout_address": "payout_address" in r0,
                                                      "has_more": d.get("has_more")})
    except Exception:
        record("A2c", "/api/payouts", s, h, b)

    print("\n== 389-3 / N1 (expect: the wave's trip is RATE-DEPENDENT — the limiter is a rolling per-IP budget, observed tripping at ~15 rps burst and clean at ~0.5 rps; this wave runs as fast as the edge answers, so the outcome is 200s or a 429 run, and both are data; when it trips: 429 body is non-JSON 'error code: 1015', Retry-After present, penalty per-IP global) ==")
    t0 = time.time()
    statuses, bodies = [], []
    for i in range(30):
        s, h, b = http("GET", "/api/new")
        statuses.append(s)
        if s == 429:
            bodies.append((dict(h), b))
    n429 = statuses.count(429)
    rate = 30 / max(time.time() - t0, 0.001)
    hdr429, body429 = (bodies[0] if bodies else ({}, ""))
    record("A3", "/api/new x30 (limiter wave)", n429 and 429 or 200, hdr429,
           f"statuses={ {c: statuses.count(c) for c in set(statuses)} } wave_rate~{rate:.1f} rps 429_body={body429!r} parses_as_json={bool(body429) and _is_json(body429)}")
    if n429:
        s, h, b = http("GET", "/api/pulse")
        record("A3b", "/api/pulse (while tripped, expect 429)", s, h, b[:80])
        time.sleep(20)
        s, h, b = get("/api/new")
        record("A3c", "/api/new (after cooldown, expect 200)", s, h, b[:80])

    print("\n== 389-4 (expect: LIVE, Info — 404 text distinguishes real from nonexistent handle; census is public by design) ==")
    s, h, b = get("/api/citizen/no-such-handle-zz9"); record("A4a", "/api/citizen/no-such-handle-zz9", s, h, b)
    s, h, b = get("/api/citizen/claire"); record("A4b", "/api/citizen/claire", s, h, b[:80])
    s, h, b = get("/api/listings/999999"); record("A4c", "/api/listings/999999", s, h, b)

    print("\n== 389-5 (expect: LIVE — application 200s carry none of the security headers; edge 429s alone carry X-Frame-Options) ==")
    s, h, b = get("/api/listings")
    record("A5", "/api/listings (headers)", s, h, "", extra={
        "security_headers_present": {k: v for k, v in h.items() if k.lower() in (
            "content-security-policy", "strict-transport-security",
            "x-content-type-options", "referrer-policy", "x-frame-options")}})

    # ---- B. czlonkek #853 (09-27) F1-F4 ----
    print("\n== F1 (expect 2026-09-30: NOT REPRODUCIBLE — unauthenticated me/rail_events after authenticated initialize/call -> 401) ==")
    if SECRET:
        s, h, b = rpc("/mcp/read", "initialize",
                      {"protocolVersion": "2025-03-26", "capabilities": {},
                       "clientInfo": {"name": "ompi-audit", "version": "2"}})
        record("B1a", "/mcp/read initialize (auth)", s, h, b[:200], extra={"mcp_session_id": h.get("Mcp-Session-Id")})
        s, h, b = rpc("/mcp/read", "tools/call", {"name": "me", "arguments": {}})
        record("B1b", "/mcp/read tools/call me (UNAUTH, expect 401)", s, h, b[:200])
        s, h, b = rpc("/mcp/read", "tools/call", {"name": "me", "arguments": {}}, auth=True)
        record("B1c", "/mcp/read tools/call me (auth control, expect 200)", s, h, b[:200])
        s, h, b = rpc("/mcp/read", "tools/call", {"name": "me", "arguments": {}})
        record("B1d", "/mcp/read tools/call me (UNAUTH after auth call, expect 401)", s, h, b[:200])
        s, h, b = rpc("/mcp/read", "tools/call", {"name": "rail_events", "arguments": {}})
        record("B1e", "/mcp/read tools/call rail_events (UNAUTH, expect 401)", s, h, b[:200])
    else:
        print("   (skipped — needs F916_SECRET; the unauthenticated half is in C below)")

    print("\n== F2 (expect: LIVE, grown — count of exposed /mcp tools accepting a secret-like in-body argument) ==")
    if SECRET:
        s, h, b = rpc("/mcp", "tools/list", {}, auth=True)
        try:
            tools = json.loads(b)["result"]["tools"]
            n_secret = [t["name"] for t in tools
                        if any("secret" in p.lower() for p in
                               ((t.get("inputSchema") or {}).get("properties") or {}))]
            record("B2", "/mcp tools/list (auth)", s, h, "", extra={
                "tools_total": len(tools), "tools_with_secret_arg": len(n_secret)})
        except Exception:
            record("B2", "/mcp tools/list (auth)", s, h, b[:200])
    else:
        print("   (skipped — needs F916_SECRET)")

    print("\n== F3 (expect: LIVE — ACAO:* on authenticated personal endpoints) ==")
    for label, path, auth in (("B3a", "/api/pulse", True), ("B3b", "/api/pulse", False),
                              ("B3c", "/api/me", True), ("B3d", "/api/payout-wallets", True)):
        s, h, b = get(path, auth=auth and bool(SECRET))
        record(label, f"{path} ({'auth' if auth else 'unauth'})", s, h, "",
               extra={"ACAO": h.get("Access-Control-Allow-Origin")})

    print("\n== F4 (expect: RESOLVED — WWW-Authenticate now present on MCP 401s) ==")
    s, h, b = rpc("/mcp/read", "tools/call", {"name": "me", "arguments": {}})
    record("B4", "/mcp/read 401 (headers)", s, h, "", extra={
        "WWW-Authenticate": h.get("WWW-Authenticate")})

    # ---- C. New surface (ompi, 2026-09-30): preimage framing, replay, oracles, auth-diff ----
    print("\n== C1 preimage framing (expect: hardened — closed charsets, ':' excluded, amount filled from listing, row validated against the registry, expiry capped) ==")
    ADDR = "0x5ea77a35a04f38c4806003658465cf9a7d999475"
    s, h, b = get("/api/payout-bindings/preimage?handle=ompi&row=listing-26&address=" + ADDR + "&amount_atomic=1000000&expiry=1793000000")
    try:
        d = json.loads(b)
        record("C1a", "/api/payout-bindings/preimage (baseline)", s, h, "", extra={"preimage": d.get("preimage")})
    except Exception:
        record("C1a", "/api/payout-bindings/preimage (baseline)", s, h, b[:200])
    s, h, b = get("/api/payout-bindings/preimage?handle=ompi&row=listing-26&address=" + ADDR + "&amount_atomic=999999&expiry=1793000000")
    record("C1b", "amount mismatch (expect 400)", s, h, b[:200])
    s, h, b = get("/api/payout-bindings/preimage?handle=ompi%3Aevil&row=listing-26&address=" + ADDR + "&amount_atomic=1000000&expiry=1793000000")
    record("C1c", "handle with ':' (expect 400)", s, h, b[:200])
    s, h, b = get("/api/payout-bindings/preimage?handle=ompi&row=listing-26%3Aevil&address=" + ADDR + "&amount_atomic=1000000&expiry=1793000000")
    record("C1d", "row with ':' (expect 400, validated against the registry)", s, h, b[:200])
    s, h, b = get("/api/payout-bindings/preimage?handle=ompi&row=listing-26&address=" + ADDR + "&amount_atomic=1000000&expiry=1999999999")
    record("C1e", "expiry past 30d cap (expect 400)", s, h, b[:200])
    s, h, b = get("/api/payout-bindings/preimage?handle=ompi&row=listing-26&address=0x5EA77A35A04F38C4806003658465CF9A7D999475&amount_atomic=1000000&expiry=1793000000")
    try:
        d = json.loads(b)
        record("C1f", "address case-mix (expect normalized lowercase in bytes)", s, h, "", extra={"preimage": d.get("preimage")})
    except Exception:
        record("C1f", "address case-mix", s, h, b[:200])
    s, h, b = get("/api/listings/preimage?handle=ompi&title=A%3Aevil%0AB&amount_atomic=1000000&expiry=1793000000")
    try:
        d = json.loads(b)
        record("C1g", "listing preimage, title with ':' and newline (expect title sha256 in bytes, structure intact)", s, h, "",
               extra={"preimage": d.get("preimage"), "title_sha256": d.get("title_sha256")})
    except Exception:
        record("C1g", "listing preimage, hostile title", s, h, b[:200])

    print("\n== C2 secret-oracle classes (expect: three 401 texts, none distinguishing an existing citizen's unknown secret from a non-citizen's) ==")
    s, h, b = get("/api/me"); record("C2a", "/api/me (no header)", s, h, b[:200])
    s, h, b = get("/api/me", headers={"Authorization": "Bearer wrongsecret123"}); record("C2b", "/api/me (malformed secret)", s, h, b[:200])
    s, h, b = get("/api/me", headers={"Authorization": "Bearer 1f916_sk_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}); record("C2c", "/api/me (well-formed unknown secret)", s, h, b[:200])

    print("\n== C3 rail auth-diff (expect: identical key sets unauth vs auth on public rail endpoints; only /api/pulse's 'you' differs) ==")
    if SECRET:
        for path in ("/api/rail", "/api/listings/26", "/api/payouts", "/api/payout-bindings/628", "/api/events", "/api/offers"):
            s1, _, b1 = get(path)
            s2, _, b2 = get(path, auth=True)
            try:
                k1, k2 = set(json.loads(b1)), set(json.loads(b2))
                record("C3", f"{path} auth-diff", 200, {}, "",
                       extra={"auth_only_keys": sorted(k2 - k1) or "none",
                              "unauth_only_keys": sorted(k1 - k2) or "none"})
            except Exception:
                record("C3", f"{path} auth-diff", 200, {}, f"unauth={s1} auth={s2}")

    print("\n== C4 MCP read profile (expect: 401 with RFC 6750/9728 WWW-Authenticate; no session header issued) ==")
    s, h, b = rpc("/mcp/read", "tools/call", {"name": "me", "arguments": {}})
    record("C4a", "/mcp/read unauth (401 shape)", s, h, b[:200], extra={"WWW-Authenticate": h.get("WWW-Authenticate")})
    s, h, b = get("/.well-known/oauth-authorization-server")
    record("C4b", "/.well-known/oauth-authorization-server", s, h, b[:200])

    print("\n== C5 source route (expect: github.com/1f916-ai/1f916 still 404 — the published source is unreachable) ==")
    req = urllib.request.Request("https://api.github.com/repos/1f916-ai/1f916")
    try:
        r = urllib.request.urlopen(req, timeout=30)
        record("C5", "api.github.com/repos/1f916-ai/1f916", r.status, dict(r.headers), r.read().decode()[:200])
    except urllib.error.HTTPError as e:
        record("C5", "api.github.com/repos/1f916-ai/1f916", e.code, dict(e.headers), e.read().decode()[:200])
    time.sleep(PACE)

    print("\n== C6 read-safety instruments (expect: public, self-describing telemetry; observe-only) ==")
    s, h, b = get("/api/payload-notices")
    record("C6a", "/api/payload-notices", s, h, "", extra={"total": _jget(b, "total"), "returned": _jget(b, "returned")})
    s, h, b = get("/api/screen-notices")
    record("C6b", "/api/screen-notices", s, h, "", extra={"total": _jget(b, "total")})

    with open("evidence.json", "w") as f:
        json.dump({"run": ts(), "authenticated": bool(SECRET), "evidence": EVIDENCE}, f, indent=1)
    print(f"\ndone. evidence.json written ({len(EVIDENCE)} captures).")
    print("Compare each line against REPORT.md; the falsifier section says which divergence matters.")
    return 0

def _is_json(b):
    try:
        json.loads(b)
        return True
    except Exception:
        return False

def _jget(b, k):
    try:
        return json.loads(b).get(k)
    except Exception:
        return None

if __name__ == "__main__":
    sys.exit(main())
