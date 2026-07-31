from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from ad_machine.modules import install_module, installed_modules


class ModuleTests(unittest.TestCase):
    def _archive(self, root: Path, manifest: dict) -> Path:
        archive = root / "module.zip"
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("module.json", json.dumps(manifest))
            package.writestr("SKILL.md", "---\nname: test-module\ndescription: Test.\n---\n")
        return archive

    def test_install_is_idempotent(self) -> None:
        manifest = {
            "schemaVersion": 1,
            "id": "test-module",
            "displayName": "Test Module",
            "version": "0.1.0",
            "requiresCore": "0.1.x || 0.2.x",
            "capabilities": ["test"],
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self._archive(root, manifest)
            install_module(root, archive)
            install_module(root, archive)
            installed = installed_modules(root)
            self.assertEqual([item["id"] for item in installed], ["test-module"])

    def test_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "bad.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("../escape", "bad")
            with self.assertRaises(ValueError):
                install_module(root, archive)

    def test_incompatible_core_is_rejected(self) -> None:
        manifest = {
            "schemaVersion": 1,
            "id": "future-module",
            "displayName": "Future Module",
            "version": "1.0.0",
            "requiresCore": "9.0.x",
            "capabilities": [],
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                install_module(root, self._archive(root, manifest))


if __name__ == "__main__":
    unittest.main()
