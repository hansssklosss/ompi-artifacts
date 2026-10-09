"""Behavioral tests for compute_headroom (1f916 listing 57).

unittest only; run: python3 -m unittest -v test_headroom
T1-T2 are the buyer's two worked examples, asserted field by field against
the exact values in the order. The buyer's example 1 view omits "block"; the
output rule names five fields, so the tests assert both the five-field row
and the buyer's four-field view.
"""

import unittest

from headroom import compute_headroom


class ComputeHeadroom(unittest.TestCase):

    def test_T1_buyer_example_one_recruited(self):
        got = compute_headroom(
            [{"ref_id": "lxviii", "block": "02->08", "published_at_appends": 3}],
            {"02->08": 8},
            H=5)
        self.assertEqual(got, [{"ref_id": "lxviii", "block": "02->08",
                                "appends_since_publish": 5, "headroom": 0,
                                "status": "RECRUITED"}])
        buyer_view = {k: got[0][k] for k in
                      ("ref_id", "appends_since_publish", "headroom", "status")}
        self.assertEqual(buyer_view, {"ref_id": "lxviii",
                                      "appends_since_publish": 5, "headroom": 0,
                                      "status": "RECRUITED"})

    def test_T2_buyer_example_two_live(self):
        got = compute_headroom(
            [{"ref_id": "lxx", "block": "15->02", "published_at_appends": 4}],
            {"15->02": 6},
            H=5)
        self.assertEqual(got, [{"ref_id": "lxx", "block": "15->02",
                                "appends_since_publish": 2, "headroom": 3,
                                "status": "LIVE"}])

    def test_T3_expired(self):
        got = compute_headroom(
            [{"ref_id": "rx", "block": "b", "published_at_appends": 2}],
            {"b": 10}, H=5)
        self.assertEqual(got, [{"ref_id": "rx", "block": "b",
                                "appends_since_publish": 8, "headroom": -3,
                                "status": "EXPIRED"}])

    def test_T4_empty_input(self):
        self.assertEqual(compute_headroom([], {}, H=5), [])

    def test_T5_default_H_is_five(self):
        got = compute_headroom(
            [{"ref_id": "d", "block": "b", "published_at_appends": 1}],
            {"b": 5})
        self.assertEqual(got[0]["headroom"], 1)
        self.assertEqual(got[0]["status"], "LIVE")
        self.assertEqual(got[0]["appends_since_publish"], 4)

    def test_T6_multi_ref_input_order(self):
        refs = [{"ref_id": "r3", "block": "b2", "published_at_appends": 0},
                {"ref_id": "r1", "block": "b1", "published_at_appends": 2},
                {"ref_id": "r2", "block": "b2", "published_at_appends": 4}]
        got = compute_headroom(refs, {"b1": 7, "b2": 9}, H=5)
        self.assertEqual([r["ref_id"] for r in got], ["r3", "r1", "r2"])
        self.assertEqual([(r["appends_since_publish"], r["headroom"],
                           r["status"]) for r in got],
                         [(9, -4, "EXPIRED"), (5, 0, "RECRUITED"),
                          (5, 0, "RECRUITED")])

    def test_T7_duplicate_ref_id(self):
        refs = [{"ref_id": "same", "block": "b", "published_at_appends": 0},
                {"ref_id": "same", "block": "b", "published_at_appends": 6}]
        got = compute_headroom(refs, {"b": 6}, H=5)
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0]["appends_since_publish"], 6)
        self.assertEqual(got[0]["headroom"], -1)
        self.assertEqual(got[0]["status"], "EXPIRED")
        self.assertEqual(got[1]["appends_since_publish"], 0)
        self.assertEqual(got[1]["headroom"], 5)
        self.assertEqual(got[1]["status"], "LIVE")

    def test_T8_unknown_block_raises(self):
        with self.assertRaises(ValueError):
            compute_headroom(
                [{"ref_id": "u", "block": "missing", "published_at_appends": 0}],
                {"b": 1}, H=5)

    def test_T9_published_at_current_total(self):
        got = compute_headroom(
            [{"ref_id": "c", "block": "b", "published_at_appends": 9}],
            {"b": 9}, H=5)
        self.assertEqual(got[0]["appends_since_publish"], 0)
        self.assertEqual(got[0]["headroom"], 5)
        self.assertEqual(got[0]["status"], "LIVE")

    def test_T10_inconsistent_input_shrunk_block(self):
        got = compute_headroom(
            [{"ref_id": "s", "block": "b", "published_at_appends": 7}],
            {"b": 4}, H=5)
        self.assertEqual(got[0]["appends_since_publish"], -3)
        self.assertEqual(got[0]["headroom"], 8)
        self.assertEqual(got[0]["status"], "LIVE")

    def test_T11_H_override(self):
        got = compute_headroom(
            [{"ref_id": "h", "block": "b", "published_at_appends": 0}],
            {"b": 2}, H=2)
        self.assertEqual(got[0]["headroom"], 0)
        self.assertEqual(got[0]["status"], "RECRUITED")

    def test_T12_H_zero(self):
        live = compute_headroom(
            [{"ref_id": "z0", "block": "b", "published_at_appends": 1}],
            {"b": 1}, H=0)
        dead = compute_headroom(
            [{"ref_id": "z1", "block": "b", "published_at_appends": 0}],
            {"b": 1}, H=0)
        self.assertEqual(live[0]["headroom"], 0)
        self.assertEqual(live[0]["status"], "RECRUITED")
        self.assertEqual(dead[0]["appends_since_publish"], 1)
        self.assertEqual(dead[0]["headroom"], -1)
        self.assertEqual(dead[0]["status"], "EXPIRED")


if __name__ == "__main__":
    unittest.main()
