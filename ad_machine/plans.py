from __future__ import annotations

from copy import deepcopy
from typing import Any


BEATS = {"hook", "problem", "mechanism", "proof", "objection", "cta", "transition", "context"}
RATIOS = {"9:16", "4:5", "1:1", "16:9"}


def validate_and_normalize(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    normalized = deepcopy(data)
    errors: list[str] = []
    if normalized.get("schemaVersion") != 1:
        errors.append("schemaVersion must equal 1")
    source = normalized.get("source") or {}
    duration = source.get("durationSeconds")
    if not isinstance(duration, (int, float)) or duration <= 0:
        errors.append("source.durationSeconds must be positive")
        duration = 0
    if not isinstance(source.get("path"), str) or not source.get("path"):
        errors.append("source.path is required")

    variants = normalized.get("variants")
    if not isinstance(variants, list) or not 1 <= len(variants) <= 10:
        errors.append("variants must contain 1 to 10 entries")
        variants = []
    seen_ids: set[str] = set()
    for variant_index, variant in enumerate(variants):
        prefix = f"variants[{variant_index}]"
        variant_id = variant.get("id")
        if not isinstance(variant_id, str) or not variant_id:
            errors.append(f"{prefix}.id is required")
        elif variant_id in seen_ids:
            errors.append(f"{prefix}.id duplicates {variant_id!r}")
        else:
            seen_ids.add(variant_id)
        ratios = variant.get("targetRatios", ["4:5"])
        if not isinstance(ratios, list) or not ratios or any(ratio not in RATIOS for ratio in ratios):
            errors.append(f"{prefix}.targetRatios contains an unsupported ratio")
        segments = variant.get("segments")
        if not isinstance(segments, list) or not segments:
            errors.append(f"{prefix}.segments must be nonempty")
            continue
        output_cursor = 0.0
        ranges: list[tuple[float, float, int]] = []
        for segment_index, segment in enumerate(segments):
            segment_prefix = f"{prefix}.segments[{segment_index}]"
            start, end = segment.get("sourceStart"), segment.get("sourceEnd")
            if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                errors.append(f"{segment_prefix} sourceStart/sourceEnd must be numbers")
                continue
            start, end = float(start), float(end)
            if start < 0 or end <= start or end > float(duration) + 0.05:
                errors.append(f"{segment_prefix} has invalid source range {start}..{end}")
                continue
            for prior_start, prior_end, prior_index in ranges:
                if not variant.get("allowSourceReuse") and max(start, prior_start) < min(end, prior_end) - 0.001:
                    errors.append(f"{segment_prefix} overlaps segment {prior_index}; source reuse must be explicit")
            ranges.append((start, end, segment_index))
            if not isinstance(segment.get("text"), str) or not segment.get("text", "").strip():
                errors.append(f"{segment_prefix}.text is required")
            if not isinstance(segment.get("reason"), str) or not segment.get("reason", "").strip():
                errors.append(f"{segment_prefix}.reason is required")
            if segment.get("beat") not in BEATS:
                errors.append(f"{segment_prefix}.beat must be one of {sorted(BEATS)}")
            confidence = segment.get("confidence")
            if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                errors.append(f"{segment_prefix}.confidence must be between 0 and 1")
            segment["sourceStart"] = round(start, 3)
            segment["sourceEnd"] = round(end, 3)
            segment["outputStart"] = round(output_cursor, 3)
            output_cursor += end - start
            segment["outputEnd"] = round(output_cursor, 3)
        variant["durationSeconds"] = round(output_cursor, 3)
        if output_cursor < 3 or output_cursor > 180:
            errors.append(f"{prefix} duration {output_cursor:.3f}s is outside 3..180s")
    return normalized, errors

