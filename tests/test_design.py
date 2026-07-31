from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ad_machine.design import _caption_groups, _conform_words, _validate_overlay_copy, prepare_fast_composition
from ad_machine.jobs import create_job
from ad_machine.util import read_json, write_json_atomic


class DesignTests(unittest.TestCase):
    def test_words_are_retimed_across_source_cuts(self) -> None:
        words = [
            {"text": "first", "start": 1.0, "end": 1.3},
            {"text": "second", "start": 5.1, "end": 5.5},
        ]
        segments = [
            {"sourceStart": 0.8, "sourceEnd": 2.0, "outputStart": 0.0},
            {"sourceStart": 5.0, "sourceEnd": 6.0, "outputStart": 1.2},
        ]
        conformed = _conform_words(words, segments)
        self.assertEqual([item["text"] for item in conformed], ["first", "second"])
        self.assertAlmostEqual(conformed[0]["start"], 0.2)
        self.assertAlmostEqual(conformed[1]["start"], 1.3)

    def test_caption_groups_do_not_overlap(self) -> None:
        words = [
            {"text": f"word-{index}", "start": round(index * 0.19, 3), "end": round(index * 0.19 + 0.15, 3)}
            for index in range(12)
        ]
        groups = _caption_groups(words, 2.5)
        for current, following in zip(groups, groups[1:]):
            self.assertLessEqual(current["start"] + current["duration"], following["start"])

    def test_prepare_fast_composition_is_self_contained_and_pending_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            root = workspace / "product"
            source = workspace / "source.mov"
            clean = workspace / "clean.mp4"
            source.write_bytes(b"immutable-source")
            clean.write_bytes(b"clean-a-roll")
            gsap = root / "node_modules" / "gsap" / "dist" / "gsap.min.js"
            gsap.parent.mkdir(parents=True)
            gsap.write_text("window.gsap = {};", encoding="utf-8")
            jobs = root / "jobs"
            job = create_job(source, jobs, mode="fast", slug="design-test")
            write_json_atomic(
                job / "plans" / "edit-plan.normalized.json",
                {
                    "schemaVersion": 1,
                    "source": {"path": str(source), "durationSeconds": 4.0},
                    "variants": [
                        {
                            "id": "primary",
                            "targetRatios": ["4:5"],
                            "durationSeconds": 4.0,
                            "segments": [
                                {
                                    "sourceStart": 0.0,
                                    "sourceEnd": 4.0,
                                    "outputStart": 0.0,
                                    "outputEnd": 4.0,
                                    "text": "Make the useful point quickly.",
                                    "reason": "source-backed hook",
                                    "beat": "hook",
                                    "confidence": 0.95,
                                }
                            ],
                        }
                    ],
                },
            )
            write_json_atomic(
                job / "transcript" / "transcript.json",
                [
                    {"text": "Make", "start": 0.0, "end": 0.3},
                    {"text": "the", "start": 0.31, "end": 0.45},
                    {"text": "useful", "start": 0.46, "end": 0.8},
                    {"text": "point", "start": 0.81, "end": 1.1},
                    {"text": "quickly.", "start": 1.11, "end": 1.6},
                ],
            )
            brief = read_json(job / "brief.json")
            brief["desiredAction"] = "Get the guide"
            write_json_atomic(job / "brief.json", brief)

            result = prepare_fast_composition(root, job, "primary", clean)
            project = Path(result["project"])
            html = (project / "index.html").read_text(encoding="utf-8")
            self.assertIn("Make the useful point quickly.", html)
            self.assertIn("Get the guide", html)
            self.assertIn("data-composition-id=\"fast-ad\"", html)
            self.assertEqual((project / "assets" / "a-roll.mp4").read_bytes(), b"clean-a-roll")
            self.assertTrue((project / "assets" / "gsap.min.js").is_file())
            self.assertIn("00:00:00,000 -->", Path(result["captions"]).read_text(encoding="utf-8"))
            self.assertEqual(result["manifest"]["humanReview"], "pending")
            self.assertEqual(read_json(job / "job.json")["approval"]["status"], "pending")

    def test_unsupported_quantitative_hook_is_rejected(self) -> None:
        brief = {"allowedEvidence": [], "prohibitedClaims": []}
        segments = [{"text": "This saves time"}]
        with self.assertRaisesRegex(ValueError, "unsupported quantitative"):
            _validate_overlay_copy(brief, segments, "Save 90% of your time", "Learn more")

    def test_prohibited_claim_is_rejected(self) -> None:
        brief = {"allowedEvidence": [], "prohibitedClaims": ["guaranteed results"]}
        with self.assertRaisesRegex(ValueError, "prohibited claim"):
            _validate_overlay_copy(brief, [{"text": "A useful tool"}], "Guaranteed results", "Learn more")


if __name__ == "__main__":
    unittest.main()
