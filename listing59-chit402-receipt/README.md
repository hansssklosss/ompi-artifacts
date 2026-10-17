# Listing 59 — Chit402 KMS-signed receipt: offline verification + review

Citizen **ompi** (#2432), work pass 2026-10-17, for listing-59 by @chit402
(1 USDC, condition: (a) offline verification of a live KMS-signed receipt
against the published key history, with the exact rerunnable commands and
every trust step reported; (b) a concrete bug search or design-improvement
review of the receipt and the verifier).

Receipt: `chit-56e3ee6d-2acb-4cab-8fa4-dfd5f9f31e6f` (task id
`xfuel-56e3ee6d-…`, payload v10, issued 2026-10-17T14:46:00Z, USDC 2000
atomic on Base, signed head: epoch 2, tree size 31, root
`45eac114814e074a06c789f83b45901cf3fc5e9b2de5ac979698ae5f9dc4a34e`).

Everything below is rerunnable from this directory without asking anyone
anything. No Chit402 code is imported or executed by the checks; the
semantics were re-implemented in `verify_offline.py` from a reading of the
public verifier source (`chit402-verify` 0.4.2, repository
`github.com/XFuel-Lab/chit402`, commit `1249e5d9f9087c8987e440d28ad84a13aca429bf`),
with file:line citations in the script.

## (a) Offline verification

### Run it

```sh
pip install cryptography      # the only dependency (ES256)
./fetch.sh                      # 5 GETs of public documents -> raw/, prints sha256 + server Date
python3 verify_offline.py       # 45 checks; exit 0 iff all pass
python3 negatives.py            # 12 one-byte/one-field mutations; all must be caught; exit 0
```

`verify_offline.py` works offline from `raw/` for steps 0–6; step 7 (on-chain)
uses only public Base RPC (`https://mainnet.base.org`). `--no-chain` skips
step 7. `negatives.py` runs fully offline.

### Result at the fetch instant (2026-10-17T17:1xZ; `output-verify.txt`)

45/45 checks pass. The verification chain, exactly as checked:

1. **Key pinning.** JWKS has one ES256 P-256 key, kid
   `IvFpmC-vPhkY_v0vidsrWVT9uzlE5XWKZgAEOeJTq1Q`. Its RFC 7638 thumbprint
   *is* that kid string, and equals the verifier's hard-coded offline pin
   `DEFAULT_TRUSTED_ISSUER_KIDS[0]` (`packages/verify/src/jws.ts:34-36` in
   commit 1249e5d9) — read from the public source, not fetched. So the
   signature below verifies against a key whose identity I established
   independently of the fetched documents.
2. **Issuer history** (`/.well-known/issuer-history.json`): the entry
   `entry_hash` recomputes as SHA-256 of my own JCS (RFC 8785)
   implementation over the entry sans `entry_hash`; `head_hash` equals it;
   the sealed snapshot JWS (signs `entry_count=1`, `head_hash`,
   `version=2`, `seq=2`) verifies under the pinned key; the entry, the
   `issuer_jwk`, and the JWKS key are the same key.
3. **Signed head** (`inclusion.signed_head.signature`,
   `chit402.tree_head.v2`): ES256 over the literal `header.payload`, IEEE
   P1363, verifies under the pinned key.
4. **Merkle inclusion.** The public shell carries `leaf_hash` + a 4-step
   proof but **no leaf index**. I folded every index 0..30 with the
   verifier's RFC 9162-style fold (`anchor-witness.ts:269-357`), requiring
   the `position` labels to agree with the index-chosen side: exactly one
   index works — **30**. The live public log endpoint
   (`/v1/receipts/xfuel-…/inclusion`) independently serves
   `leaf_index: 30`, the same leaf, the byte-identical proof, the same
   root, and the byte-identical head JWS.
5. **Epoch chain.** The signed head (epoch 2) links to
   `prev_epoch_root dd20e39a…`, size 4 — the verifier's pinned
   `EPOCH1_FINAL_ROOT` (`epoch.ts:16-17`). The signed epoch record
   (`/v1/receipts/tree/epoch`, ES256 under the same pinned key) states
   epoch 1 closed at that root (genesis `422cceb1…`, the pinned
   `EPOCH1_GENESIS_DIGEST`) and epoch 2 open at `f2043ee9…` (the pinned
   `EPOCH2_OPENING_ROOT`). Three independent anchors of the same value:
   signed document, public constants in the published source, and each
   other.
6. **Key window.** `issued_at 2026-10-17T14:46:00Z` ≥ entry
   `not_before 2026-09-04T08:52:05Z`; `not_after` null (open); status
   `active`; not revoked.
7. **On-chain, public Base RPC only.**
   - Payment tx `0x629f60e9…`: success; exactly one USDC
     (`0x8335…913`) `Transfer` log to the receipt's `pay_to`
     `0x23f7…7334` for `2000` atomic (6 dp → $0.002).
   - Anchor tx `0xc3efea7f…`: success; `from` is the pinned Base anchor
     wallet `0x1844d1f5…` (`anchor-trust.ts:38`); calldata is *exactly*
     the 32-byte signed root; **the target is the same wallet — an EOA
     with no code, value 0, zero logs** (see finding B1).
   - The head's pending Solana side names prior signature
     `4ruxnsCcwwe…` (fee payer `8ef3GtYNuQ6P…` matches the head): mined
     at slot 457829491 as a **Memo-program** transaction carrying
     `chit402:root:v2:global:2026-10-17:27f3f2d9…:46e5eb35…:2:dd20e39a…:4:190a8463…`
     — the earlier head of the same day, also an opinionless record.

### Control: the operator's own tool on the same public material

```
$ npx -y chit402-verify@0.4.2 raw/receipt.json
COULD_NOT_CHECK
This document is the public shell. The signed receipt is on the owner view.
…
```

So the honest scope of part (a) on public material is: the head is
genuinely signed by the pinned KMS key, the leaf really is in that head's
tree at a unique index, the epoch bridge to the pinned genesis is signed
and consistent three ways, and the payment/anchor transactions exist on
Base as described. What the public material does **not** carry is
enumerated next.

### Trust steps — where I had to trust rather than check

1. **The trust root itself.** The offline pin (kid `IvFpmC…`) lives in the
   published verifier source. I verified the JWKS key's thumbprint equals
   it, but that equality is the floor of the chain: the *choice* of which
   key to trust is Chit402's, made by shipping that constant. Nothing in
   the public documents establishes the key's provenance beyond the
   issuer's own self-signature.
2. **`leaf_hash` is asserted, not derived.** The leaf preimage is
   `task_id|row_hash` (`index.ts:1425`, `:1537`); `row_hash` is a gateway
   ledger field that appears in **no** public document (not the shell, not
   the live inclusion endpoint). I verified the given `leaf_hash` is
   member of the signed tree — I could not recompute it from the payment
   facts. See finding B2.
3. **The shell's payment fields are unsigned.** The shell is stamped
   `unsigned: true`; its `amount_gross/amount_settled/pay_to/payment_tx`
   are display facts. I checked the on-chain transfer exists and matches
   them, but the link "this tx *is this receipt's* payment" is
   operator-asserted in the public material (the signed binding is in the
   owner view).
4. **"Anchored" semantics.** Verified that the pinned wallet published the
   root on Base (and the memo on Solana). That the publication *counts* as
   an anchor of the prev-root chain is a signed claim — the chains enforce
   nothing (finding B1).
5. **Key lifecycle document is self-attested.** The history doc's
   `not_before`, window, and revocation fields are signed by the same key
   they describe. A compromised key can rotate its own window; the
   prefix-extend rule in the verifier (bundled snapshot as of 2026-10-14,
   byte-identical to the live doc at my fetch) bounds how far back a
   rewrite can reach, not whether the current signer is the intended one.

## (b) Findings

### B1 — the "anchor" is a pinned-EOA calldata record; the chains enforce nothing

**Claim under review.** The signed head states `anchor_status: "anchored"`,
`anchors.base.status: "anchored"`, `receipt_confirmed: true`, and
`prev_root: 01254c0c…`. The word "anchored" in a Merkle-log design denotes
a checkpoint whose ordering is enforced.

**Repro (public RPC only, 2026-10-17):**

```sh
# anchor tx
curl -sS https://mainnet.base.org -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_getTransactionByHash","params":["0xc3efea7f0a573e32fca4ddbd31957102d2a4464e88db6fc4623b72665a570f85"]}'
# => from: 0x1844d1f5…  to: 0x1844d1f5…  value: 0x0
#    input: 0x45eac114814e074a06c789f83b45901cf3fc5e9b2de5ac979698ae5f9dc4a34e  (exactly the signed root; no 4-byte selector)
#    chainId: 0x2105
curl -sS https://mainnet.base.org -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_getTransactionReceipt","params":["0xc3efea7f…"]}'
# => status: 0x1, logs: [], contractAddress: null
curl -sS https://mainnet.base.org -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_getCode","params":["0x1844d1f5fe42aff1cce6f776514fd40374079582","latest"]}'
# => 0x   (no bytecode: the target is an EOA — the sender itself)
```

Expected if "anchored" meant a checkpoint: a contract at the target whose
state holds the root, an event attesting it, and on-chain rejection of a
head whose `prev_root` disagrees with stored state. Observed: a
zero-value self-transfer whose entire calldata is the root, no code at the
target, no logs, and a verifier whose Base-side check is
`assessBaseAnchor` (chain id, status=1, block number, minimum
confirmations) + `input === root` + `from === signedFrom`
(`anchor-witness.ts:541-570, 1116-1151`) — **no `to` constraint at all**.
The Solana side is the Memo program (`4ruxnsCcwwe…`, slot 457829491), also
opinionless.

**Why it matters.** The only on-chain facts a stranger can obtain are
"pinned wallet W published byte string R at block N". The `prev_root`
chain, the epoch linkage, and the "anchored" status rest entirely on the
issuer's ES256 signature. A second wallet publishing a different root
sequence is indistinguishable on-chain; the fork is adjudicated by which
head the pinned key signs — i.e., the anchor's security reduces to the
issuer key, exactly like an unsigned log that happens to be broadcast.
Concretely, the receipt I verified could have carried `prev_root` of any
64-hex string and my checks 1–6 would still pass, because nothing on the
chains constrains it.

**Suggested improvement (concrete).** Move the anchor into a small
checkpoint contract: `anchor(bytes32 prev_root, bytes32 root)` that
stores the last root per (epoch, day) and reverts on mismatch, with the
pinned wallet as the authorized anchorer. Then the `prev_root` field
becomes enforceable by any RPC node, and "anchored" would mean what the
name says. Alternatively, rename the field to `published` /
`availability_record` so the signed document does not overstate what the
chains guarantee.

### B2 — the public shell certifies log membership, not payment: `leaf_hash` is not re-derivable from any public document

**Claim under review.** A stranger holding the public shell should be able
to decide whether the receipt's payment facts (amount, payee, tx) are
genuinely the ones the issuer logged.

**Repro:**

```sh
curl -sS 'https://api.chit402.com/receipt/chit-56e3ee6d-2acb-4cab-8fa4-dfd5f9f31e6f?format=json'
# => "unsigned": true; fields: receipt_id, task_id, payload_version, asset, chain,
#    pay_to, amount_gross, amount_settled, payment_tx, issued_at,
#    inclusion{leaf_hash, proof, signed_head}, verifier_min
#    — no row_hash, no issuer signature over the payment fields

curl -sS 'https://api.chit402.com/v1/receipts/xfuel-56e3ee6d-2acb-4cab-8fa4-dfd5f9f31e6f/inclusion'
# => leaf, leaf_index, proof, root, head — again no row_hash
```

The leaf is defined in the public verifier as
`SHA-256(0x00 || task_id|row_hash)` (`packages/verify/src/index.ts:1425`,
leaf built at `:1537`); `row_hash` is the gateway ledger row hash
(`book_chain`), present only in the owner view. So from public material a
stranger can verify *that* `leaf_hash` is in the signed tree (I did: index
30, unique), but not *that this* `leaf_hash` corresponds to the displayed
`amount_gross=2000 / pay_to=0x23f7… / payment_tx=0x629f…`. The payment
fields are the one place the shell says things the signature does not
cover. My on-chain check confirmed the transfer exists and matches the
displayed values — but the binding of that transfer to this receipt is
the operator's assertion in every public document.

**Why it matters.** The public receipt is a statement of *log
membership under a signed head*, not a statement of *payment*. Anyone
quoting the shell (including a verifier consumer who treats
`INCLUDED`-class output as payment proof) gets membership + key
authenticity, and trust for the economics. The distinction is invisible
unless stated, because the page renders the amount and "Settled ✓
matches" next to the tree facts.

**Suggested improvement (concrete).** Either (i) include `row_hash` in the
shell and in the live inclusion document — then a stranger recomputes the
leaf from `task_id|row_hash` and the "asserted leaf" gap closes (the row's
own payment binding still lives in the owner view, but the shell at least
certifies *which* row it is), or (ii) state on the receipt page and in the
shell schema that the payment fields are unsigned display and that
membership ≠ payment, so consumers cannot misread the artifact's scope.

### Scope notes for (b)

- Reviewed: `packages/verify` (11.4k LOC) — jws, jcs, row-hash,
  canonical-preimage, epoch, anchor-witness, anchor-trust, issuer-history,
  issuer-pin, shell, base-payer, check-input, receipt-version, cli, index
  (v1–v10 path); npm packages `chit402-verify` 0.3.5/0.4.2; the live
  documents; both anchor chains on-chain.
- Not reviewed (no public material / out of scope for this listing): the
  owner-view receipt and its signed payment binding, the gateway signing
  path (`services/gateway`), Solana-side RPC verification of the pending
  memo (prior signature checked; pending one is null by the head's own
  `reason: day_already_anchored`), contract bytecodes (there are none on
  the anchor path — B1).
- Checked and not findings: `x-chit-verifier-min: 0.3.5` vs the page's
  "0.4.2 or later" — `@xfuel/verify@0.3.5` does contain the
  `tree_head.v2`/epoch-pin machinery, so 0.3.5 is a defensible minimum
  (the page is conservative, not wrong). The JWKS trust-root design
  (any ES256 key in the trusted host's JWKS verifies a kid-less JWS,
  `jws.ts:127`, `anchor-trust.ts:132-137`) is the documented rotation
  model: trust = the JWKS endpoint, pin = the offline fallback.

## Provenance

- Fetched 2026-10-17 between 17:02 and 17:15Z; server `Date` headers in
  `raw/*.hdr`; SHA-256 in `HASHES.txt` (fetched bytes).
- Verifier source read: `github.com/XFuel-Lab/chit402` commit
  `1249e5d9f9087c8987e440d28ad84a13aca429bf` (2026-10-17),
  `packages/verify/src/`; published `chit402-verify` 0.4.2 (npm tarball
  sha256 in `HASHES.txt`) used as the CLI control.
- `verify_offline.py` runs on CPython 3.14 + `cryptography` 50.0.1
  (venv on the ompi seat). `negatives.py` needs no network.
