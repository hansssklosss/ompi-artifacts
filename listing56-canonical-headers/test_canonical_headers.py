# test_canonical_headers.py — unittest suite for canonical_headers.
# License: MIT (see LICENSE). Copyright (c) 2026 ompi (#2432) on 1f916.ai.
#
# Run:  python3 -m unittest -v test_canonical_headers
# No dependencies, no network. The three buyer byte examples from the order
# brief are T1-T3 and their sha256 digests are asserted (the acceptance check:
# "run the tests from a fresh copy in a sandbox and check the three example
# hashes").

import hashlib
import unittest

from canonical_headers import canonical_headers


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class CanonicalHeaders(unittest.TestCase):
    # ---- the three buyer byte examples (MUST be present; hashes asserted) ----

    def test_T1_buyer_example_one(self):
        got = canonical_headers([("Content-Type", "application/json"),
                                 ("Accept", "application/json")])
        want = b"accept: application/json\ncontent-type: application/json\n"
        self.assertEqual(got, want)
        self.assertEqual(sha256_hex(got),
                         "456ddcb6fecb295c1b5c5e7c8d6f9546865210d81e62652ce121e358c59c4156")

    def test_T2_buyer_example_two(self):
        got = canonical_headers([("X-A", " 1 "), ("x-a", "2")])
        want = b"x-a: 1, 2\n"
        self.assertEqual(got, want)
        self.assertEqual(sha256_hex(got),
                         "84269ab74a81b33403bc0c4c45a484b4acd08fb08e76a01b0fe8085c02255e81")

    def test_T3_buyer_example_empty(self):
        got = canonical_headers([])
        self.assertEqual(got, b"")
        self.assertEqual(sha256_hex(got),
                         "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")

    # ---- the two buyer ValueError cases (MUST be present) ----

    def test_T4_buyer_valueerror_bad_name(self):
        # space is not an RFC 9110 token character
        with self.assertRaises(ValueError):
            canonical_headers([("Bad Name", "x")])

    def test_T5_buyer_valueerror_crlf_value(self):
        with self.assertRaises(ValueError):
            canonical_headers([("x-a", "1\r\n2")])

    # ---- rule 2: strip only space (0x20) and tab (0x09) at the ends ----

    def test_T6_strip_ends_only(self):
        self.assertEqual(canonical_headers([("x", "\t  v  \t")]), b"x: v\n")

    def test_T7_interior_whitespace_kept(self):
        # interior space and tab are preserved, not collapsed
        self.assertEqual(canonical_headers([("x", " a  b\t c ")]),
                         b"x: a  b\t c\n")

    def test_T8_other_whitespace_not_stripped(self):
        # vertical tab / form feed / non-breaking space are NOT in the strip set,
        # so a value that begins or ends with one keeps it
        self.assertEqual(canonical_headers([("x", "\x0bv")]),
                         b"x: \x0bv\n")

    # ---- rule 3: duplicates join in input order with ', ' ----

    def test_T9_duplicate_join_order(self):
        self.assertEqual(canonical_headers([("a", "1"), ("b", "2"), ("a", "3")]),
                         b"a: 1, 3\nb: 2\n")

    def test_T10_case_insensitive_duplicate(self):
        self.assertEqual(canonical_headers([("Content-Type", "a"),
                                            ("content-type", "b"),
                                            ("CONTENT-TYPE", "c")]),
                         b"content-type: a, b, c\n")

    # ---- rule 4: sort by name, bytewise ascending ----

    def test_T11_sort_bytewise(self):
        self.assertEqual(canonical_headers([("Zeta", "1"), ("alpha", "2"), ("Beta", "3")]),
                         b"alpha: 2\nbeta: 3\nzeta: 1\n")

    # ---- rule 1: name charset (full RFC 9110 tchar set is legal) ----

    def test_T12_all_token_specials_legal(self):
        name = "a!b#d$e%f&g'h*i+j-k.l^m_n`o|p~"
        self.assertEqual(canonical_headers([(name, "v")]),
                         name.encode("utf-8") + b": v\n")

    def test_T13_empty_name_raises(self):
        with self.assertRaises(ValueError):
            canonical_headers([("", "x")])

    def test_T14_non_ascii_name_raises(self):
        with self.assertRaises(ValueError):
            canonical_headers([("xé", "1")])

    def test_T15_cr_only_value_raises(self):
        with self.assertRaises(ValueError):
            canonical_headers([("x", "1\r2")])

    def test_T16_lf_only_value_raises(self):
        with self.assertRaises(ValueError):
            canonical_headers([("x", "1\n2")])

    # ---- rule 5: 'name: value\n' shape, LF only, UTF-8; empty value edge ----

    def test_T17_empty_value_after_strip(self):
        # a value that is all strip-able whitespace becomes ""; the line keeps
        # its single space after the colon per the 'name: value\n' template
        self.assertEqual(canonical_headers([("x", "   ")]), b"x: \n")

    def test_T18_utf8_value_roundtrip(self):
        self.assertEqual(canonical_headers([("x", "véc")]),
                         "x: véc\n".encode("utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
