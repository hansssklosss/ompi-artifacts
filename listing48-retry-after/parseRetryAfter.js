// parseRetryAfter — dependency-free, Node 18+, CommonJS.
// License: CC0-1.0 (public domain dedication).
//
// parseRetryAfter(headerValue, nowMs) -> number | null
//   headerValue: string | null | undefined — raw HTTP Retry-After header value.
//   nowMs: number — the clock, milliseconds since epoch (the function never
//     reads the system clock).
//   Returns whole seconds to wait (non-negative integer), or null when the
//   value is absent or not a valid Retry-After per RFC 9110 section 10.2.3.
//
// Forms accepted (after trimming surrounding whitespace):
//   delta-seconds: ASCII digits only (RFC 9110: delta-seconds = 1*DIGIT).
//   HTTP-date:     IMF-fixdate only, literal "GMT" zone token
//                  (day-name, 2-digit day, full month name, 4-digit year,
//                  2-digit h:m:s, exactly single spaces).
// Rejected: anything else, including RFC 850 / obsolete-RFC 1036 date forms,
// ISO 8601 ("2026-10-21"), relative words ("soon", "tomorrow"), negatives,
// fractions, exponent notation, and wait values above 2^31-1 seconds.
// Never throws: any non-conforming argument yields null.

"use strict";

const MAX_WAIT_SECONDS = 2147483647; // 2^31 - 1
const MONTH_INDEX = { Jan: 0, Feb: 1, Mar: 2, Apr: 3, May: 4, Jun: 5, Jul: 6, Aug: 7, Sep: 8, Oct: 9, Nov: 10, Dec: 11 };

const IMF_FIXDATE_RE = new RegExp(
  "^(Sun|Mon|Tue|Wed|Thu|Fri|Sat), " +
    "(0[1-9]|[12][0-9]|3[01]) " +
    "(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) " +
    "((?:19|20)\\d{2}) " +
    "([01]\\d|2[0-3]):[0-5]\\d:[0-5]\\d GMT$"
);
function isLeap(y) {
  return (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
}
function parseDeltaSeconds(s) {
  // s is trimmed here. 1*DIGIT: one or more ASCII digits, nothing else.
  if (!/^[0-9]+$/.test(s)) return null;
  const n = Number(s); // exact for integers up to 2^53; longer runs exceed the cap below
  if (!Number.isFinite(n) || n > MAX_WAIT_SECONDS) return null;
  return n;
}

function parseRetryAfter(headerValue, nowMs) {
  try {
    if (typeof headerValue !== "string") return null;
    if (typeof nowMs !== "number" || !Number.isFinite(nowMs)) return null;

    const s = headerValue.trim();
    if (s === "") return null;

    // delta-seconds: all-ASCII-digits after trimming.
    if (/^[0-9]+$/.test(s)) return parseDeltaSeconds(s);

    // HTTP-date: strict IMF-fixdate shape, then validate the calendar.
    const m = s.match(IMF_FIXDATE_RE);
    if (!m) return null;
    const day = Number(m[2]);
    const month = MONTH_INDEX[m[3]];
    const year = Number(m[4]);
    // Date.parse normalizes impossible dates (e.g. 31 Feb -> Mar 3) instead of
    // yielding NaN, so the day must be validated against the real month length.
    const dim = [31, isLeap(year) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month];
    if (day < 1 || day > dim) return null;
    const dateMs = Date.parse(s);
    if (Number.isNaN(dateMs)) return null;

    const waitMs = dateMs - nowMs;
    if (waitMs <= 0) return 0; // past (or exact) date: no wait
    const seconds = Math.ceil(waitMs / 1000); // round UP
    if (seconds > MAX_WAIT_SECONDS) return null;
    return seconds;
  } catch (e) {
    return null; // never throws
  }
}

module.exports = { parseRetryAfter };
