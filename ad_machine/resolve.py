from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from xml.etree import ElementTree as ET

from .render import probe_media


def _seconds(value: float) -> str:
    fraction = Fraction(str(round(float(value), 6))).limit_denominator(1_000_000)
    return f"{fraction.numerator}/{fraction.denominator}s" if fraction.denominator != 1 else f"{fraction.numerator}s"


def make_fcpxml(plan: dict, variant_id: str, output: Path) -> dict:
    source = Path(plan["source"]["path"]).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"source is unavailable: {source}")
    variant = next((item for item in plan.get("variants", []) if item.get("id") == variant_id), None)
    if not variant:
        raise ValueError(f"variant not found: {variant_id}")
    if variant.get("allowSourceReuse"):
        raise ValueError("FCPXML generation refuses source-reuse plans")

    probe = probe_media(source)
    video = next((stream for stream in probe.get("streams", []) if stream.get("codec_type") == "video"), None)
    if not video:
        raise ValueError("source has no video stream")
    fps = Fraction(str(video.get("avg_frame_rate") or "0/1"))
    if fps <= 0:
        raise ValueError("could not determine a constant frame rate")
    width, height = int(video["width"]), int(video["height"])
    source_duration = float(probe.get("format", {}).get("duration") or 0)
    frame_duration = Fraction(1, 1) / fps
    output_duration = sum(float(item["sourceEnd"]) - float(item["sourceStart"]) for item in variant["segments"])

    root = ET.Element("fcpxml", version="1.10")
    resources = ET.SubElement(root, "resources")
    ET.SubElement(resources, "format", id="r1", name=f"FFVideoFormat{height}p", frameDuration=f"{frame_duration.numerator}/{frame_duration.denominator}s", width=str(width), height=str(height))
    ET.SubElement(resources, "asset", id="r2", name=source.name, start="0s", duration=_seconds(source_duration), hasVideo="1", hasAudio="1", format="r1", src=source.as_uri())
    library = ET.SubElement(root, "library")
    event = ET.SubElement(library, "event", name="Talking-Head Ad Machine")
    project = ET.SubElement(event, "project", name=variant.get("label") or variant["id"])
    sequence = ET.SubElement(project, "sequence", format="r1", duration=_seconds(output_duration), tcStart="0s", tcFormat="NDF", audioLayout="stereo", audioRate="48k")
    spine = ET.SubElement(sequence, "spine")
    offset = 0.0
    for index, segment in enumerate(variant["segments"], 1):
        clip_duration = float(segment["sourceEnd"]) - float(segment["sourceStart"])
        clip = ET.SubElement(spine, "asset-clip", name=f"{index:02d}-{segment.get('beat', 'clip')}", ref="r2", offset=_seconds(offset), start=_seconds(segment["sourceStart"]), duration=_seconds(clip_duration))
        ET.SubElement(clip, "note").text = segment.get("reason", "")
        offset += clip_duration

    ET.indent(root, space="  ")
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    body = ET.tostring(root, encoding="utf-8")
    output.write_bytes(b'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n' + body + b"\n")
    return {"success": True, "output": str(output), "verification": "best-effort-until-resolve-import"}

