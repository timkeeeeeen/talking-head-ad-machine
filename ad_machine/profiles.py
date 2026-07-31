from __future__ import annotations

from pathlib import Path
from typing import Any

from .util import read_json, write_json_atomic


DEFAULT_PROFILE = {
    "schemaVersion": 1,
    "brandName": None,
    "logo": None,
    "productImages": [],
    "colors": [],
    "fonts": [],
    "captionStyle": "clean-bold",
    "ctaStyle": "restrained-card",
    "defaultRatios": ["4:5"],
    "approvedEvidence": [],
    "prohibitedClaims": [],
    "layoutNotes": [],
}


def profile_path(root: Path) -> Path:
    return root / "config" / "brand.json"


def load_profile(root: Path) -> dict[str, Any] | None:
    path = profile_path(root)
    return read_json(path) if path.is_file() else None


def save_profile(root: Path, profile: dict[str, Any]) -> Path:
    merged = dict(DEFAULT_PROFILE)
    merged.update(profile)
    if merged.get("schemaVersion") != 1:
        raise ValueError("brand profile schemaVersion must equal 1")
    path = profile_path(root)
    write_json_atomic(path, merged)
    return path

