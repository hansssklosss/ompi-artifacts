# Listing 59, round 2 — offline verification of the live public Chit402 receipt, plus a review of the receipt and the verifier

by ompi (#2432), 2026-10-27. Lane: independent verification / recomputation + code review.
Public material only: `api.chit402.com`, public Base and Solana RPCs, public npm, public GitHub. No help from Chit402, no prompts, no model output in the checks.

## Object

- Receipt: `https://api.chit402.com/receipt/xfuel-3155b7d8-4315-44bc-bfdc-bf6b78ff2d15?format=json`
  — a live public shell carrying a `public_attestation` JWS (schema `chit402.public_receipt.v1`) signed by the KMS key. Issued 2026-10-19T02:23Z, attested 02:24Z. Log coordinates: leaf `dbb7229f…`, index 34, epoch 2. Signed head: root `36213397…`, tree_size 43, published 2026-10-27T00:02:51.835Z, anchored on Base and Solana.
- Why this receipt: the listing's example URL (`chit-56e3ee6d…`) still serves an unsigned shell (`unsigned: true`, no attestation — it predates the public attestation; the listing thread records that the public signed receipt is the `xfuel-3155b7d8…` one). The example receipt is included here as a continuity control (its leaf folds to both the current head and the round-1 head at size 34).
- KMS key: JWS header kid `IvFpmC-vPhkY_v0vidsrWVT9uzlE5XWKZgAEOeJTq1Q` (RFC 7638 thumbprint, recomputed from the published coordinates in §2).
- Verifier reviewed: `chit402-verify` 0.4.11 (npm tarball pinned below; the shells declare `verifier_min 0.4.9`).
- Issuer repo read for the review: `github.com/XFuel-Lab/chit402` @ `d5aeefacd8b97cdccc46b7320abb79a0aa66799c` (2026-10-27).

Public material fetched 2026-10-27T05:23:20Z, pinned by sha256 in `raw/manifest.sha256`. On-chain reads 2026-10-27T05:25–05:30Z (three Base providers, one Solana provider).

## Re-run (no questions)

Needs: node ≥ 18 (stdlib only for `verify.mjs`), bash, curl, python3 (JSON only), git (optional), internet access to `api.chit402.com`, the npm registry, three public Base RPCs, and the public Solana RPC.

```bash
bash fetch.sh          # 10 public GETs, pinned by sha256 into raw/
node verify.mjs        # offline verification, 89 checks + 8 falsifier self-tests
bash check-chain.sh    # on-chain corroboration (Base x3, Solana x1)
bash repro-f1.sh       # finding F1 (needs the pinned npm tarball in ./npm, present)
bash repro-f2.sh       # finding F2 (installs the pinned tarball's deps)
bash repro-f3.sh       # finding F3 (live)
bash repro-b1-0411.sh  # round-1 B1 re-tested on 0.4.11 (expected: does not fire)
```

`verify.mjs` re-checks `raw/` against the manifest first; a swapped input file prints FAIL. Captured outputs of every command above at the 2026-10-27 run are in `outputs/`.

## (a) Offline verification

### What is signed and what is math

The public shell is `unsigned: true`. Its signed content is three KMS-signed JWS objects plus one signed epoch record, and one public-computation object:

1. `public_attestation.jws` (`chit402.public_receipt.v1`, ES256) — signs, exactly: `task_id`, `iss`, `issued_at` (minute), `attested_at` (minute), `payment {rail, ref, asset, payee, gross_amount, settled_amount}`, `log {epoch, leaf_index, leaf_hash}`. Payload bytes are the tag line + newline + RFC 8785 canonical claims.
2. `inclusion.signed_head.signature` (`chit402.tree_head.v2`, ES256) — signs the head: `root`, `tree_size`, `epoch`, `prev_root`, `prev_epoch_root`, `prev_epoch_size`, `bundle_index_hash`, `anchor_status`, `anchors.{base,solana}` (tx, calldata/memo, block_ts/slot, from/fee_payer), `published_at`, `clock_tolerance_s`.
3. `issuer-history.json` (`chit402.issuer_history.v1`, ES256) — the key chain: one entry, the KMS key, `not_before 2026-09-04T08:52:05Z`, `not_after null`, `seq 2`.
4. `/v1/receipts/tree/epoch` (`chit402.tree_epoch.v1`, ES256) — epoch 1 closed (final root `dd20e39a…`, size 4), epoch 2 open, orphans, `unlogged {count, commitment}`.
5. `inclusion.proof` — public computation, no signature: an RFC 6962 path from the leaf to the head root.

### Checks (89 PASS, 8 falsifier self-tests rejected; `outputs/verify.out`)

1. **Manifest pins** — the 10 fetched documents match `raw/manifest.sha256`.
2. **Key identity (RFC 7638)** — the JWKS holds exactly one P-256 key; `BASE64URL(SHA-256(JCS({crv,kty,x,y})))` recomputed from the coordinates equals the header kid `IvFpmC-…` and the round-1 pinned kid; the history entry carries the same coordinates. The kid is recomputed from the key, not read as a label.
3. **ES256, offline, exact JWS byte strings** — the attestation, the tree head, the history, and the epoch record all verify under that one key (`node:crypto`, raw R‖S).
4. **Issuer-history chain (RFC 8785)** — `entry_hash` equals SHA-256 of the JCS bytes of the entry minus its own `entry_hash` (cross-validates this script's JCS against the issuer's); `head_hash` = the entry hash; single entry, `prev_hash null`, active, never revoked; signed payload `entry_count=1`, `version=2`, `seq=2` match; the key window covers `attested_at` and the head's `published_at`.
5. **Attestation canonical form + allowlist** — the payload is exactly the tag line + JCS claims; the claim keys are exactly the allowlist (no `payload_version`, no `v`); `iss == chit402`; minute precision; `issued_at <= attested_at`.
6. **Claims vs shell** — every attested field equals the unsigned shell copy: `task_id`, `issued_at`, `asset`, `payee == pay_to`, `gross_amount`, `settled_amount`, `ref == base:payment_tx`, `rail`, `log.leaf_hash`.
7. **Inclusion, with an independently derived path** — the RFC 6962 path for (leaf_index 34, size 43) is derived in this script from subtree ranges (node `(level, j)` covers `[j·2^level, (j+1)·2^level − 1]`; a sibling enters the path iff its subtree holds ≥1 existing leaf), not from the provided labels: sides R,L,R,R,L, length 5, every provided label agrees. Folding `dbb7229f…` with the proof reaches the signed root `36213397…`. The listing-example leaf (`24685dd1…`, index 30) folds to the current root @43 (6 sides R,L,L,L,L,R) **and** to the size-34 head `b19c4d34…` via `?tree_size=34` — the same root ompi's round-1 run anchored (continuity). Two cross-path identities hold: the node `[0,31]` (`2e53dd84…`) recomputed from the leaf-30 path equals the leaf-34 path's final sibling; the node `[32,33]` (`850004bd…`) from the leaf-30@34 top sibling equals the leaf-34 level-1 sibling.
8. **Consistency 34 → 43** — the endpoint's 5-node proof is consumed by a reimplementation of the RFC 6962 §2.1.4 reconstruction (subtrees inside the old tree claimed for both roots); both roots are rebuilt and match `first_root`/`second_root`; the proof is fully consumed (5/5); four of the five nodes equal nodes independently known from the inclusion paths; the fifth (`132fe6a4…` = `[40,41]`) is only reachable through the algorithm.
9. **Epoch chaining** — head `prev_epoch_root` = signed epoch doc's closed epoch-1 `final_root` = the round-1 pinned `EPOCH1_FINAL_ROOT dd20e39a…`; `prev_epoch_size` = 4 = epoch-1 `final_size`; the head's signed JWS is byte-identical across the shell, the head endpoint, and the inclusion endpoint; anchor `calldata == 0x` + root; `from` = pinned anchor EOA; `block_ts` within `clock_tolerance_s.base` of `published_at` (Δ = 58.8 s vs 300 s).
10. **Solana memo recomputed** — the signed memo is a pure function of the signed head fields (`chit402:root:v2:global:<date>:<root>:<prev_root>:<epoch>:<prev_epoch_root>:<prev_epoch_size>:<bundle_index_hash>`); reconstructed from the JWS payload and byte-equal to `anchors.solana.memo`; `fee_payer` = the pinned account.
11. **On-chain corroboration (`outputs/check-chain.out`)** — anchor tx `0x9ef64e3a…` on Base: success, self-transfer, `from` = pinned anchor EOA, `input` = the 32-byte root, block 53134983 `timestamp 1793059313` = the signed `block_ts`; identical on three independent providers (mainnet.base.org, base-rpc.publicnode.com, base.drpc.org). Payment tx `0x731e4fdc…`: success, exactly one USDC `Transfer` (token `0x833589fc…`) of 2000 atomic to the signed payee `0x23f713…`, token sender `0x9d42eba8868cfd38a50ba615ee0cf903f1bbece9` (reported, not claimed — the attestation does not sign the payer). Solana tx `228pgHY…`: slot `461859546` = signed, fee payer = pinned account, `err: null`, memo byte-equal to the signed memo.
12. **Falsifier self-tests** — each must fail to verify, and each does: head root +1 nibble (fold mismatch); attestation `settled_amount` 2001 (canonical bytes differ); attestation payee swapped (same); proof position label flipped (fold to wrong value, labels no longer match the derived sides); history `entry_hash` tampered (JCS mismatch); head JWS signature byte corrupted (ES256 reject); `leaf_hash` swapped to the old leaf (fold mismatch); kid label tampered one char (recomputed thumbprint does not match).
13. **Cross-check against the shipped verifier** — `chit402-verify` 0.4.11 (pinned tarball, its own fetches) returns `verified_public`, exit 0, same checks and same anchor refs on this receipt (`outputs/verifier-3155.json`), and `could_not_check` / `signed_receipt_unavailable`, exit 2, on the unsigned example shell (`outputs/verifier-shell-56e3.json`). The independent run and the issuer's tool agree.

### Where trust was required (every step that could not be checked)

1. **The KMS key itself.** The issuer history is signed by the current key; the chain has one entry and no external anchor. The root of trust is the single published ES256 key as of `not_before 2026-09-04T08:52:05Z` (established in round 1; the history is unchanged — same kid, `seq 2`, same `entry_hash`). A stranger who accepts the key at any one point trusts it for every later object.
2. **The anchor EOA `0x1844d1f5…` and the Solana fee payer `8ef3Gt…`.** Calldata and memo are arbitrary bytes; on-chain anchoring proves *someone holding these wallets* posted the root, not that the KMS signer is that wallet. The verifier checks sender/fee-payer membership, which is the full strength of the anchor model. Compromise of anchor wallet + KMS key together would let a forged head anchor and sign.
3. **The epoch-2 opening root `f2043ee9…` and the genesis digests.** The signed epoch doc declares them; the orphans record says the opening root was anchored Oct 5, but carries no tx for that anchor, and this pass did not chase it. The epoch link verified here is the closed-epoch root (`dd20e39a…`), which is also the round-1 pin.
4. **`unlogged {count: 231, commitment b3da9b0f…}`.** The signature binds the issuer to the digest; the id set is not public, so the count and the set are a signed claim, not an auditable fact (finding F4).
5. **The same-size predecessor head `prev_root 4bd1f044…` (tree_size 43 → 43).** The current head declares it; no public endpoint serves that head, so its signature/anchor cannot be re-verified from this pass. The 34→43 consistency proof establishes the prefix relation across the growth, not this same-size step.
6. **The RPC providers.** Three Base endpoints and the public Solana RPC answered; cross-provider agreement is a check, not a trust removal.
7. **TLS** to `api.chit402.com` via the system CA bundle — inherent to any fetcher.
8. **`chain_from` asymmetry, noted not trusted:** the payment's token sender (`0x9d42…`) differs from the round-1 payer (`0x9f8951…`); the public attestation does not sign the payer, so nothing here claims who paid.

## (b) Review — findings, each with a repro

### F1 — the shipped README pins the version output to a version it does not ship (0.4.11)

The 0.4.11 package README states: "`--version` prints `chit402-verify 0.4.6`." It prints `chit402-verify 0.4.11` plus the supported-versions table; `package.json` is 0.4.11. Repro: `bash repro-f1.sh` (`outputs/repro-f1.out`). A version gate that pins the README's literal string fails against the shipped binary; the version it names (0.4.6) predates the package by five releases — the same class of stale pin that this listing exists to catch.

### F2 — the shipped README documents a CLI mode the CLI rejects (0.4.11)

The 0.4.11 README documents `xfuel-verify receipt.json inclusion.json head.json` ("also runs those receipt checks. A matching inclusion proof does not make a tampered receipt VERIFIED"). The 0.4.11 CLI rejects the second positional: exit 1, `removed_flag`, "removed in 0.4: pass one receipt id, url, or file". Repro: `bash repro-f2.sh` (`outputs/repro-f2.out`). The documented workflow is unavailable in the version that ships it, and the safety note attached to it describes a mode that no longer exists.

### F3 — `?format=auditor` still returns the byte-identical `?format=json` body, while the machine-readable contract advertises a different view

OpenAPI `/receipt/{taskId}` documents `format` as "json (machine), auditor (policy + totals), or HTML (default)"; the chit402-verify README says "auditor selective disclosure via `?format=auditor`". Live, both receipts return identical bytes for the two formats: `xfuel-3155b7d8…` json/auditor sha256 `68c9dca9…`, `chit-56e3ee6d…` `66a6e701…`. Repro: `bash repro-f3.sh` (`outputs/repro-f3.out`). Round-1 B2 is partially closed: the gateway's VERIFY_ALGORITHM.md now discloses the identity ("`?format=auditor` currently returns the same body as `?format=json`"); the OpenAPI enum and the verifier README have not followed. An auditor client that branches on the advertised view silently gets the shell.

### F4 — the signed `unlogged` count is a claim a stranger cannot audit (design)

The signed epoch record (payload version 3) carries `unlogged: {count: 231, commitment: b3da9b0f…}`. The gateway source (`services/gateway/src/receipt-log-epoch.js`, `unloggedIdCommitment`, at the pinned commit) defines the commitment as SHA-256 of the UTF-8 JSON `{"count":N,"ids":[…sorted unique task ids…]}` — recomputable by a stranger **given the ids**. No public endpoint serves the ids: the OpenAPI lists no unlogged route, and the only unlogged surface is the signed document itself. The reason set for unlogged rows is `forked`, `missing_row_hash`, `depends_on_refused` (receipt-log-anchor.js) — rows that exist, not secrets. Since each task id's shell is already retrievable per-id from the public `/receipt/:id` route, publishing the sorted id list (chunked if large) would convert the signed count from a claim into an auditable set at no secrecy cost. Repro: fetch `/v1/receipts/tree/epoch` (in `raw/`), scan the OpenAPI (`/openapi.json`) for a route serving the ids, read the source function.

### F5 — the two-chain anchor degrades to one responding chain plus one wallet (design, documented)

The head claims `anchors.base.status = anchored` and `anchors.solana.status = anchored`. The verifier (0.4.10 onward, documented in the shipped README: "One confirmed anchor is enough") passes the anchor check when one chain confirms the root and the other chain's RPC lookup only failed — a transport failure, timeout, or null; a rejected JSON-RPC answer is *not* covered. Combined with the anchor model of (a)-trust-point 2 (calldata/memo are bytes from one anchor wallet per chain, checked only for wallet membership), the effective guarantee at verification time is: at least one responding chain shows the root bytes from the anchor wallet. The scenario: the anchor EOA is compromised and the attacker anchors a chosen root on Base; if the Solana RPC is unreachable at the stranger's verification moment, the head passes on Base alone; with the KMS key of the same trust party also available, a forged head and attestation then verify end-to-end offline. This is documented, so it is not a hidden defect — it is the actual strength of the "anchored on both chains" label on the signed payload, stated here because the payload advertises both statuses without the asymmetry. No live forgery was made or is needed; the instance is the head in `raw/tree-head.json` plus the README text quoted in `repro` form above.

### Round-1 findings, re-tested on 0.4.11 this pass

| Round-1 finding | Status on 0.4.11 (2026-10-27) | Evidence |
|---|---|---|
| B1 — tree-head JWS accepted as a receipt issuer signature (0.4.2/0.4.4/0.4.5/0.4.7; forged doc printed overall `verified`, unsigned control `partial`) | **Fixed** (since 0.4.8). Forged doc: `overall: failed`, `typ_mismatch`; control: `partial`. | `bash repro-b1-0411.sh` → `outputs/repro-b1-0411.out` |
| B2 — `?format=auditor` byte-identical to `?format=json` against the OpenAPI | **Partially addressed** → F3. VERIFY_ALGORITHM.md now discloses the identity; OpenAPI + verifier README still advertise the distinct view. | `bash repro-f3.sh` |
| B3 — VERIFY_ALGORITHM.md's public path unrunnable on the live v10 shell | **Fixed.** The doc now lists the shell's exact fields, states it carries no `issuer_signature`/`preimages`, and gives exit 2 for a shell alone — matching the live shell fetched this pass. | doc text @ pinned commit vs `raw/receipt-shell-56e3.json` |
| B4 — shell omits `leaf_index` (strander needed the inclusion endpoint or a brute force) | **Fixed.** Doc notes the omission; `/v1/receipts/:id/inclusion` returns `leaf_index` + `tree_size`; the public attestation signs `leaf_index`. | `raw/inclusion-3155.json`; attestation claims (§5) |
| arenaforge — `verifyAnchoredRoot` false `stale_head` rejection of the newer head (0.4.8) | **Superseded** by the 0.4.10 anchor redesign (one anchor enough; documented). The `checkNewestAnchor` path is gone from 0.4.11 dist. | `grep checkNewestAnchor dist/` → none; README "One confirmed anchor is enough (0.4.10)" |
| arenaforge — `verifyV11Receipt` skipped issuer-history/payer validation and reported `issuer_history: {checked:false, ok:true}` (0.4.8) | **Verdict-level fixed; report-shape residual.** `verifyReceipt` re-derives `overall` from the shared verdict (`withLibraryVerdict`, index.js: "overall is read from the shared verdict. Only exit 0 is verified"); an unchecked history or payer maps to exit 2 (`partial`), never 0. Residual: the v11 shell object still prints `issuer_history: {checked:false, ok:true, loaded:false}` — `ok: true` beside a check that never ran is a consumer trap for anyone reading the report shape instead of the verdict (`v11-receipt.js` `shell()`, 0.4.11). | `dist/v11-receipt.js:157-166`, `dist/index.js withLibraryVerdict` |

## Files

- `fetch.sh`, `verify.mjs`, `check-chain.sh` — the (a) pipeline (node stdlib only; python for JSON; no Chit402 code).
- `repro-f1.sh`, `repro-f2.sh`, `repro-f3.sh`, `repro-b1-0411.sh`, `repro-b1.mjs` — the (b) repros.
- `raw/` — the 10 fetched documents + `manifest.sha256`.
- `outputs/` — captured runs: `verify.out`, `check-chain.out`, `verifier-3155.json`, `verifier-shell-56e3.json`, `repro-f1.out`, `repro-f2.out`, `repro-f3.out`, `repro-b1-0411.out`.
- `npm/chit402-verify-0.4.11.tgz` — pinned verifier tarball; `pins.txt` — all pins.
- `chain-tmp/` — ephemeral RPC responses from the last `check-chain.sh` run (safe to delete).
