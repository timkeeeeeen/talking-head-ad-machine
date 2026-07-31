from __future__ import annotations

import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_release import ZIP_TIMESTAMP, include_core, write_deterministic_file


ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def test_zip_output_ignores_source_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "payload.txt"
            source.write_text("same payload\n", encoding="utf-8")
            outputs: list[bytes] = []
            for timestamp, name in ((1_000_000_000, "one.zip"), (1_700_000_000, "two.zip")):
                os.utime(source, (timestamp, timestamp))
                archive_path = root / name
                with zipfile.ZipFile(archive_path, "w") as archive:
                    write_deterministic_file(archive, source, Path("product/payload.txt"), executable=True)
                outputs.append(archive_path.read_bytes())
                with zipfile.ZipFile(archive_path) as archive:
                    member = archive.getinfo("product/payload.txt")
                    self.assertEqual(member.date_time, ZIP_TIMESTAMP)
                    self.assertEqual((member.external_attr >> 16) & 0o777, 0o755)
            self.assertEqual(outputs[0], outputs[1])

    def test_acceptance_records_are_not_part_of_buyer_zip(self) -> None:
        report = ROOT / "docs" / "acceptance" / "macos-arm64-v0.2.0.json"
        for platform_id in ("macos-arm64", "macos-x64", "windows-x64"):
            self.assertFalse(include_core(report, platform_id))


if __name__ == "__main__":
    unittest.main()
