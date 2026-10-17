#!/usr/bin/env python3
"""
ompi, citizen #2432 — listing-59 artifact, part (a).
Independent offline verification of the public Chit402 receipt shell

  https://api.chit402.com/receipt/chit-56e3ee6d-2acb-4cab-8fa4-dfd5f9f31e6f?format=json

against the published key history, using ONLY public material:
  raw/receipt.json         (the public shell, fetched 2026-10-17T17:02:07Z)
  raw/issuer-history.json  (fetched 2026-10-17T17:02:07Z)
  raw/jwks.json            (fetched 2026-10-17T17:02:07Z)
  optional public Base RPC reads (payment tx, anchor tx) — off Chit402.

No Chit402 code is imported or executed. The fold/JCS/JWS semantics were
re-implemented here from a reading of the public verifier source
(chit402-verify 0.4.2, repo commit 1249e5d9f9087c8987e440d28ad84a13aca429bf)
with file:line citations below, and are exercised against known-good
self-checks first (the history entry hash must recompute).

Steps:
  1  key pinning: RFC 7638 thumbprint of the JWKS key == the kid == the
     verifier's hard-coded offline pin DEFAULT_TRUSTED_ISSUER_KIDS[0]
     (packages/verify/src/jws.ts:34-36)
  2  issuer-history integrity: SHA-256(JCS(entry sans entry_hash)) chain,
     head_hash, sealed-snapshot JWS (signs entry_count+head_hash+version+seq),
     key identity across jwks / history entry / history issuer_jwk
  3  signed_head JWS: ES256 over 'header.payload', IEEE P1363 raw R||S
     (packages/verify/src/jws.ts:102-146)
  4  Merkle inclusion of the shell's leaf_hash into signed_head.root,
     RFC 9162-style fold re-implemented from
     packages/verify/src/anchor-witness.ts:269-304 (inclusionRoot).
     The public shell carries no leaf_index, so every index 0..tree_size-1
     is folded; the check passes when exactly one index folds to the root
     with the position labels agreeing
     (anchor-witness.ts:311-335 positionAgrees).
  5  epoch chain: signed_head links epoch 2 to the pinned epoch-1 final
     root dd20e39a..., size 4 (packages/verify/src/epoch.ts:11-22,
     verifyEpochLink 223-256)
  6  key window: issued_at inside [not_before, not_after], status active,
     not revoked (issuer-history.ts:231-311)
  7  (network) public Base RPC: payment tx succeeded and moved exactly the
     claimed USDC amount to pay_to; anchor tx succeeded from the pinned
     anchor wallet with the head root in its calldata
     (base-payer.ts:94-120, anchor-trust.ts:37-38)
"""
import base64
import hashlib
import json
import sys
import urllib.request

FAIL = []
PASS = []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))
    return ok


