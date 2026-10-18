#!/usr/bin/env bash
# fetch.sh — part (a) of listing-59. Fresh public-material fetch for offline
# verification. No Chit402 help: four public HTTPS GETs, pinned by sha256.
# Re-run: bash fetch.sh  (writes raw/*.json + raw/manifest.sha256)
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p raw
base=https://api.chit402.com
{
  curl -sS "$base/receipt/chit-56e3ee6d-2acb-4cab-8fa4-dfd5f9f31e6f?format=json" -o raw/receipt.json -w 'receipt.json  http=%{http_code}\n'
  curl -sS "$base/.well-known/jwks.json" -o raw/jwks.json -w 'jwks.json  http=%{http_code}\n'
  curl -sS "$base/.well-known/issuer-history.json" -o raw/issuer-history.json -w 'issuer-history.json  http=%{http_code}\n'
  curl -sS "$base/v1/receipts/xfuel-56e3ee6d-2acb-4cab-8fa4-dfd5f9f31e6f/inclusion" -o raw/inclusion.json -w 'inclusion.json  http=%{http_code}\n'
} | tee raw/fetch.out
(cd raw && sha256sum receipt.json jwks.json issuer-history.json inclusion.json > manifest.sha256)
cat raw/manifest.sha256
