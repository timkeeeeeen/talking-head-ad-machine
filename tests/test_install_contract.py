from __future__ import annotations

import json
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class InstallContractTests(unittest.TestCase):
    def test_product_versions_are_synchronized(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(version, "0.2.0")
        self.assertEqual(package["version"], version)
        self.assertEqual(project["project"]["version"], version)

    def test_windows_bootstrap_matches_the_locked_whisper_artifact(self) -> None:
        lock = json.loads((ROOT / "runtime-lock.json").read_text(encoding="utf-8"))
        installer_path = ROOT / "install.ps1"
        if not installer_path.is_file():
            self.skipTest("Windows installer is intentionally absent from this platform-specific artifact")
        installer = installer_path.read_text(encoding="utf-8")
        windows = lock["whisperCpp"]["windowsX64"]
        self.assertIn(windows["url"], installer)
        self.assertIn(windows["sha256"], installer)
        self.assertIn("astral-sh.uv", installer)
        self.assertIn("Gyan.FFmpeg", installer)
        self.assertIn("OpenJS.NodeJS.LTS", installer)

    def test_installers_end_in_doctor_and_demo(self) -> None:
        installers = [path for path in (ROOT / "install.sh", ROOT / "install.ps1") if path.is_file()]
        self.assertTrue(installers)
        for path in installers:
            installer = path.read_text(encoding="utf-8")
            self.assertIn("doctor", installer)
            self.assertIn("demo", installer)
        if (ROOT / "install.sh").is_file():
            self.assertIn("Homebrew/install/HEAD/install.sh", (ROOT / "install.sh").read_text(encoding="utf-8"))
        if (ROOT / "install.ps1").is_file():
            self.assertIn("22000", (ROOT / "install.ps1").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
