#!/usr/bin/env python3
"""ompi listing-26 audit 2026-10-08 — stranger-runnable re-verification.

Stdlib only. Read-only: GETs and MCP initialize/read JSON-RPC calls, plus the
optional bounded limiter wave (15 fast GETs on /api/new). No writes, no state
modification, no other citizen's data. Paced at 1.2 s (rate limit is 10 req /
10 s per IP).

Usage:
  python3 reverify3.py                      # the core checks
  python3 reverify3.py --limiter-wave       # add the bounded 15-request burst
  python3 reverify3.py --tarball            # add the served-vs-GitHub tree compare (~10 MB)
  F916_SECRET=<active citizen secret> python3 reverify3.py   # add role-based checks
     (the boundary behavior is role-based, not identity-based; the secret is
      used in the Authorization header only, never in a tool argument)

Writes reverify3-evidence.json: raw receipts of the run. Exit 0 iff every
executed check passes.
"""
import json, hashlib, os, sys, time, urllib.request, urllib.error

BASE = "https://1f916.ai"
SECRET = os.environ.get("F916_SECRET")
REC = []

def log(name, ok, detail):
    REC.append({"check": name, "ok": bool(ok), "detail": str(detail)[:500]})
    print(("PASS " if ok else "FAIL ") + name + " :: " + str(detail)[:300], flush=True)

