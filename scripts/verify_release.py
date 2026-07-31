#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
CORE_PLATFORMS = ("macos-arm64", "macos-x64", "windows-x64")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str | Path], *, cwd: Path, env: dict[str, str] | None = None, timeout: int = 3600) -> str:
    result = subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(str(part) for part in command)}\n"
            f"stdout:\n{result.stdout[-4000:]}\nstderr:\n{result.stderr[-4000:]}"
        )
    return result.stdout


def checksum_manifest() -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line in (DIST / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        path = DIST / name
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"checksum failed: {name}")
        checksums[name] = expected
    return checksums


def current_platform_id() -> str:
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Darwin" and machine in {"arm64", "aarch64"}:
        return "macos-arm64"
    if system == "Darwin" and machine in {"x86_64", "amd64"}:
        return "macos-x64"
    if system == "Windows" and machine in {"x86_64", "amd64"}:
        return "windows-x64"
    raise RuntimeError(f"release acceptance is unsupported on {system} {machine}")


def expected_core_name(platform_id: str, version: str) -> str:
    return f"talking-head-ad-machine-{platform_id}-v{version}.zip"


def verify_core_structure(path: Path, platform_id: str) -> None:
    prefix = "talking-head-ad-machine/"
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        required = {
            f"{prefix}START-HERE.md",
            f"{prefix}runtime-lock.json",
            f"{prefix}skills/talking-head-ad-machine/SKILL.md",
        }
        if platform_id == "windows-x64":
            required.update({f"{prefix}install.ps1", f"{prefix}bin/ad-machine.ps1"})
            forbidden = {f"{prefix}install.sh", f"{prefix}bin/ad-machine"}
        else:
            required.update({f"{prefix}install.sh", f"{prefix}bin/ad-machine"})
            forbidden = {f"{prefix}install.ps1", f"{prefix}bin/ad-machine.ps1"}
        missing = required - names
        unexpected = forbidden & names
        if missing:
            raise RuntimeError(f"{path.name} is missing: {', '.join(sorted(missing))}")
        if unexpected:
            raise RuntimeError(f"{path.name} contains launchers for another platform: {', '.join(sorted(unexpected))}")


