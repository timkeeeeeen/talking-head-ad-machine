from __future__ import annotations

import unittest

from ad_machine.render import duration_matches, duration_tolerance, expected_plan_duration


class RenderTests(unittest.TestCase):
    def test_duration_tolerance_is_at_least_quarter_second(self) -> None:
        self.assertEqual(duration_tolerance(30), 0.25)

    def test_duration_mismatch_is_rejected(self) -> None:
        self.assertTrue(duration_matches(10.0, 10.2, 30))
        self.assertFalse(duration_matches(10.0, 23.19, 30))

    def test_expected_duration_uses_segments(self) -> None:
        plan = {"variants": [{"id": "a", "segments": [{"sourceStart": 1, "sourceEnd": 3}, {"sourceStart": 5, "sourceEnd": 8}]}]}
        self.assertEqual(expected_plan_duration(plan, "a"), 5.0)


if __name__ == "__main__":
    unittest.main()

