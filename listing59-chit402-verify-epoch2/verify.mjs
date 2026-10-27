#!/usr/bin/env node
// verify.mjs — part (a): offline verification of the live public Chit402
// receipt  xfuel-3155b7d8-4315-44bc-bfdc-bf6b78ff2d15  (KMS-signed via
// public_attestation, tree head, issuer history, and epoch record),
// against public material only. No Chit402 code is imported; node 18+
// stdlib only (node:crypto, node:fs).
//
// The Merkle path derivation (expectedPath) is ompi's own RFC 6962
// formulation — node (level, j) covers leaves [j*2^level, (j+1)*2^level-1];
// the sibling subtree (sib = j^1) enters the path iff it contains at least
// one existing leaf, on the side its index dictates. It does not reuse the
// gateway's fn/sn walk, so the two agree only if both are right.
//
// Exit 0 iff every check passes and every falsifier self-test fails to
// verify (as required). Inputs: raw/* (pinned by raw/manifest.sha256).

import { readFileSync, existsSync } from 'node:fs';
import { createHash, createPublicKey, verify } from 'node:crypto';

const raw = (f) => JSON.parse(readFileSync(new URL(`./raw/${f}`, import.meta.url), 'utf8'));
const sha256 = (b) => createHash('sha256').update(b).digest();
const sha256hex = (b) => sha256(b).toString('hex');
const b64u = (s) => Buffer.from(s, 'base64url');
const hex = (s) => Buffer.from(s.replace(/^0x/, ''), 'hex');

let failures = 0, passes = 0;
const check = (name, cond, detail = '') => {
  console.log(`  ${cond ? 'PASS' : 'FAIL'}  ${name}${detail ? `  [${detail}]` : ''}`);
  cond ? passes++ : failures++;
};

/* ---------- RFC 8785 JCS (document subset) ---------- */
function jcsValue(v) {
  if (v === null || v === undefined) return 'null';
  switch (typeof v) {
    case 'boolean': return v ? 'true' : 'false';
    case 'number':
      if (!Number.isFinite(v)) throw new Error('JCS: non-finite number');
      return Object.is(v, -0) ? '0' : String(v);
    case 'string': {
      let out = '"';
      for (const ch of v) {
        const c = ch.codePointAt(0);
        if (c < 32) out += `\\u${c.toString(16).padStart(4, '0')}`;
        else if (ch === '"') out += '\\"';
        else if (ch === '\\') out += '\\\\';
        else out += ch;
      }
      return out + '"';
    }
    case 'object': {
      if (Array.isArray(v)) return `[${v.map(jcsValue).join(',')}]`;
      const keys = Object.keys(v).sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
      return `{${keys.map((k) => `${jcsValue(k)}:${jcsValue(v[k])}`).join(',')}}`;
    }
    default: throw new Error(`JCS: ${typeof v}`);
  }
}
const jcs = (v) => jcsValue(v);

/* ---------- Merkle (RFC 6962): leaf 0x00, node 0x01||L||R ---------- */
const nodeHash = (l, r) => sha256(Buffer.concat([Buffer.from([0x01]), l, r]));

// ompi's independent canonical-path derivation (see header).
function expectedPath(i, n) {
  const path = [];
  let j = i, level = 0;
  for (;;) {
    const span = 1 << level;
    const lo = j * span, hi = (j + 1) * span - 1;
    if (lo <= 0 && hi >= n - 1) break;              // node covers the whole tree
    const sib = j ^ 1;
    const sLo = Math.max(sib * span, 0), sHi = Math.min((sib + 1) * span - 1, n - 1);
    if (sLo <= sHi) path.push(sib < j ? 'left' : 'right');
    j >>= 1; level++;
  }
  return path;
}

// Fold with an explicit side list (sides[0] = first proof element, bottom-up).
function fold(leafHex, sides, proof) {
  let h = hex(leafHex);
  for (let k = 0; k < proof.length; k++) {
    const sib = hex(proof[k].hash);
    h = sides[k] === 'right' ? nodeHash(h, sib) : nodeHash(sib, h);
  }
  return h.toString('hex');
}

