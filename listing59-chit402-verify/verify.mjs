#!/usr/bin/env node
// verify.mjs — part (a): offline verification of Chit402 receipt
//   chit-56e3ee6d-2acb-4cab-8fa4-dfd5f9f31e6f  (xfuel-56e3ee6d-…)
// against public material only: the live receipt shell, the JWKS, the
// signed issuer history, the inclusion witness, and the pinned historical
// epoch-1 constants from the public verifier source.
//
// Inputs (from fetch.sh / the public endpoints):
//   raw/receipt.json          GET /receipt/chit-…?format=json
//   raw/jwks.json             GET /.well-known/jwks.json
//   raw/issuer-history.json   GET /.well-known/issuer-history.json
//   raw/inclusion.json        GET /v1/receipts/xfuel-…/inclusion
//
// Node 18+ stdlib only (node:crypto, node:fs). No Chit402 code is imported.
// Exit 0 when every check and every falsifier self-test behaves.
import { readFileSync, existsSync } from 'node:fs';
import { createHash, createPublicKey, verify, timingSafeEqual } from 'node:crypto';

const raw = (f) => JSON.parse(readFileSync(new URL(`./raw/${f}`, import.meta.url), 'utf8'));
const sha256hex = (b) => createHash('sha256').update(b).digest('hex');
const b64u = (s) => Buffer.from(s, 'base64url');

let failures = 0;
const check = (name, cond, detail = '') => {
  console.log(`  ${cond ? 'PASS' : 'FAIL'}  ${name}${detail ? ': ' + detail : ''}`);
  if (!cond) failures += 1;
};

/* --- minimal RFC 8785 JCS (document subset: no floats, no control chars) --- */
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
        const code = ch.codePointAt(0);
        if (code < 32) out += `\\u${code.toString(16).padStart(4, '0')}`;
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

/* --- RFC 9162 inclusion fold (mirrors the public verifier's inclusionRoot) --- */
const half = (n) => Math.floor(n / 2);
const nodeHash = (l, r) => createHash('sha256').update(Buffer.concat([Buffer.from([1]), l, r])).digest();
function inclusionRoot(leaf, index, size, proof) {
  if (index < 0 || index >= size) return null;
  let fn = index, sn = size - 1;
  let h = Buffer.from(leaf);
  for (const step of proof) {
    if (sn === 0) return null;
    if (!/^[0-9a-fA-F]{64}$/.test(step.hash)) return null;
    const sib = Buffer.from(step.hash, 'hex');
    const siblingOnLeft = (fn % 2) === 1 || fn === sn;
    if (siblingOnLeft) {
      h = nodeHash(sib, h);
      if ((fn % 2) === 0) while ((fn % 2) === 0 && fn !== 0) { fn = half(fn); sn = half(sn); }
    } else h = nodeHash(h, sib);
    fn = half(fn); sn = half(sn);
  }
  return sn !== 0 ? null : h.toString('hex');
}
function positionAgrees(index, size, proof) {
  let fn = index, sn = size - 1;
  for (const step of proof) {
    if (sn === 0) return false;
    const siblingOnLeft = (fn % 2) === 1 || fn === sn;
    if (typeof step.position === 'string' && step.position !== ''
      && step.position !== (siblingOnLeft ? 'left' : 'right')) return false;
    if (siblingOnLeft && (fn % 2) === 0) while ((fn % 2) === 0 && fn !== 0) { fn = half(fn); sn = half(sn); }
    fn = half(fn); sn = half(sn);
  }
  return true;
}

/* --- RFC 7638 thumbprint --- */
const rfc7638 = (jwk) =>
  Buffer.from(sha256hex(jcs({ crv: jwk.crv, kty: jwk.kty, x: jwk.x, y: jwk.y })), 'hex')
    .toString('base64url');

