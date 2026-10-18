#!/usr/bin/env bash
# check-chain.sh — part (a), on-chain corroboration of listing-59's receipt,
# against ONE public Base RPC. Run once per independent provider and compare.
# No Chit402 help: only JSON-RPC POST to the named public RPC.
# Usage: bash check-chain.sh <rpc-url>
set -euo pipefail
cd "$(dirname "$0")"
RPC="${1:?usage: check-chain.sh <rpc-url>}"
TAG=$(echo "$RPC" | md5sum | cut -c1-8)
mkdir -p chain
ANCHOR_TX=0x667fb3f5a3a5804e56a9c64548b718e33266b70e3fa204b92f41278192b7fecb
PAYMENT_TX=0x629f60e9e48312fabaa2c5e362fceebceb2eddee220f25d40b756d3790684ab8

rpc() { curl -sS -X POST -H 'content-type: application/json' --data "{\"jsonrpc\":\"2.0\",\"id\":$1,\"method\":\"$2\",\"params\":$3}" "$RPC"; }

echo "# RPC: $RPC   at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
rpc 1 eth_blockNumber '[]' > "chain/tip.$TAG.json";                    cat "chain/tip.$TAG.json"; echo
rpc 2 eth_getTransactionByHash "[\"$ANCHOR_TX\"]" > "chain/anchor_tx.$TAG.json";  cat "chain/anchor_tx.$TAG.json"; echo
BLOCK_HASH=$(python3 -c "import json; print(json.load(open('chain/anchor_tx.$TAG.json'))['result']['blockHash'])")
rpc 3 eth_getBlockByHash "[\"$BLOCK_HASH\", false]" > "chain/anchor_block.$TAG.json";  cat "chain/anchor_block.$TAG.json"; echo
rpc 4 eth_getTransactionReceipt "[\"$PAYMENT_TX\"]" > "chain/payment_tx.$TAG.json";   cat "chain/payment_tx.$TAG.json"; echo
rpc 5 eth_getTransactionReceipt "[\"$ANCHOR_TX\"]" > "chain/anchor_receipt.$TAG.json";  cat "chain/anchor_receipt.$TAG.json"; echo
python3 - "$TAG" <<'EOF'
import json, sys, os
tag = sys.argv[1]
def load(name):
    return json.load(open(f'chain/{name}.{tag}.json'))['result']
anchor_tx = load('anchor_tx')
anchor_block = load('anchor_block')
payment = load('payment_tx')
tip = int(json.load(open(f'chain/tip.{tag}.json'))['result'], 16)

ok = lambda name, cond, detail: print(f'  {"PASS" if cond else "FAIL"}  {name}: {detail}')

ok('anchor_tx exists', anchor_tx is not None, f'block {int(anchor_tx["blockNumber"],16) if anchor_tx else None}')
if anchor_tx:
    ok('anchor status', load('anchor_receipt').get('status') == '0x1', '0x1 = success')
    ok('anchor from', anchor_tx['from'].lower() == '0x1844d1f5fe42aff1cce6f776514fd40374079582', anchor_tx['from'])
    inp = anchor_tx['input']
    want = '0xb19c4d34d54c47be11525a8d02c6161d4b16b41d16eb5dbfc4a56eadf6e6ad6f'
    ok('anchor input is exactly the root bytes', inp == want, f'input len {len(inp)-2} hex chars, to={anchor_tx.get("to")}')
    ok('anchor confirmations', tip - int(anchor_tx['blockNumber'], 16) >= 32, f'tip {tip} - block {int(anchor_tx["blockNumber"],16)} = {tip - int(anchor_tx["blockNumber"],16)}')
ok('anchor block ts', int(anchor_block['timestamp'], 16) == 1792288757, anchor_block['timestamp'])
if payment:
    ok('payment status', payment.get('status') == '0x1', '0x1 = success')
    usdc = '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913'
    payto = '0x' + '0'*24 + '23f713411c30bbd9a989c9cbc22eb0b55f7f7334'
    TRANSFER = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
    amt = '0x' + (2000).to_bytes(32, 'big').hex()
    matches = [l for l in payment.get('logs', [])
               if l['address'].lower() == usdc and l['topics'][0] == TRANSFER
               and l['topics'][2].lower() == payto and l['data'] == amt]
    ok('USDC Transfer to pay_to of 2000 atomic', len(matches) == 1, f'{len(matches)} matching log(s)')
    if matches:
        tfrom = '0x' + matches[0]['topics'][1][-40:]
        print(f'  INFO  Transfer.from (payer observed on chain; the public shell asserts no payer): {tfrom}')
        ok('tx submitter (observed relay)', True, payment.get('from'))
        n_auth = sum(1 for l in payment['logs'] if l['address'].lower() == usdc and l['topics'][0] != TRANSFER)
        print(f'  INFO  non-Transfer USDC logs in the payment tx (authorization-style events): {n_auth}; exact event signature not identified offline')
else:
    ok('payment tx exists', False, 'null')
EOF
