#!/usr/bin/env bash
# repro-b2.sh — B2: OpenAPI documents format=auditor as a distinct view
# ("policy + totals"); the live API serves byte-identical bytes to format=json.
# No Chit402 help: two public GETs + the public OpenAPI document.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p scratch && cd scratch
base=https://api.chit402.com
id=chit-56e3ee6d-2acb-4cab-8fa4-dfd5f9f31e6f
curl -sS "$base/receipt/$id?format=json" -o b2.json
curl -sS "$base/receipt/$id?format=auditor" -o b2.aud
curl -sS "$base/openapi.json" -o b2.openapi
hj=$(sha256sum b2.json | cut -d' ' -f1)
ha=$(sha256sum b2.aud | cut -d' ' -f1)
echo "sha256 format=json   : $hj"
echo "sha256 format=auditor: $ha"
python3 - "$hj" "$ha" <<'EOF'
import json, sys
hj, ha = sys.argv[1], sys.argv[2]
o = json.load(open('b2.openapi'))
fmt = [p for p in o['paths']['/receipt/{taskId}']['get']['parameters'] if p['name'] == 'format'][0]
print('OpenAPI format enum   :', fmt['schema']['enum'])
print('OpenAPI description   :', fmt.get('description'))
print('byte-identical        :', hj == ha)
print('B2 ' + ('FIRES: the documented auditor view is not served' if hj == ha else 'does not fire'))
EOF
