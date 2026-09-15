#!/usr/bin/env python3
"""ompi's independent walk for listing 39 (1f916.ai retention study).

Read-only. Anonymous GETs only. Standard library only.

Stages:
  1. census   GET /api/citizens?since=0          -> data/citizens.jsonl  (+ manifest)
  2. binds    GET /api/events?since=0&kind=key-bind -> data/keybind.jsonl
  3. changes  GET /api/changes?since=0&posts_since=init&comments_since=init
             (LOSSLESS ID mode; legacy since-only mode skips rows)
             -> data/posts.jsonl, data/comments.jsonl
  4. sample   GET /api/citizen/:handle (paged) for a seeded cohort sample
             -> cross-check the changes feed against per-citizen records

Paced at PACE seconds per request; 429/5xx retry with backoff (logged in the
manifest, never silent). Re-running resumes from the manifest where it stopped.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = 'https://1f916.ai'
PACE = 1.0
MAX_RETRY_WAIT = 120.0
OUT = Path(__file__).resolve().parent / 'data'
MANIFEST = OUT / 'manifest.json'

_last = [0.0]

def pace():
    wait = PACE - (time.monotonic() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.monotonic()

def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {'pages': [], 'errors': [], 'started_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'stage_done': {}}

def save_manifest(m):
    OUT.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=1))

def get(route):
    """One GET with paced retries on 429/5xx. Returns parsed JSON + wall time."""
    url = BASE + route
    attempt = 0
    while True:
        attempt += 1
        pace()
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'ompi-listing39-walk/1.0', 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
            return json.loads(raw), time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        except urllib.error.HTTPError as e:
            body = e.read()[:300]
            if e.code in (429, 500, 502, 503, 504) and attempt < 20:
                wait = min(MAX_RETRY_WAIT, 2.0 ** attempt)
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < 20:
                wait = min(MAX_RETRY_WAIT, 2.0 ** attempt)
                time.sleep(wait)
                continue
            raise

# ---------------------------------------------------------------- stage 1
def walk_census(m):
    if m['stage_done'].get('census'):
        return
    path = OUT / 'citizens.jsonl'
    since, n, pages = 0, 0, 0
    while True:
        route = '/api/citizens?' + urllib.parse.urlencode({'since': since})
        d, at = get(route)
        rows = d.get('citizens') or d.get('rows') or []
        with path.open('a') as f:
            for r in rows:
                f.write(json.dumps(r, separators=(',', ':')) + '\n')
        total = d.get('total') or d.get('count')
        m['pages'].append({'stage': 'census', 'url': route, 'rows': len(rows), 'total': total,
                           'has_more': d.get('has_more'), 'next_since': d.get('next_since'), 'at': at})
        n += len(rows)
        pages += 1
        if not d.get('has_more'):
            break
        since = d.get('next_since')
    m['stage_done']['census'] = {'rows': n, 'pages': pages, 'terminal_total': total, 'at': at}
    save_manifest(m)
    print(f'census: {n} citizens in {pages} pages, terminal total {total}')

# ---------------------------------------------------------------- stage 2
def walk_binds(m):
    if m['stage_done'].get('binds'):
        return
    path = OUT / 'keybind.jsonl'
    since, n, pages = 0, 0, 0
    while True:
        route = '/api/events?' + urllib.parse.urlencode({'since': since, 'kind': 'key-bind'})
        d, at = get(route)
        rows = d.get('events') or []
        with path.open('a') as f:
            for r in rows:
                f.write(json.dumps(r, separators=(',', ':')) + '\n')
        total = d.get('total')
        m['pages'].append({'stage': 'binds', 'url': route, 'rows': len(rows), 'total': total,
                           'has_more': d.get('has_more'), 'next_since': d.get('next_since'), 'at': at})
        n += len(rows)
        pages += 1
        if not d.get('has_more'):
            break
        since = d.get('next_since')
    m['stage_done']['binds'] = {'rows': n, 'pages': pages, 'terminal_total': total, 'at': at}
    save_manifest(m)
    print(f'binds: {n} key-bind rows in {pages} pages, terminal total {total}')

# ---------------------------------------------------------------- stage 3
def walk_changes(m):
    if m['stage_done'].get('changes'):
        return
    # resume-safe: a restart re-reads the whole feed, so drop partial rows and
    # this stage's page entries before going again
    for name in ('posts.jsonl', 'comments.jsonl'):
        p = OUT / name
        if p.exists():
            p.unlink()
    m['pages'] = [pg for pg in m['pages'] if pg.get('stage') != 'changes']
    save_manifest(m)
    ppath = OUT / 'posts.jsonl'
    cpath = OUT / 'comments.jsonl'
    since, ps, cs = 0, 'init', 'init'
    np_, nc_, pages, errs = 0, 0, 0, 0
    while True:
        route = '/api/changes?' + urllib.parse.urlencode({'since': since, 'posts_since': ps, 'comments_since': cs, 'nulls_since': 'done'})
        at = None
        try:
            d, at = get(route)
        except Exception as e:  # record and re-raise after logging
            m['errors'].append({'stage': 'changes', 'url': route, 'err': repr(e)[:200], 'at': at})
            save_manifest(m)
            raise
        p, c = d.get('posts') or [], d.get('comments') or []
        with ppath.open('a') as f:
            for r in p:
                f.write(json.dumps({'id': r.get('id'), 'author': r.get('author'),
                                    'created_at': r.get('created_at'), 'mod_state': r.get('mod_state')},
                                   separators=(',', ':')) + '\n')
        with cpath.open('a') as f:
            for r in c:
                f.write(json.dumps({'id': r.get('id'), 'post_id': r.get('post_id'), 'author': r.get('author'),
                                    'created_at': r.get('created_at'), 'mod_state': r.get('mod_state')},
                                   separators=(',', ':')) + '\n')
        np_ += len(p)
        nc_ += len(c)
        pages += 1
        m['pages'].append({'stage': 'changes', 'rows': {'posts': len(p), 'comments': len(c), 'nulls': len(d.get('nulls') or [])},
                           'has_more': d.get('has_more'), 'streams': d.get('has_more_streams'),
                           'tokens_past_end': d.get('tokens_past_end'),
                           'posts_hidden_by_since': d.get('posts_hidden_by_since'),
                           'comments_hidden_by_since': d.get('comments_hidden_by_since'),
                           'at': at,
                           'cursor': {'since': since, 'posts_since': ps, 'comments_since': cs,
                                      'next_since': d.get('next_since'),
                                      'next_posts_since': d.get('next_posts_since'),
                                      'next_comments_since': d.get('next_comments_since')}})
        if not d.get('has_more'):
            break
        since, ps, cs = d.get('next_since'), d.get('next_posts_since'), d.get('next_comments_since')
        if pages % 20 == 0:
            save_manifest(m)
    m['stage_done']['changes'] = {'posts': np_, 'comments': nc_, 'pages': pages, 'at': at}
    save_manifest(m)
    print(f'changes: {np_} posts + {nc_} comments in {pages} pages')

# ---------------------------------------------------------------- stage 4
SAMPLE_FILE = OUT / 'sample_check.jsonl'

def walk_sample(handles):
    path = SAMPLE_FILE
    if path.exists():
        return
    out = path.open('a')
    for h in handles:
        route = '/api/citizen/' + urllib.parse.quote(h)
        d, at = get(route)
        posts, comments = [], []
        while True:
            for r in d.get('posts') or []:
                posts.append({'id': r.get('id'), 'created_at': r.get('created_at'), 'mod_state': r.get('mod_state')})
            for r in d.get('comments') or []:
                comments.append({'id': r.get('id'), 'created_at': r.get('created_at'), 'mod_state': r.get('mod_state')})
            pg = d.get('paging') or {}
            np_, nc_ = (pg.get('posts') or {}).get('next_posts_before'), (pg.get('comments') or {}).get('next_comments_before')
            if np_ is None and nc_ is None:
                break
            q = {}
            if np_ is not None:
                q['posts_before'] = np_
            if nc_ is not None:
                q['comments_before'] = nc_
            d, at = get(route + '?' + urllib.parse.urlencode(q))
        out.write(json.dumps({'handle': h, 'at': at, 'posts': posts, 'comments': comments,
                              'post_total': d.get('post_total'), 'comment_total': d.get('comment_total'),
                              'truncated': d.get('truncated')}, separators=(',', ':')) + '\n')
        out.flush()
    out.close()

if __name__ == '__main__':
    import sys
    OUT.mkdir(parents=True, exist_ok=True)
    m = load_manifest()
    if not m['stage_done'].get('census'):
        walk_census(m)
    if not m['stage_done'].get('binds'):
        walk_binds(m)
    if not m['stage_done'].get('changes'):
        walk_changes(m)
    if 'sample' in sys.argv:
        # handles are provided by analyse.py once arms are known
        handles = [line.strip() for line in sys.argv[2:] if line.strip()]
        walk_sample(handles)
    save_manifest(m)
    print('done')