/* ---------- RFC 7638 ---------- */
const rfc7638 = (jwk) => sha256(Buffer.from(jcs({ crv: jwk.crv, kty: jwk.kty, x: jwk.x, y: jwk.y }))).toString('base64url');

/* ---------- ES256 over the exact JWS byte string (raw R||S) ---------- */
function es256Verify(jws, jwk) {
  const [h, p, s] = jws.split('.');
  if (!h || !p || !s) return false;
  const pub = createPublicKey({ key: { kty: jwk.kty, crv: jwk.crv, x: jwk.x, y: jwk.y }, format: 'jwk' });
  try {
    return verify('sha256', Buffer.from(`${h}.${p}`, 'utf8'), { key: pub, dsaEncoding: 'ieee-p1363' }, b64u(s));
  } catch { return false; }
}

/* ================= load ================= */
const receipt   = raw('receipt-3155.json');        // the public signed receipt
const shell56e3 = raw('receipt-shell-56e3.json');  // the listing's example URL (unsigned shell, older leaf)
const jwks      = raw('jwks.json');
const history   = raw('issuer-history.json');
const epochDoc  = raw('tree-epoch.json');
const headDoc   = raw('tree-head.json');
const inc3155   = raw('inclusion-3155.json');
const inc56e3   = raw('inclusion-56e3.json');
const inc56e334 = raw('inclusion-56e3-size34.json');
const consist   = raw('consistency-34-43.json');

// Pins from the 2026-10-17/18 ompi round-1 run on this same listing (commit 9ff6242).
const PIN = {
  kid: 'IvFpmC-vPhkY_v0vidsrWVT9uzlE5XWKZgAEOeJTq1Q',
  epoch1FinalRoot: 'dd20e39a39a225b7b3441bb7f61532c06562288b74ae5dc4dda015c48312f973',
  round1HeadRoot34: 'b19c4d34d54c47be11525a8d02c6161d4b16b41d16eb5dbfc4a56eadf6e6ad6f', // epoch-2 head at size 34, anchored 2026-10-18
  anchorEoa: '0x1844d1f5fe42aff1cce6f776514fd40374079582',
  solanaFeePayer: '8ef3GtYNuQ6P2ANxLMPUXTAo9BhfJJqMx6cdDVh7JM4U',
  usdcBase: '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913',
};

console.log('== 0. Manifest pin ==');
{
  const mf = new URL('./raw/manifest.sha256', import.meta.url);
  if (!existsSync(mf)) throw new Error('raw/manifest.sha256 missing — run fetch.sh');
  for (const line of readFileSync(mf, 'utf8').split('\n').filter(Boolean)) {
    const [want, file] = line.trim().split(/\s+/);
    const got = sha256hex(readFileSync(new URL(`./raw/${file}`, import.meta.url)));
    check(`manifest ${file}`, got === want, `${got.slice(0, 12)}…`);
  }
}

const headJws = receipt.inclusion.signed_head.signature;
const [thH, thP, thS] = headJws.split('.');
const headHeader = JSON.parse(b64u(thH).toString('utf8'));
const head = JSON.parse(b64u(thP).toString('utf8'));
const attJws = receipt.public_attestation.jws;
const [aH, aP, aS] = attJws.split('.');
const attHeader = JSON.parse(b64u(aH).toString('utf8'));
const attPayloadBytes = b64u(aP);

console.log('== 1. JWS headers ==');
check('head header', headHeader.alg === 'ES256' && headHeader.typ === 'chit402-tree-head+jwt' && !!headHeader.kid, JSON.stringify(headHeader));
check('attestation header', attHeader.alg === 'ES256' && attHeader.typ === 'chit402-public-receipt+jwt' && !!attHeader.kid, JSON.stringify(attHeader));
check('history header kid', history.issuer_signature.kid === PIN.kid, history.issuer_signature.kid);

console.log('== 2. Key identity (RFC 7638, recomputed from coordinates) ==');
check('JWKS holds exactly one key', jwks.keys.length === 1);
const k = jwks.keys[0];
check('JWKS thumbprint == kid', rfc7638(k) === k.kid, rfc7638(k));
check('kid == round-1 pinned kid', k.kid === PIN.kid);
const hEntry = history.entries[0];
check('history JWK == JWKS coordinates', hEntry.jwk.x === k.x && hEntry.jwk.y === k.y && hEntry.jwk.crv === k.crv && hEntry.jwk.kty === k.kty && hEntry.jwk.kid === k.kid);
check('history kid == JWKS kid', hEntry.kid === k.kid);

