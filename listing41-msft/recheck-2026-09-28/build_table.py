#!/usr/bin/env python3
"""Microsoft CNA panel: monthly CVE publication table, 2025-09 .. 2026-08.

Built exclusively from CVEProject/cvelistV5 at one named commit (sparse
checkout of cves/2024, cves/2025, cves/2026). No other data source.

REQUIRED TABLE — selection predicate (exact):
  cveMetadata.assignerShortName == "microsoft"
  cveMetadata.state == "PUBLISHED"
  "2025-09-01T00:00:00Z" <= cveMetadata.datePublished < "2026-09-01T00:00:00Z"
  month = cveMetadata.datePublished truncated to YYYY-MM (UTC)

REQUIRED TABLE — CVSS source (exact JSON path):
  containers.adp[?providerMetadata.shortName == "CISA-ADP"]
    .metrics[?key starts with "cvssV" and value.baseScore is a number]
  A record is "rated" iff such a base score exists. Per record, the first
  CISA-ADP container in array order is used; within its metrics the version
  preference is cvssV3_1, else cvssV4_0, else the first cvssV* key.
  NVD scores and vendor severity labels are NOT used in the required table.

SUPPLEMENTARY TABLE (clearly separate, NOT the stated source):
  vendor CNA-provided score: containers.cna.metrics[?cvssV3_1].baseScore
  (first cvssV* in the cna metrics array), same month bucket.

Usage:
  python3 build_table.py <path-to-cvelistV5-worktree>

stdout is the full deliverable data block: paste it verbatim into the README
and diff a re-run's stdout against it.
"""
import datetime
import json
import os
import sys
from collections import defaultdict

WINDOW_START = "2025-09-01T00:00:00Z"
WINDOW_END = "2026-09-01T00:00:00Z"  # exclusive
ID_YEARS = ("2024", "2025", "2026")


def cisa_cvss(rec):
    """(cvss_key, base_score) from the CISA-ADP Vulnrichment ADP container,
    or None. Deterministic as documented in the module docstring."""
    for container in (rec.get("containers") or {}).get("adp") or []:
        if (container.get("providerMetadata") or {}).get("shortName") != "CISA-ADP":
            continue
        found = {}
        for m in container.get("metrics") or []:
            if not isinstance(m, dict):
                continue
            for k, v in m.items():
                if isinstance(k, str) and k.startswith("cvssV") and isinstance(v, dict) \
                        and isinstance(v.get("baseScore"), (int, float)) and k not in found:
                    found[k] = (v["baseScore"], v)
        if not found:
            continue
        for pref in ("cvssV3_1", "cvssV4_0"):
            if pref in found:
                return pref, found[pref][0], found[pref][1]
        for k, (score, obj) in found.items():
            return k, score, obj
    return None


def vendor_cvss(rec):
    """(cvss_key, base_score) from the vendor CNA container, or None."""
    for m in (rec.get("containers") or {}).get("cna", {}).get("metrics") or []:
        if not isinstance(m, dict):
            continue
        for k, v in m.items():
            if isinstance(k, str) and k.startswith("cvssV") and isinstance(v, dict) \
                    and isinstance(v.get("baseScore"), (int, float)):
                return k, v["baseScore"]
    return None


def second_tuesday(y, m):
    first = datetime.date(y, m, 1).weekday()
    return 1 + (1 - first) % 7 + 7


