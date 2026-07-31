from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from ad_machine.jobs import create_job
from ad_machine.support import create_support_report


class SupportTests(unittest.TestCase):
    def test_support_report_omits_source_path_and_media(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "secret-camera.mov"
            source.write_bytes(b"private-media")
            job = create_job(source, root / "jobs")
            report = create_support_report(root, root / "support.zip", job)
            with zipfile.ZipFile(report) as archive:
                combined = b"".join(archive.read(name) for name in archive.namelist())
            self.assertNotIn(str(source).encode(), combined)
            self.assertNotIn(b"private-media", combined)


if __name__ == "__main__":
    unittest.main()