/* --- ES256 (raw R||S, as JWS requires) --- */
const es256 = (jws, jwk) => {
  const [h, p, s] = jws.split('.');
  const pub = createPublicKey({ key: { kty: jwk.kty, crv: jwk.crv, x: jwk.x, y: jwk.y }, format: 'jwk' });
  return verify('sha256', Buffer.from(`${h}.${p}`, 'utf8'), { key: pub, dsaEncoding: 'ieee-p1363' }, b64u(s));
};

/* ================= load ================= */
const receipt = raw('receipt.json');
const jwks = raw('jwks.json');
const history = raw('issuer-history.json');
const inclusion = raw('inclusion.json');

const treeHeadJws = receipt.inclusion.signed_head.signature;
const [thH, thP, thS] = treeHeadJws.split('.');
const headClaims = JSON.parse(b64u(thP).toString('utf8'));
const headHeader = JSON.parse(b64u(thH).toString('utf8'));

console.log('== 0. Manifest pin (if fetch.sh was run) ==');
{
  const mf = new URL('./raw/manifest.sha256', import.meta.url);
  if (existsSync(mf)) {
    for (const line of readFileSync(mf, 'utf8').split('\n').filter(Boolean)) {
      const [want, file] = line.split(/\s+/);
      const got = sha256hex(readFileSync(new URL(`./raw/${file}`, import.meta.url)));
      check(`sha256 raw/${file}`, got === want, got);
    }
  } else {
    console.log('  INFO  no manifest.sha256 (run fetch.sh first for a pinned fetch)');
  }
}

console.log('== 1. JWS header ==');
check('alg ES256', headHeader.alg === 'ES256', headHeader.alg);
check('typ chit402-tree-head+jwt', headHeader.typ === 'chit402-tree-head+jwt', headHeader.typ);
const kid = headHeader.kid;
check('kid present', /^[A-Za-z0-9_-]+$/.test(kid || ''), kid);

console.log('== 2. Key identity: RFC 7638 ==');
const jwkKeys = jwks.keys;
check('JWKS has exactly one key', jwkKeys.length === 1, `${jwkKeys.length} key(s)`);
const jwk = jwkKeys[0];
const t1 = rfc7638(jwk);
check('JWKS thumbprint == kid', timingSafeEqual(Buffer.from(t1), Buffer.from(jwk.kid)), t1);
const hEntry = history.entries[0];
const t2 = rfc7638(hEntry.jwk);
check('history-entry thumbprint == kid', timingSafeEqual(Buffer.from(t2), Buffer.from(hEntry.kid)), t2);
check('JWKS key == history key (same coordinates)', jwk.x === hEntry.jwk.x && jwk.y === hEntry.jwk.y);

console.log('== 3. ES256 signatures (offline) ==');
check('tree-head JWS verifies under the JWKS key', es256(treeHeadJws, jwk));
const histJws = history.issuer_signature.jws;
check('issuer-history JWS verifies under the same key', es256(histJws, jwk));
const histHeader = JSON.parse(b64u(histJws.split('.')[0]).toString('utf8'));
check('history JWS typ is chit402-issuer-history+jwt', histHeader.typ === 'chit402-issuer-history+jwt', histHeader.typ);

console.log('== 4. Issuer-history chain + JCS ==');
check('single entry', history.entries.length === 1);
const entryNoHash = { ...hEntry };
delete entryNoHash.entry_hash;
const recomputedEntry = sha256hex(Buffer.from(jcs(entryNoHash), 'utf8'));
check('entry_hash == SHA-256(JCS(entry minus entry_hash)) — also proves this JCS implementation',
  recomputedEntry === hEntry.entry_hash, `${recomputedEntry} vs ${hEntry.entry_hash}`);
check('head_hash == last entry_hash', history.head_hash === hEntry.entry_hash);
check('first entry prev_hash is null', hEntry.prev_hash === null);
const histClaims = JSON.parse(b64u(histJws.split('.')[1]).toString('utf8'));
check('signed entry_count == 1', histClaims.entry_count === 1, String(histClaims.entry_count));
check('signed head_hash matches', histClaims.head_hash === history.head_hash);
check('signed version/seq match the document', histClaims.version === history.version && histClaims.seq === history.seq,
  `v${histClaims.version}/s${histClaims.seq} vs v${history.version}/s${history.seq}`);

