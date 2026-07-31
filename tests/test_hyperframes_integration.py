from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from ad_machine.demo import run_demo
from ad_machine.design import check_composition, prepare_fast_composition, render_preview
from ad_machine.qa import inspect_output


RUN_GOLDEN = os.environ.get("AD_MACHINE_RUN_HYPERFRAMES_TESTS") == "1"


@unittest.skipUnless(RUN_GOLDEN and shutil.which("ffmpeg") and shutil.which("ffprobe"), "enable the HyperFrames golden render")
class HyperFramesIntegrationTests(unittest.TestCase):
    def test_fast_composition_checks_and_renders_review_preview(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            jobs = Path(temporary) / "jobs"
            demo = run_demo(root, jobs)
            job = Path(demo["job"])
            prepared = prepare_fast_composition(
                root,
                job,
                "demo-cut",
                Path(demo["preview"]),
                hook="Turn one raw clip into an ad",
                cta="Review before delivery",
                ratio="4:5",
            )
            project = Path(prepared["project"])
            checked = check_composition(root, project)
            rendered = render_preview(root, job, "demo-cut", project)
            qa = inspect_output(Path(rendered["preview"]), expected_duration=3.0)
            self.assertTrue(checked["ok"])
            self.assertEqual(checked["lint"]["warningCount"], 0)
            self.assertEqual(qa["video"]["width"], 1080)
            self.assertEqual(qa["video"]["height"], 1350)
            self.assertEqual(qa["humanReview"], "pending")
            self.assertEqual(rendered["humanReview"], "pending")


if __name__ == "__main__":
    unittest.main()
