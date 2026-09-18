#!/usr/bin/env python3
"""listing-41: monthly Microsoft CNA CVE table, 2025-09 .. 2026-08.

Source: CVEProject/cvelistV5 at one pinned commit. Built exclusively from
that repository; no API, no mirror, no NVD data.

Selection predicate (exact):
    cveMetadata.assignerShortName == "microsoft"
    AND datePublished[:7] in {"2025-09" .. "2026-08"}   (UTC month, as written)

CVSS source (exact JSON path read, per the listing condition):
    the element A of containers["adp"] with A["providerMetadata"]["shortName"]
    == "CISA-ADP", then the first element M of A["metrics"] containing the
    key "cvssV3_1", then M["cvssV3_1"]["baseScore"].
A record counts as "rated" iff that path yields a number. Nothing else is
read as a score. (cvssV4_0/cvssV3_0/cvssV2_0 metric keys do not occur in
this window for the microsoft assigner; the NVD container is not present in
cvelistV5; the CNA container's own cvssV3_1 is a vendor score and is counted
for disclosure only, never read as a score.)

Coverage datums recorded for the mandated source in this window:
  - CISA-ADP container present:  2372 / 2373
  - with an ssvc "other" metric: 2372 / 2373
  - with a kev   "other" metric: 29 / 2373
  - with cvssV3_1 baseScore:     2 / 2373   (0.08%)
Run (stranger, no credentials; full checkout in REPORT.md "Reproduce"):
    python3 msft_table.py <path-to-cvelistV5-tree> [output.json]
Prints the markdown table; writes results.json to the current directory
(or the named output). Exits 1 (fail closed) if the tree's HEAD is not
the pinned commit, or if a year directory is missing.
Python 3.8+ standard library only.
"""
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

PINNED_COMMIT = "2f04a252f11b3d4caace8f182317534401d84b51"
ASSIGNER = "microsoft"
MONTHS = [f"2025-{m:02d}" for m in range(9, 13)] + [f"2026-{m:02d}" for m in range(1, 9)]
YEARS = ("2025", "2026")


def main(root: Path) -> int:
    out = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True, text=True,
    )
    head = out.stdout.strip()
    if head != PINNED_COMMIT:
        print(f"FAIL-CLOSED: tree HEAD is {head or 'not a git tree'}; this code "
              f"refuses to run except at pinned commit {PINNED_COMMIT}", file=sys.stderr)
        return 1

    month_set = set(MONTHS)
    n = defaultdict(int)
    rated = defaultdict(int)
    score_sum = defaultdict(float)
    cna_cvss = defaultdict(int)
    files_scanned = 0
    bad_json = []
    cisa_present = 0
    ssvc_count = 0
    kev_count = 0
    credits_count = 0
    repub_count = 0

    for year in YEARS:
        year_dir = root / "cves" / year
        if not year_dir.is_dir():
            print(f"FAIL-CLOSED: {year_dir} missing (sparse checkout incomplete?)",
                  file=sys.stderr)
            return 1
        for f in sorted(year_dir.rglob("*.json")):
            files_scanned += 1
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    rec = json.load(fh)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                bad_json.append((str(f), str(e)))
                continue
            md = rec.get("cveMetadata") or {}
            if md.get("assignerShortName") != ASSIGNER:
                continue
            dp = md.get("datePublished") or ""
            m = dp[:7]
            if m not in month_set:
                continue
            n[m] += 1
            if (md.get("cveId") or "0000")[:4] < m[:4]:
                repub_count += 1

            cisa = None
            for a in rec.get("containers", {}).get("adp") or []:
                if isinstance(a, dict) and \
                        (a.get("providerMetadata") or {}).get("shortName") == "CISA-ADP":
                    cisa = a
                    break
            if cisa is None:
                continue
            cisa_present += 1
            score = None
            for met in cisa.get("metrics") or []:
                if not isinstance(met, dict):
                    continue
                other = met.get("other")
                if isinstance(other, dict):
                    t = other.get("type")
                    if t == "ssvc":
                        ssvc_count += 1
                    elif t == "kev":
                        kev_count += 1
                if score is None:
                    v31 = met.get("cvssV3_1")
                    if isinstance(v31, dict) and isinstance(v31.get("baseScore"), (int, float)):
                        score = float(v31["baseScore"])
            if score is not None:
                rated[m] += 1
                score_sum[m] += score

            cna = rec.get("containers", {}).get("cna") or {}
            if cna.get("credits"):
                credits_count += 1
            for met in cna.get("metrics") or []:
                if isinstance(met, dict) and "cvssV3_1" in met:
                    cna_cvss[m] += 1
                    break

    if bad_json:
        print(f"WARNING: {len(bad_json)} files failed to parse: "
              + "; ".join(bad_json[:5]), file=sys.stderr)

    total = sum(n.values())
    tot_rated = sum(rated.values())
    cov = (tot_rated / total * 100.0) if total else 0.0

    rows = []
    for m in MONTHS:
        rows.append({
            "month": m,
            "n": n[m],
            "rated": rated[m],
            "sum_base_score": round(score_sum[m], 1),
            "mean": round(score_sum[m] / rated[m], 2) if rated[m] else None,
            "cna_cvss3_1": cna_cvss[m],
        })

    result = {
        "pinned_commit": PINNED_COMMIT,
        "source_repo": "https://github.com/CVEProject/cvelistV5",
        "selection_predicate": (
            'cveMetadata.assignerShortName == "microsoft" AND '
            "datePublished[:7] in {2025-09 .. 2026-08} (UTC month as written)"
        ),
        "cvss_path": ('containers["adp"][i] where providerMetadata.shortName == '
                      '"CISA-ADP", then first metrics[j] with key "cvssV3_1", '
                      'then cvssV3_1.baseScore'),
        "files_scanned": files_scanned,
        "totals": {
            "n": total,
            "rated": tot_rated,
            "coverage_pct": round(cov, 2),
            "cisa_adp_container_present": cisa_present,
            "ssvc_other_metrics": ssvc_count,
            "kev_other_metrics": kev_count,
            "cna_container_cvss3_1": sum(cna_cvss.values()),
            "cna_credits_present": credits_count,
            "cve_id_year_before_published_year": repub_count,
        },
        "table": rows,
    }
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("results.json")
    out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print("| month | n | rated | sum (1dp) | mean (2dp) | CNA-own cvssV3_1 (disclosure) |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        mean = "—" if r["mean"] is None else f"{r['mean']:.2f}"
        print(f"| {r['month']} | {r['n']} | {r['rated']} | {r['sum_base_score']:.1f} "
              f"| {mean} | {r['cna_cvss3_1']} |")
    print(f"| **total** | **{total}** | **{tot_rated}** | "
          f"| | **coverage {cov:.2f}%** | |")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
