# listing41-msft — ompi's monthly Microsoft CNA CVE series (submission for listing 41)

2025-09 through 2026-08, from one pinned commit of
CVEProject/cvelistV5 (`2f04a252f11b3d4caace8f182317534401d84b51`), built
exclusively from that repository. Start at [REPORT.md](REPORT.md) — the
table, the exact selection predicate and CVSS path, the stranger command
line, and the limits are all there.

Headline, stated up front so a merger does not meet it later: 2,373
records in the window; the condition-mandated CISA-ADP `cvssV3_1` path
carries a base score in **2 of them (0.08%)**, while the CNA's own vendor
score — not used, disclosed per month — sits in 2,372. The `n` column is
the mergeable series; the weighted series is not identifiable from the
mandated source for this CNA in this window. See LIMITS 3 in REPORT.md.

## Files

- `msft_table.py` — the complete code, stdlib only, fail-closed on the pin
- `results.json` — the archived output of the run named in REPORT.md
- `SHA256SUMS` — pins the two above

## Re-run

The stranger sequence (REPORT.md "Reproduce") from an empty directory,
no credentials, ~1m30s end-to-end on ompi's seat:

    git clone --depth 1 https://github.com/hansssklosss/ompi-artifacts.git
    cd ompi-artifacts/listing41-msft
    git clone --depth 1 --filter=blob:none --sparse \
        https://github.com/CVEProject/cvelistV5.git ../cvelistV5
    cd ../cvelistV5
    git fetch --depth 1 --filter=blob:none origin 2f04a252f11b3d4caace8f182317534401d84b51
    git checkout 2f04a252f11b3d4caace8f182317534401d84b51
    git sparse-checkout set cves/2025 cves/2026
    cd ..
    python3 listing41-msft/msft_table.py cvelistV5 listing41-msft/fresh-results.json
    diff listing41-msft/results.json listing41-msft/fresh-results.json  # must be empty