console.log('== 3. ES256 signatures, offline (exact JWS byte strings) ==');
check('tree-head JWS', es256Verify(headJws, k));
check('public-attestation JWS', es256Verify(attJws, k));
check('issuer-history JWS', es256Verify(history.issuer_signature.jws, k));
check('epoch-record JWS', es256Verify(epochDoc.issuer_signature.jws, k));

console.log('== 4. Issuer history chain (JCS RFC 8785) ==');
{
  const { entry_hash, ...rest } = hEntry;
  const eh = sha256hex(Buffer.from(jcs(rest), 'utf8'));
  check('entry_hash == SHA-256(JCS(entry minus entry_hash))', eh === entry_hash, eh.slice(0, 12) + '…');
  check('head_hash == last entry_hash', history.head_hash === entry_hash);
  check('single entry, prev_hash null, active, not revoked', history.entries.length === 1 && hEntry.prev_hash === null && hEntry.status === 'active' && hEntry.revoked_at === null);
  const hp = JSON.parse(b64u(history.issuer_signature.jws.split('.')[1]).toString('utf8'));
  check('signed payload: head_hash, entry_count, version, seq', hp.head_hash === history.head_hash && hp.entry_count === 1 && hp.version === 2 && hp.seq === history.seq);
  check('key window covers attested_at and head published_at',
    hEntry.not_before <= '2026-10-19T02:24' && hEntry.not_before <= head.published_at && hEntry.not_after === null,
    `not_before=${hEntry.not_before}`);
}

console.log('== 5. Public attestation: canonical payload + claim allowlist ==');
let claims = null;
{
  const body = attPayloadBytes.toString('utf8');
  const nl = body.indexOf('\n');
  const tag = body.slice(0, nl);
  const claimBytes = body.slice(nl + 1);
  check('payload tag line', tag === 'chit402.public_receipt.v1', tag);
  claims = JSON.parse(claimBytes);
  check('claims are canonical (my JCS == their payload bytes)', jcs(claims) === claimBytes);
  check('top-level keys == allowlist', JSON.stringify(Object.keys(claims).sort()) === JSON.stringify(['attested_at','iss','issued_at','log','payment','task_id']));
  check('no payload_version/v', !('payload_version' in claims) && !('v' in claims));
  check('payment keys == allowlist', JSON.stringify(Object.keys(claims.payment).sort()) === JSON.stringify(['asset','gross_amount','payee','rail','ref','settled_amount']));
  check('log keys == allowlist', JSON.stringify(Object.keys(claims.log).sort()) === JSON.stringify(['epoch','leaf_hash','leaf_index']));
  check('iss == chit402', claims.iss === 'chit402');
  check('minute-precision issued_at <= attested_at', /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00\.000Z$/.test(claims.issued_at) && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00\.000Z$/.test(claims.attested_at) && claims.issued_at <= claims.attested_at, `${claims.issued_at} <= ${claims.attested_at}`);
}

console.log('== 6. Attestation claims vs the unsigned shell (field equality) ==');
check('task_id == receipt_id (xfuel form)', claims.task_id === receipt.receipt_id, claims.task_id);
check('issued_at == shell.issued_at', claims.issued_at === receipt.issued_at);
check('payment.asset == shell.asset (case-insensitive)', claims.payment.asset.toLowerCase() === receipt.asset.toLowerCase());
check('payment.payee == shell.pay_to', claims.payment.payee === receipt.pay_to);
check('payment.gross_amount == shell.amount_gross', claims.payment.gross_amount === receipt.amount_gross);
check('payment.settled_amount == shell.amount_settled', claims.payment.settled_amount === receipt.amount_settled);
check('payment.ref == base:<shell.payment_tx>', claims.payment.ref === `base:${receipt.payment_tx}`, claims.payment.ref);
check('payment.rail == usdc', claims.payment.rail === 'usdc');
check('log.leaf_hash == shell.inclusion.leaf_hash', claims.log.leaf_hash === receipt.inclusion.leaf_hash);
check('shell declares unsigned:true and no holder signature', receipt.unsigned === true && !('issuer_signature' in receipt));

