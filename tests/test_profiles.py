from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ad_machine.profiles import load_profile, save_profile


class ProfileTests(unittest.TestCase):
    def test_single_profile_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = save_profile(root, {"schemaVersion": 1, "brandName": "Acme", "colors": ["#112233"]})
            self.assertTrue(path.is_file())
            self.assertEqual(load_profile(root)["brandName"], "Acme")
            self.assertEqual(load_profile(root)["captionStyle"], "clean-bold")


if __name__ == "__main__":
    unittest.main()

