#!/bin/sh
# ompi listing-59 artifact: fetch the five public documents, record their hashes.
# Run from the artifact root. Nothing is sent; all reads are GET.
set -eu
mkdir -p raw
base=https://api.chit402.com
id=chit-56e3ee6d-2acb-4cab-8fa4-dfd5f9f31e6f
task=xfuel-56e3ee6d-2acb-4cab-8fa4-dfd5f9f31e6f

fetch() { # url outfile
  curl -sS --fail -D "raw/$2.hdr" -o "raw/$2" "$1"
  echo "saved raw/$2"
}

fetch "$base/receipt/$id?format=json" receipt.json
fetch "$base/.well-known/issuer-history.json" issuer-history.json
fetch "$base/.well-known/jwks.json" jwks.json
fetch "$base/v1/receipts/$task/inclusion" inclusion.json
fetch "$base/v1/receipts/tree/epoch" epoch.json

echo
echo "server timestamps (Date headers):"
grep -i '^date:' raw/*.hdr
echo
sha256sum raw/*.json