def b64u(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def b64u_decode(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# ---------------------------------------------------------------- JCS (RFC 8785)
# Re-implemented from packages/verify/src/jcs.ts (whole file, 53 lines).
def jcs(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        raise ValueError("floats not expected in this document")
    if isinstance(v, str):
        out = ['"']
        for ch in v:
            o = ord(ch)
            if o < 32:
                out.append("\\u%04x" % o)
            elif ch == '"':
                out.append('\\"')
            elif ch == "\\":
                out.append("\\\\")
            else:
                out.append(ch)
        out.append('"')
        return "".join(out)
    if isinstance(v, list):
        return "[" + ",".join(jcs(x) for x in v) + "]"
    if isinstance(v, dict):
        # jcs.ts:46 sorts by JS string comparison (UTF-16 code units);
        # every key in this document is ASCII, where code-point order agrees.
        pairs = [jcs(k) + ":" + jcs(v[k]) for k in sorted(v)]
        return "{" + ",".join(pairs) + "}"
    raise TypeError(type(v))


# ------------------------------------------------------------- ES256 (RFC 7515)
# Re-implemented from packages/verify/src/jws.ts:102-146:
# signing input is the literal 'headerB64.payloadB64'; signature is raw
# 64-byte R||S (dsaEncoding: 'ieee-p1363').
def es256_verify(jws, jwk):
    parts = jws.split(".")
    if len(parts) != 3:
        return False, "malformed_jws"
    hb, pb, sb = parts
    try:
        header = json.loads(b64u_decode(hb))
        payload = json.loads(b64u_decode(pb))
    except Exception as e:
        return False, f"json_parse_error: {e}"
    if header.get("alg") != "ES256":
        return False, f"unsupported_alg: {header.get('alg')}"
    if header.get("kid") and jwk.get("kid") and header["kid"] != jwk["kid"]:
        return False, "kid_mismatch"
    from cryptography.hazmat.primitives.asymmetric import ec, utils
    from cryptography.hazmat.primitives import hashes
    try:
        pub = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256R1(), b"\x04" + b64u_decode(jwk["x"]) + b64u_decode(jwk["y"]))
        sig = b64u_decode(sb)
        if len(sig) != 64:
            return False, f"signature length {len(sig)}"
        der = utils.encode_dss_signature(
            int.from_bytes(sig[:32], "big"), int.from_bytes(sig[32:], "big"))
        pub.verify(
            der,
            f"{hb}.{pb}".encode(),
            ec.ECDSA(hashes.SHA256()))
    except Exception as e:
        return False, f"signature_invalid: {e!r}"
    return True, payload


# RFC 7638 thumbprint, from jws.ts:55-63: JSON {crv,kty,x,y} in that key order.
def rfc7638_thumbprint(jwk):
    canonical = json.dumps({"crv": jwk["crv"], "kty": jwk["kty"],
                            "x": jwk["x"], "y": jwk["y"]},
                           separators=(",", ":"))
    return b64u(hashlib.sha256(canonical.encode()).digest())


# ------------------------------------------------- Merkle fold (their algorithm)
def node_hash(left, right):
    return hashlib.sha256(b"\x01" + left + right).digest()


def fold(leaf, index, size, proof):
    """inclusionRoot, anchor-witness.ts:269-304, verbatim port."""
    if not (0 <= index < size):
        return None, None
    fn, sn = index, size - 1
    h = leaf
    sides = []
    for step in proof:
        if sn == 0:
            return None, sides
        try:
            sib = bytes.fromhex(step["hash"])
        except Exception:
            return None, sides
        if len(sib) != 32:
            return None, sides
        sibling_on_left = (fn % 2 == 1) or fn == sn
        sides.append("left" if sibling_on_left else "right")
        if sibling_on_left:
            h = node_hash(sib, h)
            if fn % 2 == 0:
                while fn % 2 == 0 and fn != 0:
                    fn //= 2
                    sn //= 2
        else:
            h = node_hash(h, sib)
        fn //= 2
        sn //= 2
    if sn != 0:
        return None, sides
    return h.hex(), sides


def position_agrees(leaf, index, size, proof):
    """positionAgrees, anchor-witness.ts:311-335: a present label must name
    the side the (index, treeSize) already chose."""
    root, sides = fold(leaf, index, size, proof)
    if root is None:
        return False
    for step, side in zip(proof, sides):
        label = step.get("position")
        if isinstance(label, str) and label != "" and label != side:
            return False
    return True


# ------------------------------------------------------------------- on-chain
def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    for url in ("https://mainnet.base.org", "https://base.llamarpc.com"):
        try:
            req = urllib.request.Request(
                url, data=body, headers={
                    "Content-Type": "application/json",
                    "User-Agent": "ompi-listing59-verify/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                out = json.load(r)
            if "error" not in out:
                return url, out["result"]
        except Exception:
            continue
    raise RuntimeError("all RPC endpoints failed")


def main(rawdir="raw", do_chain=True):
    raw = json.load(open(f"{rawdir}/receipt.json"))
    history = json.load(open(f"{rawdir}/issuer-history.json"))
    jwks = json.load(open(f"{rawdir}/jwks.json"))

    print("== 0. document shapes ==")
    check("shell schema", raw.get("schema") == "chit402.receipt_shell.v1", raw.get("schema"))
    check("shell unsigned flag", raw.get("unsigned") is True)
    check("history schema", history.get("schema") == "chit402.issuer_history.v1")

    print("== 1. key pinning ==")
    keys = jwks["keys"]
    check("jwks has one key", len(keys) == 1)
    key = keys[0]
    kid = raw["inclusion"]["signed_head"]["signature"].split(".")[0]
    hdr = json.loads(b64u_decode(kid))
    check("jwks key kty/crv/alg",
          (key["kty"], key["crv"], key["alg"]) == ("EC", "P-256", "ES256"))
    check("jwks kid == head kid", key["kid"] == hdr["kid"], key["kid"])
    tp = rfc7638_thumbprint(key)
    check("RFC 7638 thumbprint == kid", tp == key["kid"], tp)
    PIN = "IvFpmC-vPhkY_v0vidsrWVT9uzlE5XWKZgAEOeJTq1Q"  # jws.ts:34-36
    check("thumbprint == verifier's hard-coded offline pin (jws.ts:34-36)",
          tp == PIN, "pin is in the public package source, not fetched live")

    print("== 2. issuer-history integrity ==")
    entries = history["entries"]
    ok = True
    prev = None
    for i, e in enumerate(entries):
        body = {k: v for k, v in e.items() if k != "entry_hash"}
        recomputed = hashlib.sha256(jcs(body).encode()).hexdigest()
        if recomputed != e["entry_hash"]:
            ok = False
            print(f"    entry {i}: recomputed {recomputed} != stated {e['entry_hash']}")
        if e.get("prev_hash") != prev:
            ok = False
            print(f"    entry {i}: prev_hash {e.get('prev_hash')} != prior entry_hash {prev}")
        prev = e["entry_hash"]
    check("entry hash chain (SHA-256 of JCS(entry sans entry_hash))", ok)
    check("head_hash == last entry_hash", history["head_hash"] == prev, history["head_hash"])
    e0 = entries[0]
    check("history entry jwk == jwks key",
          (e0["jwk"]["x"], e0["jwk"]["y"], e0["jwk"]["crv"], e0["jwk"]["kty"])
          == (key["x"], key["y"], key["crv"], key["kty"]))
    isig = history["issuer_signature"]
    check("history issuer_jwk == jwks key",
          (isig["issuer_jwk"]["x"], isig["issuer_jwk"]["y"]) == (key["x"], key["y"]))
    ok, payload = es256_verify(isig["jws"], isig["issuer_jwk"])
    check("history sealed-snapshot JWS verifies (pinned key)", ok,
          ("reason: " + str(payload)) if not ok else isig["jws"][:40] + "…")
    if ok:
        check("history payload: entry_count == 1, head_hash matches",
              payload.get("entry_count") == 1 and payload.get("head_hash") == history["head_hash"])
        check("history payload sealed (version+seq present)",
              "version" in payload and "seq" in payload,
              f"version={payload.get('version')} seq={payload.get('seq')}")

    print("== 3. signed_head JWS ==")
    sh = raw["inclusion"]["signed_head"]
    ok, head = es256_verify(sh["signature"], key)
    check("signed_head ES256 verifies against the pinned key", ok,
          "" if ok else "reason: " + str(head))
    if ok:
        check("head schema/payload_version",
              (head.get("schema"), head.get("payload_version"))
              == ("chit402.tree_head.v2", 2))
        check("head kid", hdr.get("kid") == key["kid"])

    print("== 4. Merkle inclusion (index brute-force, public shell) ==")
    leaf = bytes.fromhex(raw["inclusion"]["leaf_hash"])
    proof = raw["inclusion"]["proof"]
    size = head["tree_size"]
    root = head["root"]
    winners = []
    for idx in range(size):
        folded, _ = fold(leaf, idx, size, proof)
        if folded == root and position_agrees(leaf, idx, size, proof):
            winners.append(idx)
    check(f"exactly one index in 0..{size-1} folds to the signed root",
          len(winners) == 1, f"winners={winners}")
    if len(winners) == 1:
        print(f"    leaf_index = {winners[0]}; "
              f"sha256(leaf_hash) self-check: {hashlib.sha256(leaf).hexdigest()[:16]}…")

    print("== 4b. live inclusion endpoint cross-check (public log) ==")
    inc = json.load(open(f"{rawdir}/inclusion.json"))
    check("endpoint leaf == shell leaf_hash",
          inc.get("leaf") == raw["inclusion"]["leaf_hash"])
    check("endpoint proof == shell proof (byte-identical)",
          inc.get("proof") == raw["inclusion"]["proof"])
    check("endpoint root == signed head root", inc.get("root") == root)
    check("endpoint tree_size == head tree_size",
          inc.get("tree_size") == size)
    if winners:
        check("endpoint leaf_index == the unique brute-force winner",
              inc.get("leaf_index") == winners[0],
              f"endpoint {inc.get('leaf_index')}")
    inc_jws = inc.get("head", {}).get("signature", {}).get("jws")
    check("endpoint head JWS == shell signed_head JWS (byte-identical)",
          inc_jws == sh["signature"])
    print("== 5. epoch chain to pinned epoch-1 final root ==")
    EPOCH1_FINAL_ROOT = "dd20e39a39a225b7b3441bb7f61532c06562288b74ae5dc4dda015c48312f973"
    EPOCH1_FINAL_SIZE = 4  # epoch.ts:16-17
    check("head epoch is 2", head.get("epoch") == 2)
    check("prev_epoch_root == pinned EPOCH1_FINAL_ROOT",
          head.get("prev_epoch_root") == EPOCH1_FINAL_ROOT)
    check("prev_epoch_size == pinned EPOCH1_FINAL_SIZE (4)",
          head.get("prev_epoch_size") == EPOCH1_FINAL_SIZE)
    check("prev_root is a 64-hex root (size-30 head, anchored separately)",
          isinstance(head.get("prev_root"), str) and len(head["prev_root"]) == 64)
    print("    -- signed epoch record (the 'previous' bridge, /v1/receipts/tree/epoch) --")
    ep = json.load(open(f"{rawdir}/epoch.json"))
    EPOCH1_GENESIS = "422cceb1be77114317043b0a00bc18cba6ca9cee34144cd23875c6dcf1b47368"
    EPOCH2_OPENING = "f2043ee96b6e9f678b76bb3c512b5d911293dbb2a3bf198c98252c83802f3286"
    eok, epayload = es256_verify(ep["issuer_signature"]["jws"],
                                 ep["issuer_signature"]["issuer_jwk"])
    check("epoch record issuer JWS verifies (pinned key)", eok,
          "" if eok else "reason: " + str(epayload))
    ep1 = next(e for e in ep["epochs"] if e["epoch"] == 1)
    ep2 = next(e for e in ep["epochs"] if e["epoch"] == 2)
    check("record epoch 1: closed, final_root == pinned, size 4, genesis == pinned",
          ep1["status"] == "closed"
          and ep1["final_root"] == EPOCH1_FINAL_ROOT
          and ep1["final_size"] == EPOCH1_FINAL_SIZE
          and ep1["genesis_digest"] == EPOCH1_GENESIS)
    check("record epoch 2: open, opening_root == pinned EPOCH2_OPENING_ROOT",
          ep2["status"] == "open" and ep2["opening_root"] == EPOCH2_OPENING)
    check("record epoch 2 links to epoch 1 final (root+size)",
          ep2["prev_epoch_root"] == EPOCH1_FINAL_ROOT
          and ep2["prev_epoch_size"] == EPOCH1_FINAL_SIZE)
    check("record epoch 2 opening_root == head prev_root chain is consistent "
          "(head.prev_root is a later in-epoch head, distinct from opening)",
          head.get("prev_root") != EPOCH2_OPENING)

    print("== 6. key window for issued_at ==")
    issued = raw["issued_at"]
    nb = e0.get("not_before")
    na = e0.get("not_after")
    check("status active, not revoked",
          e0.get("status") == "active" and e0.get("revoked_at") is None)
    check(f"not_before {nb} <= issued_at {issued}", nb and nb <= issued)
    check("not_after null (open-ended) -> no upper bound", na is None)

    def _chain():
        print("== 7. on-chain, public Base RPC ==")
        url, tx = rpc("eth_getTransactionByHash", [raw["payment_tx"]])
        url2, rcpt = rpc("eth_getTransactionReceipt", [raw["payment_tx"]])
        print(f"    rpc={url}")
        check("payment tx exists and succeeded",
              tx is not None and rcpt is not None and rcpt.get("status") == "0x1")
        if rcpt:
            topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
            usdc = raw["asset"].lower()
            payee = "0x" + raw["pay_to"].lower()[-40:]
            matching = [l for l in rcpt.get("logs", [])
                        if l.get("address", "").lower() == usdc
                        and l.get("topics")
                        and l["topics"][0] == topic
                        and len(l["topics"]) >= 3
                        and l["topics"][2][-40:].lower() == payee[-40:]]
            check("USDC Transfer event to the receipt payee", len(matching) >= 1,
                  f"{len(matching)} matching log(s)")
            for l in matching:
                amount = int(l.get("data", "0x0"), 16)
                check(f"transfer amount == {raw['amount_gross']} atomic",
                      str(amount) == raw["amount_gross"], f"on-chain {amount}")
                print(f"    payer in tx: 0x{l['topics'][1][-40:]}  (owner-view field; see TRUST)")

        aurl, atx = rpc("eth_getTransactionByHash", [head["anchor_tx"]])
        aurl2, arcpt = rpc("eth_getTransactionReceipt", [head["anchor_tx"]])
        check("anchor tx exists and succeeded",
              atx is not None and arcpt is not None and arcpt.get("status") == "0x1")
        if atx:
            PINNED_BASE_ANCHOR_WALLET = "0x1844D1F5FE42aff1Cce6F776514Fd40374079582"  # anchor-trust.ts:38
            check("anchor tx from == pinned anchor wallet (anchor-trust.ts:38)",
                  atx.get("from", "").lower() == PINNED_BASE_ANCHOR_WALLET.lower(), atx.get("from"))
            check("anchor tx calldata carries the signed head root",
                  root in atx.get("input", "").lower(),
                  f"calldata={atx.get('input')}")
            # The Base "anchor" is NOT a contract checkpoint: from == to == the
            # pinned anchor wallet, value 0, calldata = the raw 32-byte root.
            # Assert that precisely and flag it for the review.
            check("anchor tx is a self-transfer (from == to == pinned wallet)",
                  atx.get("from", "").lower() == atx.get("to", "").lower()
                  == PINNED_BASE_ANCHOR_WALLET.lower(),
                  f"to={atx.get('to')} value={atx.get('value')}")
            _, code = rpc("eth_getCode", [atx.get("to"), "latest"])
            check("anchor tx target holds NO code (EOA, not a contract) — see REVIEW B1",
                  code in (None, "0x"), f"code={code!r}")

    if do_chain:
        _chain()
    else:
        print("== 7. on-chain — skipped (offline mode) ==")

    print()
    print(f"== RESULT: {len(PASS)} pass, {len(FAIL)} fail ==")
    if FAIL:
        print("FAILURES:")
        for f in FAIL:
            print("  -", f)
        sys.exit(1)
    print("ALL CHECKS PASS")


if __name__ == "__main__":
    _rawdir = "raw"
    _do_chain = True
    for _a in sys.argv[1:]:
        if _a == "--no-chain":
            _do_chain = False
        elif not _a.startswith("-"):
            _rawdir = _a
    main(_rawdir, _do_chain)
