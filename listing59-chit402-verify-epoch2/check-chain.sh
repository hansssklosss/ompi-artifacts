#!/usr/bin/env bash
# check-chain.sh — on-chain corroboration via PUBLIC RPCs only.
# Usage: bash check-chain.sh   (writes nothing outside ./chain-tmp)
#   Base:   mainnet.base.org, base-rpc.publicnode.com, base.drpc.org
#   Solana: api.mainnet-beta.solana.com
# Prints, per provider: the anchor tx (sender, self-transfer, calldata, status,
# block timestamp), the payment tx (USDC Transfer logs + token sender), and the
# Solana memo tx (slot, fee payer, memo, status). No accounts, no keys.
set -uo pipefail
cd "$(dirname "$0")"
T=chain-tmp; mkdir -p "$T"

ANCHOR_TX=0x9ef64e3a2f00ac018041f5ff2b2d26144bf9a7c6dacfe050f805cdf3db5b4d8a
PAY_TX=0x731e4fdc70a8dba370c579c23e8520d2edcde052f28abaf3ed26c95c8603116f
ANCHOR_FROM=0x1844d1f5fe42aff1cce6f776514fd40374079582
USDC=0x833589fcd6edb6e08f4c7c32d4f71b54bda02913
PAY_TO=0x23f713411c30bbd9a989c9cbc22eb0b55f7f7334
SOL_SIG=228pgHYNgwHPCyKDUi1N7342ixZpq3HMkny6x1H4KXA1jeEtBQvJaL8d4yNwVQQWNrns7zwBEUzuua3gDZ7yF3df
SOL_FEE_PAYER=8ef3GtYNuQ6P2ANxLMPUXTAo9BhfJJqMx6cdDVh7JM4U
SOL_SLOT=461859546
ANCHOR_CALLEDATA=0x36213397e111e8bfd2086d592670925e5f8bb00141ce6088a8e5de617da4d2ee

rpc() { # url method params out
  curl -fsSL -m 25 -X POST "$1" -H 'content-type: application/json' \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"$2\",\"params\":$3}" -o "$4"
}

py_anchor_tx() { python3 - "$1" "$ANCHOR_FROM" "$ANCHOR_CALLEDATA" <<'EOF'
import json, sys
t = (json.load(open(sys.argv[1])).get("result") or {})
if not t: print("  anchor tx: NOT FOUND"); sys.exit(0)
print(f"  anchor tx: from={t['from']} (== pinned anchor EOA: {t['from'].lower()==sys.argv[2].lower()})")
print(f"  self-transfer (to==from): {t['to'].lower()==t['from'].lower()}  value={t['value']}")
print(f"  calldata == signed root: {t['input'].lower()==sys.argv[3].lower()}")
open("chain-tmp/bn.txt", "w").write(t["blockNumber"])
EOF
}
py_block() { python3 - "$1" <<'EOF'
import json, sys
from datetime import datetime, timezone
b = (json.load(open(sys.argv[1])).get("result") or {})
if not b: print("  anchor block: NOT FOUND"); sys.exit(0)
ts = int(b["timestamp"], 16)
print(f"  anchor block: {int(b['number'],16)} timestamp={ts} ({datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()})")
EOF
}
py_receipt() { python3 - "$1" <<'EOF'
import json, sys
r = (json.load(open(sys.argv[1])).get("result") or {})
if not r: print("  receipt: NOT FOUND"); sys.exit(0)
print(f"  tx status: {r['status']} (0x1 = success)")
EOF
}
py_pay() { python3 - "$1" "$USDC" "$PAY_TO" <<'EOF'
import json, sys
r = (json.load(open(sys.argv[1])).get("result") or {})
if not r: print("  payment receipt: NOT FOUND"); sys.exit(0)
usdc, payto = sys.argv[2].lower(), sys.argv[3].lower()
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
n, ok = 0, True
for lg in r.get("logs", []):
    if lg["topics"] and lg["topics"][0].lower() == TRANSFER and lg["address"].lower() == usdc:
        n += 1
        frm, to, amt = "0x" + lg["topics"][1][-40:], "0x" + lg["topics"][2][-40:], int(lg["data"], 16)
        print(f"  payment USDC Transfer #{n}: {frm} -> {to}  amount={amt}  (to == signed payee: {to.lower()==payto})")
        if to.lower() != payto or amt != 2000: ok = False
print(f"  payment: status={r['status']}  usdc_transfers={n}  exactly_one_to_signed_payee_for_2000={ok}")
EOF
}

