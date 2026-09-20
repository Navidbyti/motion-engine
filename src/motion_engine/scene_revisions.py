"""Scoped, source-bound scene edits proposed by a producer or model.

This is a typed edit executor. Natural-language interpretation belongs to a
separate planner, which must show the proposed operations before applying them.
"""
from __future__ import annotations

import copy
import json
import math
import re
from pathlib import Path
from typing import Any

from .revisions import file_sha256, spec_sha256
from .preview_contract import PREVIEW_EASING
from .validation import validate


class SceneRevisionError(ValueError):
    pass


def revise_scene(spec: dict[str, Any], request: dict[str, Any], *,
                 request_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    request_file = Path(request_path).resolve()
    output_file = Path(output_path).resolve()
    try:
        request_uri = request_file.relative_to(output_file.parent).as_posix()
    except ValueError as exc:
        raise SceneRevisionError("revision request must be inside the new MotionSpec directory") from exc
    if not request_file.is_file() or request_file.suffix.lower() != ".json":
        raise SceneRevisionError("revision request must be an existing JSON file")
    try:
        stored_request = json.loads(request_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SceneRevisionError("revision request is not readable JSON") from exc
    if stored_request != request:
        raise SceneRevisionError("revision request does not match its source file")
    if request.get("baseSpecSha256") != spec_sha256(spec):
        raise SceneRevisionError("base MotionSpec hash mismatch; replan against the current revision")
    scene_id = request.get("sceneId")
    scene = next((item for item in spec["timeline"] if item["id"] == scene_id), None)
    if scene is None:
        raise SceneRevisionError(f"unknown scene {scene_id!r}")
    operations = request.get("operations")
    if not isinstance(operations, list) or not 1 <= len(operations) <= 20:
        raise SceneRevisionError("revision needs 1 to 20 typed operations")
    source_hash = file_sha256(request_file)
    source_id = "revision_" + source_hash[:16]
    if any(item["id"] == source_id for item in spec["sources"]):
        raise SceneRevisionError("revision request is already part of this MotionSpec")
    revised = copy.deepcopy(spec)
    target_scene = next(item for item in revised["timeline"] if item["id"] == scene_id)
    revised["sources"].append({"id": source_id, "uri": request_uri, "mediaType": "application/json",
                               "sha256": source_hash, "authority": ["user revision"]})
    elements = {item["id"]: item for item in target_scene["elements"]}
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict) or set(operation) - {"op", "elementId", "value"}:
            raise SceneRevisionError(f"operation {index} has unknown fields")
        element = elements.get(operation.get("elementId"))
        if element is None:
            raise SceneRevisionError(f"operation {index}: unknown element {operation.get('elementId')!r} in scene {scene_id}")
        ref = {"sourceId": source_id, "location": f"/operations/{index}/value",
               "method": "user revision request", "confidence": 1.0}
        action, value = operation.get("op"), operation.get("value")
        if action == "set_text":
            if element["kind"] != "text" or not isinstance(value, str) or not value.strip():
                raise SceneRevisionError(f"operation {index}: set_text needs a text element and nonblank string")
            previous = element["text"]["value"]
            element["text"]["value"] = value
            element["sourceRefs"] = [ref]
            for beat in target_scene["beats"]:
                if element["id"] in beat.get("elementIds", []):
                    for line in beat.get("onScreen", []):
                        if line["value"] == previous:
                            line["value"] = value
                    beat["sourceRefs"] = [ref]
        elif action == "set_color":
            if element["kind"] not in ("text", "shape", "chart.bar", "chart.line") or not isinstance(value, str):
                raise SceneRevisionError(f"operation {index}: set_color needs a colorable element and hex string")
            if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
                raise SceneRevisionError(f"operation {index}: color must be #RRGGBB")
            element["params"]["color"] = value
            element.setdefault("sourceRefs", []).append(ref)
        elif action in ("set_image_zoom", "set_visual_zoom"):
            allowed = ("image",) if action == "set_image_zoom" else ("image", "video")
            if element["kind"] not in allowed or not isinstance(value, list) or not 1 <= len(value) <= 20:
                raise SceneRevisionError(f"operation {index}: {action} needs a supported visual and 1 to 20 keyframes")
            for key in value:
                if not isinstance(key, dict) or set(key) - {"frame", "value", "easing"} or "frame" not in key or "value" not in key:
                    raise SceneRevisionError(f"operation {index}: invalid zoom keyframe")
                if (not isinstance(key["frame"], int) or isinstance(key["frame"], bool)
                    or not element["startFrame"] <= key["frame"] < element["endFrameExclusive"]
                    or not isinstance(key["value"], (int, float)) or isinstance(key["value"], bool)
                    or not math.isfinite(key["value"]) or not 1 <= key["value"] <= 3
                    or key.get("easing", "linear") not in PREVIEW_EASING):
                    raise SceneRevisionError(f"operation {index}: zoom frame, value, or easing is unsupported")
            if [key["frame"] for key in value] != sorted({key["frame"] for key in value}):
                raise SceneRevisionError(f"operation {index}: zoom keyframes must be unique and sorted")
            target_scene["animations"] = [a for a in target_scene["animations"]
                                          if not (a["targetId"] == element["id"] and a["property"] == "scale")]
            target_scene["animations"].append({"targetId": element["id"], "property": "scale", "keyframes": value})
            element.setdefault("sourceRefs", []).append(ref)
        else:
            raise SceneRevisionError(f"operation {index}: unsupported edit {action!r}")
    errors = validate(revised)
    if errors:
        raise SceneRevisionError("revised MotionSpec is invalid: " + "; ".join(errors))
    return revised
