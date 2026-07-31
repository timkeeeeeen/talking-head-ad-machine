from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from ad_machine.resolve import make_fcpxml
from ad_machine.util import run


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is required")
class ResolveTests(unittest.TestCase):
    def test_simple_constant_speed_plan_generates_valid_fcpxml(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.mp4"
            run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=black:size=320x240:rate=30:duration=2",
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=48000",
                    "-t",
                    "2",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    str(source),
                ],
                timeout=120,
            )
            plan = {
                "source": {"path": str(source)},
                "variants": [
                    {
                        "id": "primary",
                        "segments": [
                            {"sourceStart": 0.0, "sourceEnd": 0.8, "beat": "hook", "reason": "keep hook"},
                            {"sourceStart": 1.1, "sourceEnd": 2.0, "beat": "cta", "reason": "keep CTA"},
                        ],
                    }
                ],
            }
            output = root / "handoff.fcpxml"
            result = make_fcpxml(plan, "primary", output)
            parsed = ET.parse(output)
            self.assertTrue(result["success"])
            self.assertEqual(parsed.getroot().tag, "fcpxml")
            self.assertEqual(len(parsed.findall(".//asset-clip")), 2)
            self.assertIn("best-effort", result["verification"])

    def test_source_reuse_plan_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.mp4"
            source.write_bytes(b"placeholder")
            plan = {"source": {"path": str(source)}, "variants": [{"id": "a", "allowSourceReuse": True, "segments": []}]}
            with self.assertRaisesRegex(ValueError, "source-reuse"):
                make_fcpxml(plan, "a", Path(temporary) / "out.fcpxml")


if __name__ == "__main__":
    unittest.main()
