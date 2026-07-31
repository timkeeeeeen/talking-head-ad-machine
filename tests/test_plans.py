from __future__ import annotations

import unittest

from ad_machine.plans import validate_and_normalize


class PlanTests(unittest.TestCase):
    def valid_plan(self) -> dict:
        return {
            "schemaVersion": 1,
            "source": {"path": "/tmp/source.mp4", "durationSeconds": 10.0},
            "variants": [
                {
                    "id": "main",
                    "targetRatios": ["4:5"],
                    "segments": [
                        {"sourceStart": 0, "sourceEnd": 2, "text": "Hook", "reason": "Complete hook", "beat": "hook", "confidence": 0.9},
                        {"sourceStart": 4, "sourceEnd": 6, "text": "CTA", "reason": "Complete CTA", "beat": "cta", "confidence": 0.95},
                    ],
                }
            ],
        }

    def test_normalizes_output_timing(self) -> None:
        normalized, errors = validate_and_normalize(self.valid_plan())
        self.assertEqual(errors, [])
        variant = normalized["variants"][0]
        self.assertEqual(variant["durationSeconds"], 4.0)
        self.assertEqual(variant["segments"][1]["outputStart"], 2.0)

    def test_overlap_is_rejected(self) -> None:
        value = self.valid_plan()
        value["variants"][0]["segments"][1]["sourceStart"] = 1.5
        _, errors = validate_and_normalize(value)
        self.assertTrue(any("overlaps" in error for error in errors))

    def test_missing_reason_is_rejected(self) -> None:
        value = self.valid_plan()
        value["variants"][0]["segments"][0]["reason"] = ""
        _, errors = validate_and_normalize(value)
        self.assertTrue(any("reason" in error for error in errors))


if __name__ == "__main__":
    unittest.main()