console.log('== 5. Key window ==');
const notBefore = Date.parse(hEntry.not_before);
const issuedAt = Date.parse(receipt.issued_at);
const publishedAt = Date.parse(headClaims.published_at);
check('issued_at >= not_before', issuedAt >= notBefore, `${receipt.issued_at} vs ${hEntry.not_before}`);
check('published_at >= not_before', publishedAt >= notBefore, `${headClaims.published_at}`);
check('not_after open (null)', hEntry.not_after === null);
check('status active, not revoked', hEntry.status === 'active' && hEntry.revoked_at === null,
  `${hEntry.status}/${hEntry.revoked_at}`);

console.log('== 6. Merkle inclusion (RFC 9162) ==');
const index = inclusion.leaf_index;
const size = inclusion.tree_size;
check('leaf_hash present on the shell', /^[0-9a-f]{64}$/.test(receipt.inclusion.leaf_hash || ''), receipt.inclusion.leaf_hash);
check('shell leaf_hash == inclusion.leaf', receipt.inclusion.leaf_hash === inclusion.leaf);
check('leaf_index < tree_size', index >= 0 && index < size, `${index} / ${size}`);
const folded = inclusionRoot(Buffer.from(receipt.inclusion.leaf_hash, 'hex'), index, size, inclusion.proof);
check('fold(leaf, index, size) == root', folded === headClaims.root, `${folded} vs ${headClaims.root}`);
check('root equal across shell / JWS claims / inclusion endpoint',
  receipt.inclusion.signed_head.root === headClaims.root && headClaims.root === inclusion.root);
check('proof position labels agree with the index-chosen sides', positionAgrees(index, size, inclusion.proof));
check('tree_size 34 consistent in shell, claims, inclusion',
  receipt.inclusion.signed_head.tree_size === 34 && headClaims.tree_size === 34 && size === 34);

console.log('== 7. Epoch link (against the public verifier pinned constants) ==');
// Pinned in the public source packages/verify/src/epoch.ts (commit 89577f3a):
const EPOCH1_FINAL_ROOT = 'dd20e39a39a225b7b3441bb7f61532c06562288b74ae5dc4dda015c48312f973'; // epoch.ts:16
const EPOCH1_FINAL_SIZE = 4; // epoch.ts:17
check('epoch is 2', headClaims.epoch === 2, String(headClaims.epoch));
check('prev_epoch_root == pinned EPOCH1_FINAL_ROOT', headClaims.prev_epoch_root === EPOCH1_FINAL_ROOT);
check('prev_epoch_size == pinned EPOCH1_FINAL_SIZE (4)', headClaims.prev_epoch_size === EPOCH1_FINAL_SIZE);

console.log('== 8. Anchor claims vs on-chain (see check-chain.sh) ==');
check('calldata == signed root bytes (0x-prefixed)', headClaims.anchors.base.calldata === '0x' + headClaims.root);
check('anchor_from == anchors.base.from', headClaims.anchor_from === headClaims.anchors.base.from, headClaims.anchor_from);
const clockDeltaS = Math.round((publishedAt - headClaims.anchors.base.block_ts * 1000) / 1000);
check('published_at within clock_tolerance_s.base of the anchor block ts',
  Math.abs(clockDeltaS) <= headClaims.clock_tolerance_s.base, `${clockDeltaS}s vs ${headClaims.clock_tolerance_s.base}s`);
check('anchor_status anchored, receipt_confirmed true (self-asserted; chain facts in check-chain.sh)',
  headClaims.anchor_status === 'anchored' && headClaims.anchors.base.status === 'anchored');

