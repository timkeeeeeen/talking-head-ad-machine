from __future__ import annotations

import json
import platform
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from .util import run
from .version import VERSION


@dataclass(frozen=True)
class Check:
    name: str
    required: bool
    ok: bool
    detail: str
    repair: str | None = None


def _command_check(
    name: str,
    command: str,
    args: Sequence[str],
    *,
    required: bool,
    repair: str,
) -> Check:
    executable = shutil.which(command)
    if not executable:
        return Check(name, required, False, "Not found", repair)
    try:
        result = run([executable, *args], timeout=15)
        output = (result.stdout or result.stderr).strip().splitlines()
        detail = output[0] if output else executable
        return Check(name, required, True, detail)
    except Exception as error:  # diagnostics must report, not crash
        return Check(name, required, False, f"Found but unusable: {error}", repair)


def collect_checks() -> list[Check]:
    system = platform.system()
    machine = platform.machine().lower()
    checks = [
        Check(
            "Apple Silicon Mac",
            True,
            system == "Darwin" and machine in {"arm64", "aarch64"},
            f"Detected {system or 'unknown'} {machine or 'unknown'}",
            "Version 0.1 supports Apple Silicon Macs only.",
        ),
        _command_check("FFmpeg", "ffmpeg", ["-version"], required=True, repair="Install FFmpeg with the supported Mac setup."),
        _command_check("FFprobe", "ffprobe", ["-version"], required=True, repair="Install FFmpeg with the supported Mac setup."),
        _command_check("Node.js", "node", ["--version"], required=True, repair="Install Node 22 with the supported Mac setup."),
        _command_check("npm", "npm", ["--version"], required=True, repair="Install npm with Node 22."),
        _command_check("whisper.cpp", "whisper-cli", ["--version"], required=True, repair="Install whisper-cpp with the supported Mac setup."),
        _command_check("Kinocut", "kino", ["--version"], required=True, repair="Install the pinned Kinocut version through setup."),
        _command_check("HyperFrames", "hyperframes", ["--version"], required=True, repair="Install the pinned HyperFrames version through setup."),
        _command_check("Docker", "docker", ["--version"], required=False, repair="Optional; not required for local host rendering."),
    ]
    return checks


def doctor_report(root: Path) -> dict:
    checks = collect_checks()
    required = [check for check in checks if check.required]
    return {
        "schemaVersion": 1,
        "productVersion": VERSION,
        "productRoot": str(root.resolve()),
        "summary": {
            "requiredOk": all(check.ok for check in required),
            "requiredPassed": sum(1 for check in required if check.ok),
            "requiredTotal": len(required),
            "optionalMissing": [check.name for check in checks if not check.required and not check.ok],
        },
        "checks": [asdict(check) for check in checks],
        "notes": [
            "Docker, local TTS, generated music, and DaVinci Resolve are optional.",
            "An optional missing tool does not make the Talking-Head Ad Machine unavailable.",
        ],
    }


def format_doctor(report: dict) -> str:
    lines = [f"Talking-Head Ad Machine {report['productVersion']}"]
    for check in report["checks"]:
        marker = "PASS" if check["ok"] else ("MISS" if check["required"] else "OPTIONAL")
        lines.append(f"[{marker}] {check['name']}: {check['detail']}")
        if check.get("repair") and not check["ok"]:
            lines.append(f"        {check['repair']}")
    summary = report["summary"]
    lines.append("")
    lines.append("READY" if summary["requiredOk"] else "NOT READY")
    return "\n".join(lines)


def report_json(report: dict) -> str:
    return json.dumps(report, indent=2) + "\n"