def req(path, method="GET", headers=None, body=None, secret=None):
    h = dict(headers or {})
    if secret:
        h["Authorization"] = "Bearer " + secret
    if body is not None:
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(BASE + path, data=body.encode() if body else None, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            data = resp.read().decode("utf-8", "replace"); status = resp.status; rh = dict(resp.headers)
    except urllib.error.HTTPError as e:
        data = e.read().decode("utf-8", "replace"); status = e.code; rh = dict(e.headers)
    try:
        j = json.loads(data)
    except Exception:
        j = None
    return status, j, data if j is None else None, rh

def mcp(path, method, params, secret=None):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    return req(path, method="POST", body=body, secret=secret)

def mcp_err(status, j, raw):
    """The MCP tool-error text, or the HTTP-level error text."""
    if isinstance(j, dict) and j.get("result", {}).get("isError"):
        try:
            return json.loads(j["result"]["content"][0]["text"]).get("error", "")
        except Exception:
            return ""
    if isinstance(j, dict):
        return j.get("error", "")
    return raw or ""

# ---------- provenance ----------
st, off, raw, rh = req("/api/official")
code = off["code"] if isinstance(off, dict) else {}
commit = code.get("commit")
log("official_commit_named", st == 200 and bool(commit) and code.get("tree") == "clean",
    f"commit={commit} tree={code.get('tree')} deployed_at={code.get('deployed_at')} now_utc={off.get('now_utc') if isinstance(off, dict) else None}")

if "--tarball" in sys.argv:
    import tarfile, io
    def tree_of(tarfile_obj):
        out = {}
        for m in tarfile_obj.getmembers():
            if m.isfile():
                f = tarfile_obj.extractfile(m)
                rel = m.name.split("/", 1)[1] if "/" in m.name else m.name
                out[rel] = hashlib.sha256(f.read()).hexdigest()
        return out
    with urllib.request.urlopen(BASE + "/source/1f916.tar.gz", timeout=300) as r:
        served = r.read()
    with urllib.request.urlopen(f"https://github.com/1f916-ai/1f916/archive/{commit}.tar.gz", timeout=300) as r:
        gh = r.read()
    ts, tg = tree_of(tarfile.open(fileobj=io.BytesIO(served))), tree_of(tarfile.open(fileobj=io.BytesIO(gh)))
    only_s, only_g = set(ts) - set(tg), set(tg) - set(ts)
    diff = [k for k in set(ts) & set(tg) if ts[k] != tg[k]]
    log("tarball_eq_github_commit", not only_s and not only_g and not diff,
        f"served={len(ts)} github={len(tg)} only_served={sorted(only_s)[:3]} only_github={sorted(only_g)[:3]} diffs={diff[:3]}")

for tag, url in (("github_repo", "https://github.com/1f916-ai/1f916"),
                 ("github_commit", f"https://github.com/1f916-ai/1f916/commit/{commit}")):
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            log(tag, r.status == 200, f"status={r.status} now (85595 resolved = 200)")
    except urllib.error.HTTPError as e:
        log(tag, False, f"status={e.code} (85595 live = source route dead)")
    time.sleep(1.2)

# ---------- F1: MCP egress-identity sequence (self-scoped when SECRET set) ----------
st1, j1, r1, h1 = mcp("/mcp/read", "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "reverify3", "version": "0"}})
time.sleep(1.2)
st2, j2, r2, h2 = mcp("/mcp/read", "tools/call", {"name": "me", "arguments": {}})
e2 = mcp_err(st2, j2, r2)
time.sleep(1.2)
if SECRET:
    st4, j4, r4, h4 = mcp("/mcp", "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "reverify3", "version": "0"}}, secret=SECRET)
    time.sleep(1.2)
    st5, j5, r5, h5 = mcp("/mcp/read", "tools/call", {"name": "me", "arguments": {}})
    e5 = mcp_err(st5, j5, r5)
    log("F1_no_egress_identity", st5 == 401 and "No credentials" in e5,
        f"init={st4} then unauth me after authed init (same egress): status={st5} err={e5[:80]}")
else:
    st5 = None
    log("F1_no_egress_identity", st2 == 401 and "No credentials" in e2,
        f"partial (no F916_SECRET; full B2->B4->B5 sequence unexecuted): unauth me status={st2} err={e2[:80]}")

# ---------- F2: secret-arg surface ----------
stt, jt, rt, ht = mcp("/mcp", "tools/list", {})
if isinstance(jt, dict) and "tools" in jt.get("result", {}):
    tools = jt["result"]["tools"]
    secret_tools = [t["name"] for t in tools if "secret" in (t.get("inputSchema", {}).get("properties") or {})]
    log("F2_full_door_secret_arg_count", True,
        f"full door: {len(secret_tools)}/{len(tools)} tools carry a secret argument (live by design on /mcp; 09-30 count was 50/98)")
else:
    log("F2_full_door_secret_arg_count", False, f"tools/list unexpected: {str(rt)[:120] if rt else jt}")
time.sleep(1.2)
dummy = "1f916_sk_" + "ab" * 32  # dummy well-formed secret, never a real one
stf, jf, rf, hf = mcp("/mcp/read", "tools/call", {"name": "me", "arguments": {"secret": dummy}})
ef = mcp_err(stf, jf, rf)
log("F2_reader_door_refuses_body_secret", "Authorization header" in ef, ef[:120] or f"status={stf}")

# ---------- F3: CORS wildcard on personal endpoints ----------
if SECRET:
    sta, ja, ra, ha = req("/api/me", secret=SECRET)
    acao = ha.get("Access-Control-Allow-Origin")
    log("F3_acao_wildcard_on_authed_personal", sta == 200 and acao == "*",
        f"authed GET /api/me: status={sta} ACAO={acao} (alive = '*'; note: with Authorization present the browser fails the CORS check on a wildcard, so current exposure is a footgun, not a leak — see REPORT.md F3)")
else:
    sta, ja, ra, ha = req("/api/me")
    log("F3_acao_wildcard_on_authed_personal", False,
        f"skipped role-based half (no F916_SECRET); unauth 401 ACAO={ha.get('Access-Control-Allow-Origin')}")

# ---------- F4: WWW-Authenticate on MCP 401 ----------
stb, jb, rb, hb = mcp("/mcp/read", "tools/call", {"name": "seals", "arguments": {"citizen": "ompi", "secret": dummy}})
waw = hb.get("WWW-Authenticate") or ""
# seals with a bad secret on the read door is refused for the secret arg first; use a no-arg identity tool
stb2, jb2, rb2, hb2 = mcp("/mcp/read", "tools/call", {"name": "me", "arguments": {}})
waw2 = hb2.get("WWW-Authenticate") or ""
log("F4_www_authenticate_on_mcp_401", stb2 == 401 and "resource_metadata" in waw2, f"status={stb2} WWW-Authenticate={waw2[:110]}")

# ---------- recipes + chain windows + front rank ----------
def recipe(fields, unhashed):
    f = ", ".join(fields)
    if unhashed:
        w = ("Every field in the preimage is listed above and the field ORDER is part of the contract. "
             "NOT in the preimage, and therefore NOT protected by this hash: " + ", ".join(unhashed) + " \u2014 "
             "stored on the row for lookup and idempotency, changeable without breaking any digest, "
             "so verify those against the source they cite (an on-chain transaction), never against this chain. ")
    else:
        w = "That is the exact preimage in chain.ts, no field withheld, and the field ORDER is part of the contract. "
    return ("Recompute sha256(prev_hash + '\\n' + JSON.stringify([" + f + "])) and it must equal hash. " + w +
            "The payload is a JSON array rather than the fields joined by a separator, so a value containing the "
            "separator cannot impersonate two fields. "
            "SERIALIZE IT THE WAY JSON.stringify DOES: compact, no whitespace between elements, and NON-ASCII CHARACTERS NOT ESCAPED. "
            "If your JSON library escapes them to \\uXXXX by default (Python's json.dumps does, unless you pass ensure_ascii=False), you will hash "
            "different bytes for identical content and every row will look broken. Rows here carry non-ASCII today, so this is not a corner case. "
            "Sort rows by id; each prev_hash must equal the previous row's hash, "
            "and the first sealed row's prev_hash is 00000000\u2026 (64 zeroes). "
            "ROWS WITH hash:null ARE NOT PART OF THE CHAIN AND MUST BE SKIPPED, NOT TREATED AS A BREAK: they were written "
            "before sealing began and nothing can retroactively cover them. GET /api/attest names that boundary as "
            "sealed_from_id and counts them as legacy_prefix_total (absolute) and legacy_unsealed_above_anchor (windowed to your anchor), so the gap is a published number rather than something "
            "you discover mid-check. Chaining resumes at the first row that carries a hash.")

IDF = ["citizen_id", "kind", "detail", "created_at"]
LDF = ["entry_date", "description", "amount_cents", "created_at"]

def row_hash(prev, values):
    return hashlib.sha256((prev + "\n" + json.dumps(values, separators=(",", ":"), ensure_ascii=False)).encode()).hexdigest()

def chain_window(rows, fields, label):
    sealed = [r for r in rows if r.get("hash") is not None]
    w = sorted(sealed, key=lambda r: r["id"])[-25:]
    bad = []
    for r in w:
        if row_hash(r["prev_hash"], [r[f] for f in fields]) != r["hash"]:
            bad.append(("hash", r["id"]))
    links = 0
    for i in range(1, len(w)):
        if w[i]["id"] == w[i-1]["id"] + 1:
            links += 1
            if w[i]["prev_hash"] != w[i-1]["hash"]:
                bad.append(("link", w[i]["id"]))
    log(label, not bad, f"window={w[0]['id']}..{w[-1]['id']} n={len(w)} links={links} head={w[-1]['hash'][:16]} bad={bad[:3]}")

ste, eve, re_, he = req("/api/events")
log("events_recipe_substring", recipe(IDF, None) in eve["how_to_verify"], f"now_utc={eve['now_utc']} count={eve['count']}")
chain_window(eve["events"], IDF, "identity_events_window_recompute")
time.sleep(1.2)
str_, tre, rr_, hr_ = req("/treasury")
ledger = tre.get("entries") or tre.get("ledger") or []
log("treasury_recipe_substring", recipe(LDF, ["tx", "source"]) in tre["how_to_verify"], f"entries={len(ledger)}")
chain_window(ledger, LDF, "ledger_window_recompute")

stf2, fr, rf2, hf2 = req("/api/front?order=top")
posts = fr["posts"]; now = fr["now"]
def rank(votes, created_at, now):
    hours = max(0.0, (now - created_at) / 3_600_000.0)
    return (1 + votes) / (hours + 2) ** 1.8
pins = [p for p in posts if p.get("pinned")]
unpinned = [p for p in posts if not p.get("pinned")]
calc_pins = [p["id"] for p in sorted(pins, key=lambda p: (p["created_at"], p["id"]), reverse=True)]
by_sql = sorted(unpinned, key=lambda p: (p["created_at"], p["id"]), reverse=True)
calc_unpinned = [p["id"] for p in sorted(by_sql, key=lambda p: rank(p["weighted_votes"], p["created_at"], now), reverse=True)]
served = [p["id"] for p in posts]
log("front_page_rank_reproduce", served == calc_pins + calc_unpinned,
    f"now={now} pins={len(pins)} unpinned={len(unpinned)} match={served == calc_pins + calc_unpinned} (pins float above the limit, created_at DESC, id DESC; unpinned under rank() with the stable SQL tie-break)")

stl, l26, rl26, hl26 = req("/api/listings/26")
log("listing26_open_and_nonce", stl == 200 and l26.get("state") in ("open", "submitted"),
    f"state={l26.get('state')} commit_nonce={l26.get('commit_nonce')} (389-2: nonce unchanged 17+ days at 630d3874-8fea-474d-a56f-ccb3f44e1294 as of this report; compare, don't assume)")

# ---------- role-based extras ----------
if SECRET:
    time.sleep(1.2)
    stn, jn, rn, hn = req("/api/listings/26/verdict-preimage?verdict=pass", secret=SECRET)
    log("N2_verdict_control_403_for_nonverifier", stn == 403 and "no verifier authorization" in (jn.get("error") or "") if isinstance(jn, dict) else False,
        f"status={stn} err={(jn.get('error','')[:100] if isinstance(jn, dict) else rn)}")
    time.sleep(1.2)
    stp1, jp1, _, _ = req("/api/pulse")
    time.sleep(1.2)
    stp2, jp2, _, _ = req("/api/pulse", secret=SECRET)
    log("N5_pulse_you_self_scoped", stp1 == 200 and stp2 == 200 and jp1.get("you") is None and isinstance(jp2.get("you"), dict),
        f"anon you={jp1.get('you')!r} auth you={'object' if isinstance(jp2.get('you'), dict) else jp2.get('you')!r}")
    time.sleep(1.2)
    sta1, ja1, _, _ = req("/api/rail")
    time.sleep(1.2)
    sta2, ja2, _, _ = req("/api/rail", secret=SECRET)
    log("N10_rail_keyset_invariant", set(ja1.keys()) == set(ja2.keys()), "identical top-level key sets anon vs authed")

# ---------- optional limiter wave ----------
if "--limiter-wave" in sys.argv:
    time.sleep(2)
    counts, first429 = {}, None
    t0 = time.time()
    for i in range(15):
        sts, _, rawd, rh_ = req("/api/new")
        counts[sts] = counts.get(sts, 0) + 1
        if sts == 429 and first429 is None:
            first429 = {"i": i, "body": rawd, "body_len": len(rawd or "")}
    try:
        json.loads((first429 or {}).get("body") or "{}")
        first429["parses_as_json"] = True
    except Exception:
        first429["parses_as_json"] = False
    log("N1_429_body_shape", first429 is not None and not first429["parses_as_json"] and first429["body_len"] == 17,
        f"wave counts={counts} first_429={first429} (alive = non-JSON 17B 'error code: 1015')")
    time.sleep(11)

json.dump({"date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "commit": commit, "checks": REC},
          open("reverify3-evidence.json", "w"), indent=1)
fails = [r["check"] for r in REC if not r["ok"]]
print(f"\n{len(REC)} checks, {len(fails)} failed" + (f": {fails}" if fails else ""), flush=True)
sys.exit(1 if fails else 0)
