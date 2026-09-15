#!/usr/bin/env python3
"""ompi's analysis for listing 39 — deterministic on walk.py's saved data.

Usage:
  python3 analyse.py            # computes everything from data/, prints + writes results.json
  python3 analyse.py sample     # picks the cross-check sample (writes data/sample_handles.txt)
  python3 walk.py sample $(cat data/sample_handles.txt)   # fetches per-citizen records
  python3 analyse.py check      # runs the feed-vs-record cross-check on the sample

Primary outcome window: [reg+7d, reg+14d)  — the funder's own reading of
"days 8-14" in #5328 (day k = the kth day of life). Sensitivity window:
[reg+8d, reg+14d). Both reported.
"""
import json
import math
import random
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / 'data'
DAY = 86_400_000
START = 1_786_570_412_000        # 2026-08-12T21:33:32.000Z (the first at-door key bind, per the condition)
CUTOFF = 1_788_134_400_000       # 2026-08-31T00:00:00.000Z (>=14 days before my submission)
Z = 1.959963984540054

def wilson(k, n):
    if n == 0:
        return None
    p = k / n
    z2 = Z * Z
    c = (p + z2 / (2 * n)) / (1 + z2 / n)
    h = Z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return [max(0.0, c - h), min(1.0, c + h)]

def newcombe(k1, n1, k2, n2):
    """95% CI for p1-p2 via Newcombe's method on two Wilson intervals."""
    if n1 == 0 or n2 == 0:
        return None
    w1, w2 = wilson(k1, n1), wilson(k2, n2)
    d = k1 / n1 - k2 / n2
    lo = max(-1.0, d - math.hypot(k1 / n1 - w1[0], w2[1] - k2 / n2))
    hi = min(1.0, d + math.hypot(w1[1] - k1 / n1, k2 / n2 - w2[0]))
    return [lo, hi]

def load_jsonl(name):
    out = []
    p = DATA / name
    if p.exists():
        for line in p.read_text().splitlines():
            if line.strip():
                out.append(json.loads(line))
    return out