def extract_with_permissions(archive_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            extracted = Path(archive.extract(member, destination))
            mode = member.external_attr >> 16
            if mode and extracted.is_file():
                extracted.chmod(mode)


def extracted_python(buyer: Path, platform_id: str) -> Path:
    if platform_id == "windows-x64":
        return buyer / ".venv" / "Scripts" / "python.exe"
    return buyer / ".venv" / "bin" / "python"


def product_command(buyer: Path, platform_id: str, *arguments: str | Path) -> list[str | Path]:
    if platform_id == "windows-x64":
        return [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            buyer / "bin" / "ad-machine.ps1",
            *arguments,
        ]
    return [buyer / "bin" / "ad-machine", *arguments]


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the packaged Talking-Head Ad Machine release")
    parser.add_argument("--fresh-setup", action="store_true", help="Run the buyer setup inside the extracted ZIP")
    parser.add_argument("--golden", action="store_true", help="Include the real HyperFrames check and render test")
    parser.add_argument("--full-workflow", action="store_true", help="Run transcription through final review and support output")
    parser.add_argument("--platform", choices=CORE_PLATFORMS, help="Artifact to verify; defaults to this machine")
    args = parser.parse_args()

    checksums = checksum_manifest()
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    expected_cores = {expected_core_name(item, version) for item in CORE_PLATFORMS}
    core_names = {name for name in checksums if name.startswith("talking-head-ad-machine-")}
    if core_names != expected_cores:
        raise RuntimeError(f"release core artifacts do not match the platform matrix: {sorted(core_names)}")
    for platform_id in CORE_PLATFORMS:
        verify_core_structure(DIST / expected_core_name(platform_id, version), platform_id)
    if any(name.startswith("client-edition-") for name in checksums):
        raise RuntimeError("Client Edition must remain absent until completed")

    required_modules = {"hook-recording-pack-v0.1.0.zip", "ad-test-lab-v0.1.0.zip"}
    if not required_modules.issubset(checksums):
        raise RuntimeError("release is missing a paid-module ZIP")

    selected_platform = args.platform or current_platform_id()
    if args.fresh_setup and selected_platform != current_platform_id():
        raise RuntimeError("fresh setup must run on a machine matching the selected artifact")
    selected_core = expected_core_name(selected_platform, version)
    steps: list[dict[str, object]] = [
        {"name": "three-platform-structure", "ok": True, "platforms": list(CORE_PLATFORMS)}
    ]
    if not args.fresh_setup:
        report = {
            "schemaVersion": 1,
            "success": True,
            "structuralOnly": True,
            "selectedPlatform": selected_platform,
            "coreArchive": selected_core,
            "coreSha256": checksums[selected_core],
            "steps": steps,
        }
        output = DIST / f"structure-report-{selected_platform}.json"
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0

    with tempfile.TemporaryDirectory(prefix="ad-machine-release-acceptance-") as temporary:
        extraction = Path(temporary)
        extract_with_permissions(DIST / selected_core, extraction)
        buyer = extraction / "talking-head-ad-machine"
        if not (buyer / "START-HERE.md").is_file():
            raise RuntimeError("core ZIP does not have the expected buyer root")
        if selected_platform.startswith("macos-") and not os.access(buyer / "bin" / "ad-machine", os.X_OK):
            raise RuntimeError("buyer command lost its executable permission in the ZIP")

        if selected_platform == "windows-x64":
            installer = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", buyer / "install.ps1", "-SkipDemo"]
        else:
            installer = [buyer / "install.sh", "--skip-demo"]
        run(installer, cwd=buyer, timeout=3600)
        steps.append({"name": "fresh-setup", "ok": True, "platform": selected_platform})
        run(installer, cwd=buyer, timeout=3600)
        steps.append({"name": "installer-idempotence", "ok": True})

        doctor = json.loads(run(product_command(buyer, selected_platform, "doctor", "--json"), cwd=buyer))
        if not doctor["summary"]["requiredOk"] or doctor["summary"]["requiredPassed"] != doctor["summary"]["requiredTotal"]:
            raise RuntimeError("buyer doctor did not pass every required check")
        if doctor["platform"]["id"] != selected_platform:
            raise RuntimeError(f"doctor reported the wrong platform: {doctor['platform']['id']}")
        steps.append({"name": "doctor", "ok": True, "required": doctor["summary"]["requiredPassed"]})

        python = extracted_python(buyer, selected_platform)
        versions = run(
            [
                python,
                "-c",
                "import importlib.metadata as m; import mcp.server.fastmcp; print(m.version('kinocut')); print(m.version('mcp'))",
            ],
            cwd=buyer,
        ).splitlines()
        if versions != ["1.11.1", "1.29.0"]:
            raise RuntimeError(f"unexpected Kinocut/MCP versions: {versions}")
        steps.append({"name": "dependency-pins", "ok": True, "kinocut": versions[0], "mcp": versions[1]})

        environment = os.environ.copy()
        if args.golden:
            environment["AD_MACHINE_RUN_HYPERFRAMES_TESTS"] = "1"
        tests = run([python, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=buyer, env=environment)
        steps.append({"name": "tests", "ok": True, "golden": args.golden, "summary": tests.splitlines()[-1] if tests.splitlines() else "passed"})

        demo = json.loads(run(product_command(buyer, selected_platform, "demo", "--json"), cwd=buyer))
        if not demo["render"]["durationMatches"] or not demo["qa"]["success"]:
            raise RuntimeError("buyer demo did not pass render and QA")
        steps.append({"name": "demo", "ok": True, "durationSeconds": demo["render"]["actualDurationSeconds"]})

        for module_name in sorted(required_modules):
            installed = json.loads(
                run(product_command(buyer, selected_platform, "modules", "install", DIST / module_name, "--json"), cwd=buyer)
            )
            if not installed["success"]:
                raise RuntimeError(f"module installation failed: {module_name}")
        listed = json.loads(run(product_command(buyer, selected_platform, "modules", "list", "--json"), cwd=buyer))
        if {item["id"] for item in listed["modules"]} != {"hook-recording-pack", "ad-test-lab"}:
            raise RuntimeError("installed module list is incomplete")
        steps.append({"name": "paid-modules", "ok": True, "count": 2})

        support = json.loads(run(product_command(buyer, selected_platform, "support-report", "--json"), cwd=buyer))
        support_path = Path(support["supportReport"])
        if not support_path.is_file() or not zipfile.is_zipfile(support_path):
            raise RuntimeError("support report was not created as a ZIP")
        steps.append({"name": "support-report", "ok": True})

        if args.full_workflow:
            acceptance = json.loads(run([python, buyer / "scripts" / "platform_acceptance.py"], cwd=buyer, timeout=10800))
            if not acceptance.get("success"):
                raise RuntimeError(f"full platform workflow failed: {acceptance.get('error')}")
            retained_report = DIST / f"media-acceptance-report-{selected_platform}.json"
            shutil.copy2(Path(acceptance["report"]), retained_report)
            steps.append({"name": "full-media-workflow", "ok": True, "report": str(retained_report)})

    report = {
        "schemaVersion": 1,
        "success": True,
        "selectedPlatform": selected_platform,
        "coreArchive": selected_core,
        "coreSha256": checksums[selected_core],
        "freshSetup": args.fresh_setup,
        "goldenHyperFrames": args.golden,
        "fullMediaWorkflow": args.full_workflow,
        "steps": steps,
    }
    (DIST / f"acceptance-report-{selected_platform}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
