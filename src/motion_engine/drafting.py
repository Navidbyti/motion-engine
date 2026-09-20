"""Conservative, literal text-to-MotionSpec authoring.

This is a useful prompt-to-preview subset, not a semantic interpretation of a
brief. Each nonblank source line becomes one cited scene without paraphrasing.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .ingest import ingest
from .validation import validate


def draft_text(
    source: str | Path,
    output: str | Path,
    *,
    project_id: str,
    locale: str,
    direction: str = "ltr",
    width: int = 1080,
    height: int = 1920,
    frame_rate: int = 30,
    frames_per_line: int = 60,
    font_family: str = "DejaVu Sans",
    max_lines: int = 40,
) -> dict[str, Any]:
    source_path = Path(source).resolve()
    output_path = Path(output).resolve()
    if source_path.suffix.lower() != ".txt":
        raise ValueError("draft-text currently accepts plain UTF-8 .txt only")
    try:
        source_uri = source_path.relative_to(output_path.parent).as_posix()
    except ValueError as exc:
        raise ValueError("source must be inside the MotionSpec output directory for portable links") from exc
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", project_id):
        raise ValueError("project id must start with a letter and contain only letters, digits, _, ., or -")
    if len(locale) < 2 or direction not in ("ltr", "rtl"):
        raise ValueError("provide a locale and direction ltr or rtl")
    if width < 320 or height < 320 or frame_rate not in (24, 25, 30, 50, 60):
        raise ValueError("canvas must be at least 320x320 and frame rate must be 24, 25, 30, 50, or 60")
    if not 2 <= frames_per_line <= 1800 or not 1 <= max_lines <= 200:
        raise ValueError("frames-per-line must be 2..1800 and max-lines must be 1..200")
    if not font_family.strip():
        raise ValueError("font family must not be blank")
    evidence = ingest(source_path, limit=max_lines + 1)
    if evidence["issues"]:
        raise ValueError("source has extraction issues; review them before drafting")
    lines = [record for record in evidence["evidence"] if record["kind"] == "text"]
    if not lines:
        raise ValueError("source has no nonblank text lines")
    if len(lines) > max_lines:
        raise ValueError(f"source has more than {max_lines} lines; raise --max-lines explicitly")
    if any("\x00" in record["value"] or not record["value"].strip() for record in lines):
        raise ValueError("source contains an invalid text line")

    inset = max(24, round(min(width, height) * 0.07))
    usable_width = width - inset * 2
    usable_height = height - inset * 2
    if usable_width <= 0 or usable_height <= 0:
        raise ValueError("canvas is too small for the safe area")
    text_height = max(120, round(usable_height * 0.42))
    text_height = min(text_height, usable_height)
    text_y = inset + (usable_height - text_height) // 2
    font_size = max(20, round(min(width, height) * 0.055))
    timeline = []
    source_id = evidence["source"]["id"]
    for index, record in enumerate(lines, 1):
        start = (index - 1) * frames_per_line
        end = index * frames_per_line
        scene_id = f"scene_{index}"
        element_id = f"text_{index}"
        ref = {"sourceId": source_id, "location": record["location"],
               "method": record["method"], "confidence": record["confidence"]}
        value = record["value"]
        timeline.append({
            "id": scene_id, "startFrame": start, "endFrameExclusive": end,
            "transitionIn": "start" if index == 1 else "cut",
            "elements": [{
                "id": element_id, "kind": "text", "startFrame": start,
                "endFrameExclusive": end,
                "bounds": {"x": inset, "y": text_y, "width": usable_width, "height": text_height},
                "text": {"value": value, "locale": locale, "direction": direction,
                         "fontFamily": font_family, "fontWeight": 700, "align": "center"},
                "params": {"color": "#FFFFFF", "fontSize": font_size, "wrap": True},
                "sourceRefs": [ref],
            }],
            "beats": [{"id": f"beat_{index}", "startFrame": start,
                       "endFrameExclusive": end, "onScreen": [{"value": value, "locale": locale,
                                                                  "direction": direction}],
                       "elementIds": [element_id], "sourceRefs": [ref]}],
            "animations": [{"targetId": element_id, "property": "opacity",
                            "keyframes": [{"frame": start, "value": 0},
                                          {"frame": start + min(8, frames_per_line - 1),
                                           "value": 1, "easing": "ease_out"}]}],
            "sourceRefs": [ref],
        })
    spec = {
        "schemaVersion": "1.0.0",
        "project": {"id": project_id, "title": lines[0]["value"], "locale": locale,
                    "direction": direction,
                    "description": "Literal line-by-line draft; review timing, design, and source meaning."},
        "canvas": {"width": width, "height": height,
                   "frameRate": {"numerator": frame_rate, "denominator": 1},
                   "durationFrames": len(lines) * frames_per_line,
                   "colorSpace": "Rec.709", "background": "#101820",
                   "safeArea": {"top": inset, "right": inset,
                                "bottom": inset, "left": inset}},
        "sources": [{**evidence["source"], "uri": source_uri, "authority": ["text"]}],
        "assets": [], "datasets": [], "timeline": timeline,
        "deliverables": [{"id": "preview", "target": "video/mp4", "profile": "preview",
                          "required": True, "editable": False}],
        "policies": {"qa": [{"id": "text_safe_area", "rule": "text.within_safe_area",
                             "severity": "error"}], "disclosures": [],
                     "approvals": ["visual and source review"], "unsupportedFeature": "error"},
    }
    errors = validate(spec)
    if errors:
        raise ValueError("draft failed MotionSpec validation: " + "; ".join(errors))
    return spec
