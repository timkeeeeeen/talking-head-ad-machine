#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ad_machine.design import check_composition, prepare_fast_composition, render_preview
from ad_machine.jobs import create_job, record_artifact, set_stage
from ad_machine.plans import validate_and_normalize
from ad_machine.qa import inspect_output
from ad_machine.render import duration_seconds, normalize_dialogue, render_ffmpeg_concat
from ad_machine.review import generate_review
from ad_machine.util import run, sha256_file, write_json_atomic


PROOF = ROOT / "examples" / "first-ad" / "proof"
PRESENTER = PROOF / "synthetic-presenter.png"
VOICE = "Samantha"
GAP_SECONDS = 0.42

LINES = [
    "Most people think you need... sorry. Let me start again.",
    "Most people think you need a whole editing team to turn a talking head video into an ad.",
    "You don't. This kit finds the clean take, adds captions and useful graphics, checks the output, and gives you a review page before anything is final.",
    "If you want the exact workflow, get the Talking Head Ad Machine.",
]


def words_for_line(text: str, start: float, end: float) -> list[dict[str, float | str]]:
    words = re.findall(r"\S+", text)
    if not words:
        return []
    usable = max(0.2, end - start)
    step = usable / len(words)
    return [
        {
            "text": word,
            "start": round(start + index * step, 3),
            "end": round(min(end, start + (index + 0.82) * step), 3),
        }
        for index, word in enumerate(words)
    ]


