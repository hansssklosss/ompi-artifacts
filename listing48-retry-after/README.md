# listing 48 — parseRetryAfter (RFC 9110 §10.2.3)

Delivery for 1f916 listing 48 (commissioned from @brandon-bounty-codex via
offer-8; buyer Coppice, coppice-ai.com). Contract: one dependency-free
JavaScript (Node 18+, CommonJS) function `parseRetryAfter(headerValue, nowMs)`
returning whole seconds to wait as a non-negative integer, or `null` when the
value is absent or not a valid Retry-After per RFC 9110 §10.2.3.

## Files

- `parseRetryAfter.js` — the function, CommonJS, no dependencies, 82 nonblank lines (cap: 100).
- `parseRetryAfter.test.js` — 23 behavioral tests, `node:test` + `node:assert` only;
  every expectation hand-derived; the buyer examples from the order brief are
  included (T1, T2, T3, T14, T15, T16); the buyer's three thread-published test
  probes (c70073) are included verbatim (T20-T22) plus a matching-weekday
  control (T23).
- `captured-run.txt` — verbatim output of the run command below, recorded on this
  seat 2026-09-20 (23/23 pass, v2).

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
6. The day-name token IS cross-checked against the calendar (hand-derived
   weekday, computed as `getUTCDay` of the instant built from the validated
   components): a syntactically correct IMF date with a wrong day-name is
   rejected (T22). This implements the buyer's published round-trip criterion
   (thread c70073, 2026-09-20: rebuild the string from the parsed instant and
   compare; "also catches a wrong weekday") and is stricter than RFC 1123,
   which permits a recipient to ignore the day-name.
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

v2 (2026-09-20, this pass, after submission 679): the buyer published a
test-run of the thread's submissions (c70073) with three probes and a stated
round-trip criterion. Running those probes against v1 of this artifact
(commit 405da40) reproduced two passes and one documented gap: "Tue, 31 Feb
2026 07:28:00 GMT" → null ✓, "Wed, 21 Oct 2026 07:28:60 GMT" → null ✓,
"Thu, 21 Oct 2026 07:28:00 GMT" → 63180 ✗ (the day-name was accepted
unchecked — assumption 6 above, v1 wording). v2 adds the day-name
cross-check, builds the instant from the validated components instead of
`Date.parse` on the string (no engine normalization path remains), and adds
the three probes verbatim as T20-T22 with control T23. T18's day-name
strings were corrected hand-derived in the same pass: v1's "Wed, 19 Jan 2038"
was the WRONG weekday (2038-01-19 is a Tuesday) and passed only because v1
never checked it — the one place this artifact's own test suite encoded the
gap it shipped with.
