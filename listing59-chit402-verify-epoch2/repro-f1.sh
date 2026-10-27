#!/usr/bin/env bash
# repro-f1.sh — the chit402-verify 0.4.11 package README documents the
# version output as: `--version` prints `chit402-verify 0.4.6`.
# Observed: it prints `chit402-verify 0.4.11` plus the supported-versions table.
# A literal string pin copied from the README fails; the version it names
# (0.4.6) predates the shipped package by five releases.
set -uo pipefail
cd "$(dirname "$0")"
D=v0411
rm -rf "$D"; mkdir -p "$D"
echo "0c1defae050771efff3b40e7555df2a4e4e45d2323c29179683522a718305120  npm/chit402-verify-0.4.11.tgz" | sha256sum -c --quiet || { echo "tarball pin failed"; exit 3; }
tar xzf npm/chit402-verify-0.4.11.tgz -C "$D" --strip-components=1
[ -d "$D/node_modules" ] || ( cd "$D" && npm install --no-save --no-audit --no-fund >/dev/null 2>&1 )
echo "--- README claim (package/README.md) ---"
grep -n 'prints `chit402-verify 0.4' "$D/README.md"
echo "--- observed output ---"
( cd "$D" && node dist/cli.js --version ) | head -3
echo "--- package.json version ---"
python3 -c "import json; print(json.load(open('$D/package.json'))['version'])"
