from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .util import read_json, sha256_file, slugify, write_json_atomic
from .version import VERSION


STAGES = (
    "initialized",
    "preflighted",
    "transcribed",
    "planned",
    "clean-cut-rendered",
    "designed",
    "qa-complete",
    "awaiting-review",
    "approved",
    "delivered",
    "failed-recoverable",
    "failed-terminal",
)

MODES = ("fast", "designed", "studio")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_job(source: Path, output_root: Path, *, mode: str = "fast", slug: str | None = None) -> Path:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"source is not a file: {source}")
    if mode not in MODES:
        raise ValueError(f"mode must be one of: {', '.join(MODES)}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    job_dir = output_root.expanduser().resolve() / f"{stamp}-{slugify(slug or source.stem)}"
    if job_dir.exists():
        raise FileExistsError(f"refusing to reuse job directory: {job_dir}")

    for directory in (
        "transcript",
        "plans",
        "previews",
        "renders",
        "hyperframes",
        "qa",
        "review",
        "cache",
        "resolve-handoff",
        "logs",
    ):
        (job_dir / directory).mkdir(parents=True, exist_ok=False)

    created = now_iso()
    job = {
        "schemaVersion": 1,
        "productVersion": VERSION,
        "jobId": job_dir.name,
        "createdAt": created,
        "updatedAt": created,
        "stage": "initialized",
        "mode": mode,
        "source": {
            "path": str(source),
            "sha256": sha256_file(source),
        },
        "briefPath": "brief.json",
        "artifacts": {},
        "events": [{"at": created, "stage": "initialized", "message": "Job created"}],
        "approval": {"status": "pending", "decidedAt": None, "note": None},
        "lastError": None,
        "publish": False,
    }
    brief = {
        "schemaVersion": 1,
        "offer": None,
        "audience": None,
        "desiredAction": None,
        "allowedEvidence": [],
        "prohibitedClaims": [],
        "targetDurationSeconds": [15, 45],
        "targetRatios": ["4:5"],
        "brandProfile": None,
    }
    write_json_atomic(job_dir / "job.json", job)
    write_json_atomic(job_dir / "brief.json", brief)
    return job_dir


def load_job(job_dir: Path) -> dict[str, Any]:
    return read_json(job_dir.expanduser().resolve() / "job.json")


def save_job(job_dir: Path, job: dict[str, Any]) -> None:
    job["updatedAt"] = now_iso()
    write_json_atomic(job_dir.expanduser().resolve() / "job.json", job)


def set_stage(job_dir: Path, stage: str, message: str) -> dict[str, Any]:
    if stage not in STAGES:
        raise ValueError(f"unknown stage: {stage}")
    job = load_job(job_dir)
    now = now_iso()
    job["stage"] = stage
    job.setdefault("events", []).append({"at": now, "stage": stage, "message": message})
    if not stage.startswith("failed-"):
        job["lastError"] = None
    save_job(job_dir, job)
    return job


def record_error(job_dir: Path, message: str, *, recoverable: bool) -> dict[str, Any]:
    job = load_job(job_dir)
    now = now_iso()
    stage = "failed-recoverable" if recoverable else "failed-terminal"
    job["stage"] = stage
    job["lastError"] = {"at": now, "message": message, "recoverable": recoverable}
    job.setdefault("events", []).append({"at": now, "stage": stage, "message": message})
    save_job(job_dir, job)
    return job


def record_artifact(
    job_dir: Path,
    name: str,
    path: Path,
    *,
    producer: str,
    input_hashes: dict[str, str] | None = None,
) -> dict[str, Any]:
    job_dir = job_dir.expanduser().resolve()
    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    job = load_job(job_dir)
    try:
        relative_path = str(path.relative_to(job_dir))
    except ValueError:
        relative_path = str(path)
    job.setdefault("artifacts", {})[name] = {
        "path": relative_path,
        "sha256": sha256_file(path),
        "producer": producer,
        "productVersion": VERSION,
        "inputHashes": input_hashes or {},
        "createdAt": now_iso(),
    }
    save_job(job_dir, job)
    return job


def artifact_path(job_dir: Path, artifact: dict[str, Any]) -> Path:
    value = Path(str(artifact["path"]))
    return value if value.is_absolute() else job_dir / value


def reusable_artifacts(job_dir: Path) -> dict[str, bool]:
    job_dir = job_dir.expanduser().resolve()
    job = load_job(job_dir)
    current_inputs: dict[str, str | None] = {"source": None, "plan": None, "transcript": None}
    source_path = Path(str(job.get("source", {}).get("path", ""))).expanduser()
    if source_path.is_file():
        current_inputs["source"] = sha256_file(source_path)
    plan_path = job_dir / "plans" / "edit-plan.normalized.json"
    if plan_path.is_file():
        current_inputs["plan"] = sha256_file(plan_path)
    transcript_path = job_dir / "transcript" / "transcript.json"
    if transcript_path.is_file():
        current_inputs["transcript"] = sha256_file(transcript_path)
    for name, artifact in job.get("artifacts", {}).items():
        candidate = artifact_path(job_dir, artifact)
        current_inputs[name] = sha256_file(candidate) if candidate.is_file() else None

    result: dict[str, bool] = {}
    for name, artifact in job.get("artifacts", {}).items():
        path = artifact_path(job_dir, artifact)
        valid = (
            path.is_file()
            and sha256_file(path) == artifact.get("sha256")
            and artifact.get("productVersion") == VERSION
        )
        if valid:
            for input_name, expected_hash in artifact.get("inputHashes", {}).items():
                current_hash = current_inputs.get(input_name)
                if current_hash is not None and current_hash != expected_hash:
                    valid = False
                    break
        result[name] = valid
    return result
