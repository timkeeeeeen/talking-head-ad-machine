from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from ad_machine.demo import run_demo


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is required")
class DemoIntegrationTests(unittest.TestCase):
    def test_demo_resets_timestamps_and_generates_review(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            result = run_demo(root, Path(temporary) / "jobs")
            self.assertTrue(result["render"]["durationMatches"])
            self.assertTrue(Path(result["preview"]).is_file())
            self.assertIn("Review before delivery", Path(result["review"]).read_text(encoding="utf-8"))
            self.assertEqual(result["qa"]["video"]["codec_name"], "h264")
            self.assertEqual(result["qa"]["video"]["pix_fmt"], "yuv420p")
            self.assertEqual(result["qa"]["audio"]["codec_name"], "aac")
            self.assertAlmostEqual(float(result["qa"]["loudness"]["input_i"]), -14.0, delta=0.25)
            self.assertEqual(result["qa"]["humanReview"], "pending")


if __name__ == "__main__":
    unittest.main()
