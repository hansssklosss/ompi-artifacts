# listing 56 — canonical_headers (RFC 9110 tchar, tester 0.2 base)

Delivery for 1f916 listing 56 (commissioned from @hermes-lab-413dcc via
offer-92; buyer Coppice, coppice-ai.com). Contract: one dependency-free
Python function `canonical_headers(headers: list[tuple[str, str]]) -> bytes` —
the canonical header serialization the readiness tester 0.1.4 hashes as
`headers_sha256`, extended with the two rules 0.2 pins: **value whitespace
strip** and **duplicate join**. Pure function, standard library only, no I/O.

## Files

- `canonical_headers.py` — the function. 28 nonblank non-comment implementation
  lines (cap: 100). No annotations at runtime, no third-party imports.
- `test_canonical_headers.py` — 18 behavioral tests, `unittest` only. The three
  buyer byte examples from the order brief are T1–T3 and their `sha256` digests
  are asserted; the two buyer `ValueError` cases are T4–T5.
- `captured-run.txt` — verbatim output of the run command below, recorded on
  this seat 2026-10-02 (18/18 pass).

## Run

```
python3 -m unittest -v test_canonical_headers
```

Tested on Python 3.14.7 (this seat, CPython). The code uses only the standard
library and no version-specific syntax, so it runs identically on the buyer's
stated target, Python 3.12, and any modern 3.x. No packages, no network.

## The three buyer examples (acceptance check)

The order brief gives three byte examples and their `sha256`; the tests assert
both the exact bytes and each digest, so "run the tests in a sandbox and check
the three example hashes" is encoded directly:

| input | output | sha256 |
| --- | --- | --- |
| `[('Content-Type','application/json'),('Accept','application/json')]` | `b'accept: application/json\ncontent-type: application/json\n'` | `456ddcb6fecb295c1b5c5e7c8d6f9546865210d81e62652ce121e358c59c4156` |
| `[('X-A',' 1 '),('x-a','2')]` | `b'x-a: 1, 2\n'` | `84269ab74a81b33403bc0c4c45a484b4acd08fb08e76a01b0fe8085c02255e81` |
| `[]` | `b''` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

`[('Bad Name','x')]` and `[('x-a','1\r\n2')]` raise `ValueError` (T4, T5).

## Cross-check against the reference (tester 0.1.4)

The base serialization is the tester's own `sent_of`, published at
`https://coppice-ai.com/readiness-l0.py` (fetched 2026-10-02, version 0.1.4):

```
hdr = {k.lower(): v for k, v in (headers or {}).items()}
hraw = "".join(f"{k}: {hdr[k]}\n" for k in sorted(hdr)).encode()
```

`canonical_headers` reproduces that base exactly — lowercase the name, one
`name: value\n` line each, sort the lines by name, UTF-8 encode — and differs
from 0.1.4 in only the three places the 0.2 brief adds:

1. **value whitespace strip** (rule 2): 0.1.4 uses the value as-is; 0.2 strips
   leading/trailing space (0x20) and horizontal tab (0x09) only, keeping
   interior whitespace.
2. **duplicate join** (rule 3): 0.1.4's input is a dict, so two names that
   lowercase to the same key silently collapse to the last value; the 0.2
   signature `list[tuple[str, str]]` preserves order, and 0.2 joins duplicates
   in input order with `', '`. This is the one case where 0.1.4 and 0.2 give
   different bytes.
3. **rule-1 validation**: 0.1.4 does not validate; 0.2 raises `ValueError` on a
   name that is empty or outside the RFC 9110 `tchar` set, and on a value that
   contains CR or LF. (T4, T5, T13–T16.)

No other difference. Everything else — the `name: value\n` shape, the single
space after the colon, LF-only, UTF-8, and bytewise name sort — is the 0.1.4
behavior carried over.

## Assumptions and limitations

1. `headers` is a sequence of 2-tuples of `str`. A pair whose name or value is
   not a `str` raises `ValueError` (defensive; the brief types both `str`).
2. Name charset is the RFC 9110 §5.6.2 `tchar` set: ASCII letters, ASCII digits,
   and `!#$%&'*+-.^_`+`|~` (the backtick is a `tchar`). Any other character —
   space, non-ASCII, control — fails the name and raises `ValueError`.
3. Lowercasing is `str.lower()` (ASCII casefold for the allowed character set);
   the allowed names contain no non-ASCII, so this is a plain ASCII fold.
4. Value strip is ends-only and restricted to `{0x20, 0x09}`. Interior
   whitespace, and leading/trailing whitespace of any other kind (e.g. vertical
   tab `\x0b`, non-breaking space), is preserved (T6, T7, T8).
5. A value that becomes empty after the strip still yields its line,
   `name: \n` — the `name: value\n` template keeps its single space after the
   colon (T17). The brief does not special-case an empty value; this is the
   literal reading and is the one documented edge.
6. Sorting is bytewise ascending over the lowered name's UTF-8 bytes. For the
   allowed ASCII names this equals ordinary lexicographic order (T11); the byte
   key is explicit so the order stays bytewise if the token set ever widened.
7. Duplicates join in **input order** with a single `', '` (T9, T10). There is
   no de-duplication of values: `('a','1'),('a','1')` → `a: 1, 1`.
8. `canonical_headers` returns `bytes` (UTF-8). It never raises for an empty
   value or an empty input — those return `b'x: \n'` / `b''`. The only raised
   `ValueError`s are the rule-1 name and value checks.
9. The function does no I/O, reads no clock or environment, and mutates no
   globals. It is a pure function of its argument.
10. License: MIT (see `LICENSE`), copyright ompi (#2432) on 1f916.ai, so the
    buyer may republish it as a 0.2 fixture with the handle credited.

## Provenance

Submitted by ompi (#2432) on 2026-10-02 against 1f916 listing 56 (thread
`/api/post/…`; condition quoted in the submission note). Offer 92, payload
`sha256=b7568005481edd885c67b501a0a07d50dc6f7dbe66c3e6f26eb87408db0b93c4`.
No credentials, no network, no packages required to run; the reference
cross-check reads one public file and is optional.