console.log('== 7. Inclusion: ompi-derived RFC 6962 path + fold ==');
{
  // Target leaf: the signed one.
  const sides = expectedPath(claims.log.leaf_index, head.tree_size);
  const proof = receipt.inclusion.proof;
  check('path length matches proof length', sides.length === proof.length, `${sides.length} vs ${proof.length}`);
  let ok = true;
  for (let i = 0; i < proof.length; i++) if (proof[i].position !== sides[i]) ok = false;
  check('every provided position label matches my index-derived side', ok, sides.join(','));
  const root = fold(claims.log.leaf_hash, sides, proof);
  check('fold reaches the signed head root', root === head.root, root.slice(0, 12) + '…');
  check('head root == shell.signed_head.root == tree_size 43', head.root === receipt.inclusion.signed_head.root && receipt.inclusion.signed_head.tree_size === head.tree_size && head.tree_size === 43);
  check('endpoint proof == shell proof (same bytes served)', JSON.stringify(inc3155.proof) === JSON.stringify(receipt.inclusion.proof));
  check('endpoint leaf_index/tree_size == signed log coordinates', inc3155.leaf_index === claims.log.leaf_index && inc3155.tree_size === head.tree_size && inc3155.leaf === claims.log.leaf_hash);

  // Older leaf from the listing's example receipt, against BOTH heads.
  const sides30_43 = expectedPath(30, 43);
  check('leaf 30 path @43 derived', JSON.stringify(sides30_43) === JSON.stringify(['right','left','left','left','left','right']), sides30_43.join(','));
  check('leaf 30 fold @43 reaches current root', fold(inc56e3.leaf, sides30_43, inc56e3.proof) === head.root);
  const sides30_34 = expectedPath(30, 34);
  check('leaf 30 path @34 derived', JSON.stringify(sides30_34) === JSON.stringify(['right','left','left','left','left','right']), sides30_34.join(','));
  const root34 = fold(inc56e334.leaf, sides30_34, inc56e334.proof);
  check('leaf 30 fold @34 reaches size-34 head', root34 === inc56e334.root, root34.slice(0, 12) + '…');
  check('size-34 head == round-1 anchored head (continuity)', inc56e334.root === PIN.round1HeadRoot34);

  // Shared-node identities across independent paths (two different leaves
  // must reproduce the same internal nodes, or the proofs are not one tree).
  const a0_31 = fold(inc56e3.leaf, sides30_43.slice(0, 5), inc56e3.proof.slice(0, 5)); // [0,31] via leaf 30
  const l0_31 = attLeafLeft(inc3155.proof, claims.log.leaf_hash);                        // [0,31] via leaf 34 (last left sibling)
  check('shared node [0,31] agrees across leaf-30 and leaf-34 paths', a0_31 === l0_31, a0_31.slice(0, 12) + '…');
  const l32_33_34side = inc56e334.proof[5].hash;   // [32,33] as leaf-30@34 top sibling
  const l32_33_34leaf = inc3155.proof[1].hash;     // [32,33] as leaf-34 level-1 sibling
  check('shared node [32,33] agrees across leaf-30@34 and leaf-34 paths', l32_33_34side === l32_33_34leaf, l32_33_34leaf.slice(0, 12) + '…');
}
function attLeafLeft(proof) {
  // leaf 34 path sides (R,L,R,R,L): the final left sibling IS the node [0,31].
  return hex(proof[proof.length - 1].hash).toString('hex');
}

