from __future__ import annotations

import json
import platform
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .doctor import doctor_report
from .jobs import load_job
from .version import VERSION


def _sanitized_job(job_dir: Path) -> dict:
    job = load_job(job_dir)
    return {
        "schemaVersion": job.get("schemaVersion"),
        "productVersion": job.get("productVersion"),
        "jobId": job.get("jobId"),
        "stage": job.get("stage"),
        "mode": job.get("mode"),
        "source": {"sha256": job.get("source", {}).get("sha256")},
        "artifacts": {
            name: {
                "sha256": artifact.get("sha256"),
                "producer": artifact.get("producer"),
                "productVersion": artifact.get("productVersion"),
            }
            for name, artifact in job.get("artifacts", {}).items()
        },
        "lastError": job.get("lastError"),
    }


def create_support_report(root: Path, output: Path, job_dir: Path | None = None) -> Path:
    payload = {
        "schemaVersion": 1,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "productVersion": VERSION,
        "platform": {"system": platform.system(), "machine": platform.machine()},
    }
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("summary.json", json.dumps(payload, indent=2) + "\n")
        archive.writestr("doctor.json", json.dumps(doctor_report(root), indent=2) + "\n")
        if job_dir:
            archive.writestr("job-sanitized.json", json.dumps(_sanitized_job(job_dir), indent=2) + "\n")
    return output

