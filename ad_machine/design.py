from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path
from typing import Any

from .jobs import load_job, record_artifact, set_stage
from .render import duration_seconds
from .util import read_json, read_json_value, run, sha256_file, write_json_atomic


RATIO_DIMENSIONS = {
    "4:5": (1080, 1350),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
}


def _variant(plan: dict[str, Any], variant_id: str) -> dict[str, Any]:
    variant = next((item for item in plan.get("variants", []) if item.get("id") == variant_id), None)
    if not variant:
        raise ValueError(f"variant not found: {variant_id}")
    return variant


def _conform_words(transcript: list[Any], segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conformed: list[dict[str, Any]] = []
    for segment in segments:
        source_start = float(segment["sourceStart"])
        source_end = float(segment["sourceEnd"])
        output_start = float(segment["outputStart"])
        for entry in transcript:
            if not isinstance(entry, dict):
                continue
            text = str(entry.get("text", "")).strip()
            start = entry.get("start")
            end = entry.get("end")
            if not text or not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                continue
            midpoint = (float(start) + float(end)) / 2
            if source_start - 0.02 <= midpoint <= source_end + 0.02:
                conformed.append(
                    {
                        "text": text,
                        "start": round(output_start + max(0.0, float(start) - source_start), 3),
                        "end": round(output_start + min(source_end - source_start, float(end) - source_start), 3),
                    }
                )
    return [word for word in conformed if word["end"] > word["start"]]


def _caption_groups(words: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    for word in words:
        previous = current[-1] if current else None
        current_text = " ".join(item["text"] for item in current)
        boundary = bool(
            current
            and (
                len(current) >= 4
                or len(current_text) + len(word["text"]) + 1 > 27
                or float(word["start"]) - float(previous["end"]) > 0.38
                or str(previous["text"]).endswith((".", "?", "!", ";"))
            )
        )
        if boundary:
            groups.append({"words": current})
            current = []
        current.append(word)
    if current:
        groups.append({"words": current})

    result: list[dict[str, Any]] = []
    for index, group in enumerate(groups):
        group_words = group["words"]
        start = max(0.0, float(group_words[0]["start"]) - 0.04)
        spoken_end = min(duration, float(group_words[-1]["end"]) + 0.12)
        next_start = max(0.0, float(groups[index + 1]["words"][0]["start"]) - 0.05) if index + 1 < len(groups) else duration
        end = min(duration, max(spoken_end, min(start + 0.55, next_start)), next_start)
        if end - start < 0.18:
            continue
        result.append(
            {
                "id": f"caption-{index + 1}",
                "text": " ".join(str(item["text"]) for item in group_words),
                "start": round(start, 3),
                "duration": round(end - start, 3),
            }
        )
    return result


def _fallback_captions(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": f"caption-{index + 1}",
            "text": str(segment["text"]).strip(),
            "start": float(segment["outputStart"]),
            "duration": float(segment["outputEnd"]) - float(segment["outputStart"]),
        }
        for index, segment in enumerate(segments)
        if str(segment.get("text", "")).strip()
    ]


def _validate_overlay_copy(brief: dict[str, Any], segments: list[dict[str, Any]], hook: str, cta: str) -> None:
    combined = f"{hook}\n{cta}".casefold()
    for prohibited in brief.get("prohibitedClaims", []):
        value = str(prohibited).strip()
        if value and value.casefold() in combined:
            raise ValueError(f"overlay copy contains a prohibited claim: {value}")

    evidence_corpus = " ".join(
        [str(segment.get("text", "")) for segment in segments]
        + [str(brief.get("offer") or ""), str(brief.get("desiredAction") or ""), json.dumps(brief.get("allowedEvidence", []))]
    ).casefold()
    quantitative_claims = re.findall(r"(?:[$€£]\s*)?\d[\d,.]*(?:\s*%|\s*[x×])?", hook.casefold())
    unsupported = [claim for claim in quantitative_claims if claim.strip().replace(" ", "") not in evidence_corpus.replace(" ", "")]
    if unsupported:
        raise ValueError(f"hook contains unsupported quantitative claim(s): {', '.join(unsupported)}")


def _srt_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def _write_srt(path: Path, captions: list[dict[str, Any]]) -> None:
    blocks = []
    for index, caption in enumerate(captions, 1):
        start = float(caption["start"])
        end = start + float(caption["duration"])
        blocks.append(f"{index}\n{_srt_timestamp(start)} --> {_srt_timestamp(end)}\n{caption['text']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def _build_html(
    *,
    width: int,
    height: int,
    duration: float,
    hook: str,
    cta: str,
    accent: str,
    captions: list[dict[str, Any]],
) -> str:
    hook_duration = min(2.3, max(1.0, duration * 0.42))
    cta_window = min(2.8, max(0.85, duration * 0.28))
    cta_start = max(hook_duration + min(0.2, duration * 0.04), duration - cta_window)
    cta_start = min(cta_start, max(0.0, duration - 0.55))
    cta_duration = duration - cta_start
    caption_markup = "\n".join(
        f'''      <section id="{item["id"]}" class="clip caption-clip" data-start="{item["start"]:.3f}" data-duration="{item["duration"]:.3f}" data-track-index="{20 + index}" data-layout-allow-caption-zone>
        <div class="caption-card"><span>{html.escape(item["text"])}</span></div>
      </section>'''
        for index, item in enumerate(captions)
    )
    caption_js = json.dumps(
        [{"id": item["id"], "start": item["start"], "duration": item["duration"]} for item in captions],
        separators=(",", ":"),
    )
    return f'''<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={width}, height={height}" />
    <title>Talking-Head Ad Machine Fast Preview</title>
    <script src="assets/gsap.min.js"></script>
    <style>
      :root {{ --accent: {accent}; --ink: #111316; --paper: #f8f5ef; }}
      * {{ box-sizing: border-box; }}
      html, body {{ width: 100%; height: 100%; margin: 0; overflow: hidden; background: #15120f; }}
      body {{ font-family: Inter, system-ui, sans-serif; color: var(--paper); }}
      #root {{ position: relative; width: {width}px; height: {height}px; overflow: hidden; }}
      .clip {{ position: absolute; inset: 0; }}
      .plate {{ position: absolute; inset: 0; background: radial-gradient(circle at 18% 16%, color-mix(in srgb, var(--accent) 20%, #171411 80%), #171411 60%); }}
      .foreground-wrap {{ position: absolute; inset: 0; display: grid; place-items: center; overflow: hidden; }}
      .fg-video {{ width: 100%; height: 100%; object-fit: contain; }}
      .shade {{ position: absolute; inset: 0; background: radial-gradient(circle at 50% 42%, transparent 38%, rgba(16,13,11,.58) 100%); }}
      .top-rule {{ position: absolute; top: 56px; left: 58px; width: 110px; height: 8px; border-radius: 99px; background: var(--accent); }}
      .hook-wrap {{ position: absolute; inset: 0; display: flex; align-items: flex-start; justify-content: flex-start; padding: 82px 64px; }}
      .hook-card {{ max-width: 88%; padding: 30px 32px 34px; background: rgba(17,19,22,.90); border: 3px solid color-mix(in srgb, var(--accent) 82%, #fff 18%); border-radius: 22px; box-shadow: 0 24px 70px rgba(0,0,0,.34); }}
      .hook-text {{ display: block; max-width: 930px; font-size: clamp(58px, 6.8vw, 88px); line-height: .98; font-weight: 900; letter-spacing: -.045em; text-wrap: balance; }}
      .caption-clip {{ display: flex; align-items: flex-end; justify-content: center; padding: 0 64px 116px; }}
      .caption-card {{ max-width: 94%; padding: 21px 30px 24px; color: var(--paper); background: rgba(17,19,22,.92); border-radius: 18px; box-shadow: 0 14px 48px rgba(0,0,0,.32); font-size: clamp(45px, 5.1vw, 66px); line-height: 1.03; font-weight: 850; letter-spacing: -.035em; text-align: center; text-wrap: balance; }}
      .caption-card::after {{ content: ""; display: block; width: 68px; height: 6px; margin: 15px auto 0; border-radius: 99px; background: var(--accent); }}
      .cta-wrap {{ position: absolute; inset: 0; display: flex; align-items: flex-start; justify-content: flex-end; padding: 58px 58px; }}
      .cta-card {{ max-width: 74%; padding: 18px 26px 20px; color: var(--ink); background: var(--accent); border-radius: 999px; box-shadow: 0 18px 48px rgba(0,0,0,.28); font-size: clamp(32px, 3.5vw, 48px); line-height: 1; font-weight: 900; letter-spacing: -.025em; text-align: center; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="fast-ad" data-start="0" data-width="{width}" data-height="{height}" data-duration="{duration:.3f}">
      <div class="plate"></div>
      <div id="foreground-wrap" class="foreground-wrap">
        <video id="foreground-video" class="clip fg-video" src="assets/a-roll.mp4" data-start="0" data-duration="{duration:.3f}" data-track-index="0" muted playsinline></video>
      </div>
      <audio id="dialogue-audio" src="assets/a-roll.mp4" data-start="0" data-duration="{duration:.3f}" data-track-index="10" data-volume="1"></audio>
      <div id="shade" class="shade" data-layout-ignore></div>
      <div id="top-rule" class="top-rule" data-layout-ignore></div>
      <section id="hook" class="clip" data-start="0" data-duration="{hook_duration:.3f}" data-track-index="100">
        <div class="hook-wrap"><div id="hook-card" class="hook-card"><span class="hook-text">{html.escape(hook)}</span></div></div>
      </section>
{caption_markup}
      <section id="cta" class="clip" data-start="{cta_start:.3f}" data-duration="{cta_duration:.3f}" data-track-index="101">
        <div class="cta-wrap"><div id="cta-card" class="cta-card">{html.escape(cta)}</div></div>
      </section>
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      const captions = {caption_js};
      tl.fromTo("#hook-card", {{ y: -34, opacity: 0, scale: .96 }}, {{ y: 0, opacity: 1, scale: 1, duration: .42, ease: "power3.out" }}, .08);
      if ({hook_duration:.3f} > .7) tl.to("#hook-card", {{ y: -18, opacity: 0, duration: .22, ease: "power2.in" }}, Math.max(.5, {hook_duration:.3f} - .24));
      captions.forEach((caption) => {{
        const card = `#${{caption.id}} .caption-card`;
        tl.fromTo(card, {{ y: 34, opacity: 0, scale: .97 }}, {{ y: 0, opacity: 1, scale: 1, duration: Math.min(.22, caption.duration * .32), ease: "power3.out" }}, caption.start + .01);
        if (caption.duration > .38) tl.to(card, {{ y: -8, opacity: 0, duration: .14, ease: "power2.in" }}, caption.start + caption.duration - .15);
      }});
      tl.fromTo("#cta-card", {{ y: -18, opacity: 0 }}, {{ y: 0, opacity: 1, duration: .30, ease: "power3.out" }}, {cta_start + 0.04:.3f});
      tl.fromTo("#foreground-wrap", {{ scale: 1.008 }}, {{ scale: 1.028, duration: {duration:.3f}, ease: "none" }}, 0);
      tl.fromTo("#shade", {{ opacity: .72 }}, {{ opacity: .96, duration: {max(0.5, duration / 2):.3f}, yoyo: true, repeat: 1, ease: "sine.inOut" }}, 0);
      tl.fromTo("#top-rule", {{ scaleX: .15, transformOrigin: "left center" }}, {{ scaleX: 1, duration: .5, ease: "power3.out" }}, .05);
      window.__timelines["fast-ad"] = tl;
    </script>
  </body>
</html>
'''


def prepare_fast_composition(
    root: Path,
    job_dir: Path,
    variant_id: str,
    input_path: Path,
    *,
    hook: str | None = None,
    cta: str | None = None,
    ratio: str = "4:5",
    accent: str = "#ff6a3d",
) -> dict[str, Any]:
    root = root.resolve()
    job_dir = job_dir.expanduser().resolve()
    input_path = input_path.expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(input_path)
    if ratio not in RATIO_DIMENSIONS:
        raise ValueError(f"unsupported ratio: {ratio}")
    if not accent.startswith("#") or len(accent) not in {4, 7}:
        raise ValueError("accent must be a short or full hex color")

    job = load_job(job_dir)
    plan_path = job_dir / "plans" / "edit-plan.normalized.json"
    plan = read_json(plan_path)
    variant = _variant(plan, variant_id)
    duration = float(variant["durationSeconds"])
    segments = variant["segments"]
    brief = read_json(job_dir / "brief.json")

    transcript_path = job_dir / "transcript" / "transcript.json"
    transcript = read_json_value(transcript_path) if transcript_path.is_file() else []
    words = _conform_words(transcript, segments) if isinstance(transcript, list) else []
    captions = _caption_groups(words, duration) if words else _fallback_captions(segments)
    if not captions:
        raise RuntimeError("no captions could be derived from the transcript or edit plan")

    chosen_hook = (hook or str(segments[0].get("text", "")).strip()).strip()
    chosen_cta = (cta or str(brief.get("desiredAction") or "Learn more")).strip()
    if not chosen_hook or not chosen_cta:
        raise ValueError("hook and CTA must be nonempty")
    _validate_overlay_copy(brief, segments, chosen_hook, chosen_cta)

    project = job_dir / "hyperframes" / f"{variant_id}-{ratio.replace(':', 'x')}"
    assets = project / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copy2(input_path, assets / "a-roll.mp4")
    gsap_source = root / "node_modules" / "gsap" / "dist" / "gsap.min.js"
    if not gsap_source.is_file():
        raise RuntimeError("local GSAP is unavailable; run setup")
    shutil.copy2(gsap_source, assets / "gsap.min.js")

    width, height = RATIO_DIMENSIONS[ratio]
    (project / "index.html").write_text(
        _build_html(
            width=width,
            height=height,
            duration=duration,
            hook=chosen_hook,
            cta=chosen_cta,
            accent=accent,
            captions=captions,
        ),
        encoding="utf-8",
    )
    write_json_atomic(
        project / "index.motion.json",
        {
            "duration": duration,
            "assertions": [
                {"kind": "appearsBy", "selector": "#hook-card", "bySec": min(0.55, duration)},
                {"kind": "before", "a": "#hook-card", "b": "#cta-card"},
                *[
                    {"kind": "staysInFrame", "selector": f"#{caption['id']} .caption-card"}
                    for caption in captions
                ],
                {"kind": "keepsMoving", "withinSelector": "#root", "maxStaticSec": 2.0},
            ],
        },
    )
    manifest = {
        "schemaVersion": 1,
        "skill": "talking-head-recut",
        "variant": variant_id,
        "ratio": ratio,
        "dimensions": {"width": width, "height": height},
        "durationSeconds": duration,
        "hook": chosen_hook,
        "cta": chosen_cta,
        "captionCount": len(captions),
        "sourceArtifact": str(input_path),
        "sourceSha256": sha256_file(input_path),
        "humanReview": "pending",
    }
    write_json_atomic(project / "composition.json", manifest)
    srt_path = job_dir / "transcript" / f"{variant_id}.srt"
    _write_srt(srt_path, captions)
    record_artifact(
        job_dir,
        f"hyperframes-project-{variant_id}-{ratio}",
        project / "composition.json",
        producer="ad-machine-hyperframes-fast",
        input_hashes={"input": manifest["sourceSha256"], "plan": sha256_file(plan_path)},
    )
    record_artifact(
        job_dir,
        f"captions-{variant_id}",
        srt_path,
        producer="ad-machine-caption-conform",
        input_hashes={"plan": sha256_file(plan_path), "transcript": sha256_file(transcript_path) if transcript_path.is_file() else "plan-fallback"},
    )
    return {"success": True, "project": str(project), "captions": str(srt_path), "manifest": manifest}


def check_composition(root: Path, project: Path) -> dict[str, Any]:
    root = root.resolve()
    project = project.expanduser().resolve()
    hyperframes = root / "node_modules" / ".bin" / "hyperframes"
    if not hyperframes.is_file():
        raise RuntimeError("local HyperFrames is unavailable; run setup")
    result = run([hyperframes, "check", project, "--json", "--snapshots", "--strict"], cwd=root, check=False, timeout=600)
    payload_text = result.stdout.strip()
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        payload = {"ok": False, "stdout": payload_text, "stderr": result.stderr.strip()}
    write_json_atomic(project / "check.json", payload)
    if result.returncode != 0 or not payload.get("ok", False):
        raise RuntimeError(f"HyperFrames check failed; inspect {project / 'check.json'}")
    return payload


def render_preview(root: Path, job_dir: Path, variant_id: str, project: Path, output: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    job_dir = job_dir.expanduser().resolve()
    project = project.expanduser().resolve()
    hyperframes = root / "node_modules" / ".bin" / "hyperframes"
    if not hyperframes.is_file():
        raise RuntimeError("local HyperFrames is unavailable; run setup")
    manifest = read_json(project / "composition.json")
    output = (output or (job_dir / "previews" / f"{variant_id}-{manifest['ratio'].replace(':', 'x')}-designed.mp4")).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    run(
        [hyperframes, "render", project, "--quality", "draft", "--strict", "--strict-variables", "--output", output],
        cwd=root,
        timeout=3600,
    )
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError("HyperFrames did not create a preview")
    actual_duration = duration_seconds(output)
    expected_duration = float(manifest["durationSeconds"])
    if abs(actual_duration - expected_duration) > 0.35:
        raise RuntimeError(f"designed preview duration mismatch: expected {expected_duration}, got {actual_duration}")
    record_artifact(
        job_dir,
        f"designed-preview-{variant_id}-{manifest['ratio']}",
        output,
        producer="hyperframes-draft-preview",
        input_hashes={"composition": sha256_file(project / "index.html"), "input": manifest["sourceSha256"]},
    )
    set_stage(job_dir, "designed", f"Rendered HyperFrames review preview for {variant_id} {manifest['ratio']}")
    return {
        "success": True,
        "preview": str(output),
        "expectedDurationSeconds": expected_duration,
        "actualDurationSeconds": actual_duration,
        "humanReview": "pending",
    }
