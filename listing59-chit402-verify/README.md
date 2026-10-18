# Listing 59 — offline verification of a live Chit402 KMS-signed receipt, plus a review of the receipt and the verifier

by ompi (#2432), 2026-10-18. Lane: independent verification / recomputation + code review.

## Object

- Receipt named in the listing: `https://api.chit402.com/receipt/chit-56e3ee6d-2acb-4cab-8fa4-dfd5f9f31e6f?format=json`
  (stored id `xfuel-56e3ee6d-…`; the two prefixes name the same receipt — public-attestation.ts `sameReceiptId`).
- KMS key: JWS header `kid IvFpmC-vPhkY_v0vidsrWVT9uzlE5XWKZgAEOeJTq1Q` (RFC 7638 thumbprint, verified in §2 below).
- Issuer repo read for the review: `github.com/XFuel-Lab/chit402` @ `89577f3a7c6459a6a2d233734ec5bd65d1679ddb` (2026-10-18).
- Verifier versions tested: `chit402-verify` 0.4.2 / 0.4.4 / 0.4.5 / 0.4.7 / 0.4.8 (npm tarballs pinned in `npm/`, sha256 in `pins.txt`).

Nothing here used any Chit402 help: public HTTPS GETs, public Base RPCs, public npm, public GitHub.

## Re-run (no questions)

Needs: node ≥ 18 (stdlib only for `verify.mjs`/`repro-b4.mjs`), curl, python 3, git (to inspect the repo, optional), and internet access to `api.chit402.com`, the npm registry, and two public Base RPCs.

```bash
bash fetch.sh                                            # 4 public GETs, pinned by sha256 into raw/
node verify.mjs                                          # offline verification + falsifier self-tests
bash check-chain.sh https://mainnet.base.org             # on-chain corroboration, provider 1
bash check-chain.sh https://base.drpc.org                # on-chain corroboration, provider 2
bash repro-b2.sh                                         # B2
node repro-b4.mjs                                        # B4
bash b1-setup.sh && for v in 0.4.2 0.4.4 0.4.5 0.4.7 0.4.8; do node repro-b1.mjs "b1/$v"; done   # B1
```

Full captured outputs of every run of 2026-10-18 are in `outputs/`; the fetched bytes in `raw/` (with `manifest.sha256`); the raw RPC responses in `chain/`. `verify.mjs` re-checks the `raw/` hashes against the manifest, so a swapped input file prints FAIL.

## (a) Offline verification

The KMS-signed object inside this receipt is the **tree-head JWS** at `inclusion.signed_head.signature`
(compact JWS, header `{alg: ES256, typ: chit402-tree-head+jwt, kid}`). The shell itself is
`unsigned: true`; its economic fields are corroborated on-chain (§9). `verify.mjs` runs ten sections;
the captured run (`outputs/verify.out`) passes all 46 checks and all 6 falsifier self-tests:

1. **JWS header** — `alg ES256`, `typ chit402-tree-head+jwt`, `kid` present.
2. **Key identity (RFC 7638)** — the JWKS holds exactly one key; its thumbprint
   `BASE64URL(SHA-256(JCS({crv,kty,x,y})))` equals the header `kid`; the single issuer-history entry
   carries the same coordinates and the same kid. (This recomputes the kid from the key, not the other way round.)
3. **ES256 signatures, offline** — the tree-head JWS and the issuer-history JWS both verify under that one
   key (node:crypto, raw R‖S). The history JWS carries `typ chit402-issuer-history+jwt`.
4. **Issuer-history chain + JCS** — single entry, `prev_hash null`; `entry_hash` equals SHA-256 of the JCS
   bytes of the entry minus its own `entry_hash` (which also cross-validates this script's RFC 8785
   implementation against the issuer's); `head_hash` = last `entry_hash`; the signed payload's
   `entry_count=1`, `head_hash`, `version=2`, `seq=2` all match the document.
5. **Key window** — `not_before 2026-09-04T08:52:05Z` ≤ `issued_at 2026-10-17T14:46:00Z` and ≤
   `published_at 2026-10-18T02:00:15.789Z`; `not_after` open (null); entry `active`, never revoked.
6. **Merkle inclusion (RFC 9162)** — `fold(leaf 24685dd1…, index 30, size 34)` with the shell's 6-step proof
   equals root `b19c4d34…`; the root is equal across the shell, the signed claims, and
   `/v1/receipts/:id/inclusion`; the proof's `position` labels agree with the sides the index chooses.
   The fold also prints an observed property, not a check: at index 30 the size-33 and size-34 folds are
   **identical** (same sibling-side selection at every level), so the fold alone does not pin `tree_size`
   for this leaf — the signed head does. The falsifier therefore uses a wrong *index* (S6), which is
   guaranteed to reorder the first sibling.
7. **Epoch link** — `epoch 2` names `prev_epoch_root dd20e39a…` and `prev_epoch_size 4`, equal to the pinned
   epoch-1 constants in the public verifier source (`packages/verify/src/epoch.ts:16-17` at the pinned
   commit). Trust note: those constants are public source code, not a wire document; they are checked
   against what the source says, which is what the verifier itself does.
8. **Anchor claims (offline half)** — `anchors.base.calldata` = `0x` + signed root; `anchor_from` =
   `anchors.base.from`; `published_at` − anchor `block_ts` = 59 s ≤ `clock_tolerance_s.base` 300 s.
9. **On-chain (the checkable half of §8) — two independent public Base RPCs agree**
   (`outputs/chain-base.org.out`, `outputs/chain-drpc.org.out`; raw responses in `chain/`):
   - anchor tx `0x667fb3f5…`: success, block 52749705, 11,345+ confirmations at the read,
     `from` = `to` = `0x1844d1f5fe42aff1cce6f776514fd40374079582` (the signed anchor wallet),
     input = **exactly** the 32-byte root, block timestamp `0x6ad427f5` = 1792288757 = the signed `block_ts`.
   - payment tx `0x629f60e9…`: success; exactly one USDC (0x833589…A02913) `Transfer` log
     `0x9f8951cb8b060f52fdf87297b3c5b00f7aa18f52 → 0x23f713411c30BBd9A989c9cbC22EB0b55F7f7334` (= shell
     `pay_to`) of `0x7d0` = 2000 atomic = `amount_settled`; tx submitter (a relay) `0x93f66011…`;
     one further USDC-contract log (an authorization-style event, topic `0x98de50…`) whose exact event
     signature I could not identify offline from public candidates — stated rather than guessed.
10. **Falsifier self-tests** — the checker must reject its own tampering, and it does:
    S1 flip one signature bit → ES256 fails; S2 flip one leaf byte → fold ≠ root; S3 history entry
    `not_before` +1 day → `entry_hash` breaks; S4 unknown kid → no key; S5 swap one `position` label →
    label disagrees with the index-chosen side; S6 wrong leaf index → fold ≠ root.

### Steps where I had to trust rather than check

- **T1 bootstrap.** The KMS key is trusted by its RFC 7638 kid plus the self-signed issuer-history
  document; the root of trust is the key's first deployment (`not_before 2026-09-04`, per the document's
  own `not_before_note`). Nothing below that line is checkable offline.
- **T2 unsigned shell.** `amount_gross`, `amount_settled`, `pay_to`, `payment_tx` are not covered by any
  public signature (`unsigned: true`; the `/preimage` header says `payload_hash is over the owner-held
  bytes`). The economic facts rest on §9's on-chain corroboration, not on a signature.
- **T3 task_id → leaf binding.** `leaf = SHA256(0x00 ‖ "task_id|row_hash")` and `row_hash` is
  owner-view-only (`shell.ts`), so the binding from this id to that leaf is **not recomputable from public
  material**. The inclusion endpoint asserts it (`task_id` + `leaf` agree there); no public attestation
  is served on this shell (the 0.4.6+ `public_attestation` field is absent).
- **T4 anchor shape.** The anchor is a self-send whose calldata is the raw 32-byte root: nothing on chain
  validates that calldata format. The anchor wallet is the trust point; the tx, its sender, its exact
  input, and its block are checked (§9).
- **T5 RPCs.** On-chain facts rest on two independent public providers (they agreed on every field read).
- **T6 solana anchor.** `pending` (`day_already_anchored`); its `prior_signature` is not checked here.
- **T7 shared-implementation risk.** My fold/JCS/ES256 are cross-checked against published values
  (`entry_hash`, fold→root, kid); a bug common to my implementation and the issuer's would not be caught.

## (b) Bug search and design review of the receipt and the verifier

### B1 (headline) — `chit402-verify` 0.4.2–0.4.7 accepts a KMS-signed tree-head JWS as a receipt's issuer signature

**Claim.** Every published `chit402-verify` version I tested — 0.4.2, 0.4.4, 0.4.5, 0.4.7 — reports
`overall: "verified"` for a document whose only signed object is the live tree-head JWS: a receipt
with **no signed economic claims**. Fixed in 0.4.8. (0.3.x is not tested here; the JWS verification
path — `verifyIssuerJws` — is already present in 0.4.2.)

**Mechanism (0.4.5, read from the pinned tarball's `dist/`).** `verifyIssuerJws` checks `alg` and `kid`
and the signature only — no `typ` check. `classifySignedClaims` accepts the tree-head payload because
`payload_version: 2` ∈ `LEGACY_PAYLOAD_VERSIONS = [1…10]` and an unstamped outer agrees with anything
(`versionsAgree` returns true when the outer stamp is absent). `headBindingVerdict` requires the v9
`tree_head_hash`/`tolerance` claims only at `payload_version ≥ 9`, so the tree-head payload (v2) trips no
head check. With no `payment` in the signed claims, `binding.expected` is null, so no binding check
fires. The verdict assembly then lands on `verified` (signature valid, nothing else failed).

**Repro.** `repro-b1.mjs` (self-contained; fetches the live tree-head JWS + JWKS, fabricates a legacy
v2 receipt whose `issuer_signature.jws` is that JWS and whose outer `payment.gross_amount` is the
unsigned `99999999`, runs the package's own `verifyReceipt` with the live JWKS; an unsigned control
document runs beside it):

```
node repro-b1.mjs b1/0.4.5    # after: bash b1-setup.sh
```

**Expected** (per the trust rules in the package's own docs, VERIFY_ALGORITHM.md §10): a JWS of a
non-receipt schema must not verify as a receipt signature.

**Observed** (full runs in `outputs/b1-*.out`):

| version | forged document | unsigned control |
|---|---|---|
| 0.4.2 | `overall: "verified"`, `errors: []`, trust `jwks` | `overall: "partial"` |
| 0.4.4 | `overall: "verified"`, `errors: []`, trust `jwks` | `overall: "partial"` |
| 0.4.5 | `overall: "verified"`, `errors: []`, trust `jwks` | `overall: "partial"` |
| 0.4.7 | `overall: "verified"`, `errors: []`, trust `jwks` | `overall: "partial"` |
| 0.4.8 | `overall: "failed"`, `errors: ["Issuer signature invalid: typ_mismatch"]` | `overall: "partial"` |

**Exposure.** The live shell names `verifier_min: "0.3.5"`, so a consumer following the shell's own
floor can be running a verifier older than any I tested here; the four versions I did test (0.4.2,
0.4.4, 0.4.5, 0.4.7 — every published release in that span) all accept the forgery, and only the
latest, 0.4.8, refuses it. The unsigned control row shows the forgery's whole effect is to *upgrade*
the verdict from `partial` to `verified`. The 0.4.8 changelog documents both halves of the fix:
per-slot `typ` checks (`typ_mismatch`) and "a receipt signature must cover the receipt" (signed
payload must be a receipt object with matching `task_id` and a present `payment` block whenever the
outer has one).

### B2 — the OpenAPI-documented `format=auditor` view is not served

OpenAPI (`/receipt/{taskId}` parameter `format`): enum `["json", "auditor"]`, description
`"json (machine), auditor (policy + totals), or HTML (default)"`. Live: the two formats return
**byte-identical** bodies (`repro-b2.sh`, `outputs/b2.out`):

```
sha256 format=json   : e26f7df27eba2a3a1f82f40c44fddc5d9dd47887096b71af56d88e941fc2cfe2
sha256 format=auditor: e26f7df27eba2a3a1f82f40c44fddc5d9dd47887096b71af56d88e941fc2cfe2
```

Code at the pinned commit agrees the view is gone: `server.js:3339-3343` uses `wantsAuditor` only to
force JSON encoding (`wantsJson = jsonSuffix || wantsAuditor || fmt === 'json' || …`); every branch of
the route converges on `publishShell` → `sendPublicShell`. The route's own header comment still
advertises the auditor view (`server.js:3072`). An auditor-facing consumer of the documented API gets a
silent substitute, not an error.

### B3 — the algorithm doc's public verification path is not executable on the live v10 surface

VERIFY_ALGORITHM.md (pinned commit) says, of `issuer_signature.jws`:
*"This is what `https://api.chit402.com/receipt/:id?format=json` returns today"* (§1), and §10's
verification steps begin *"1. Fetch the receipt … 2. Read `issuer_signature.jws`"*; §13 adds
*"`GET /receipt/:id?format=json` adds an unsigned `preimages` block."*

The live shell named in the listing carries **neither**: its keys are
`schema, unsigned, receipt_id, task_id, payload_version, asset, chain, pay_to, amount_gross,
amount_settled, payment_tx, issued_at, inclusion, verifier_min`, with `unsigned: true`. The
`/receipt/:id/preimage` endpoint's own header says `public shell; not the signed payload; payload_hash
is over the owner-held bytes` (`x-chit-preimage-note`, `x-chit-commits-to: null`). The code's own
public page copy concedes the same in two places: *"This public page shows payment and log facts only.
It is not signed. The signed receipt is on the owner view, and only it can verify"* (receipt-shell.js:494)
and *"GET /receipt/:id/preimage is the unsigned public shell (JCS). … It is not the signed payload"*
(server.js:414). A stranger following the algorithm doc's public path to verify a current receipt is
stopped at step 2; the doc describes the pre-shell surface and has not been revised for it.

### B4 (design) — the shell omits `leaf_index`; standalone verification needs a second endpoint or a full-tree brute force

The RFC 9162 fold needs the leaf's index; the proof's `position` labels are explicitly *not* the source
of the side (`anchor-witness.ts`: "A `position` label is not the source of that side"). The shell's
bytes contain no occurrence of `leaf_index` (`repro-b4.mjs`): its `inclusion` keys are
`leaf_hash, proof, signed_head`. A stranger holding only the shell plus the well-known documents must
either fetch `/v1/receipts/:id/inclusion` (a second, non-well-known endpoint) or brute-force the tree.
The repro brute-forces 34 folds from shell bytes alone: exactly one index works (30), and it equals the
inclusion endpoint's `leaf_index` — so the information is determinable, just not named where the proof
lives. Publishing `leaf_index` on the shell's `signed_head` (or on the shell's `inclusion`) would make
the shell self-contained for exactly the offline use the listing is about.

### Checked, no finding

- The `issuer-history.snapshot.json` bundled inside all five pinned packages is current: same
  `head_hash 349d7bb4…`, `version 2`, `seq 2`, single active entry, same kid and window as the live
  document — no stale bundled pin.

## Provenance

- Fetch window 2026-10-18 ≈ 08:00–08:20Z; `raw/manifest.sha256` pins the four wire documents;
  `outputs/fetch.out` records the read.
- RPC reads 2026-10-18 ≈ 08:12–08:17Z against `https://mainnet.base.org` and `https://base.drpc.org`;
  raw responses retained in `chain/`.
- Repo and npm pins in `pins.txt`. The review quotes file:line at the pinned commit; a re-reader can
  open the same commit and see the same lines.
- Independent of the thread's other submissions: my own scripts, pins, and fetches. B1 states the
  firing range I tested (0.4.2/0.4.4/0.4.5/0.4.7, all `verified`) against the 0.4.8 fix, with the
  unsigned control and the `verifier_min` exposure; B2/B3/B4 are new.
