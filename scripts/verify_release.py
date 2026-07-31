#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the packaged Talking-Head Ad Machine release")
    parser.add_argument("--fresh-setup", action="store_true", help="Run the buyer setup inside the extracted ZIP")
    parser.add_argument("--golden", action="store_true", help="Include the real HyperFrames check and render test")
    args = parser.parse_args()

    checksums = checksum_manifest()
    core_names = [name for name in checksums if name.startswith("talking-head-ad-machine-")]
    if len(core_names) != 1:
        raise RuntimeError("release must contain exactly one core buyer ZIP")
    if any(name.startswith("client-edition-") for name in checksums):
        raise RuntimeError("Client Edition must remain absent until completed")

    required_modules = {"hook-recording-pack-v0.1.0.zip", "ad-test-lab-v0.1.0.zip"}
    if not required_modules.issubset(checksums):
        raise RuntimeError("release is missing a paid-module ZIP")

    steps: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="ad-machine-release-acceptance-") as temporary:
        extraction = Path(temporary)
        run(["unzip", "-q", DIST / core_names[0], "-d", extraction], cwd=ROOT)
        buyer = extraction / "talking-head-ad-machine"
        if not (buyer / "START-HERE.md").is_file():
            raise RuntimeError("core ZIP does not have the expected buyer root")
        if not os.access(buyer / "bin" / "ad-machine", os.X_OK):
            raise RuntimeError("buyer command lost its executable permission in the ZIP")

        if args.fresh_setup:
            run([buyer / "bin" / "ad-machine", "setup", "--apply", "--json"], cwd=buyer, timeout=3600)
            steps.append({"name": "fresh-setup", "ok": True})
        elif not (buyer / ".venv" / "bin" / "python").is_file():
            raise RuntimeError("use --fresh-setup when the extracted archive has no environment")

        doctor = json.loads(run([buyer / "bin" / "ad-machine", "doctor", "--json"], cwd=buyer))
        if not doctor["summary"]["requiredOk"] or doctor["summary"]["requiredPassed"] != doctor["summary"]["requiredTotal"]:
            raise RuntimeError("buyer doctor did not pass every required check")
        steps.append({"name": "doctor", "ok": True, "required": doctor["summary"]["requiredPassed"]})

        versions = run(
            [
                buyer / ".venv" / "bin" / "python",
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
        tests = run([buyer / ".venv" / "bin" / "python", "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=buyer, env=environment)
        steps.append({"name": "tests", "ok": True, "golden": args.golden, "summary": tests.splitlines()[-1] if tests.splitlines() else "passed"})

        demo = json.loads(run([buyer / "bin" / "ad-machine", "demo", "--json"], cwd=buyer))
        if not demo["render"]["durationMatches"] or not demo["qa"]["success"]:
            raise RuntimeError("buyer demo did not pass render and QA")
        steps.append({"name": "demo", "ok": True, "durationSeconds": demo["render"]["actualDurationSeconds"]})

        for module_name in sorted(required_modules):
            installed = json.loads(
                run([buyer / "bin" / "ad-machine", "modules", "install", DIST / module_name, "--json"], cwd=buyer)
            )
            if not installed["success"]:
                raise RuntimeError(f"module installation failed: {module_name}")
        listed = json.loads(run([buyer / "bin" / "ad-machine", "modules", "list", "--json"], cwd=buyer))
        if {item["id"] for item in listed["modules"]} != {"hook-recording-pack", "ad-test-lab"}:
            raise RuntimeError("installed module list is incomplete")
        steps.append({"name": "paid-modules", "ok": True, "count": 2})

        support = json.loads(run([buyer / "bin" / "ad-machine", "support-report", "--json"], cwd=buyer))
        support_path = Path(support["supportReport"])
        if not support_path.is_file() or not zipfile.is_zipfile(support_path):
            raise RuntimeError("support report was not created as a ZIP")
        steps.append({"name": "support-report", "ok": True})

    report = {
        "schemaVersion": 1,
        "success": True,
        "coreArchive": core_names[0],
        "coreSha256": checksums[core_names[0]],
        "freshSetup": args.fresh_setup,
        "goldenHyperFrames": args.golden,
        "steps": steps,
    }
    (DIST / "acceptance-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