console.log('== 9. Trust points (steps where checking was not possible) ==');
console.log('  T1 bootstrap: the KMS key is trusted by its RFC 7638 kid + the self-signed history document;');
console.log('     the root of trust is the key first deployed 2026-09-04 (not_before_note), out of band.');
console.log('  T2 the shell is unsigned (unsigned: true): amount_gross/amount_settled/pay_to/payment_tx are');
console.log('     not covered by any public signature. /preimage says "payload_hash is over the owner-held bytes".');
console.log('     The economic facts are corroborated on-chain instead (check-chain.sh, two RPCs).');
console.log('  T3 leaf = SHA256(0x00 || task_id|row_hash); row_hash is owner-view only (shell.ts), so the');
console.log('     task_id -> leaf binding is NOT recomputable from public material. The inclusion endpoint');
console.log('     asserts it (task_id + leaf agree); no public attestation is served on this shell.');
console.log('  T4 the anchor is a self-send (to == from == anchor wallet) whose calldata is the raw 32-byte');
console.log('     root: nothing on chain validates the calldata format. The anchor wallet is the trust point.');
console.log('  T5 on-chain facts rest on public Base RPCs (two independent providers agree).');
console.log('  T6 the solana anchor is pending (day_already_anchored); its prior_signature is not checked here.');
console.log('  T7 my fold/JCS/ES256 implementations are cross-checked against published values (entry_hash,');
console.log('     fold->root); an implementation bug shared with the issuer would not be caught.');

console.log('== 10. Falsifier self-tests (the checker must reject its own tampering) ==');
{
  // flip the last bit of the signature
  const sig = b64u(thS);
  const sig2 = Buffer.from(sig);
  sig2[sig2.length - 1] ^= 0x01;
  const flipped = `${thH}.${thP}.${sig2.toString('base64url')}`;
  let threw = false, res = null;
  try { res = es256(flipped, jwk); } catch { threw = true; }
  check('S1 flipped signature bit is rejected', threw || res === false);
  const badLeaf = Buffer.from(receipt.inclusion.leaf_hash, 'hex');
  badLeaf[31] ^= 0x01;
  const folded2 = inclusionRoot(badLeaf, index, size, inclusion.proof);
  check('S2 flipped leaf byte does not fold to the root', folded2 !== headClaims.root, folded2);
  const badEntry = { ...hEntry, not_before: '2026-09-05T08:52:05Z' };
  delete badEntry.entry_hash;
  const recomputedBad = sha256hex(Buffer.from(jcs(badEntry), 'utf8'));
  check('S3 history entry +1 day breaks entry_hash', recomputedBad !== hEntry.entry_hash);
  const wrongKid = 'X' + kid.slice(1);
  check('S4 unknown kid has no JWKS key', !jwkKeys.some((k) => k.kid === wrongKid));
  const proof2 = inclusion.proof.map((p, i) => (i === 0 ? { ...p, position: p.position === 'left' ? 'right' : 'left' } : p));
  check('S5 swapped position label fails positionAgrees', !positionAgrees(index, size, proof2));
  // RFC 9162 property: for this leaf (index 30) the size-33 and size-34 folds
  // are identical, so a wrong tree_size is NOT a valid falsifier here; the
  // tree_size binding comes from the signed head, not the fold. A wrong leaf
  // index IS a valid falsifier (it reorders the first sibling).
  const idxOff = inclusionRoot(Buffer.from(receipt.inclusion.leaf_hash, 'hex'), index + 1, size, inclusion.proof);
  check('S6 wrong leaf index does not fold to the root', idxOff !== headClaims.root, idxOff);
  const size33 = inclusionRoot(Buffer.from(receipt.inclusion.leaf_hash, 'hex'), index, size - 1, inclusion.proof);
  console.log('  INFO  RFC9162: size-33 fold at this index is ' + (size33 === headClaims.root ? 'EQUAL to the signed root — the fold does not pin tree_size for this leaf; the signed head does' : 'different'));
}

console.log(failures === 0 ? '\nALL CHECKS PASS' : `\n${failures} CHECK(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