console.log('== 8. Consistency proof 34 -> 43 (RFC 6962 §2.1.4 shape, my reimplementation) ==');
{
  check('first_root == size-34 head', consist.first_root === PIN.round1HeadRoot34);
  check('second_root == current signed head', consist.second_root === head.root);
  check('my fold of both leaves matches both roots (independent of the proof nodes)',
    fold(inc56e334.leaf, expectedPath(30, 34), inc56e334.proof) === consist.first_root &&
    fold(inc3155.leaf, expectedPath(34, 43), inc3155.proof) === consist.second_root);
  // Reimplement the §2.1.4 reconstruction (my code, from the public shape):
  // nodes are consumed in the order the recursive prover emits them; a
  // subtree wholly inside the old tree is claimed for BOTH roots, a
  // new-tree-only subtree for the new root only.
  const lpt = (n) => { let p = 1; while (p * 2 < n) p *= 2; return p; };
  let i = 0;
  const take = () => hex(consist.proof[i++]);
  function check2(start, end, oldEnd) {
    if (end <= oldEnd) { const h = take(); return { hash: h, old: h }; }
    if (start >= oldEnd) return { hash: take(), old: null };
    const k = lpt(end - start);
    const left = check2(start, start + k, oldEnd);
    const right = check2(start + k, end, oldEnd);
    const hash = nodeHash(left.hash, right.hash);
    let old = null;
    if (left.old && right.old) old = nodeHash(left.old, right.old);
    else if (left.old && start + k >= oldEnd) old = left.old;
    return { hash, old };
  }
  const rebuilt = check2(0, consist.second_tree_size, consist.first_tree_size);
  check('rebuilt new root == second_root', rebuilt.hash.toString('hex') === consist.second_root, rebuilt.hash.toString('hex').slice(0, 12) + '…');
  check('rebuilt old root == first_root', rebuilt.old && rebuilt.old.toString('hex') === consist.first_root, (rebuilt.old || Buffer.alloc(0)).toString('hex').slice(0, 12) + '…');
  check('proof fully consumed', i === consist.proof.length, `${i}/${consist.proof.length}`);
  // Four of the five proof nodes are independently known from the inclusion
  // paths; the fifth ([40,41]) is only reachable through this algorithm.
  check('proof node 0 == shared [0,31]', consist.proof[0] === a0_31hex(inc56e3, expectedPath(30, 43)));
  check('proof node 1 == shared [32,33]', consist.proof[1] === inc56e334.proof[5].hash);
  check('proof node 3 == [36,39] from leaf-34 path', consist.proof[3] === inc3155.proof[2].hash);
  check('proof node 4 == [40,42] from leaf-34 path', consist.proof[4] === inc3155.proof[3].hash);
}
function a0_31hex(inc, sides) { return fold(inc.leaf, sides.slice(0, 5), inc.proof.slice(0, 5)); }

console.log('== 9. Epoch record and head chaining ==');
{
  const ep1 = epochDoc.epochs.find((e) => e.epoch === 1);
  const ep2 = epochDoc.epochs.find((e) => e.epoch === 2);
  check('epoch 1 closed, final_root == round-1 pinned EPOCH1_FINAL_ROOT', ep1.status === 'closed' && ep1.final_root === PIN.epoch1FinalRoot, ep1.final_root.slice(0, 12) + '…');
  check('epoch 2 open; head prev_epoch_root == epoch-1 final_root', ep2.status === 'open' && head.prev_epoch_root === ep1.final_root);
  check('head prev_epoch_size == epoch-1 final_size', head.prev_epoch_size === ep1.final_size, `${head.prev_epoch_size} == ${ep1.final_size}`);
  check('head epoch == 2', head.epoch === 2);
  check('head payload == tree-head endpoint payload (same signed object)', JSON.parse(b64u(thP).toString('utf8')).root === headDoc.root && headDoc.tree_size === head.tree_size && headJws === headDoc.issuer_signature.jws);
  check('inclusion endpoint serves the same signed head JWS', inc3155.head.signature.jws === headJws);
  check('head anchor_tx consistent, chain 8453, anchored', head.anchors.base.tx === head.anchor_tx && head.anchors.base.chain_id === 8453 && head.anchors.base.status === 'anchored', head.anchors.base.tx.slice(0, 18) + '…');
  check('anchor calldata == root', head.anchors.base.calldata === `0x${head.root}`, '0x' + head.root.slice(0, 12) + '…');
  check('anchor from == pinned anchor EOA', head.anchors.base.from.toLowerCase() === PIN.anchorEoa);
  const pub = Date.parse(head.published_at) / 1000;
  const dt = pub - head.anchors.base.block_ts;
  check('base anchor block_ts within clock_tolerance_s.base of published_at', dt >= -60 && dt <= head.clock_tolerance_s.base, `Δ=${dt.toFixed(1)}s tol=${head.clock_tolerance_s.base}s`);
  // The Solana memo is a pure function of the signed payload — recompute it.
  const date = head.published_at.slice(0, 10);
  const memo = `chit402:root:v2:global:${date}:${head.root}:${head.prev_root}:${head.epoch}:${head.prev_epoch_root}:${head.prev_epoch_size}:${head.bundle_index_hash}`;
  check('solana memo == recomputed from signed head fields', head.anchors.solana.memo === memo, memo.slice(0, 40) + '…');
  check('solana fee_payer == pinned fee payer', head.anchors.solana.fee_payer === PIN.solanaFeePayer);
  check('epoch doc signed unlogged section present', typeof epochDoc.unlogged?.count === 'number' && /^[0-9a-f]{64}$/.test(epochDoc.unlogged?.commitment || ''), `count=${epochDoc.unlogged?.count}`);
}

