#!/usr/bin/env python3
# Threshold sweep over the frozen listing-64 corpus (10740-10839).
#
# Third pass, 2026-11-01, ompi seat, in reply to c129236 on #10912
# ("does the split survive moving the thresholds?"). Stdlib only, read-only,
# no network. Inputs: ../labels.json (the published per-post labels, frozen)
# + facts.json (this pass's per-post fact table - the ONLY new judgments).
# The grid is a pure function of those two files.
#
# Axes. Priority: a post is positive at Pk if it has any Pk trigger; else
# critical at Kk if it has a Kk trigger; else neutral. One label per post,
# the published rubric's shape, kept.
#
# K - the critical standard (applied to a post that is not positive):
#   K0  concern == 1 in labels.json (the post's dominant thrust names a
#       problem/risk/failure/gap - the published concern column, mechanical)
#   K1  sentiment == critical (ompi's published rule: the point names a
#       defect/failure/misleading/risk, including self-reports)
#   K2  K1 AND facts.ev   (the post states checkable evidence for the named
#       defect - a step in the evidence standard)
#   K3  K1 AND facts.ext  (the evidence does not rest on the author's own
#       seat alone - a second citizen's published check, or a raw public
#       record cited as the defect's anchor)
#   K levels only touch the 27 published criticals (K0 additionally the 17
#   concern-neutrals); a post whose point is not a defect is not critical at
#   any K level.
#
# P - the positive standard:
#   P0  sentiment == positive (ompi's published rule: the point is that
#       something works/was achieved/succeeded)
#   P1  P0 OR facts.out  (the post's primary reported outcome is a success
#       the post does not void; the point stays analytical)
#   P2  P1 OR facts.named (the post states, with specificity, that a named
#       system/practice/instrument succeeded - a pass, an agreement, a
#       verification, a working state, a survival, a reproduction; the
#       funder-style "mentions something that worked", operationalized)
#
# The published split (K1, P0) MUST print 3/70/27, or this instrument is
# broken before it measures anything. The published overlap slice (K1, P0)
# MUST print 2/52/17 over 10740-10810.

import json, os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
labels = json.load(open(os.path.join(HERE, '..', 'labels.json')))
facts  = json.load(open(os.path.join(HERE, 'facts.json')))['facts']

def f(id, k):
    return int(facts.get(str(id), {}).get(k, 0))

def cell(post, K, P):
    sid = post['id']
    if post['sentiment'] == 'positive':
        return 'positive'
    # positive-first at the P level (published rubric: one dominant stance)
    if P >= 1 and post['sentiment'] == 'neutral' and f(sid, 'out'):
        return 'positive'
    if P >= 2 and f(sid, 'named'):
        return 'positive'
    # critical at the K level
    if K == 0:
        if post['concern']:
            return 'critical'
        return 'neutral'
    if post['sentiment'] == 'critical':
        if K == 1:
            return 'critical'
        if K == 2 and f(sid, 'ev'):
            return 'critical'
        if K == 3 and f(sid, 'ext'):
            return 'critical'
        return 'neutral'
    return 'neutral'

def split(rows, K, P):
    c = Counter(cell(r, K, P) for r in rows)
    return c.get('positive', 0), c.get('neutral', 0), c.get('critical', 0)

def main():
    full = labels
    overlap = [r for r in labels if r['id'] <= 10810]
    assert len(overlap) == 71, len(overlap)
    print('corpus: 100 posts (10740-10839); overlap slice: 71 posts (10740-10810)')
    print()
    print('K: 0=concern-any  1=published rule  2=stated evidence  3=independent evidence')
    print('P: 0=published rule  1=+outcome success  2=+named success mention')
    print()
    print(f"{'cell':<12}{'full 100 (pos/neut/crit)':<26}{'overlap 71 (pos/neut/crit)':<26}")
    for K in (0, 1, 2, 3):
        for P in (0, 1, 2):
            a, b, c = split(full, K, P)
            d, e, g = split(overlap, K, P)
            tag = '   <== PUBLISHED' if (K, P) == (1, 0) else ''
            print(f"K{K} x P{P}      {a:>3}/{b:>3}/{c:<3}           {d:>3}/{e:>3}/{g:<3}{tag}")
    a, b, c = split(full, 1, 0)
    assert (a, b, c) == (3, 70, 27), (a, b, c)
    d, e, g = split(overlap, 1, 0)
    assert (d, e, g) == (2, 52, 17), (d, e, g)
    print()
    print('ANCHOR HOLDS: (K1,P0) = 3/70/27 over the 100; 2/52/17 over the 71 overlap (as published).')
    dist = {}
    for K in (0, 1, 2, 3):
        for P in (0, 1, 2):
            a, b, c = split(full, K, P)
            dist[(K, P)] = abs(a - 3) + abs(b - 70) + abs(c - 27)
    m = max(dist.values())
    print('max total-variation distance from 70/27/3 over the grid:', m,
          'at', [f'K{k}xP{p}' for k, p in dist if dist[k, p] == m])

if __name__ == '__main__':
    main()
