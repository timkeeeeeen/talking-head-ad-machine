from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PlatformSpec:
    id: str
    system: str
    machine: str
    family: str
    supported: bool

    @property
    def is_windows(self) -> bool:
        return self.family == "windows"

    @property
    def is_macos(self) -> bool:
        return self.family == "macos"


def detect_platform(system: str | None = None, machine: str | None = None) -> PlatformSpec:
    detected_system = system or platform.system()
    detected_machine = (machine or platform.machine()).lower()
    normalized_machine = {
        "aarch64": "arm64",
        "amd64": "x86_64",
        "x64": "x86_64",
    }.get(detected_machine, detected_machine)

    if detected_system == "Darwin" and normalized_machine == "arm64":
        return PlatformSpec("macos-arm64", detected_system, normalized_machine, "macos", True)
    if detected_system == "Darwin" and normalized_machine == "x86_64":
        return PlatformSpec("macos-x64", detected_system, normalized_machine, "macos", True)
    if detected_system == "Windows" and normalized_machine == "x86_64":
        return PlatformSpec("windows-x64", detected_system, normalized_machine, "windows", True)
    family = "windows" if detected_system == "Windows" else "macos" if detected_system == "Darwin" else "other"
    return PlatformSpec(
        f"unsupported-{detected_system.lower() or 'unknown'}-{normalized_machine or 'unknown'}",
        detected_system,
        normalized_machine,
        family,
        False,
    )


def venv_bin_dir(root: Path, spec: PlatformSpec | None = None) -> Path:
    current = spec or detect_platform()
    return root / ".venv" / ("Scripts" if current.is_windows else "bin")


def venv_executable(root: Path, name: str, spec: PlatformSpec | None = None) -> Path:
    current = spec or detect_platform()
    suffix = ".exe" if current.is_windows else ""
    return venv_bin_dir(root, current) / f"{name}{suffix}"


def node_executable(root: Path, name: str, spec: PlatformSpec | None = None) -> Path:
    current = spec or detect_platform()
    suffix = ".cmd" if current.is_windows else ""
    return root / "node_modules" / ".bin" / f"{name}{suffix}"


def resolve_product_command(root: Path, name: str, *, kind: str) -> str | None:
    spec = detect_platform()
    candidate = venv_executable(root, name, spec) if kind == "venv" else node_executable(root, name, spec)
    if candidate.is_file():
        return str(candidate)
    return shutil.which(name)


def product_environment(root: Path) -> dict[str, str]:
    spec = detect_platform()
    environment = os.environ.copy()
    prefixes = [str(venv_bin_dir(root, spec)), str(root / "node_modules" / ".bin")]
    environment["PATH"] = os.pathsep.join([*prefixes, environment.get("PATH", "")])
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join([str(root), existing_pythonpath]) if existing_pythonpath else str(root)
    return environment


def open_path(path: Path) -> None:
    spec = detect_platform()
    if spec.is_macos:
        subprocess.run(["open", str(path)], check=False)
    elif spec.is_windows:
        os.startfile(str(path))  # type: ignore[attr-defined]

