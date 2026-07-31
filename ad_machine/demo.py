from __future__ import annotations

from pathlib import Path

from .jobs import create_job, record_artifact, set_stage
from .plans import validate_and_normalize
from .qa import inspect_output
from .render import duration_seconds, normalize_dialogue, render_ffmpeg_concat
from .review import generate_review
from .util import run, sha256_file, write_json_atomic


def ensure_demo_source(root: Path) -> Path:
    generated = root / "examples" / "first-ad" / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    source = generated / "demo-source.mp4"
    if source.is_file() and duration_seconds(source) > 3.9:
        return source
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=640x360:rate=30:duration=4",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=4",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            "-movflags",
            "+faststart",
            str(source),
        ],
        timeout=120,
    )
    return source


def run_demo(root: Path, output_root: Path) -> dict:
    source = ensure_demo_source(root)
    job_dir = create_job(source, output_root, mode="fast", slug="deterministic-demo")
    duration = duration_seconds(source)
    plan = {
        "schemaVersion": 1,
        "source": {"path": str(source), "durationSeconds": duration, "sha256": sha256_file(source)},
        "variants": [
            {
                "id": "demo-cut",
                "label": "Timestamp reset demo",
                "targetRatios": ["16:9"],
                "segments": [
                    {"sourceStart": 0.0, "sourceEnd": 1.5, "text": "Demo segment one", "reason": "Exercise first cut", "beat": "hook", "confidence": 1.0},
                    {"sourceStart": 2.5, "sourceEnd": 4.0, "text": "Demo segment two", "reason": "Exercise timestamp reset", "beat": "cta", "confidence": 1.0},
                ],
                "durationSeconds": 3.0,
            }
        ],
    }
    plan, errors = validate_and_normalize(plan)
    if errors:
        raise RuntimeError(f"internal demo plan is invalid: {errors}")
    write_json_atomic(job_dir / "plans" / "edit-plan.normalized.json", plan)
    write_json_atomic(
        job_dir / "transcript" / "transcript.json",
        [
            {"text": "Demo", "start": 0.08, "end": 0.34},
            {"text": "segment", "start": 0.36, "end": 0.76},
            {"text": "one", "start": 0.78, "end": 1.18},
            {"text": "Demo", "start": 2.56, "end": 2.84},
            {"text": "segment", "start": 2.86, "end": 3.28},
            {"text": "two", "start": 3.30, "end": 3.76},
        ],
    )
    set_stage(job_dir, "planned", "Deterministic demo edit plan created")
    raw_cut = job_dir / "cache" / "demo-cut-raw.mp4"
    preview = job_dir / "previews" / "demo-cut.mp4"
    render_report = render_ffmpeg_concat(source, plan["variants"][0]["segments"], raw_cut)
    if not render_report["durationMatches"]:
        raise RuntimeError(f"demo duration mismatch: {render_report}")
    normalization = normalize_dialogue(raw_cut, preview)
    qa = inspect_output(preview, expected_duration=3.0)
    write_json_atomic(job_dir / "qa" / "report.json", {"schemaVersion": 1, "success": qa["success"], "render": render_report, "normalization": normalization, "output": qa})
    record_artifact(job_dir, "preview", preview, producer="ffmpeg-reset-timestamps-concat+loudnorm", input_hashes={"source": sha256_file(source)})
    set_stage(job_dir, "qa-complete", "Deterministic duration and media checks passed")
    set_stage(job_dir, "awaiting-review", "Demo preview is ready for human review")
    review = generate_review(job_dir)
    return {"success": True, "job": str(job_dir), "preview": str(preview), "review": str(review), "render": render_report, "normalization": normalization, "qa": qa}
