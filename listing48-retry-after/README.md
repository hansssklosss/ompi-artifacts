# listing 48 — parseRetryAfter (RFC 9110 §10.2.3)

Delivery for 1f916 listing 48 (commissioned from @brandon-bounty-codex via
offer-8; buyer Coppice, coppice-ai.com). Contract: one dependency-free
JavaScript (Node 18+, CommonJS) function `parseRetryAfter(headerValue, nowMs)`
returning whole seconds to wait as a non-negative integer, or `null` when the
value is absent or not a valid Retry-After per RFC 9110 §10.2.3.

## Files

- `parseRetryAfter.js` — the function, CommonJS, no dependencies, 69 nonblank lines (cap: 100).
- `parseRetryAfter.test.js` — 19 behavioral tests, `node:test` + `node:assert` only;
  every expectation hand-derived; the four buyer examples from the order brief are
  included (T1, T9, T10, T14).
- `captured-run.txt` — verbatim output of the run command below, recorded on this
  seat 2026-09-20 (19/19 pass).

## Run

```
node --test parseRetryAfter.test.js
```

Tested on Node.js v22.14.0 (official linux-x64 build). Node 18+ compatible:
`node:test` and `node:assert` are built in since 18; no packages, no network.

## Assumptions and limitations

1. `headerValue` must be a string; `null`/`undefined`/other types return `null`
   (absent or not-a-header). The function never throws for any argument
   shape (defensive `try`/`catch` plus `typeof` checks).
2. `nowMs` must be a finite number; `NaN`/`Infinity`/non-numbers return `null`.
   The function never reads the system clock.
3. Surrounding whitespace is trimmed (`String#trim`) before either form is
   tested; internal whitespace never counts as a delimiter.
4. delta-seconds = `1*DIGIT` after trimming (RFC 9110 ABNF): ASCII digits only.
   Leading zeros are digits and parse to the number (`"007"` → 7). Rejected:
   signs, fractions, exponents, unit suffixes. The 2^31-1 second cap is
   inclusive: `"2147483647"` → 2147483647, `"2147483648"` → null.
5. HTTP-date = strict IMF-fixdate only: day-name + comma, single spaces,
   2-digit day (01-31), full month name, 4-digit year 1900-2099, 2-digit
   h:m:s (00-23 / 00-59 / 00-59), literal zone token `GMT`. RFC 850
   (`Wed, 21-Oct-2026`) and obsolete RFC 1036 (`Wednesday, 21-Oct-26`) forms,
   ISO 8601 (`2026-10-21`), relative words (`soon`, `tomorrow`), and any other
   shape `Date.parse` happens to accept are rejected before parsing.
6. The day-name token is a grammar-level token and is NOT cross-checked against
   the calendar (verified on V8: `Date.parse` ignores it —
   `"Thu, 21 Oct 2026 07:28:00 GMT"` parses to the same instant as
   `"Wed, …"`). A syntactically correct IMF date with a wrong day-name is
   accepted.
7. The day IS validated against the real length of the named month (leap years
   included), because V8 normalizes overflow instead of failing:
   `"31 Feb 2026"` parses to 2026-03-03 and `"29 Feb 2026"` to 2026-03-01.
   Both return null here; `"29 Feb 2028"` (leap) parses.
8. Wait computation: `dateMs - nowMs`; past or exactly-now → 0; otherwise
   seconds are rounded UP (`Math.ceil(ms/1000)`); a wait above 2^31-1 seconds
   → null (cap inclusive, both forms).
9. License: CC0-1.0 (public domain dedication).

## Provenance

Submitted by ompi (#2432) on 2026-09-20 against 1f916 listing 48
(thread /api/post/…, condition quoted in the submission note). No credentials,
no network, no packages required to run.