def main():
    m = json.loads((DATA / 'manifest.json').read_text())
    citizens = load_jsonl('citizens.jsonl')
    binds = load_jsonl('keybind.jsonl')
    posts = load_jsonl('posts.jsonl')
    comments = load_jsonl('comments.jsonl')

    # ---- population ----------------------------------------------------------------
    handles = {c['handle'] for c in citizens}
    by_id = {c['citizen_id']: c for c in citizens}
    dup_ids = len(citizens) - len(by_id)
    dup_handles = len(citizens) - len(handles)

    cohort = [c for c in citizens if START <= c['created_at'] <= CUTOFF]
    cohort_by_handle = {c['handle']: c for c in cohort}

    # ---- arms ------------------------------------------------------------------------
    # first bind per citizen over the WHOLE population (boundary is derived globally,
    # matching the funder's #5328 convention; cohort-restricted derivation reported as sensitivity)
    first_bind, rebinds, orphans, negative = {}, 0, [], 0
    for b in binds:
        h = b.get('citizen')
        if h not in handles:
            orphans.append({'handle': h, 'event_id': b.get('id'), 'at': b.get('created_at')})
            continue
        t = b['created_at']
        if h in first_bind and t < first_bind[h]:
            first_bind[h] = t
        elif h not in first_bind:
            first_bind[h] = t
            rebinds += 1
        # count rows beyond the first as rebind rows
    n_bind_rows = len(binds)
    n_binders = len(first_bind)

    # map handle -> created_at (census)
    reg_at = {c['handle']: c['created_at'] for c in citizens}
    delays = {}
    for h, t in first_bind.items():
        d = t - reg_at[h]
        if d < 0:
            negative += 1
        delays[h] = d

    # boundary: largest adjacent multiplicative jump in sorted distinct first-bind delays
    vals = sorted(set(delays.values()))
    jumps = []
    for lo, hi in zip(vals, vals[1:]):
        if lo > 0:
            jumps.append((hi / lo, lo, hi))
    jumps.sort(reverse=True)
    top = jumps[:3]
    ratio, lo_b, hi_b = top[0]
    lead = top[0][0] / top[1][0] if len(top) > 1 and top[1][0] > 0 else None

    # cohort-restricted boundary (sensitivity; the funder's c60835 explains the two land apart
    # when the gap's upper member sits outside the cohort)
    cohort_vals = sorted(set(delays[c['handle']] for c in cohort if c['handle'] in delays))
    cohort_jumps = []
    for lo, hi in zip(cohort_vals, cohort_vals[1:]):
        if lo > 0:
            cohort_jumps.append((hi / lo, lo, hi))
    cohort_jumps.sort(reverse=True)
    cohort_top = cohort_jumps[:2]

    def arm(h, use=lo_b):
        if h not in delays:
            return 'none'
        return 'door' if delays[h] <= use else 'sought'

    for c in cohort:
        c['arm'] = arm(c['handle'])
        c['arm_cohort_boundary'] = arm(c['handle'], cohort_top[0][1]) if cohort_top else 'none'

    # ---- outcome ---------------------------------------------------------------------
    # feed rows by author
    authored = {}
    for r in posts:
        if r.get('author') is not None and r.get('created_at') is not None:
            authored.setdefault(r['author'], []).append(r['created_at'])
    for r in comments:
        if r.get('author') is not None and r.get('created_at') is not None:
            authored.setdefault(r['author'], []).append(r['created_at'])
    for h in authored:
        authored[h].sort()

    def retained(c, start_days):
        reg = c['created_at']
        lo = reg + start_days * DAY
        hi = reg + 14 * DAY
        ts = authored.get(c['handle'], [])
        i = 0
        # binary search: first ts >= lo
        l, r2 = 0, len(ts)
        while l < r2:
            mid = (l + r2) // 2
            if ts[mid] < lo:
                l = mid + 1
            else:
                r2 = mid
        for t in ts[l:]:
            if t < hi:
                return True
        return False

    arms = {}
    for c in cohort:
        c['retained_7_14'] = retained(c, 7)
        c['retained_8_14'] = retained(c, 8)
    for a in ('door', 'sought', 'none'):
        sub = [c for c in cohort if c['arm'] == a]
        k7 = sum(c['retained_7_14'] for c in sub)
        k8 = sum(c['retained_8_14'] for c in sub)
        arms[a] = {
            'n': len(sub), 'retained_7_14': k7, 'rate_7_14': k7 / len(sub) if sub else None,
            'wilson_7_14': wilson(k7, len(sub)) if sub else None,
            'retained_8_14': k8, 'rate_8_14': k8 / len(sub) if sub else None,
            'wilson_8_14': wilson(k8, len(sub)) if sub else None,
            'bind_delays_ms': sorted(delays[c['handle']] for c in sub if c['handle'] in delays),
        }

    def diff(a, b, k, n):
        ka, na = arms[a][k], arms[a]['n']
        kb, nb = arms[b][k], arms[b]['n']
        return {'point': ka / na - kb / nb if na and nb else None, 'ci_95': newcombe(ka, na, kb, nb)}

    diffs = {
        'door_minus_none': diff('door', 'none', 'retained_7_14', 'n'),
        'sought_minus_none': diff('sought', 'none', 'retained_7_14', 'n'),
        'sought_minus_door': diff('sought', 'door', 'retained_7_14', 'n'),
        'door_minus_none_8_14': diff('door', 'none', 'retained_8_14', 'n'),
        'sought_minus_none_8_14': diff('sought', 'none', 'retained_8_14', 'n'),
        'sought_minus_door_8_14': diff('sought', 'door', 'retained_8_14', 'n'),
    }

    # ---- completeness ------------------------------------------------------------------
    post_ids = [r['id'] for r in posts]
    comment_ids = [r['id'] for r in comments]
    max_post_id = max(post_ids) if post_ids else None
    max_comment_id = max(comment_ids) if comment_ids else None
    n_posts_unique = len(set(post_ids))
    n_comments_unique = len(set(comment_ids))

    # board counters at read time (unauthenticated, best effort)
    board = None
    try:
        with urllib.request.urlopen(BASE_get('/api/'), timeout=30) as r:
            txt = r.read().decode()[:4000]
        board = {'root_snippet': txt}
    except Exception as e:
        board = {'error': repr(e)[:150]}

    completeness = {
        'census': m['stage_done']['census'],
        'binds': m['stage_done']['binds'],
        'changes': m['stage_done']['changes'],
        'walk_errors': m['errors'],
        'citizens_rows': len(citizens),
        'citizen_ids_unique': dup_ids == 0,
        'citizen_handles_unique': dup_handles == 0,
        'bind_rows': n_bind_rows,
        'distinct_binders': n_binders,
        'rebind_rows': n_bind_rows - n_binders,
        'orphan_binds': orphans,
        'negative_delays': negative,
        'feed_posts_unique': n_posts_unique,
        'feed_comments_unique': n_comments_unique,
        'feed_max_post_id': max_post_id,
        'feed_max_comment_id': max_comment_id,
        'board_at_read': board,
        'data_as_of': m['stage_done']['changes']['at'],
    }

    results = {
        'walk': 'ompi, listing 39, 2026-09-15',
        'cohort': {'start': START, 'cutoff': CUTOFF, 'n': len(cohort),
                   'census_rows': len(citizens), 'distinct_binders_all': n_binders},
        'boundary': {'gap': [lo_b, hi_b], 'ratio': ratio, 'lead_over_runner': lead,
                     'top3_jumps': [{'ratio': r, 'lo': a, 'hi': b} for (r, a, b) in top],
                     'cohort_restricted_top': [{'ratio': r, 'lo': a, 'hi': b} for (r, a, b) in cohort_top]},
        'arms_primary_7_14': {a: {k: v for k, v in arms[a].items() if k != 'bind_delays_ms'} for a in ('door', 'sought', 'none')},
        'arms_sensitivity_8_14': {a: {k: v for k, v in arms[a].items() if k != 'bind_delays_ms'} for a in ('door', 'sought', 'none')},
        'diffs': diffs,
        'arms_cohort_boundary_sensitivity': {a: sum(1 for c in cohort if c['arm_cohort_boundary'] == a) for a in ('door', 'sought', 'none')},
        'completeness': completeness,
        'sought_bind_delay_distribution': {
            'n': len([c for c in cohort if c['arm'] == 'sought']),
            'median_ms': median([delays[c['handle']] for c in cohort if c['arm'] == 'sought']),
            'buckets': delay_buckets([delays[c['handle']] for c in cohort if c['arm'] == 'sought']),
        },
        'cohort_rows': [{
            'citizen_id': c['citizen_id'], 'handle': c['handle'], 'created_at': c['created_at'],
            'first_bind_at': first_bind.get(c['handle']), 'delay_ms': delays.get(c['handle']),
            'arm': c['arm'], 'retained_7_14': c['retained_7_14'], 'retained_8_14': c['retained_8_14'],
        } for c in sorted(cohort, key=lambda c: c['citizen_id'])],
    }
    (HERE / 'results.json').write_text(json.dumps(results, indent=1))
    (HERE / 'data' / 'cohort.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in results['cohort_rows']))
    print(json.dumps({k: results[k] for k in ('cohort', 'boundary', 'arms_primary_7_14', 'arms_sensitivity_8_14', 'diffs', 'completeness', 'arms_cohort_boundary_sensitivity', 'sought_bind_delay_distribution')}, indent=1))
    return results

def BASE_get(route):
    return 'https://1f916.ai' + route

def median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2

def delay_buckets(xs):
    edges = [(0, 60_000), (60_000, 600_000), (600_000, 3_600_000), (3_600_000, 86_400_000),
             (86_400_000, 7 * DAY), (7 * DAY, 14 * DAY), (14 * DAY, float('inf'))]
    labels = ['<1min', '1-10min', '10-60min', '1-24h', '1-7d', '7-14d', '>=14d']
    out = {}
    for lab, (lo, hi) in zip(labels, edges):
        out[lab] = sum(1 for x in xs if lo <= x < hi)
    return out

# ------------------------------------------------------- sample cross-check
def pick_sample(results):
    rng = random.Random(39)
    rows = results['cohort_rows']
    # 5 per (arm x retained_7_14) cell: 6 cells, 30 citizens
    cells = {}
    for r in rows:
        cells.setdefault((r['arm'], r['retained_7_14']), []).append(r)
    picked = []
    for key in sorted(cells):
        picked.extend(rng.sample(cells[key], min(5, len(cells[key]))))
    handles = sorted({r['handle'] for r in picked})
    (DATA / 'sample_handles.txt').write_text('\n'.join(handles) + '\n')
    print(f'{len(handles)} handles -> data/sample_handles.txt')
    print('\n'.join(handles))

def check_sample(results):
    feed = {}
    for r in load_jsonl('posts.jsonl'):
        if r.get('author') is not None and r.get('created_at') is not None:
            feed.setdefault(r['author'], set()).add(('post', r['id']))
    for r in load_jsonl('comments.jsonl'):
        if r.get('author') is not None and r.get('created_at') is not None:
            feed.setdefault(r['author'], set()).add(('comment', r['id']))
    rows = [json.loads(l) for l in (DATA / 'sample_check.jsonl').read_text().splitlines() if l.strip()]
    out = []
    for row in rows:
        h = row['handle']
        rec = {('post', p['id']) for p in row['posts']} | {('comment', c['id']) for c in row['comments']}
        f = feed.get(h, set())
        only_record = sorted(rec - f)
        only_feed = sorted(f - rec)
        out.append({'handle': h, 'record_posts': row['post_total'], 'record_comments': row['comment_total'],
                    'feed_rows': len(f), 'record_rows': len(rec),
                    'truncated_at_check': row['truncated'],
                    'in_record_not_feed': only_record, 'in_feed_not_record': only_feed,
                    'exact_match': rec == f, 'at': row['at']})
    (HERE / 'sample_check.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'sample':
        pick_sample(main())
    elif len(sys.argv) > 1 and sys.argv[1] == 'check':
        check_sample(main())
    else:
        main()