for u in https://mainnet.base.org https://base-rpc.publicnode.com https://base.drpc.org; do
  echo "== Base provider: $u =="
  if rpc "$u" eth_getTransactionByHash "[\"$ANCHOR_TX\"]" "$T/atx.json"; then
    py_anchor_tx "$T/atx.json"
    bn=$(cat "$T/bn.txt" 2>/dev/null || echo 0x)
    rpc "$u" eth_getBlockByNumber "[\"$bn\", false]" "$T/blk.json" && py_block "$T/blk.json" || true
    rpc "$u" eth_getTransactionReceipt "[\"$ANCHOR_TX\"]" "$T/arc.json" && py_receipt "$T/arc.json" || true
    rpc "$u" eth_getTransactionReceipt "[\"$PAY_TX\"]" "$T/prc.json" && py_pay "$T/prc.json" || true
  else
    echo "  (provider unreachable or errored this round)"
  fi
done

echo "== Solana provider: api.mainnet-beta.solana.com =="
if curl -fsSL -m 30 -X POST https://api.mainnet-beta.solana.com -H 'content-type: application/json' \
  -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"getTransaction\",\"params\":[\"$SOL_SIG\",{\"encoding\":\"jsonParsed\",\"maxSupportedTransactionVersion\":0}]}" -o "$T/sol.json"; then
  python3 - "$T/sol.json" "$SOL_FEE_PAYER" "$SOL_SLOT" <<'EOF'
import json, sys, base64
d = json.load(open(sys.argv[1]))
res = d.get("result") or {}
t = res.get("transaction") or {}
if not t: print("  solana tx: NOT FOUND (rate limit?)"); sys.exit(0)
msg = t.get("message") or {}
keys = msg.get("accountKeys") or []
fee_payer = keys[0].get("pubkey") if keys else None
memo = None
for ix in (msg.get("instructions") or []):
    if "memo" in (ix.get("program") or ""):
        p = ix.get("parsed")
        if isinstance(p, dict) and "message" in p: memo = p["message"]
        elif isinstance(p, str): memo = p
        else:
            try: memo = base64.b64decode(ix.get("data") or "").decode("utf-8", "replace")
            except Exception: pass
expected = ("chit402:root:v2:global:2026-10-27:"
            "36213397e111e8bfd2086d592670925e5f8bb00141ce6088a8e5de617da4d2ee:"
            "4bd1f0441a5048c442f1453bfd06415de5a9533ec279e1c579d200211666bf94:"
            "2:dd20e39a39a225b7b3441bb7f61532c06562288b74ae5dc4dda015c48312f973:"
            "4:190a84631eb90fe925f8aa50e110db503e192662d3ebf6a44d567d8febc992c0")
print(f"  slot: {res.get('slot')} (== pinned {sys.argv[3]}: {res.get('slot')==int(sys.argv[3])})  blockTime={res.get('blockTime')}")
print(f"  fee payer: {fee_payer} (== pinned: {fee_payer==sys.argv[2]})")
print(f"  error: {(res.get('meta') or {}).get('err')}")
print(f"  memo == signed head memo (pinned copy): {memo == expected}")
print(f"  memo: {memo}")
EOF
else
  echo "  (solana rpc unreachable or rate-limited this round)"
fi
echo "done."