def main(root):
    months = {"req": defaultdict(lambda: [0, 0, 0.0]),
              "sup": defaultdict(lambda: [0, 0, 0.0])}
    cisa_scored = []
    cisa_containers = 0
    cisa_ssvc_only = 0
    other_adp = defaultdict(int)
    stats = dict(files=0, parse_errors=[], ms_any=0, ms_pub_any=0, ms_pub=0,
                 ms_pub_by_id_year=defaultdict(int),
                 non_pub_in_window=[])
    cadence = dict(patch_tue=0, tue=0, total=0)
    lags = []  # dateReserved -> datePublished, days, in-window PUBLISHED
    reserved_n = 0
    assigned_n = 0
    month_top = defaultdict(list)  # month -> [day, ...]
    credits_n = refs_n = 0

    for year in ID_YEARS:
        yd = os.path.join(root, "cves", year)
        if not os.path.isdir(yd):
            stats["parse_errors"].append("missing year dir: %s" % yd)
            continue
        for bucket in sorted(os.listdir(yd)):
            bd = os.path.join(yd, bucket)
            if not os.path.isdir(bd):
                continue
            for fname in sorted(os.listdir(bd)):
                if not fname.endswith(".json"):
                    continue
                stats["files"] += 1
                try:
                    with open(os.path.join(bd, fname), encoding="utf-8") as fh:
                        rec = json.load(fh)
                except Exception as e:  # noqa: BLE001
                    stats["parse_errors"].append("%s/%s: %r" % (year, fname, e))
                    continue
                meta = rec.get("cveMetadata") or {}
                if meta.get("assignerShortName") != "microsoft":
                    continue
                stats["ms_any"] += 1
                if meta.get("state") == "PUBLISHED":
                    stats["ms_pub_any"] += 1
                dp = meta.get("datePublished") or ""
                if not (WINDOW_START <= dp < WINDOW_END):
                    continue
                # in-window microsoft record (any state)
                if meta.get("state") != "PUBLISHED":
                    stats["non_pub_in_window"].append(
                        (fname, meta.get("state"), dp, meta.get("dateAssigned")))
                    continue
                stats["ms_pub"] += 1
                stats["ms_pub_by_id_year"][year] += 1
                month = dp[:7]
                d = datetime.datetime.fromisoformat(dp.replace("Z", "+00:00")).date()
                cadence["total"] += 1
                if d.strftime("%a") == "Tue":
                    cadence["tue"] += 1
                if d.day == second_tuesday(d.year, d.month):
                    cadence["patch_tue"] += 1
                month_top[month].append((d.day, 1))
                dr = meta.get("dateReserved")
                if dr:
                    reserved_n += 1
                    lags.append((d - datetime.datetime.fromisoformat(
                        dr.replace("Z", "+00:00")).date()).days)
                if meta.get("dateAssigned"):
                    assigned_n += 1
                cna = (rec.get("containers") or {}).get("cna", {})
                if cna.get("credits"):
                    credits_n += 1
                if cna.get("references"):
                    refs_n += 1
                # required: CISA-ADP
                for a in (rec.get("containers") or {}).get("adp") or []:
                    sn = (a.get("providerMetadata") or {}).get("shortName")
                    if sn == "CISA-ADP":
                        cisa_containers += 1
                    else:
                        other_adp[sn] += 1
                months["req"][month][0] += 1
                got = cisa_cvss(rec)
                if got:
                    key, score, obj = got
                    months["req"][month][1] += 1
                    months["req"][month][2] += float(score)
                    cisa_scored.append((fname, month, key, score,
                                        obj.get("vectorString")))
                else:
                    cisa_ssvc_only += 1
                # supplementary: vendor
                v = vendor_cvss(rec)
                months["sup"][month][0] += 1
                if v:
                    months["sup"][month][1] += 1
                    months["sup"][month][2] += float(v[1])

    def table(rows, label):
        print(label)
        print()
        print("| month | n | rated | sum(base) | mean |")
        print("|---|---|---|---|---|")
        tn = tr = 0
        ts = 0.0
        for month in sorted(rows):
            n, rated, s = rows[month]
            mean = "%.2f" % (s / rated) if rated else "-"
            print("| %s | %d | %d | %.1f | %s |" % (month, n, rated, s, mean))
            tn += n
            tr += rated
            ts += s
        print()
        print("TOTALS: n=%d rated=%d sum=%.1f mean_over_rated=%s" % (
            tn, tr, ts, ("%.2f" % (ts / tr)) if tr else "-"))
        print()

    all_months = sorted(set(months["req"]) | set(months["sup"]))
    # fill months with n>0 but no rated rows so both tables share keys
    for m in all_months:
        months["req"].setdefault(m, [0, 0, 0.0])
        months["sup"].setdefault(m, [0, 0, 0.0])

    print("# Required table — stated source: CISA-ADP \"Vulnrichment\" ADP container")
    print("# containers.adp[?providerMetadata.shortName=='CISA-ADP'].metrics[?cvssV*].baseScore")
    table(months["req"], "Predicate: assignerShortName=='microsoft', state=='PUBLISHED', "
          "datePublished in [2025-09-01, 2026-09-01) UTC.")
    print("# Supplementary table — vendor CNA-provided cvssV3_1 (NOT the stated source)")
    print("# containers.cna.metrics[?cvssV*].baseScore; shown so the merged panel has data;")
    print("# the required table above does not use it.")
    table(months["sup"], "Same population, same month bucket.")

    print("## Completeness")
    print("id years scanned: %s" % ", ".join(ID_YEARS))
    print("files_scanned=%d parse_errors=%d" % (stats["files"], len(stats["parse_errors"])))
    for e in stats["parse_errors"][:10]:
        print("  %s" % e)
    print("microsoft records any state/date: %d" % stats["ms_any"])
    print("microsoft PUBLISHED any date: %d" % stats["ms_pub_any"])
    print("in-window PUBLISHED: %d" % stats["ms_pub"])
    print("in-window PUBLISHED by id-year: %s" %
          dict(sorted(stats["ms_pub_by_id_year"].items())))
    print("in-window non-PUBLISHED microsoft records (excluded): %s" %
          (stats["non_pub_in_window"] or "none"))
    print("CISA-ADP containers in-window: %d (SSVC-only: %d, with CVSS base score: %d)" %
          (cisa_containers, cisa_ssvc_only, len(cisa_scored)))
    print("other ADP providers in-window: %s" % dict(other_adp) or "none")
    print("CISA-ADP coverage of in-window records: %.2f%% (%d/%d)" % (
        100.0 * len(cisa_scored) / stats["ms_pub"], len(cisa_scored), stats["ms_pub"]))
    vendor_rated = months["sup"] and sum(r[1] for r in months["sup"].values())
    print("vendor CNA cvss in-window: %d/%d (%.2f%%)" % (
        vendor_rated, stats["ms_pub"], 100.0 * vendor_rated / stats["ms_pub"]))
    print("CISA-ADP-scored records (file, month, key, score, vector):")
    for row in cisa_scored:
        print("  %s %s %s %.1f %s" % row)
    print()
    print("## Cadence (LIMITS input a)")
    print("published on a Tuesday: %d/%d (%.1f%%)" % (
        cadence["tue"], cadence["total"], 100.0 * cadence["tue"] / cadence["total"]))
    print("published on the month's 2nd Tuesday (Patch Tuesday): %d/%d (%.1f%%)" % (
        cadence["patch_tue"], cadence["total"], 100.0 * cadence["patch_tue"] / cadence["total"]))
    for month in sorted(month_top):
        days = defaultdict(int)
        for dd, _ in month_top[month]:
            days[dd] += 1
        top = sorted(days.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        print("%s top days: %s" % (month, ", ".join("%d:%d" % t for t in top)))
    print()
    print("## Reserve-to-publish lag (LIMITS input a; completeness of id-year tail)")
    print("in-window with dateReserved: %d; with dateAssigned: %d" % (reserved_n, assigned_n))
    if lags:
        l = sorted(lags)
        n = len(l)
        print("dateReserved->datePublished lag (days): median=%d p90=%d max=%d"
              % (l[n // 2], l[int(n * 0.9)], l[-1]))
        print("lags >30d: %d; >90d: %d; >180d: %d"
              % (sum(1 for x in l if x > 30), sum(1 for x in l if x > 90),
                 sum(1 for x in l if x > 180)))
    print("## Attribution (LIMITS input b)")
    print("cna.credits present: %d/%d; cna.references present: %d/%d" % (
        credits_n, stats["ms_pub"], refs_n, stats["ms_pub"]))
    print()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
