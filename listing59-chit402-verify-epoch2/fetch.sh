#!/usr/bin/env bash
# fetch.sh — pin every public input by sha256 so verify.mjs refuses swapped bytes.
# Usage: bash fetch.sh   (writes raw/ + raw/manifest.sha256)
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p raw
B=https://api.chit402.com
fetch() { # name url
  curl -fsSL "$2" -o "raw/$1"
  echo "fetched $1 ($(wc -c < "raw/$1") bytes)"
}
fetch receipt-3155.json            "$B/receipt/xfuel-3155b7d8-4315-44bc-bfdc-bf6b78ff2d15?format=json"
fetch receipt-shell-56e3.json      "$B/receipt/chit-56e3ee6d-2acb-4cab-8fa4-dfd5f9f31e6f?format=json"
fetch jwks.json                    "$B/.well-known/jwks.json"
fetch issuer-history.json          "$B/.well-known/issuer-history.json"
fetch tree-epoch.json              "$B/v1/receipts/tree/epoch"
fetch tree-head.json               "$B/v1/receipts/tree/head"
fetch inclusion-3155.json          "$B/v1/receipts/xfuel-3155b7d8-4315-44bc-bfdc-bf6b78ff2d15/inclusion"
fetch inclusion-56e3.json          "$B/v1/receipts/xfuel-56e3ee6d-2acb-4cab-8fa4-dfd5f9f31e6f/inclusion"
fetch inclusion-56e3-size34.json   "$B/v1/receipts/xfuel-56e3ee6d-2acb-4cab-8fa4-dfd5f9f31e6f/inclusion?tree_size=34"
fetch consistency-34-43.json       "$B/v1/receipts/tree/consistency?first=34&second=43"
( cd raw && sha256sum receipt-3155.json receipt-shell-56e3.json jwks.json issuer-history.json \
    tree-epoch.json tree-head.json inclusion-3155.json inclusion-56e3.json \
    inclusion-56e3-size34.json consistency-34-43.json > manifest.sha256 )
echo "manifest written: raw/manifest.sha256"
