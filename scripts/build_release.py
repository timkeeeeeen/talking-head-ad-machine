#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
DIST = ROOT / "dist"

EXCLUDED_PARTS = {
    ".git",
    ".github",
    ".venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".runtime",
    "installed",
    "generated",
}
CORE_PLATFORMS = ("macos-arm64", "macos-x64", "windows-x64")
MAC_ONLY_FILES = {
    Path("install.sh"),
    Path("bin/ad-machine"),
    Path("START-WITH-CODEX.command"),
    Path("START-WITH-CLAUDE.command"),
}
WINDOWS_ONLY_FILES = {Path("install.ps1"), Path("bin/ad-machine.ps1")}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".DS_Store"}
ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)
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


def tracked_source_files() -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"release builds require a Git checkout: {message}")
    paths = [ROOT / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError(f"tracked release source is missing: {missing[0].relative_to(ROOT)}")
    return sorted(paths)


def include_core(path: Path, platform_id: str) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if relative.parts and relative.parts[0] == "acceptance":
        return False
    if relative.parts[:2] == ("docs", "acceptance"):
        return False
    if relative.parts[:2] == ("extensions", "catalog"):
        return False
    if relative.parts and relative.parts[0] == "jobs" and relative.name != ".gitkeep":
        return False
    if relative == Path("config/brand.json"):
        return False
    if platform_id == "windows-x64" and relative in MAC_ONLY_FILES:
        return False
    if platform_id.startswith("macos-") and relative in WINDOWS_ONLY_FILES:
        return False
    if path.suffix in EXCLUDED_SUFFIXES or path.name.startswith("support-report"):
        return False
    return path.is_file()


def write_deterministic_file(
    archive: zipfile.ZipFile,
    source: Path,
    destination: Path,
    *,
    executable: bool = False,
) -> None:
    archive_name = PurePosixPath(*destination.parts).as_posix()
    info = zipfile.ZipInfo(archive_name, date_time=ZIP_TIMESTAMP)
    info.create_system = 3
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = ((0o100755 if executable else 0o100644) << 16)
    archive.writestr(info, source.read_bytes(), compress_type=zipfile.ZIP_STORED)


def write_core_zip(platform_id: str, source_paths: list[Path]) -> Path:
    if platform_id not in CORE_PLATFORMS:
        raise ValueError(f"unsupported release platform: {platform_id}")
    output = DIST / f"talking-head-ad-machine-{platform_id}-v{VERSION}.zip"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in source_paths:
            if include_core(path, platform_id):
                relative = path.relative_to(ROOT)
                write_deterministic_file(
                    archive,
                    path,
                    Path("talking-head-ad-machine") / relative,
                    executable=relative in MAC_ONLY_FILES,
                )
    return output


def write_module_zip(module_dir: Path, source_paths: list[Path]) -> Path:
    manifest = json.loads((module_dir / "module.json").read_text(encoding="utf-8"))
    output = DIST / f"{manifest['id']}-v{manifest['version']}.zip"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in source_paths:
            if path.is_relative_to(module_dir):
                write_deterministic_file(archive, path, path.relative_to(module_dir))
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

    source_paths = tracked_source_files()
    artifacts = [write_core_zip(platform_id, source_paths) for platform_id in CORE_PLATFORMS]
    for module_dir in sorted((ROOT / "extensions" / "catalog").iterdir()):
        manifest = json.loads((module_dir / "module.json").read_text(encoding="utf-8"))
        if manifest.get("saleStatus") == "disabled-until-complete" and not args.include_client_edition:
            continue
        artifacts.append(write_module_zip(module_dir, source_paths))

    for artifact in artifacts:
        scan_archive(artifact)

    checksums = "".join(f"{sha256(path)}  {path.name}\n" for path in artifacts)
    (DIST / "SHA256SUMS").write_text(checksums, encoding="utf-8")
    manifest = {
        "schemaVersion": 1,
        "productVersion": VERSION,
        "artifacts": [
            {
                "name": path.name,
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
                "platform": next((item for item in CORE_PLATFORMS if f"-{item}-" in path.name), None),
            }
            for path in artifacts
        ],
    }
    (DIST / "release-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
