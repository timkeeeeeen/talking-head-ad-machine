from __future__ import annotations

import shutil
from pathlib import Path

from .jobs import load_job, record_artifact, reusable_artifacts, set_stage
from .util import read_json_value, run, write_json_atomic


def transcribe_job(job_dir: Path, *, model: str = "small.en", language: str = "en", force: bool = False) -> dict:
    job_dir = job_dir.expanduser().resolve()
    job = load_job(job_dir)
    existing = reusable_artifacts(job_dir).get("transcript", False)
    output = job_dir / "transcript" / "transcript.json"
    if existing and not force:
        return {"success": True, "reused": True, "transcript": str(output)}

    hyperframes = shutil.which("hyperframes")
    if not hyperframes:
        raise RuntimeError("HyperFrames is unavailable; run setup and doctor")
    work = job_dir / "cache" / "transcription"
    work.mkdir(parents=True, exist_ok=True)
    result = run(
        [
            hyperframes,
            "transcribe",
            job["source"]["path"],
            "--dir",
            str(work),
            "--model",
            model,
            "--language",
            language,
            "--json",
        ],
        timeout=3600,
    )
    generated = work / "transcript.json"
    if not generated.is_file():
        raise RuntimeError(f"HyperFrames did not create transcript.json: {(result.stdout or result.stderr).strip()}")
    transcript = read_json_value(generated)
    if not isinstance(transcript, list):
        raise RuntimeError("HyperFrames transcript must be a JSON list")
    write_json_atomic(output, transcript)
    record_artifact(job_dir, "transcript", output, producer=f"hyperframes-transcribe:{model}", input_hashes={"source": job["source"]["sha256"]})
    set_stage(job_dir, "transcribed", f"Local transcript created with {model}")
    return {"success": True, "reused": False, "transcript": str(output), "entries": len(transcript)}

