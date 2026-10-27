#!/usr/bin/env bash
# repro-f3.sh — ?format=auditor is documented as a distinct view:
#   OpenAPI /receipt/{taskId}: "format ... json (machine), auditor (policy + totals), or HTML (default)"
#   chit402-verify README: "auditor selective disclosure via ?format=auditor"
# Observed on both live receipts: format=auditor returns the BYTE-IDENTICAL
# body as format=json. (The gateway's VERIFY_ALGORITHM.md now discloses the
# identity — "currently returns the same body" — so this is the residual
# gap in the machine-readable contract and the verifier README.)
set -uo pipefail
for id in xfuel-3155b7d8-4315-44bc-bfdc-bf6b78ff2d15 chit-56e3ee6d-2acb-4cab-8fa4-dfd5f9f31e6f; do
  a=$(curl -fsSL "https://api.chit402.com/receipt/$id?format=json" | sha256sum | cut -d' ' -f1)
  b=$(curl -fsSL "https://api.chit402.com/receipt/$id?format=auditor" | sha256sum | cut -d' ' -f1)
  if [ "$a" = "$b" ]; then r=IDENTICAL; else r=DIFFER; fi
  echo "$id  json=$a  auditor=$b  -> $r"
done
