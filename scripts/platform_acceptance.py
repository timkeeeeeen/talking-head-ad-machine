#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ad_machine.platforms import detect_platform  # noqa: E402
from ad_machine.util import read_json, read_json_value, sha256_file, write_json_atomic  # noqa: E402


def run_cli(arguments: list[str], *, timeout: int = 3600) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-m", "ad_machine.cli", *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ad-machine {' '.join(arguments)} failed ({result.returncode})\n"
            f"stdout:\n{result.stdout[-3000:]}\nstderr:\n{result.stderr[-3000:]}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"command did not return JSON: {result.stdout[-3000:]}") from error
    if not isinstance(payload, dict):
        raise RuntimeError("command returned a non-object JSON value")
    return payload


def execute(model: str, acceptance_class: str) -> dict[str, Any]:
    spec = detect_platform()
    if not spec.supported:
        raise RuntimeError(f"unsupported acceptance platform: {spec.id}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_root = ROOT / "acceptance" / spec.id / timestamp
    run_root.mkdir(parents=True, exist_ok=False)
    source = ROOT / "examples" / "first-ad" / "proof" / "raw-synthetic-talking-head.mp4"
    source_hash = sha256_file(source)
    steps: list[dict[str, Any]] = []

    doctor = run_cli(["doctor", "--json"])
    if not doctor["summary"]["requiredOk"]:
        raise RuntimeError("doctor did not pass every required check")
    steps.append({"name": "doctor", "ok": True, "required": doctor["summary"]["requiredPassed"]})

    demo = run_cli(["demo", "--output-root", str(run_root / "demo"), "--json"])
    if not demo["render"]["durationMatches"] or not demo["qa"]["success"]:
        raise RuntimeError("deterministic demo failed")
    steps.append({"name": "demo", "ok": True})

    created = run_cli(
        ["new", str(source), "--mode", "fast", "--output-root", str(run_root / "jobs"), "--slug", "platform-acceptance", "--json"]
    )
    job = Path(created["job"])

    brief = read_json(ROOT / "examples" / "first-ad" / "proof" / "brief.json")
    write_json_atomic(job / "brief.json", brief)
    transcript = run_cli(["transcribe", str(job), "--model", model, "--language", "en", "--json"], timeout=7200)
    transcript_entries = read_json_value(Path(transcript["transcript"]))
    if not isinstance(transcript_entries, list) or len(transcript_entries) < 5:
        raise RuntimeError("transcription produced too few timed entries")
    steps.append({"name": "transcription", "ok": True, "model": model, "entries": len(transcript_entries)})

    plan = read_json(ROOT / "examples" / "first-ad" / "proof" / "edit-plan.normalized.json")
    plan["source"]["path"] = str(source)
    plan["source"]["sha256"] = source_hash
    raw_plan = job / "plans" / "edit-plan.json"
    normalized_plan = job / "plans" / "edit-plan.normalized.json"
    write_json_atomic(raw_plan, plan)
    run_cli(["validate-plan", str(raw_plan), "--output", str(normalized_plan), "--json"])

    variant = "proof-4x5"
    clean = run_cli(["render-clean", str(job), variant, "--json"], timeout=3600)
    clean_path = Path(clean["render"]["output"])
    steps.append({"name": "clean-render", "ok": True, "duration": clean["render"]["actualDurationSeconds"]})

    designed = run_cli(
        [
            "design-fast",
            str(job),
            variant,
            str(clean_path),
            "--hook",
            "Turn one talking-head take into a review-ready ad",
            "--cta",
            "Get the exact workflow",
            "--ratio",
            "4:5",
            "--json",
        ]
    )
    project = Path(designed["project"])
    run_cli(["check-design", str(project), "--json"], timeout=1800)
    preview = run_cli(["render-preview", str(job), variant, str(project), "--json"], timeout=3600)
    preview_path = Path(preview["preview"])
    steps.append({"name": "hyperframes-preview", "ok": True, "preview": str(preview_path)})

    normalized_output = job / "renders" / f"{variant}-normalized.mp4"
    run_cli(["normalize-audio", str(job), variant, str(preview_path), "--output", str(normalized_output), "--json"], timeout=3600)
    qa = run_cli(["qa", str(job), variant, str(normalized_output), "--json"], timeout=1800)
    if not qa["success"]:
        raise RuntimeError("final technical QA failed")
    review = run_cli(["review", str(job), "--no-open", "--json"])
    support = run_cli(
        ["support-report", "--job", str(job), "--output", str(run_root / "support-report.zip"), "--json"]
    )
    steps.append({"name": "qa-review-support", "ok": True})

    if sha256_file(source) != source_hash:
        raise RuntimeError("acceptance workflow modified the camera original")

    return {
        "schemaVersion": 1,
        "success": True,
        "acceptanceClass": acceptance_class,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "platform": {"id": spec.id, "system": spec.system, "machine": spec.machine},
        "model": model,
        "sourceSha256": source_hash,
        "sourceUnchanged": True,
        "job": str(job),
        "finalOutput": str(normalized_output),
        "review": review["review"],
        "supportReport": support["supportReport"],
        "steps": steps,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full clean-machine media acceptance workflow")
    parser.add_argument("--model", default="small.en")
    parser.add_argument("--acceptance-class", choices=("buyer-platform", "runtime-ci"), default="buyer-platform")
    args = parser.parse_args()
    spec = detect_platform()
    try:
        report = execute(args.model, args.acceptance_class)
    except Exception as error:
        report = {
            "schemaVersion": 1,
            "success": False,
            "acceptanceClass": args.acceptance_class,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "platform": {"id": spec.id, "system": spec.system, "machine": spec.machine},
            "error": str(error),
        }
    report_root = ROOT / "acceptance" / spec.id
    report_root.mkdir(parents=True, exist_ok=True)
    report_path = report_root / "latest-report.json"
    write_json_atomic(report_path, report)
    print(json.dumps({**report, "report": str(report_path)}, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
