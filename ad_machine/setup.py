from __future__ import annotations

import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from .util import run


BREW_FORMULAE = ("ffmpeg", "node@22", "whisper-cpp", "uv")


def setup_plan(root: Path) -> dict[str, Any]:
    root = root.resolve()
    brew = shutil.which("brew")
    missing_commands = [name for name in ("ffmpeg", "ffprobe", "node", "npm", "whisper-cli", "uv") if not shutil.which(name)]
    return {
        "schemaVersion": 1,
        "supportedPlatform": platform.system() == "Darwin" and platform.machine().lower() in {"arm64", "aarch64"},
        "platform": {"system": platform.system(), "machine": platform.machine()},
        "root": str(root),
        "brewAvailable": bool(brew),
        "missingCommands": missing_commands,
        "steps": [
            {"name": "system-media-tools", "changes": f"Install missing Homebrew formulae from: {', '.join(BREW_FORMULAE)}"},
            {"name": "python-environment", "changes": "Create .venv and install this product plus Kinocut 1.11.1"},
            {"name": "node-environment", "changes": "Run npm ci for HyperFrames 0.7.86"},
            {"name": "render-browser", "changes": "Ensure HyperFrames managed Chrome is downloaded"},
            {"name": "agent-skills", "changes": "Install or refresh the HyperFrames talking-head workflow skills"},
        ],
    }


def apply_setup(root: Path) -> dict[str, Any]:
    root = root.resolve()
    plan = setup_plan(root)
    if not plan["supportedPlatform"]:
        raise RuntimeError("Version 0.1 setup supports Apple Silicon Macs only")

    missing = set(plan["missingCommands"])
    if missing:
        brew = shutil.which("brew")
        if not brew:
            raise RuntimeError("Homebrew is required to install missing media tools; install Homebrew, then rerun setup")
        required_formulae = []
        if "ffmpeg" in missing or "ffprobe" in missing:
            required_formulae.append("ffmpeg")
        if "node" in missing or "npm" in missing:
            required_formulae.append("node@22")
        if "whisper-cli" in missing:
            required_formulae.append("whisper-cpp")
        if "uv" in missing:
            required_formulae.append("uv")
        if required_formulae:
            run([brew, "install", *dict.fromkeys(required_formulae)], timeout=1800)

    venv_python = root / ".venv" / "bin" / "python"
    if not venv_python.is_file():
        uv = shutil.which("uv")
        if uv:
            run([uv, "venv", "--python", "3.12", str(root / ".venv")], timeout=600)
        else:
            run([sys.executable, "-m", "venv", str(root / ".venv")], timeout=600)

    uv = shutil.which("uv")
    if uv:
        run(
            [uv, "pip", "install", "--python", str(venv_python), "-e", str(root), "kinocut==1.11.1", "mcp==1.29.0"],
            timeout=1800,
        )
    else:
        run(
            [str(venv_python), "-m", "pip", "install", "-e", str(root), "kinocut==1.11.1", "mcp==1.29.0"],
            timeout=1800,
        )
    kino = root / ".venv" / "bin" / "kino"
    kino_check = run([str(kino), "--version"], timeout=30)
    if "1.11.1" not in (kino_check.stdout or kino_check.stderr):
        raise RuntimeError("the pinned Kinocut executable did not report version 1.11.1")

    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("npm is unavailable after setup")
    npm_command = [npm, "ci"] if (root / "package-lock.json").is_file() else [npm, "install"]
    run(npm_command, cwd=root, timeout=1800)

    hyperframes = root / "node_modules" / ".bin" / "hyperframes"
    if not hyperframes.is_file():
        raise RuntimeError("local HyperFrames executable was not installed")
    hyperframes_check = run([str(hyperframes), "--version"], cwd=root, timeout=30)
    if "0.7.86" not in (hyperframes_check.stdout or hyperframes_check.stderr):
        raise RuntimeError("the pinned HyperFrames executable did not report version 0.7.86")
    run([str(hyperframes), "browser", "ensure"], cwd=root, timeout=900)
    skills_result = run(
        [str(hyperframes), "skills", "update", "talking-head-recut"],
        cwd=root,
        timeout=300,
        check=False,
    )
    return {
        "success": True,
        "venvPython": str(venv_python),
        "hyperframes": str(hyperframes),
        "skillsUpdated": skills_result.returncode == 0,
        "skillsMessage": (skills_result.stdout or skills_result.stderr).strip(),
    }
