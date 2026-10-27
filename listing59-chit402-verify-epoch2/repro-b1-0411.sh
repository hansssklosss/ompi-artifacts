#!/usr/bin/env bash
# repro-b1-0411.sh — re-run round-1's B1 forgery (a KMS-signed TREE-HEAD JWS
# presented as the issuer signature of a receipt with unsigned economics)
# against chit402-verify 0.4.11. Round 1: accepted in 0.4.2/0.4.4/0.4.5/0.4.7;
# fixed in 0.4.8 via typ_mismatch. Expected here: "B1 does not fire".
set -uo pipefail
cd "$(dirname "$0")"
D=v0411
mkdir -p "$D"
[ -f "$D/dist/cli.js" ] || tar xzf npm/chit402-verify-0.4.11.tgz -C "$D" --strip-components=1
[ -d "$D/node_modules" ] || ( cd "$D" && npm install --no-save --no-audit --no-fund >/dev/null 2>&1 )
node repro-b1.mjs "$D"
