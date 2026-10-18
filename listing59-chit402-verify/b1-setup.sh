#!/usr/bin/env bash
# b1-setup.sh — build the pinned chit402-verify versions for repro-b1.mjs.
# Extracts the pinned npm tarballs (sha256-checked against pins.txt) and
# installs their one runtime dependency (ethers, pinned to the version my
# outputs were produced with). Public npm registry only.
# Usage: bash b1-setup.sh   (creates b1/0.4.2 b1/0.4.4 b1/0.4.5 b1/0.4.7 b1/0.4.8)
set -euo pipefail
cd "$(dirname "$0")"
for v in 0.4.2 0.4.4 0.4.5 0.4.7 0.4.8; do
  ( grep "chit402-verify-$v.tgz" pins.txt ) | sha256sum -c --quiet
  rm -rf "b1/$v"
  mkdir -p "b1/$v"
  tar xzf "npm/chit402-verify-$v.tgz" -C "b1/$v" --strip-components=1
  ( cd "b1/$v" && npm install --omit=dev --no-audit --no-fund ethers@6.17.0 )
done
echo "ready: b1/0.4.2 b1/0.4.4 b1/0.4.5 b1/0.4.7 b1/0.4.8"
