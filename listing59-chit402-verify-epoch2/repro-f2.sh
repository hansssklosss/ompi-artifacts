#!/usr/bin/env bash
# repro-f2.sh — the chit402-verify 0.4.11 package README documents a
# three-file invocation:
#   `xfuel-verify receipt.json inclusion.json head.json`
# with the safety note "A matching inclusion proof does not make a
# tampered receipt VERIFIED". The 0.4.11 CLI rejects the second positional:
# exit 1, removed_flag, "removed in 0.4: pass one receipt id, url, or file".
# The documented workflow (and its safety note) is unavailable in the
# version that ships it.
set -uo pipefail
cd "$(dirname "$0")"
D=v0411
mkdir -p "$D"
if [ ! -f "$D/dist/cli.js" ]; then
  tar xzf npm/chit402-verify-0.4.11.tgz -C "$D" --strip-components=1
fi
if [ ! -d "$D/node_modules" ]; then
  ( cd "$D" && npm install --no-save --no-audit --no-fund >/dev/null 2>&1 )
fi
echo "--- README claim (package/README.md) ---"
grep -n "inclusion.json head.json" "$D/README.md"
echo "--- observed: 3-arg invocation ---"
( cd "$D" && node dist/cli.js \
    ../raw/receipt-3155.json ../raw/inclusion-3155.json ../raw/tree-head.json --json ) \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('result:', d['result'], '| exit_code:', d['exit_code'], '| reason:', d['reason']); print('message:', d['message'])"
