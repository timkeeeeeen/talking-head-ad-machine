from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .jobs import artifact_path, load_job, record_artifact
from .util import read_json, read_json_value


def _read_optional_json(path: Path) -> Any:
    return read_json_value(path) if path.is_file() else None


def _media_uri(path: Path | None) -> str:
    return path.resolve().as_uri() if path and path.is_file() else ""


def _artifact_file(job_dir: Path, job: dict[str, Any], *names: str) -> Path | None:
    for name in names:
        artifact = job.get("artifacts", {}).get(name)
        if artifact:
            path = artifact_path(job_dir, artifact)
            if path.is_file():
                return path
    return None


def generate_review(job_dir: Path) -> Path:
    job_dir = job_dir.expanduser().resolve()
    job = load_job(job_dir)
    source = Path(job["source"]["path"])
    preview = _artifact_file(job_dir, job, "preview", "clean-cut", "final")
    plan = _read_optional_json(job_dir / "plans" / "edit-plan.normalized.json")
    qa = _read_optional_json(job_dir / "qa" / "report.json")
    transcript = _read_optional_json(job_dir / "transcript" / "transcript.json")

    plan_pretty = html.escape(json.dumps(plan or {}, indent=2))
    qa_pretty = html.escape(json.dumps(qa or {}, indent=2))
    transcript_pretty = html.escape(json.dumps(transcript or {}, indent=2))
    source_uri = html.escape(_media_uri(source), quote=True)
    preview_uri = html.escape(_media_uri(preview), quote=True)
    stage = html.escape(str(job.get("stage", "unknown")))
    mode = html.escape(str(job.get("mode", "unknown")))
    approval = html.escape(str(job.get("approval", {}).get("status", "pending")))

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ad review — {html.escape(job['jobId'])}</title>
  <style>
    :root {{ color-scheme: dark; --ink:#f7f3ea; --muted:#aca89f; --panel:#171714; --line:#35352f; --accent:#b8ff5a; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:#0c0c0a; color:var(--ink); font:16px/1.55 ui-sans-serif,system-ui,sans-serif; }}
    main {{ width:min(1180px,calc(100% - 32px)); margin:0 auto; padding:40px 0 72px; }}
    header {{ display:flex; gap:24px; align-items:end; justify-content:space-between; flex-wrap:wrap; }}
    h1 {{ margin:0; font-size:clamp(2rem,5vw,4.8rem); line-height:.95; letter-spacing:-.05em; }}
    .status {{ border:1px solid var(--line); border-radius:999px; padding:8px 14px; color:var(--accent); }}
    .grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; margin-top:30px; }}
    .card {{ background:var(--panel); border:1px solid var(--line); border-radius:18px; padding:18px; overflow:hidden; }}
    video {{ width:100%; max-height:640px; border-radius:12px; background:#000; }}
    h2 {{ margin:0 0 12px; font-size:1.1rem; }}
    pre {{ white-space:pre-wrap; word-break:break-word; color:#d5d0c6; font-size:.78rem; max-height:360px; overflow:auto; }}
    .prompts {{ margin-top:18px; display:grid; gap:10px; }}
    code {{ display:block; background:#050504; border:1px solid var(--line); border-radius:10px; padding:14px; color:var(--accent); }}
    .meta {{ color:var(--muted); }}
    @media (max-width:760px) {{ .grid {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
<main>
  <header>
    <div><p class="meta">Talking-Head Ad Machine · {mode} mode</p><h1>Review before delivery.</h1></div>
    <div class="status">Stage: {stage} · Approval: {approval}</div>
  </header>
  <section class="grid" aria-label="Source and edited preview">
    <article class="card"><h2>Camera original</h2><video controls preload="metadata" src="{source_uri}"></video></article>
    <article class="card"><h2>Edited preview</h2><video controls preload="metadata" src="{preview_uri}"></video></article>
  </section>
  <section class="grid">
    <article class="card"><h2>Edit plan</h2><pre>{plan_pretty}</pre></article>
    <article class="card"><h2>Quality report</h2><pre>{qa_pretty}</pre></article>
    <article class="card"><h2>Transcript</h2><pre>{transcript_pretty}</pre></article>
    <article class="card"><h2>Decision</h2><p class="meta">Approval is recorded by the agent; opening this page never publishes anything.</p>
      <div class="prompts"><code>Approve this preview and export the final files.</code><code>Revise this preview: [describe one evidence-based change].</code></div>
    </article>
  </section>
</main>
</body>
</html>
"""
    output = job_dir / "review" / "review.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    record_artifact(job_dir, "review", output, producer="ad-machine-review")
    return output
