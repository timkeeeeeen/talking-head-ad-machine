from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path, PureWindowsPath
from unittest.mock import patch

from ad_machine.doctor import _command_check
from ad_machine.platforms import PlatformSpec, detect_platform, node_executable, venv_executable
from ad_machine.render import ffmpeg_concat_entry
from ad_machine.setup import setup_plan


class PlatformTests(unittest.TestCase):
    def test_supported_platform_matrix_is_explicit(self) -> None:
        self.assertEqual(detect_platform("Darwin", "arm64").id, "macos-arm64")
        self.assertEqual(detect_platform("Darwin", "x86_64").id, "macos-x64")
        self.assertEqual(detect_platform("Windows", "AMD64").id, "windows-x64")
        self.assertFalse(detect_platform("Linux", "x86_64").supported)
        self.assertFalse(detect_platform("Windows", "arm64").supported)

    def test_product_executables_use_platform_specific_shims(self) -> None:
        root = Path("product")
        windows = PlatformSpec("windows-x64", "Windows", "x86_64", "windows", True)
        mac = PlatformSpec("macos-x64", "Darwin", "x86_64", "macos", True)
        self.assertEqual(venv_executable(root, "python", windows), root / ".venv" / "Scripts" / "python.exe")
        self.assertEqual(node_executable(root, "hyperframes", windows), root / "node_modules" / ".bin" / "hyperframes.cmd")
        self.assertEqual(venv_executable(root, "python", mac), root / ".venv" / "bin" / "python")
        self.assertEqual(node_executable(root, "hyperframes", mac), root / "node_modules" / ".bin" / "hyperframes")

    def test_windows_setup_plan_routes_missing_tools_to_powershell(self) -> None:
        windows = PlatformSpec("windows-x64", "Windows", "x86_64", "windows", True)
        with tempfile.TemporaryDirectory() as temporary:
            with patch("ad_machine.setup.detect_platform", return_value=windows), patch(
                "ad_machine.setup.shutil.which", return_value=None
            ):
                plan = setup_plan(Path(temporary))
        self.assertTrue(plan["supportedPlatform"])
        self.assertEqual(plan["platform"]["id"], "windows-x64")
        self.assertIn("install.ps1", plan["steps"][0]["changes"])

    def test_ffmpeg_concat_entry_preserves_windows_drive_and_escapes_quote(self) -> None:
        entry = ffmpeg_concat_entry(PureWindowsPath("C:/Users/Creator's Files/clip 01.mp4"))
        self.assertEqual(entry, "file 'C:/Users/Creator'\\''s Files/clip 01.mp4'\n")

    def test_doctor_rejects_an_incompatible_version(self) -> None:
        check = _command_check(
            "Python",
            sys.executable,
            ["--version"],
            required=True,
            repair="Install Python 99.",
            expected="Python 99",
        )
        self.assertFalse(check.ok)
        self.assertIn("Incompatible", check.detail)


if __name__ == "__main__":
    unittest.main()
