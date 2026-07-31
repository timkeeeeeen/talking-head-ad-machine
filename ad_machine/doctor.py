from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from .platforms import detect_platform, resolve_product_command
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
    command: str | None,
    args: Sequence[str],
    *,
    required: bool,
    repair: str,
    expected: str | None = None,
    minimum_major: int | None = None,
) -> Check:
    executable = command if command and Path(command).is_file() else shutil.which(command or "")
    if not executable:
        return Check(name, required, False, "Not found", repair)
    try:
        result = run([executable, *args], timeout=15)
        combined = "\n".join(value for value in (result.stdout, result.stderr) if value).strip()
        output = combined.splitlines()
        detail = output[0] if output else executable
        if expected and expected not in combined:
            return Check(name, required, False, f"Incompatible: {detail}; expected {expected}", repair)
        if minimum_major is not None:
            match = re.search(r"(?:^|\D)(\d+)(?:\.\d+)", combined)
            if not match or int(match.group(1)) < minimum_major:
                return Check(name, required, False, f"Incompatible: {detail}; expected major {minimum_major} or newer", repair)
        return Check(name, required, True, detail)
    except Exception as error:  # diagnostics must report, not crash
        return Check(name, required, False, f"Found but unusable: {error}", repair)


def collect_checks(root: Path | None = None) -> list[Check]:
    spec = detect_platform()
    python = resolve_product_command(root, "python", kind="venv") if root else shutil.which("python")
    kino = resolve_product_command(root, "kino", kind="venv") if root else shutil.which("kino")
    hyperframes = resolve_product_command(root, "hyperframes", kind="node") if root else shutil.which("hyperframes")
    checks = [
        Check(
            "Supported operating system",
            True,
            spec.supported,
            f"Detected {spec.id}",
            "Use Windows 11 x64, Apple Silicon macOS, or Intel macOS.",
        ),
        _command_check("Python", python, ["--version"], required=True, repair="Run the platform installer to create Python 3.12.", expected="Python 3.12"),
        _command_check("FFmpeg", "ffmpeg", ["-version"], required=True, repair="Run the platform installer to install FFmpeg."),
        _command_check("FFprobe", "ffprobe", ["-version"], required=True, repair="Run the platform installer to install FFmpeg."),
        _command_check("Node.js", "node", ["--version"], required=True, repair="Run the platform installer to install Node 22 or newer.", minimum_major=22),
        _command_check("npm", "npm", ["--version"], required=True, repair="Install npm with Node 22."),
        _command_check("whisper.cpp", "whisper-cli", ["--version"], required=True, repair="Run the platform installer to install whisper.cpp."),
        _command_check("Kinocut", kino, ["--version"], required=True, repair="Install the pinned Kinocut version through setup.", expected="1.11.1"),
        _command_check("HyperFrames", hyperframes, ["--version"], required=True, repair="Install the pinned HyperFrames version through setup.", expected="0.7.86"),
        _command_check("Docker", "docker", ["--version"], required=False, repair="Optional; not required for local host rendering."),
    ]
    return checks


def doctor_report(root: Path) -> dict:
    checks = collect_checks(root)
    spec = detect_platform()
    required = [check for check in checks if check.required]
    return {
        "schemaVersion": 1,
        "productVersion": VERSION,
        "productRoot": str(root.resolve()),
        "platform": {"id": spec.id, "system": spec.system, "machine": spec.machine},
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
