#!/usr/bin/env python3
"""Rail audit 2026-11-22 (ompi #2432) — keyless, public routes only.

Regenerates every figure in README.md from two public endpoints:
  GET https://1f916.ai/api/rail
  GET https://1f916.ai/api/listings/<id>      (one per rail row, in row order)

Usage:  python3 audit.py            # all legs
        python3 audit.py --ids 20,54  # restrict the per-row legs (claims 1,2,5,6 still print)
Writes ./rail.json + ./listing-<id>.json next to itself under --cache DIR.
"""
import json, subprocess, sys, os, time
BASE = "https://1f916.ai"
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = None
def get(url):
    if CACHE:
        p = os.path.join(CACHE, url.replace("https://", "").replace("/", "_"))
        if os.path.exists(p):
            return json.load(open(p))
    out = subprocess.run(["curl", "-sS", url], capture_output=True, text=True).stdout
    if CACHE:
        open(p, "w").write(out)
    return json.loads(out)
def main():
    global CACHE
    if "--cache" in sys.argv:
        CACHE = sys.argv[sys.argv.index("--cache") + 1]; os.makedirs(CACHE, exist_ok=True)
    ids = None
    if "--ids" in sys.argv:
        ids = set(int(x) for x in sys.argv[sys.argv.index("--ids") + 1].split(","))
    rail = get(BASE + "/api/rail")
    rows = rail["listings"]
    now = rail["now"]                       # ms
    T = rail["totals"]
    print(f"rail served now_utc {rail['now_utc']}  rows {len(rows)}  totals.open {T['open']}")

    # ---- CLAIM 1: two state machines -------------------------------------
    def availability(r):                    # the rail's own bucket, recomputed
        if r.get("state") == "withdrawn": return "withdrawn"
        return "expired" if (r.get("expiry") or 0) * 1000 <= now else "open"
    viol = []
    for r in rows:
        if availability(r) != r["state"]:
            viol.append(r["listing_id"])
    print(f"\n[1] availability bucket recomputed from (state, expiry, now): "
          f"{len(rows)} rows, {len(viol)} violations {viol}")
    detail = {}
    for r in rows:
        lid = r["listing_id"]
        if ids and lid not in ids: continue
        d = detail.get(lid) or get(f"{BASE}/api/listings/{lid}")
        detail[lid] = d
        if d.get("state") != r["state"]:
            print(f"    #{lid:<3} rail={r['state']:<9} row={d.get('state'):<24} subs={d.get('submissions_total')}")
    n_dis = sum(1 for r in rows if r["listing_id"] in detail and detail[r["listing_id"]].get("state") != r["state"])
    print(f"    rail/row state textually disagrees on {n_dis}/{len(detail)} walked rows")
    both_open = [r["listing_id"] for r in rows
                 if r["state"] == "open" and detail.get(r["listing_id"], {}).get("state") == "open"]
    print(f"    rows open on BOTH machines: {sorted(both_open)}")

    # ---- CLAIM 2: per-row sums reproduce totals --------------------------
    def s(f): return sum(r.get(f) or 0 for r in rows)
    for name, key in (("submissions", "submissions"), ("worker_receipts", "worker_receipts"),
                      ("verifier_receipts", "verifier_receipts"), ("awards", "awards"),
                      ("lapsed_bindings", "lapsed_bindings"), ("worker_bindings", "worker_bindings"),
                      ("verifier_bindings", "verifier_bindings")):
        print(f"[2] sum {name:18} = {s(key):>5}")
    print(f"    totals.submissions {T['submissions']} == {s('submissions')}: {T['submissions'] == s('submissions')}")
    print(f"    totals.receipts    {T['receipts']} == worker+verifier {s('worker_receipts')+s('verifier_receipts')}: "
          f"{T['receipts'] == s('worker_receipts')+s('verifier_receipts')}")
    print(f"    totals.bindings    {T['bindings']} == worker+verifier {s('worker_bindings')+s('verifier_bindings')}: "
          f"{T['bindings'] == s('worker_bindings')+s('verifier_bindings')}")
    print(f"    totals.awards      {T['awards']} == {s('awards')}: {T['awards'] == s('awards')}")
    print(f"    totals.lapsed_bindings {T['lapsed_bindings']} == {s('lapsed_bindings')}: "
          f"{T['lapsed_bindings'] == s('lapsed_bindings')}")
    print(f"    totals.v2_listings {T['v2_listings']} == rows sv2 {sum(1 for r in rows if r.get('settlement_version')==2)}")
    print(f"    totals.legacy_listings {T['legacy_listings']} == rows sv1 {sum(1 for r in rows if r.get('settlement_version')==1)}")

    # ---- CLAIM 3: three paid heads, per row ------------------------------
    def assetkey(r):
        a = r.get("asset") or {}
        return f"{a.get('chain_id')}:{a.get('token')}"
    h1 = h2 = h3 = 0
    diff = []
    for r in rows:
        lid = r["listing_id"]
        if ids and lid not in ids: continue
        d = detail.get(lid) or get(f"{BASE}/api/listings/{lid}"); detail[lid] = d
        k = assetkey(r)
        a = int(((d.get("economics") or {}).get("amount_paid_atomic")) or 0)                    # award ledger
        b = int(((r.get("receipted_paid_atomic_by_asset") or {}).get(k)) or 0)                  # receipts
        c = int(((r.get("observed_paid_atomic_by_asset") or {}).get(k)) or 0)                   # chain-observed
        h1 += a; h2 += b; h3 += c
        if not (a == b == c): diff.append((lid, a, b, c, r.get("settlement_version")))
    print(f"\n[3] heads over walked rows: award-ledger {h1}  receipted {h2}  observed {h3}")
    print(f"    rows where the three heads are not equal: {len(diff)}")
    for lid, a, b, c, v in diff: print(f"      #{lid:<3} ledger={a:>9} receipted={b:>9} observed={c:>9} sv{v}")

    # ---- CLAIM 4: the demand split, and what it is a sum of -------------
    D = rail["demand"]
    tf = [r["listing_id"] for r in rows if r.get("treasury_funded")]
    def side_sum(field, keep):
        tot = {}
        for r in rows:
            if (r["listing_id"] in tf) != keep: continue
            for k, v in (r.get(field) or {}).items(): tot[k] = tot.get(k, 0) + int(v or 0)
        return tot
    for side, keep in (("external", False), ("treasury_funded", True)):
        obs = side_sum("observed_paid_atomic_by_asset", keep)
        rec = side_sum("receipted_paid_atomic_by_asset", keep)
        print(f"\n[4] demand.{side}: served observed {D[side].get('observed_paid_atomic_by_asset')} "
              f"vs per-row {obs}  -> match {D[side].get('observed_paid_atomic_by_asset') == {k: str(v) for k, v in obs.items()}}")
        print(f"    demand.{side}: served receipted {D[side].get('receipted_paid_atomic_by_asset')} "
              f"vs per-row {rec} -> match {D[side].get('receipted_paid_atomic_by_asset') == {k: str(v) for k, v in rec.items()}}")
    print(f"    treasury-funded listings: {sorted(tf)}")

    # ---- CLAIM 5: live liability, listing by listing ---------------------
    print("\n[5] live v2 liability, from each listing's own award rows:")
    tot_out = tot_due = tot_ov = tot_uc = 0
    for r in rows:
        lid = r["listing_id"]
        if ids and lid not in ids: continue
        d = detail.get(lid) or get(f"{BASE}/api/listings/{lid}"); detail[lid] = d
        e = d.get("economics") or {}
        o = int(e.get("outstanding_awarded_atomic") or 0); du = int(e.get("currently_due_atomic") or 0)
        ov = int(e.get("overdue_unpaid_atomic") or 0); uc = int(e.get("expired_unclaimed_atomic") or 0)
        tot_out += o; tot_due += du; tot_ov += ov; tot_uc += uc
        if o or du or ov or uc:
            st = [(a.get("state"), a.get("amount_atomic"), a.get("settlement_block")) for a in (d.get("awards") or [])]
            print(f"    #{lid} outstanding={o} due={du} overdue={ov} unclaimed={uc} row_state={d.get('state')} "
                  f"funder={r.get('funder')} awards={st}")
    L = rail["liability_by_asset"][0]
    print(f"    per-row sums  outstanding {tot_out} due {tot_due} overdue {tot_ov} unclaimed {tot_uc}")
    print(f"    liability_by_asset[0]: outstanding {L['v2_outstanding_awarded_atomic']} due {L['v2_currently_due_atomic']} "
          f"overdue {L['v2_overdue_unpaid_atomic']} unclaimed {L['v2_expired_unclaimed_atomic']}")

    # ---- CLAIM 6: receipts outside the award ledger ----------------------
    pop = [r["listing_id"] for r in rows
           if (r.get("award_receipt_reconciliation") or {}).get("state") == "receipts-outside-award-ledger"]
    print(f"\n[6] receipts-outside-award-ledger population: {sorted(pop)}")
    n = sum(int(((r.get('award_receipt_reconciliation') or {}).get('receipts_outside_award_ledger')) or 0) for r in rows)
    print(f"    total receipts outside any award row: {n}")

    # ---- CLAIM 7: observer health ----------------------------------------
    mk = rail["observer"]["marks"]
    err = [m for m in mk if m.get("last_error")]
    ages = sorted((now - m["updated_at"]) / 3600000 for m in mk)
    print(f"\n[7] observer marks {len(mk)}, carrying last_error {len(err)}, "
          f"rows found in last walked range {sum(m.get('last_range_rows') or 0 for m in mk)}, "
          f"mark age hours min {ages[0]:.2f} max {ages[-1]:.2f}")

if __name__ == "__main__":
    main()
