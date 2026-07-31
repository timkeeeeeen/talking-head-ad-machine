from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from .util import read_json, safe_relative_path, sha256_file, write_json_atomic
from .version import VERSION


def _version_compatible(requirement: str, version: str = VERSION) -> bool:
    if "||" in requirement:
        return any(_version_compatible(item.strip(), version) for item in requirement.split("||"))
    if requirement in {version, "*"}:
        return True
    if requirement.endswith(".x"):
        return version.startswith(requirement[:-1])
    return False


def validate_manifest(manifest: dict[str, Any]) -> None:
    required = ("schemaVersion", "id", "displayName", "version", "requiresCore", "capabilities")
    missing = [key for key in required if key not in manifest]
    if missing:
        raise ValueError(f"module manifest missing: {', '.join(missing)}")
    if manifest["schemaVersion"] != 1:
        raise ValueError("module schemaVersion must equal 1")
    module_id = str(manifest["id"])
    if not module_id or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in module_id):
        raise ValueError("module id must use lowercase letters, digits, and hyphens")
    if not _version_compatible(str(manifest["requiresCore"])):
        raise ValueError(f"module requires core {manifest['requiresCore']}; installed core is {VERSION}")
    if not isinstance(manifest["capabilities"], list):
        raise ValueError("module capabilities must be a list")


def installed_modules(root: Path) -> list[dict[str, Any]]:
    installed_root = root / "extensions" / "installed"
    if not installed_root.is_dir():
        return []
    result = []
    for manifest_path in sorted(installed_root.glob("*/module.json")):
        manifest = read_json(manifest_path)
        manifest["installPath"] = str(manifest_path.parent)
        result.append(manifest)
    return result


def install_module(root: Path, archive: Path) -> dict[str, Any]:
    root = root.resolve()
    archive = archive.expanduser().resolve()
    if not archive.is_file() or archive.suffix.lower() != ".zip":
        raise ValueError("module must be a ZIP file")

    with tempfile.TemporaryDirectory(prefix="ad-machine-module-") as temporary:
        stage = Path(temporary)
        with zipfile.ZipFile(archive) as package:
            for member in package.infolist():
                safe_relative_path(member.filename)
            package.extractall(stage)

        manifests = list(stage.glob("module.json")) + list(stage.glob("*/module.json"))
        if len(manifests) != 1:
            raise ValueError("module ZIP must contain exactly one module.json at its root or one top-level directory")
        manifest_path = manifests[0]
        module_root = manifest_path.parent
        manifest = read_json(manifest_path)
        validate_manifest(manifest)

        target = root / "extensions" / "installed" / manifest["id"]
        staged_target = target.with_name(f".{target.name}.staging")
        if staged_target.exists():
            shutil.rmtree(staged_target)
        staged_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(module_root, staged_target)
        write_json_atomic(
            staged_target / "install-receipt.json",
            {
                "schemaVersion": 1,
                "moduleId": manifest["id"],
                "moduleVersion": manifest["version"],
                "coreVersion": VERSION,
                "archiveSha256": sha256_file(archive),
            },
        )
        backup = target.with_name(f".{target.name}.previous")
        if backup.exists():
            shutil.rmtree(backup)
        if target.exists():
            target.rename(backup)
        staged_target.rename(target)
        if backup.exists():
            shutil.rmtree(backup)
        return manifest
