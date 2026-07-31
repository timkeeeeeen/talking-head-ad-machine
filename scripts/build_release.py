#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
DIST = ROOT / "dist"

EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    "installed",
    "generated",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".DS_Store"}
FORBIDDEN_TEXT = (
    b"/Users/" + b"lappy",
    b"Photo Booth" + b" Library",
    b"machine-smoke" + b"-test-ad",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def include_core(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if relative.parts[:2] == ("extensions", "catalog"):
        return False
    if relative.parts and relative.parts[0] == "jobs" and relative.name != ".gitkeep":
        return False
    if relative == Path("config/brand.json"):
        return False
    if path.suffix in EXCLUDED_SUFFIXES or path.name.startswith("support-report"):
        return False
    return path.is_file()


def write_core_zip() -> Path:
    output = DIST / f"talking-head-ad-machine-macos-arm64-v{VERSION}.zip"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(ROOT.rglob("*")):
            if include_core(path):
                archive.write(path, Path("talking-head-ad-machine") / path.relative_to(ROOT))
    return output


def write_module_zip(module_dir: Path) -> Path:
    manifest = json.loads((module_dir / "module.json").read_text(encoding="utf-8"))
    output = DIST / f"{manifest['id']}-v{manifest['version']}.zip"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(module_dir.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(module_dir))
    return output


def scan_archive(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        for member in archive.infolist():
            name = member.filename.encode("utf-8", errors="ignore")
            if any(value in name for value in FORBIDDEN_TEXT):
                raise RuntimeError(f"forbidden private value in archive name: {member.filename}")
            if member.file_size <= 2_000_000:
                payload = archive.read(member)
                if any(value in payload for value in FORBIDDEN_TEXT):
                    raise RuntimeError(f"forbidden private value in archive member: {member.filename}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-client-edition", action="store_true")
    args = parser.parse_args()
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    artifacts = [write_core_zip()]
    for module_dir in sorted((ROOT / "extensions" / "catalog").iterdir()):
        manifest = json.loads((module_dir / "module.json").read_text(encoding="utf-8"))
        if manifest.get("saleStatus") == "disabled-until-complete" and not args.include_client_edition:
            continue
        artifacts.append(write_module_zip(module_dir))

    for artifact in artifacts:
        scan_archive(artifact)

    checksums = "".join(f"{sha256(path)}  {path.name}\n" for path in artifacts)
    (DIST / "SHA256SUMS").write_text(checksums, encoding="utf-8")
    manifest = {
        "schemaVersion": 1,
        "productVersion": VERSION,
        "artifacts": [{"name": path.name, "sha256": sha256(path), "bytes": path.stat().st_size} for path in artifacts],
    }
    (DIST / "release-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
