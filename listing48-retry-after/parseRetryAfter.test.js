// Tests for parseRetryAfter — Node 18+, node:test, no packages.
// Run: node --test parseRetryAfter.test.js
// Every expectation below is hand-derived; the four buyer examples from the
// order brief are included verbatim (T1, T15, T16, T20).

"use strict";

const { test } = require("node:test");
const assert = require("node:assert");
const { parseRetryAfter } = require("./parseRetryAfter.js");

const D = (...a) => Date.UTC(...a); // month is 0-based, like Date.UTC

test("T1  buyer example: plain delta-seconds", () => {
  assert.strictEqual(parseRetryAfter("120", 0), 120);
});

test("T2  buyer example: delta with surrounding whitespace trims", () => {
  assert.strictEqual(parseRetryAfter(" 5 ", 0), 5);
});

test("T3  buyer example: zero wait", () => {
  assert.strictEqual(parseRetryAfter("0", 0), 0);
});

test("T4  rejected delta spellings: negative, fraction, exponent, unit suffix", () => {
  assert.strictEqual(parseRetryAfter("-1", 0), null);
  assert.strictEqual(parseRetryAfter("1.5", 0), null);
  assert.strictEqual(parseRetryAfter("1e3", 0), null);
  assert.strictEqual(parseRetryAfter("5s", 0), null);
});

test("T5  absent values: empty string, whitespace-only, null, undefined, non-string", () => {
  assert.strictEqual(parseRetryAfter("", 0), null);
  assert.strictEqual(parseRetryAfter("   ", 0), null);
  assert.strictEqual(parseRetryAfter(null, 0), null);
  assert.strictEqual(parseRetryAfter(undefined, 0), null);
  assert.strictEqual(parseRetryAfter(120, 0), null); // number input is not a header value
});

test("T6  2^31-1 cap on delta-seconds: inclusive at the cap, null above", () => {
  // hand-derived: 2^31 - 1 = 2147483647
  assert.strictEqual(parseRetryAfter("2147483647", 0), 2147483647);
  assert.strictEqual(parseRetryAfter("2147483648", 0), null); // 2^31
  assert.strictEqual(parseRetryAfter("99999999999999999999", 0), null); // long digit run
});

test("T7  delta leading zeros are digits (1*DIGIT) and parse to the number", () => {
  assert.strictEqual(parseRetryAfter("007", 0), 7);
});

test("T8  internal whitespace is not surrounding whitespace", () => {
  assert.strictEqual(parseRetryAfter("1 2", 0), null);
});

test("T9  buyer example: IMF-fixdate 30 s ahead of now, exact", () => {
  // "Wed, 21 Oct 2026 07:28:00 GMT" = D(2026,9,21,7,28,0); now = 07:27:30 -> 30 s
  assert.strictEqual(parseRetryAfter("Wed, 21 Oct 2026 07:28:00 GMT", D(2026, 9, 21, 7, 27, 30)), 30);
});

test("T10 buyer example: sub-second remainder rounds UP", () => {
  // same date; now = 07:27:30.500 -> 29.5 s -> ceil -> 30
  assert.strictEqual(parseRetryAfter("Wed, 21 Oct 2026 07:28:00 GMT", D(2026, 9, 21, 7, 27, 30, 500)), 30);
});

test("T11 round-up on another fractional remainder", () => {
  // date 07:28:00.000; now 07:27:31.200 -> 28.8 s -> ceil -> 29
  assert.strictEqual(parseRetryAfter("Wed, 21 Oct 2026 07:28:00 GMT", D(2026, 9, 21, 7, 27, 31, 200)), 29);
});

test("T12 past (or exactly now) date returns 0", () => {
  assert.strictEqual(parseRetryAfter("Wed, 21 Oct 2026 07:27:00 GMT", D(2026, 9, 21, 7, 27, 30)), 0);
  assert.strictEqual(parseRetryAfter("Wed, 21 Oct 2026 07:27:30 GMT", D(2026, 9, 21, 7, 27, 30)), 0);
});

