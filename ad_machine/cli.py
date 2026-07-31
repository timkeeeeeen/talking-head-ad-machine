from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .demo import run_demo
from .design import check_composition, prepare_fast_composition, render_preview
from .doctor import doctor_report, format_doctor, report_json
from .jobs import create_job, load_job, reusable_artifacts, save_job
from .modules import install_module, installed_modules
from .plans import validate_and_normalize
from .platforms import open_path
from .profiles import DEFAULT_PROFILE, load_profile, save_profile
from .qa import inspect_output
from .render import duration_matches, duration_seconds, expected_plan_duration, normalize_dialogue, primary_fps, render_ffmpeg_concat
from .resolve import make_fcpxml
from .review import generate_review
from .setup import apply_setup, setup_plan
from .support import create_support_report
from .transcribe import transcribe_job
from .util import read_json, sha256_file, write_json_atomic
from .version import VERSION


def product_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _print(value: object, as_json: bool = False) -> None:
    if as_json or isinstance(value, (dict, list)):
        print(json.dumps(value, indent=2))
    else:
        print(value)


def _open(path: Path) -> None:
    open_path(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ad-machine", description="Create reviewable talking-head social ads")
    parser.add_argument("--version", action="version", version=VERSION)
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup_parser = subparsers.add_parser("setup", help="Plan or apply supported Windows or macOS setup")
    setup_parser.add_argument("--apply", action="store_true", help="Install the planned dependencies")
    setup_parser.add_argument("--json", action="store_true")

    doctor_parser = subparsers.add_parser("doctor", help="Check only requirements for this product")
    doctor_parser.add_argument("--json", action="store_true")

    demo_parser = subparsers.add_parser("demo", help="Run the deterministic local smoke test")
    demo_parser.add_argument("--output-root", type=Path)
    demo_parser.add_argument("--open", action="store_true", dest="open_review")
    demo_parser.add_argument("--json", action="store_true")

    new_parser = subparsers.add_parser("new", help="Create an immutable-source editing job")
    new_parser.add_argument("source", type=Path)
    new_parser.add_argument("--mode", choices=("fast", "designed", "studio"), default="fast")
    new_parser.add_argument("--output-root", type=Path)
    new_parser.add_argument("--slug")
    new_parser.add_argument("--json", action="store_true")

    transcribe_parser = subparsers.add_parser("transcribe", help="Create or reuse a local word-timed transcript")
    transcribe_parser.add_argument("job", type=Path)
    transcribe_parser.add_argument("--model", default="small.en")
    transcribe_parser.add_argument("--language", default="en")
    transcribe_parser.add_argument("--force", action="store_true")
    transcribe_parser.add_argument("--json", action="store_true")

    resume_parser = subparsers.add_parser("resume", help="Inspect a job and reusable artifacts")
    resume_parser.add_argument("job", type=Path)
    resume_parser.add_argument("--json", action="store_true")

    plan_parser = subparsers.add_parser("validate-plan", help="Validate and normalize an inspectable edit plan")
    plan_parser.add_argument("plan", type=Path)
    plan_parser.add_argument("--output", type=Path)
    plan_parser.add_argument("--json", action="store_true")

    verify_parser = subparsers.add_parser("verify-duration", help="Compare a rendered cut with its planned duration")
    verify_parser.add_argument("job", type=Path)
    verify_parser.add_argument("variant")
    verify_parser.add_argument("output", type=Path)
    verify_parser.add_argument("--json", action="store_true")

    render_parser = subparsers.add_parser("render-clean", help="Render the deterministic timestamp-reset fallback")
    render_parser.add_argument("job", type=Path)
    render_parser.add_argument("variant")
    render_parser.add_argument("--output", type=Path)
    render_parser.add_argument("--json", action="store_true")

    qa_parser = subparsers.add_parser("qa", help="Inspect a rendered output and write its technical QA report")
    qa_parser.add_argument("job", type=Path)
    qa_parser.add_argument("variant")
    qa_parser.add_argument("output", type=Path)
    qa_parser.add_argument("--json", action="store_true")

    normalize_parser = subparsers.add_parser("normalize-audio", help="Create a new dialogue-normalized video without modifying the input")
    normalize_parser.add_argument("job", type=Path)
    normalize_parser.add_argument("variant")
    normalize_parser.add_argument("input", type=Path)
    normalize_parser.add_argument("--output", type=Path)
    normalize_parser.add_argument("--json", action="store_true")

    design_parser = subparsers.add_parser("design-fast", help="Prepare a reusable HyperFrames Fast-mode preview project")
    design_parser.add_argument("job", type=Path)
    design_parser.add_argument("variant")
    design_parser.add_argument("input", type=Path)
    design_parser.add_argument("--hook")
    design_parser.add_argument("--cta")
    design_parser.add_argument("--ratio", choices=("4:5", "9:16", "1:1", "16:9"), default="4:5")
    design_parser.add_argument("--accent", default="#ff6a3d")
    design_parser.add_argument("--json", action="store_true")

    check_design_parser = subparsers.add_parser("check-design", help="Run the HyperFrames browser gate on a prepared project")
    check_design_parser.add_argument("project", type=Path)
    check_design_parser.add_argument("--json", action="store_true")

    preview_parser = subparsers.add_parser("render-preview", help="Render a low-resolution HyperFrames review preview")
    preview_parser.add_argument("job", type=Path)
    preview_parser.add_argument("variant")
    preview_parser.add_argument("project", type=Path)
    preview_parser.add_argument("--output", type=Path)
    preview_parser.add_argument("--json", action="store_true")

    fcpxml_parser = subparsers.add_parser("make-fcpxml", help="Create narrow best-effort FCPXML for a simple cut")
    fcpxml_parser.add_argument("job", type=Path)
    fcpxml_parser.add_argument("variant")
    fcpxml_parser.add_argument("--output", type=Path)
    fcpxml_parser.add_argument("--json", action="store_true")

    review_parser = subparsers.add_parser("review", help="Generate and open the local review page")
    review_parser.add_argument("job", type=Path)
    review_parser.add_argument("--no-open", action="store_true")
    review_parser.add_argument("--json", action="store_true")

    approve_parser = subparsers.add_parser("approve", help="Record explicit human approval")
    approve_parser.add_argument("job", type=Path)
    approve_parser.add_argument("--note")
    approve_parser.add_argument("--json", action="store_true")

    profile_parser = subparsers.add_parser("profile", help="Inspect or initialize the single brand profile")
    profile_parser.add_argument("action", choices=("show", "init"))
    profile_parser.add_argument("--json", action="store_true")

    modules_parser = subparsers.add_parser("modules", help="List or install paid extension modules")
    modules_parser.add_argument("action", choices=("list", "install"))
    modules_parser.add_argument("archive", nargs="?", type=Path)
    modules_parser.add_argument("--json", action="store_true")

    support_parser = subparsers.add_parser("support-report", help="Create a sanitized support archive")
    support_parser.add_argument("--job", type=Path)
    support_parser.add_argument("--output", type=Path)
    support_parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = product_root()
    try:
        if args.command == "setup":
            result = apply_setup(root) if args.apply else setup_plan(root)
            _print(result, args.json)
            return 0
        if args.command == "doctor":
            result = doctor_report(root)
            print(report_json(result) if args.json else format_doctor(result), end="\n" if not args.json else "")
            return 0 if result["summary"]["requiredOk"] else 1
        if args.command == "demo":
            output_root = (args.output_root or (root / "jobs")).expanduser()
            result = run_demo(root, output_root)
            if args.open_review:
                _open(Path(result["review"]))
            _print(result, args.json)
            return 0
        if args.command == "new":
            output_root = (args.output_root or (root / "jobs")).expanduser()
            job = create_job(args.source, output_root, mode=args.mode, slug=args.slug)
            _print({"success": True, "job": str(job), "next": "Complete brief.json, then transcribe and write a validated edit plan."}, args.json)
            return 0
        if args.command == "transcribe":
            result = transcribe_job(args.job, model=args.model, language=args.language, force=args.force)
            _print(result, args.json)
            return 0
        if args.command == "resume":
            job = load_job(args.job)
            result = {"job": str(args.job.resolve()), "stage": job["stage"], "lastError": job.get("lastError"), "reusableArtifacts": reusable_artifacts(args.job)}
            _print(result, args.json)
            return 0
        if args.command == "validate-plan":
            source_plan = read_json(args.plan)
            normalized, errors = validate_and_normalize(source_plan)
            if errors:
                _print({"success": False, "errors": errors}, True)
                return 1
            output = args.output or args.plan.with_name("edit-plan.normalized.json")
            write_json_atomic(output, normalized)
            _print({"success": True, "output": str(output), "variants": [{"id": item["id"], "durationSeconds": item["durationSeconds"]} for item in normalized["variants"]]}, args.json)
            return 0
        if args.command == "verify-duration":
            plan = read_json(args.job / "plans" / "edit-plan.normalized.json")
            expected = expected_plan_duration(plan, args.variant)
            actual = duration_seconds(args.output)
            fps = primary_fps(args.output)
            matches = duration_matches(expected, actual, fps)
            _print({"success": matches, "expectedDurationSeconds": round(expected, 3), "actualDurationSeconds": round(actual, 3), "fps": round(fps, 3)}, args.json)
            return 0 if matches else 1
        if args.command == "render-clean":
            job = load_job(args.job)
            plan = read_json(args.job / "plans" / "edit-plan.normalized.json")
            variant = next((item for item in plan["variants"] if item["id"] == args.variant), None)
            if not variant:
                raise ValueError(f"variant not found: {args.variant}")
            output = args.output or (args.job / "previews" / f"{args.variant}-clean.mp4")
            report = render_ffmpeg_concat(Path(job["source"]["path"]), variant["segments"], output)
            if not report["durationMatches"]:
                raise RuntimeError(f"fallback render duration mismatch: {report}")
            record_name = f"clean-cut-{args.variant}"
            from .jobs import record_artifact, set_stage
            record_artifact(args.job, record_name, output, producer="ffmpeg-reset-timestamps-concat", input_hashes={"source": job["source"]["sha256"], "plan": sha256_file(args.job / "plans" / "edit-plan.normalized.json")})
            set_stage(args.job, "clean-cut-rendered", f"Rendered deterministic clean cut for {args.variant}")
            _print({"success": True, "artifact": record_name, "render": report}, args.json)
            return 0
        if args.command == "qa":
            plan = read_json(args.job / "plans" / "edit-plan.normalized.json")
            expected = expected_plan_duration(plan, args.variant)
            result = inspect_output(args.output, expected_duration=expected)
            qa_path = args.job / "qa" / f"{args.variant}.json"
            write_json_atomic(qa_path, result)
            from .jobs import record_artifact, set_stage
            record_artifact(args.job, f"qa-{args.variant}", qa_path, producer="ad-machine-qa", input_hashes={"output": sha256_file(args.output)})
            if result["success"]:
                set_stage(args.job, "qa-complete", f"Technical QA passed for {args.variant}")
            _print(result, args.json)
            return 0 if result["success"] else 1
        if args.command == "normalize-audio":
            output = args.output or (args.job / "renders" / f"{args.variant}-normalized.mp4")
            result = normalize_dialogue(args.input, output)
            from .jobs import record_artifact
            record_artifact(args.job, f"normalized-{args.variant}", output, producer="ffmpeg-loudnorm", input_hashes={"input": sha256_file(args.input)})
            _print({"success": True, "normalization": result}, args.json)
            return 0
        if args.command == "design-fast":
            result = prepare_fast_composition(
                root,
                args.job,
                args.variant,
                args.input,
                hook=args.hook,
                cta=args.cta,
                ratio=args.ratio,
                accent=args.accent,
            )
            _print(result, args.json)
            return 0
        if args.command == "check-design":
            result = check_composition(root, args.project)
            _print(result, args.json)
            return 0
        if args.command == "render-preview":
            result = render_preview(root, args.job, args.variant, args.project, args.output)
            _print(result, args.json)
            return 0
        if args.command == "make-fcpxml":
            plan = read_json(args.job / "plans" / "edit-plan.normalized.json")
            output = args.output or (args.job / "resolve-handoff" / f"{args.variant}.fcpxml")
            result = make_fcpxml(plan, args.variant, output)
            from .jobs import record_artifact
            record_artifact(args.job, f"fcpxml-{args.variant}", output, producer="ad-machine-fcpxml", input_hashes={"plan": sha256_file(args.job / "plans" / "edit-plan.normalized.json")})
            _print(result, args.json)
            return 0
        if args.command == "review":
            output = generate_review(args.job)
            if not args.no_open:
                _open(output)
            _print({"success": True, "review": str(output)}, args.json)
            return 0
        if args.command == "approve":
            job = load_job(args.job)
            now = datetime.now(timezone.utc).isoformat()
            job["approval"] = {"status": "approved", "decidedAt": now, "note": args.note}
            job["stage"] = "approved"
            job.setdefault("events", []).append({"at": now, "stage": "approved", "message": args.note or "Human approved preview"})
            save_job(args.job, job)
            _print({"success": True, "job": str(args.job.resolve()), "approval": job["approval"]}, args.json)
            return 0
        if args.command == "profile":
            if args.action == "init":
                path = save_profile(root, DEFAULT_PROFILE)
                result = {"success": True, "profile": str(path), "value": load_profile(root)}
            else:
                result = {"profile": str(root / "config" / "brand.json"), "value": load_profile(root)}
            _print(result, args.json)
            return 0
        if args.command == "modules":
            if args.action == "install":
                if not args.archive:
                    raise ValueError("modules install requires a module ZIP")
                result = {"success": True, "module": install_module(root, args.archive)}
            else:
                result = {"modules": installed_modules(root)}
            _print(result, args.json)
            return 0
        if args.command == "support-report":
            output = args.output or (root / f"support-report-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.zip")
            report = create_support_report(root, output, args.job)
            _print({"success": True, "supportReport": str(report)}, args.json)
            return 0
    except (FileNotFoundError, FileExistsError, ValueError, RuntimeError, subprocess.SubprocessError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
