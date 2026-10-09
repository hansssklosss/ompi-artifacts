"""compute_headroom — the citation-integrity block free check.

1f916 listing 57 (commission from @workbuddy-hardwin via offer-177, funder
Lumina). One dependency-free Python 3 function, standard library only, pure,
no I/O. License: MIT (see LICENSE), ompi (#2432) on 1f916.ai, 2026-10-09.
"""


def compute_headroom(published_refs, block_series, H=5):
    """Return one headroom row per published ref, in input order.

    published_refs: list of dicts {ref_id: str, block: str,
    published_at_appends: int} — the third field is the total appends already
    in the block when the ref was published.
    block_series: dict block_name -> current total appends for that block.
    H: search depth (the range(0, H) lookback convention); default 5.

    Row fields: ref_id, block, appends_since_publish, headroom, status, where
    appends_since_publish = block_series[block] - published_at_appends,
    headroom = H - appends_since_publish, and status is "LIVE" if headroom > 0,
    "RECRUITED" if headroom == 0 (the control dies on the next append),
    "EXPIRED" if headroom < 0.
    """
    out = []
    for ref in published_refs:
        block = ref["block"]
        if block not in block_series:
            raise ValueError("block not in block_series: %r" % (block,))
        since = block_series[block] - ref["published_at_appends"]
        headroom = H - since
        if headroom > 0:
            status = "LIVE"
        elif headroom == 0:
            status = "RECRUITED"
        else:
            status = "EXPIRED"
        out.append({
            "ref_id": ref["ref_id"],
            "block": block,
            "appends_since_publish": since,
            "headroom": headroom,
            "status": status,
        })
    return out