test("T13 buyer example: ISO 8601 is Date.parse-able but not IMF-fixdate -> null", () => {
  assert.strictEqual(parseRetryAfter("2026-10-21", 0), null);
});

test("T14 buyer example: a relative word -> null", () => {
  assert.strictEqual(parseRetryAfter("tomorrow", 0), null);
  assert.strictEqual(parseRetryAfter("soon", 0), null); // T20 of the brief
});

test("T15 only the literal GMT zone token is IMF-fixdate", () => {
  assert.strictEqual(parseRetryAfter("Wed, 21 Oct 2026 07:28:00 UTC", D(2026, 9, 21, 7, 27, 30)), null);
  assert.strictEqual(parseRetryAfter("Wed, 21-Oct-2026 07:28:00 GMT", D(2026, 9, 21, 7, 27, 30)), null); // RFC 850 form
  assert.strictEqual(parseRetryAfter("Wednesday, 21-Oct-26 07:28:00 GMT", D(2026, 9, 21, 7, 27, 30)), null); // RFC 1036 form
});

test("T16 malformed IMF shapes are rejected before parsing", () => {
  assert.strictEqual(parseRetryAfter("Wed, 21 Oct 2026", 0), null); // no time
  assert.strictEqual(parseRetryAfter("Wed, 21 Oct 2026 7:28:00 GMT", 0), null); // single-digit hour
  assert.strictEqual(parseRetryAfter("Wed, 21 Oct 2026 07:28:00", 0), null); // no zone
  assert.strictEqual(parseRetryAfter("Wed  , 21 Oct 2026 07:28:00 GMT", 0), null); // double space
  assert.strictEqual(parseRetryAfter("Wed , 21 Oct 2026 07:28:00 GMT", 0), null); // space before the comma
  assert.strictEqual(parseRetryAfter("Wed,21 Oct 2026 07:28:00 GMT", 0), null); // no space after the comma
  assert.strictEqual(parseRetryAfter("wed, 21 Oct 2026 07:28:00 GMT", 0), null); // lowercase day-name
  assert.strictEqual(parseRetryAfter("Wed, 21 Oct 2026 07:60:00 GMT", 0), null); // minute 60
});

test("T17 impossible calendar dates are rejected by month-length validation", () => {
  // V8's Date.parse normalizes "31 Feb" to "Mar 3" rather than yielding NaN,
  // so the day is checked against the real length of the named month.
  assert.strictEqual(parseRetryAfter("Wed, 31 Feb 2026 00:00:00 GMT", 0), null);
  assert.strictEqual(parseRetryAfter("Wed, 29 Feb 2026 00:00:00 GMT", 0), null); // 2026 is not a leap year
  // hand-derived: 2028-02-29T00:00:00Z = 1835395200000 ms (2028 is a leap year);
  // nowMs 1000 ms earlier -> wait exactly 1 s.
  assert.strictEqual(parseRetryAfter("Tue, 29 Feb 2028 00:00:00 GMT", 1835395199000), 1);
});

test("T18 2^31-1 cap on computed wait: inclusive at 2038-01-19 03:14:07 UTC, null beyond", () => {
  // hand-derived: 2147483647 s after epoch = 24855 d + 11647 s = 2038-01-19 03:14:07 UTC.
  // nowMs = 0, so wait == 2147483647 s exactly -> valid at the cap.
  // (The day-name token is not cross-checked against the calendar; see assumptions.)
  assert.strictEqual(parseRetryAfter("Wed, 19 Jan 2038 03:14:07 GMT", 0), 2147483647);
  assert.strictEqual(parseRetryAfter("Thu, 20 Jan 2038 03:14:07 GMT", 0), null); // +86400 s over the cap
});

test("T19 never throws: hostile arguments all yield null", () => {
  assert.strictEqual(parseRetryAfter({}, 0), null);
  assert.strictEqual(parseRetryAfter(["120"], 0), null);
  assert.strictEqual(parseRetryAfter("120", "now"), null);
  assert.strictEqual(parseRetryAfter("120", NaN), null);
  assert.strictEqual(parseRetryAfter("120", Infinity), null);
  assert.strictEqual(parseRetryAfter("120", undefined), null);
});
