from __future__ import annotations

import json
import math
import shutil
import tempfile
from pathlib import Path, PurePath
from typing import Any

from .util import run


def probe_media(path: Path) -> dict[str, Any]:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ]
    )
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise ValueError("ffprobe did not return an object")
    return value


def duration_seconds(path: Path) -> float:
    return duration_from_probe(probe_media(path))


def duration_from_probe(probe: dict[str, Any]) -> float:
    return float(probe.get("format", {}).get("duration") or 0.0)


def primary_fps(path: Path) -> float:
    return fps_from_probe(probe_media(path))


def fps_from_probe(probe: dict[str, Any]) -> float:
    video = next((stream for stream in probe.get("streams", []) if stream.get("codec_type") == "video"), None)
    if not video:
        return 30.0
    numerator, denominator = str(video.get("avg_frame_rate") or "30/1").split("/", 1)
    denominator_value = float(denominator)
    return float(numerator) / denominator_value if denominator_value else 30.0


def expected_plan_duration(plan: dict[str, Any], variant_id: str) -> float:
    variant = next((item for item in plan.get("variants", []) if item.get("id") == variant_id), None)
    if not variant:
        raise ValueError(f"variant not found: {variant_id}")
    return sum(float(segment["sourceEnd"]) - float(segment["sourceStart"]) for segment in variant["segments"])


def duration_tolerance(fps: float) -> float:
    return max(0.25, 2.0 / fps if fps > 0 else 0.25)


def duration_matches(expected: float, actual: float, fps: float) -> bool:
    return math.fabs(expected - actual) <= duration_tolerance(fps)


def ffmpeg_concat_entry(path: PurePath) -> str:
    escaped = path.as_posix().replace("'", "'\\''")
    return f"file '{escaped}'\n"


def render_ffmpeg_concat(
    source: Path,
    segments: list[dict[str, Any]],
    output: Path,
    *,
    width: int | None = None,
    height: int | None = None,
    preset: str = "veryfast",
) -> dict[str, Any]:
    """Render straight cuts with fresh timestamps and a deterministic concat fallback."""

    source = source.expanduser().resolve()
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if not segments:
        raise ValueError("at least one segment is required")

    with tempfile.TemporaryDirectory(prefix="ad-machine-concat-", dir=output.parent) as temporary:
        temporary_dir = Path(temporary)
        segment_paths: list[Path] = []
        for index, segment in enumerate(segments):
            start = float(segment["sourceStart"])
            end = float(segment["sourceEnd"])
            if start < 0 or end <= start:
                raise ValueError(f"invalid segment {index}: {start}..{end}")
            segment_path = temporary_dir / f"segment-{index:03d}.mp4"
            video_filter = ["setpts=PTS-STARTPTS"]
            if width and height:
                video_filter.append(
                    f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
                )
            command = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{start:.6f}",
                "-to",
                f"{end:.6f}",
                "-i",
                str(source),
                "-vf",
                ",".join(video_filter),
                "-af",
                "asetpts=PTS-STARTPTS",
                "-c:v",
                "libx264",
                "-preset",
                preset,
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-movflags",
                "+faststart",
                str(segment_path),
            ]
            run(command)
            segment_paths.append(segment_path)

        concat_file = temporary_dir / "concat.txt"
        concat_file.write_text(
            "".join(ffmpeg_concat_entry(path) for path in segment_paths),
            encoding="utf-8",
        )
        combined = temporary_dir / "combined.mp4"
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-fflags",
                "+genpts",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                "-avoid_negative_ts",
                "make_zero",
                str(combined),
            ]
        )
        shutil.move(combined, output)

    expected = sum(float(item["sourceEnd"]) - float(item["sourceStart"]) for item in segments)
    output_probe = probe_media(output)
    actual = duration_from_probe(output_probe)
    fps = fps_from_probe(output_probe)
    return {
        "output": str(output),
        "strategy": "ffmpeg-reset-timestamps-concat",
        "expectedDurationSeconds": round(expected, 3),
        "actualDurationSeconds": round(actual, 3),
        "fps": round(fps, 3),
        "toleranceSeconds": round(duration_tolerance(fps), 3),
        "durationMatches": duration_matches(expected, actual, fps),
    }


def normalize_dialogue(
    source: Path,
    output: Path,
    *,
    integrated_lufs: float = -14.0,
    true_peak_dbtp: float = -1.5,
    loudness_range: float = 11.0,
) -> dict[str, Any]:
    source = source.expanduser().resolve()
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-c:v",
            "copy",
            "-af",
            f"loudnorm=I={integrated_lufs}:TP={true_peak_dbtp}:LRA={loudness_range}",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(output),
        ],
        timeout=1800,
    )
    return {
        "output": str(output),
        "targetIntegratedLufs": integrated_lufs,
        "targetTruePeakDbtp": true_peak_dbtp,
        "targetLoudnessRange": loudness_range,
        "durationSeconds": round(duration_seconds(output), 3),
    }
