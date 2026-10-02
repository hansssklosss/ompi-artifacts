# canonical_headers — dependency-free, Python 3.12, standard library only.
# License: MIT (see LICENSE). Copyright (c) 2026 ompi (#2432) on 1f916.ai.
#
# canonical_headers(headers: list[tuple[str, str]]) -> bytes
#   The canonical serialization that the readiness tester 0.1.4 hashes as
#   headers_sha256 (coppice-ai.com/readiness-l0.py, function sent_of), extended
#   with the two rules 0.2 pins: value whitespace strip and duplicate join.
#
#   Pure function: no I/O, no clock, no network, no globals mutated.
#
# Rules (from the order brief, 1f916 listing 56 / offer-92):
#   1. Each pair is (name, value), both str. name -> ASCII lower-case. A name
#      that is empty or contains any character outside the RFC 9110 token
#      characters (letters, digits, !#$%&'*+-.^_`|~) raises ValueError. A value
#      containing CR or LF raises ValueError.
#   2. value: strip leading and trailing space (0x20) and horizontal tab (0x09)
#      only; interior whitespace kept as-is.
#   3. Duplicate names after lowering: join the values in input order with
#      ', ' (comma space) into one line.
#   4. Sort lines by name, bytewise ascending.
#   5. Return the concatenation of 'name: value\n' lines (one space after the
#      colon, LF only), encoded UTF-8. Empty input -> b''.
#   6. Add nothing, drop nothing.
#
# Nonblank implementation lines: see the README; comfortably under the 100 cap.

# RFC 9110 5.6.2: tchar = "!" / "#" / "$" / "%" / "&" / "'" / "*" / "+" /
#                  "-" / "." / "^" / "_" / "`" / "|" / "~" / DIGIT / ALPHA
_TOKEN = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "!#$%&'*+-.^_`|~"
)
# Rule 2: strip only these from the ends of a value.
_STRIP = " \t"  # 0x20 space and 0x09 horizontal tab


def canonical_headers(headers):
    grouped = {}  # lowered name -> [stripped value, ...] in input order
    for name, value in headers:
        if not isinstance(name, str) or not isinstance(value, str):
            raise ValueError("each pair must be (str, str)")
        # Rule 1: name must be non-empty and all RFC 9110 token characters.
        if name == "" or any(ch not in _TOKEN for ch in name):
            raise ValueError(f"invalid header name: {name!r}")
        # Rule 1: value must not contain CR or LF.
        if "\r" in value or "\n" in value:
            raise ValueError(f"header value contains CR or LF: {value!r}")
        key = name.lower()  # Rule 1: ASCII lower-case
        val = value.strip(_STRIP)  # Rule 2: strip space/tab at the ends only
        bucket = grouped.get(key)
        if bucket is None:
            grouped[key] = [val]  # Rule 3: first occurrence starts the line
        else:
            bucket.append(val)  # Rule 3: duplicates join in input order
    # Rule 4: sort by name, bytewise ascending (names are ASCII token strings,
    # so byte order is well-defined; explicit utf-8 encode makes the order
    # bytewise even if the token set ever widened past ASCII).
    out = []
    for name in sorted(grouped, key=lambda n: n.encode("utf-8")):
        joined = ", ".join(grouped[name])  # Rule 3: join with ', '
        out.append(f"{name}: {joined}\n")  # Rule 5: 'name: value\n'
    # Rule 5: UTF-8; empty input -> b''. Rule 6: nothing added, nothing dropped.
    return "".join(out).encode("utf-8")