def main() -> int:
    if not PRESENTER.is_file():
        raise FileNotFoundError(f"missing generated presenter: {PRESENTER}")
    if not shutil.which("say"):
        raise RuntimeError("the proof builder currently requires the macOS say command")

    PROOF.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ad-machine-proof-") as temporary:
        work = Path(temporary)
        wavs: list[Path] = []
        durations: list[float] = []
        for index, line in enumerate(LINES):
            aiff = work / f"line-{index}.aiff"
            wav = work / f"line-{index}.wav"
            run(["say", "-v", VOICE, "-r", "178", "-o", aiff, line], timeout=180)
            run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", aiff, "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", wav], timeout=180)
            wavs.append(wav)
            durations.append(duration_seconds(wav))

        gap = work / "gap.wav"
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
                "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-t",
                str(GAP_SECONDS),
                "-c:a",
                "pcm_s16le",
                gap,
            ],
            timeout=120,
        )
        concat = work / "concat.txt"
        sequence: list[Path] = []
        for index, wav in enumerate(wavs):
            sequence.append(wav)
            if index + 1 < len(wavs):
                sequence.append(gap)
        concat.write_text("".join(f"file '{path.as_posix()}'\n" for path in sequence), encoding="utf-8")
        dialogue = work / "raw-dialogue.wav"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", concat, "-c:a", "pcm_s16le", dialogue], timeout=180)

        raw_source = PROOF / "raw-synthetic-talking-head.mp4"
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-loop",
                "1",
                "-i",
                PRESENTER,
                "-i",
                dialogue,
                "-vf",
                "scale=1080:1350:force_original_aspect_ratio=increase,crop=1080:1350,zoompan=z='min(zoom+0.00008,1.025)':d=1:s=1080x1350:fps=30,format=yuv420p",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                "-movflags",
                "+faststart",
                raw_source,
            ],
            timeout=900,
        )

        starts: list[float] = []
        cursor = 0.0
        for duration in durations:
            starts.append(cursor)
            cursor += duration + GAP_SECONDS
        source_duration = duration_seconds(raw_source)
        segments = []
        transcript = []
        beats = ["context", "hook", "mechanism", "cta"]
        reasons = ["Remove the abandoned take", "Open on the complete source-backed hook", "Keep the concrete mechanism", "Keep the direct desired action"]
        for index, (line, start, duration) in enumerate(zip(LINES, starts, durations)):
            transcript.extend(words_for_line(line, start, start + duration))
            if index == 0:
                continue
            segments.append(
                {
                    "sourceStart": round(start, 3),
                    "sourceEnd": round(min(source_duration, start + duration + (0.16 if index < len(LINES) - 1 else 0.0)), 3),
                    "text": line,
                    "reason": reasons[index],
                    "beat": beats[index],
                    "confidence": 1.0,
                }
            )

        job = create_job(raw_source, ROOT / "jobs", mode="fast", slug="distributable-proof")
        brief = {
            "schemaVersion": 1,
            "offer": "Talking-Head Ad Machine",
            "audience": "Founders and marketers editing their own talking-head Meta ads",
            "desiredAction": "Get the exact workflow",
            "allowedEvidence": ["The included local workflow creates edit plans, captions, QA, receipts, and review previews"],
            "prohibitedClaims": ["guaranteed ad performance", "guaranteed revenue", "fully offline agent reasoning"],
            "targetDurationSeconds": [15, 45],
            "targetRatios": ["4:5"],
            "brandProfile": None,
        }
        write_json_atomic(job / "brief.json", brief)
        write_json_atomic(job / "transcript" / "transcript.json", transcript)
        plan, errors = validate_and_normalize(
            {
                "schemaVersion": 1,
                "source": {"path": str(raw_source), "durationSeconds": source_duration, "sha256": sha256_file(raw_source)},
                "variants": [{"id": "proof-4x5", "label": "Synthetic proof ad", "targetRatios": ["4:5"], "segments": segments}],
            }
        )
        if errors:
            raise RuntimeError(f"proof plan failed validation: {errors}")
        write_json_atomic(job / "plans" / "edit-plan.normalized.json", plan)
        set_stage(job, "planned", "Distributable proof edit plan created")

        clean_raw = job / "cache" / "proof-clean-raw.mp4"
        clean = job / "previews" / "proof-clean-normalized.mp4"
        clean_report = render_ffmpeg_concat(raw_source, plan["variants"][0]["segments"], clean_raw)
        if not clean_report["durationMatches"]:
            raise RuntimeError(f"proof clean-cut duration mismatch: {clean_report}")
        normalization = normalize_dialogue(clean_raw, clean)
        record_artifact(job, "proof-clean", clean, producer="ffmpeg-reset-timestamps-concat+loudnorm", input_hashes={"source": sha256_file(raw_source), "plan": sha256_file(job / "plans" / "edit-plan.normalized.json")})
        set_stage(job, "clean-cut-rendered", "Proof clean cut rendered and normalized")

        prepared = prepare_fast_composition(
            ROOT,
            job,
            "proof-4x5",
            clean,
            hook="Turn one raw clip into an ad",
            cta="Get the exact workflow",
            ratio="4:5",
            accent="#ff6a3d",
        )
        checked = check_composition(ROOT, Path(prepared["project"]))
        rendered = render_preview(ROOT, job, "proof-4x5", Path(prepared["project"]), PROOF / "finished-4x5.mp4")
        qa = inspect_output(Path(rendered["preview"]), expected_duration=float(plan["variants"][0]["durationSeconds"]))
        if not qa["success"]:
            raise RuntimeError(f"proof QA failed: {qa}")
        write_json_atomic(job / "qa" / "proof-4x5.json", qa)
        record_artifact(job, "proof-qa", job / "qa" / "proof-4x5.json", producer="ad-machine-qa", input_hashes={"output": sha256_file(Path(rendered["preview"]))})
        set_stage(job, "qa-complete", "Distributable proof passed technical QA")
        set_stage(job, "awaiting-review", "Distributable proof is ready for human review")
        review = generate_review(job)

        shutil.copy2(job / "brief.json", PROOF / "brief.json")
        shutil.copy2(job / "transcript" / "transcript.json", PROOF / "transcript.json")
        shutil.copy2(job / "transcript" / "proof-4x5.srt", PROOF / "captions.srt")
        shutil.copy2(job / "plans" / "edit-plan.normalized.json", PROOF / "edit-plan.normalized.json")
        shutil.copy2(job / "qa" / "proof-4x5.json", PROOF / "qa.json")
        shutil.copy2(Path(prepared["project"]) / "check.json", PROOF / "hyperframes-check.json")
        shutil.copy2(review, PROOF / "review.html")
        receipt = {
            "schemaVersion": 1,
            "disclosure": "Synthetic presenter image and macOS system voice created solely as distributable product demonstration media.",
            "testimonial": False,
            "performanceClaim": False,
            "humanReview": "pending",
            "sourceSha256": sha256_file(raw_source),
            "outputSha256": sha256_file(PROOF / "finished-4x5.mp4"),
            "sourceDurationSeconds": source_duration,
            "outputDurationSeconds": rendered["actualDurationSeconds"],
            "cleanRender": clean_report,
            "normalization": normalization,
            "hyperframes": {"ok": checked["ok"], "version": checked.get("_meta", {}).get("version")},
            "qa": qa,
        }
        write_json_atomic(PROOF / "receipt.json", receipt)
        print(json.dumps({"success": True, "job": str(job), "raw": str(raw_source), "finished": rendered["preview"], "receipt": str(PROOF / "receipt.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
