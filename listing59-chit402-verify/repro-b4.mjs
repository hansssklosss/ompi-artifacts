#!/usr/bin/env node
// repro-b4.mjs — B4: the public receipt shell carries the inclusion proof and
// the signed root but NOT the leaf_index; the RFC 9162 fold needs the index,
// so a stranger holding only the shell must fetch a second endpoint
// (/v1/receipts/:id/inclusion) or brute-force the tree (34 folds).
// Public GETs only. Node 18+ stdlib.
import { createHash } from 'node:crypto';

const base = 'https://api.chit402.com';
const shell = await (await fetch(`${base}/receipt/chit-56e3ee6d-2acb-4cab-8fa4-dfd5f9f31e6f?format=json`)).json();
const raw = JSON.stringify(shell);

console.log('1. leaf_index present anywhere in the shell bytes?', raw.includes('leaf_index'));
console.log('2. shell.inclusion keys:', Object.keys(shell.inclusion).sort().join(', '));

// RFC 9162 fold (same semantics as verify.mjs / the public verifier).
const sha256 = (b) => createHash('sha256').update(b).digest();
const nodeHash = (l, r) => sha256(Buffer.concat([Buffer.from([1]), l, r]));
const half = (n) => Math.floor(n / 2);
function fold(leafHex, index, size, proof) {
  let fn = index, sn = size - 1;
  let h = Buffer.from(leafHex, 'hex');
  for (const step of proof) {
    if (sn === 0) return null;
    const sib = Buffer.from(step.hash, 'hex');
    const left = (fn % 2) === 1 || fn === sn;
    h = left ? nodeHash(sib, h) : nodeHash(h, sib);
    if (left && (fn % 2) === 0) while ((fn % 2) === 0 && fn !== 0) { fn = half(fn); sn = half(sn); }
    fn = half(fn); sn = half(sn);
  }
  return sn !== 0 ? null : h.toString('hex');
}

const root = shell.inclusion.signed_head.root;
const size = shell.inclusion.signed_head.tree_size;
const proof = shell.inclusion.proof;
const leaf = shell.inclusion.leaf_hash;
const solutions = [];
for (let i = 0; i < size; i += 1) if (fold(leaf, i, size, proof) === root) solutions.push(i);
console.log('3. brute force: indices that fold to the signed root:', solutions.join(', ') || '(none)');

const inc = await (await fetch(`${base}/v1/receipts/${shell.task_id}/inclusion`)).json();
console.log('4. /v1/receipts/:id/inclusion names leaf_index:', inc.leaf_index, '(unique solution:', solutions.length === 1 ? 'yes' : 'no', ')');
console.log(solutions.length === 1 && solutions[0] === inc.leaf_index
  ? 'B4 FIRES: the shell alone does not name the index; a second endpoint or a full-tree brute force is required.'
  : 'B4 does not fire as stated; inspect the output.');
