from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .render import duration_from_probe, duration_matches, fps_from_probe, probe_media
from .util import run


LOUDNESS_PATTERN = re.compile(r"\{\s*\"input_i\".*?\}", re.DOTALL)


def _loudness(path: Path) -> dict[str, Any] | None:
    result = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-af",
            "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
            "-f",
            "null",
            "-",
        ],
        check=False,
        timeout=600,
    )
    matches = LOUDNESS_PATTERN.findall(result.stderr)
    if not matches:
        return None
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError:
        return None


def inspect_output(path: Path, *, expected_duration: float | None = None) -> dict[str, Any]:
    path = path.expanduser().resolve()
    probe = probe_media(path)
    video = next((stream for stream in probe.get("streams", []) if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in probe.get("streams", []) if stream.get("codec_type") == "audio"), None)
    duration = duration_from_probe(probe)
    fps = fps_from_probe(probe)
    checks = {
        "hasVideo": video is not None,
        "hasAudio": audio is not None,
        "deliveryPixelFormat": bool(video and video.get("pix_fmt") == "yuv420p"),
        "durationMatches": True if expected_duration is None else duration_matches(expected_duration, duration, fps),
    }
    return {
        "schemaVersion": 1,
        "success": all(checks.values()),
        "path": str(path),
        "durationSeconds": round(duration, 3),
        "expectedDurationSeconds": expected_duration,
        "fps": round(fps, 3),
        "video": None if not video else {key: video.get(key) for key in ("codec_name", "width", "height", "pix_fmt", "avg_frame_rate")},
        "audio": None if not audio else {key: audio.get(key) for key in ("codec_name", "sample_rate", "channels", "channel_layout")},
        "loudness": _loudness(path) if audio else None,
        "checks": checks,
        "humanReview": "pending",
        "limitations": ["Automated QA does not prove semantic accuracy, caption readability, safe zones, or creative quality."],
    }