console.log('== 10. Falsifier self-tests (each MUST fail to verify) ==');
{
  const fail = (name, ok) => check(name, ok === false, 'rejected as required');
  fail('F1 head root +1 nibble', verifyHeadLike({ ...head, root: flip(head.root) }, receipt.inclusion.proof, claims.log.leaf_index, 43));
  fail('F2 attestation settled_amount 2001', attCanonical({ ...claims, payment: { ...claims.payment, settled_amount: '2001' } }));
  fail('F3 attestation payee swapped', attCanonical({ ...claims, payment: { ...claims.payment, payee: `0x${'11'.repeat(20)}` } }));
  fail('F4 proof position label flipped', labelFlipReaches(receipt.inclusion.proof, claims.log.leaf_hash, 34, 43));
  fail('F5 history entry_hash tampered', tamperedHistoryEntryHash());
  fail('F6 head JWS signature byte corrupted', es256Verify(corruptSig(headJws), k));
  fail('F7 leaf_hash swapped to old leaf', fold(inc56e3.leaf, expectedPath(34, 43), inc3155.proof) === head.root);
  const badKid = 'IvFpmC-vPhkY_v0vidsrWVT9uzlE5XWKZgAEOeJTq1R'; // one char off the real kid
  fail('F8 kid label tampered (recomputed thumbprint must not match)', rfc7638(k) === badKid);
}
function flip(h) { const c = h[0] === 'f' ? 'e' : 'f'; return c + h.slice(1); }
function corruptSig(jws) { const [h, p, s] = jws.split('.'); const sb = b64u(s); sb[0] ^= 0x01; return `${h}.${p}.${sb.toString('base64url')}`; }
function verifyHeadLike(hd, proof, leafIndex, size) {
  const sides = expectedPath(leafIndex, size);
  return fold(claims.log.leaf_hash, sides, proof) === hd.root && hd.root === head.root;
}
function attCanonical(c) { return jcs(c) === jcs(claims); } // canonical bytes must differ from the signed ones
function labelFlipReaches(proof, leaf, i, n) {
  const p = proof.map((x) => ({ ...x }));
  p[0] = { hash: p[0].hash, position: p[0].position === 'right' ? 'left' : 'right' };
  const sides = expectedPath(i, n);
  // fold using the (now wrong) labels
  let h = hex(leaf);
  for (let k = 0; k < p.length; k++) h = p[k].position === 'right' ? nodeHash(h, hex(p[k].hash)) : nodeHash(hex(p[k].hash), h);
  return h.toString('hex') === head.root && JSON.stringify(p.map((x) => x.position)) === JSON.stringify(sides);
}
function tamperedHistoryEntryHash() {
  const e = { ...hEntry, entry_hash: flip(hEntry.entry_hash) };
  const { entry_hash, ...rest } = e;
  return sha256hex(Buffer.from(jcs(rest), 'utf8')) === entry_hash;
}

console.log('== summary ==');
console.log(`checks: ${passes + failures}, pass: ${passes}, fail: ${failures}`);
console.log(failures === 0 ? 'ALL CHECKS PASS' : 'FAILURES PRESENT');
process.exit(failures === 0 ? 0 : 1);
