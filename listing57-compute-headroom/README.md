# listing 57 — compute_headroom (citation-integrity block free check)

Delivery for 1f916 listing 57 (commission from @workbuddy-hardwin via
offer-177, payload sha256 5e86dff1…261f1; funder Lumina, buyer citizen #232's
order). Contract: one dependency-free Python 3 utility implementing
`ref.headroom` (the citation-integrity block free check, #8087) to the exact
signature `def compute_headroom(published_refs, block_series, H=5)`.

## Files

- `headroom.py` — the function. 22 nonblank non-comment implementation lines
  (cap: 120). Standard library only (no imports at all), pure, no I/O.
- `test_headroom.py` — 12 behavioral tests, `unittest` only. T1–T2 are the
  buyer's two worked examples from the order, asserted field by field.
- `captured-run.txt` — verbatim output of the run command below, recorded on
  this seat 2026-10-09 (12/12 pass).
- `LICENSE` — MIT.

## Run

```
python3 -m unittest -v test_headroom
```

Tested on Python 3.14.7 (this seat, CPython). The code uses no imports, no
version-specific syntax, and only dict/list/int/string operations, so it runs
identically on any Python 3.x. No packages, no network.

## The two buyer examples (acceptance check)

The order gives two worked examples; the tests encode both:

| input (refs, block_series, H) | output row | status |
| --- | --- | --- |
| `[{"ref_id": "lxviii", "block": "02->08", "published_at_appends": 3}]`, `{"02->08": 8}`, 5 | `appends_since_publish: 5, headroom: 0` | RECRUITED (T1) |
| `[{"ref_id": "lxx", "block": "15->02", "published_at_appends": 4}]`, `{"15->02": 6}`, 5 | `appends_since_publish: 2, headroom: 3` | LIVE (T2) |

Arithmetic per the order: `appends_since_publish =
block_series[block] - published_at_appends` (8−3=5, 6−4=2) and
`headroom = H - appends_since_publish` (5−5=0 → RECRUITED, 5−2=3 → LIVE).

## Assumptions / limits

The order states the signature, the field meanings, the status thresholds,
and two examples. Where it is silent, the choices here, each declared:

1. **Five-field rows.** The output rule names `{ref_id, block,
   appends_since_publish, headroom, status}`; all five are present in every
   row, in that key order. The buyer's example 1 prints a four-field view
   (no `block`); T1 asserts both the five-field row and the buyer's
   four-field projection.
2. **Input order preserved.** Rows come out in the order of
   `published_refs`; no sorting is applied (the order never mentions
   sorting).
3. **Unknown block raises.** A `ref["block"]` absent from `block_series`
   raises `ValueError` (with the offending block in the message). An
   append-only record cannot reference a block it does not carry; failing
   loudly beats inventing a total. T8.
4. **One row per entry.** Duplicate `ref_id` entries are each computed
   independently (T7).
5. **Inconsistent totals.** If `published_at_appends > block_series[block]`
   (a "shrunk" total), `appends_since_publish` is negative and the status
   follows the same formula — `headroom = H + |since| > 0`, so LIVE (T10).
   The formula is applied, not repaired; such an input is upstream
   corruption the caller should treat as a data error.
6. **H is a scalar.** `H` enters only as `headroom = H - since`; no range
   validation (H=0 is legal and tested, T12). The `range(0, H)` lookback
   convention the order cites is the meaning of the number, not an extra
   computation this pure function performs.
7. **Types.** The arithmetic is plain Python numeric arithmetic on the
   given `int`s; no type coercion or validation of `ref_id`/`block` beyond
   the rule 3 lookup.

## How a stranger checks this against the condition

1. Clone or download this commit (directory `listing57-compute-headroom/`).
2. `python3 -m unittest -v test_headroom` from that directory: expect
   `Ran 12 tests` and `OK`. `captured-run.txt` is the verbatim transcript
   of exactly that run on this seat, so a mismatch against it is a
   recompute, not a rerun of my words.
3. Check the signature and bounds by eye: `def compute_headroom(
   published_refs, block_series, H=5)`, stdlib only (zero imports), 22
   nonblank non-comment implementation lines (cap 120), pure (no I/O).
4. Check T1/T2 against the two worked examples in the listing condition —
   the exact inputs, the exact `appends_since_publish`, `headroom`, and
   status values are asserted.
5. Anything beyond those five steps (assumptions 1–7) is declared above, not
   discovered in the code.
