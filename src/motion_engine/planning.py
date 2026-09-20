"""Compile a validated MotionSpec into a frame plan and capability report."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .preview_contract import PREVIEW_ANIMATIONS_BY_KIND, PREVIEW_EASING, PREVIEW_KINDS, PREVIEW_PARAMS


BASELINE_KINDS = {
    "text", "shape", "image", "video", "audio", "chart.bar", "chart.line",
    "chart.scatter", "card", "counter", "table", "disclosure", "composition",
}


def default_capabilities() -> dict[str, dict[str, Any]]:
    """The preview MP4 adapter is available; native Adobe adapters are planned."""
    registry = {
        target: {"status": "planned", "supportedKinds": sorted(BASELINE_KINDS), "editableKinds": sorted(BASELINE_KINDS) if target.startswith("adobe.") else []}
        for target in ("adobe.after_effects", "adobe.premiere", "adobe.photoshop", "adobe.illustrator")
    }
    registry["video/mp4"] = {"status": "available", "supportedKinds": sorted(PREVIEW_KINDS), "editableKinds": []}
    return registry


def load_capabilities(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    registry = default_capabilities()
    if path is None:
        return registry
    with Path(path).open("r", encoding="utf-8") as stream:
        manifest = json.load(stream)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("targets"), list):
        raise ValueError("capability manifest must be an object with a targets array")
    for item in manifest["targets"]:
        if not isinstance(item, dict) or not isinstance(item.get("target"), str):
            raise ValueError("each capability entry needs a target string")
        if item.get("status") not in ("planned", "available"):
            raise ValueError(f"{item['target']}: status must be planned or available")
        if not isinstance(item.get("supportedKinds"), list) or not isinstance(item.get("editableKinds", []), list):
            raise ValueError(f"{item['target']}: kind lists are required")
        registry[item["target"]] = {
            "status": item["status"],
            "supportedKinds": item["supportedKinds"],
            "editableKinds": item.get("editableKinds", []),
            "version": item.get("version"),
        }
    return registry


def plan(spec: dict[str, Any], capabilities: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    registry = capabilities if capabilities is not None else default_capabilities()
    scenes = []
    requested_kinds: set[str] = set()
    assets = {asset["id"]: asset for asset in spec["assets"]}
    voice_requested = False
    preview_feature_gaps: set[str] = set()
    for scene in spec["timeline"]:
        scene_index = len(scenes)
        if scene.get("transitionIn") not in (None, "start" if scene_index == 0 else "cut"):
            preview_feature_gaps.add(f"transition:{scene['transitionIn']}")
        voice_requested = voice_requested or any(beat.get("voice", {}).get("value", "").strip() for beat in scene["beats"])
        elements = []
        element_kinds = {element["id"]: element["kind"] for element in scene["elements"]}
        for element in scene["elements"]:
            requested_kinds.add(element["kind"])
            if element["kind"] in PREVIEW_KINDS:
                extra = set(element["params"]) - PREVIEW_PARAMS[element["kind"]]
                preview_feature_gaps.update(f"parameter:{p}" for p in extra)
                if element["kind"] == "shape" and element["params"].get("shape", "rect") != "rect":
                    preview_feature_gaps.add("shape:non_rectangle")
                if element["kind"] == "image":
                    asset = assets.get(element.get("assetId"))
                    if not asset or asset.get("status") != "available" or not asset.get("uri") or not asset.get("sha256"):
                        preview_feature_gaps.add(f"image_asset:{element['id']}")
                    if element["params"].get("fit", "contain") not in ("contain", "cover", "stretch"):
                        preview_feature_gaps.add(f"image_fit:{element['id']}")
                if element["kind"] == "video":
                    asset = assets.get(element.get("assetId"))
                    if (not asset or asset.get("kind") != "video.frames" or asset.get("status") != "available"
                        or not asset.get("uri") or not asset.get("sha256")
                        or not str(asset.get("uri", "")).lower().endswith(".zip")):
                        preview_feature_gaps.add(f"video_asset:{element['id']}")
                    if element["params"].get("fit", "contain") not in ("contain", "cover", "stretch"):
                        preview_feature_gaps.add(f"video_fit:{element['id']}")
                    offset = element["params"].get("sourceStartFrame", 0)
                    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
                        preview_feature_gaps.add(f"video_source_frame:{element['id']}")
                if element["kind"] == "audio":
                    asset = assets.get(element.get("assetId"))
                    if not asset or asset.get("status") != "available" or not asset.get("uri") or not asset.get("sha256"):
                        preview_feature_gaps.add(f"audio_asset:{element['id']}")
                    elif not str(asset["uri"]).lower().endswith(".wav"):
                        preview_feature_gaps.add(f"audio_format:{element['id']}")
            elements.append({
                "id": element["id"], "kind": element["kind"],
                "startFrame": element["startFrame"],
                "endFrameExclusive": element["endFrameExclusive"],
                "bounds": element.get("bounds"),
                "dataBinding": element.get("dataBinding"),
                "assetId": element.get("assetId"),
                "sourceRefs": element.get("sourceRefs", []),
            })
        scenes.append({
            "id": scene["id"], "startFrame": scene["startFrame"],
            "endFrameExclusive": scene["endFrameExclusive"],
            "transitionIn": scene.get("transitionIn"),
            "beats": [{"id": beat["id"], "startFrame": beat["startFrame"], "endFrameExclusive": beat["endFrameExclusive"], "elementIds": beat.get("elementIds", []), "sourceRefs": beat.get("sourceRefs", [])} for beat in scene["beats"]],
            "elements": elements,
            "animations": scene["animations"],
        })
        for animation in scene["animations"]:
            if animation["property"] not in PREVIEW_ANIMATIONS_BY_KIND.get(element_kinds.get(animation["targetId"]), set()):
                preview_feature_gaps.add(f"animation:{animation['property']}:{animation['targetId']}")
            for keyframe in animation["keyframes"]:
                if keyframe.get("easing", "linear") not in PREVIEW_EASING:
                    preview_feature_gaps.add(f"easing:{keyframe['easing']}")
                if animation["property"] == "scale" and (
                    not isinstance(keyframe["value"], (int, float)) or isinstance(keyframe["value"], bool)
                    or not math.isfinite(keyframe["value"]) or not 1 <= keyframe["value"] <= 3
                ):
                    preview_feature_gaps.add(f"animation_value:scale:{animation['targetId']}")
                if animation["property"] in ("x", "y"):
                    limit = spec["canvas"]["width" if animation["property"] == "x" else "height"]
                    if (not isinstance(keyframe["value"], (int, float)) or isinstance(keyframe["value"], bool)
                        or not math.isfinite(keyframe["value"]) or not -limit <= keyframe["value"] <= limit):
                        preview_feature_gaps.add(f"animation_value:{animation['property']}:{animation['targetId']}")
    capabilities_report = []
    issues = []
    for deliverable in spec["deliverables"]:
        target = deliverable["target"]
        adapter = registry.get(target)
        if adapter is None:
            capabilities_report.append({"deliverableId": deliverable["id"], "target": target, "status": "unknown", "buildable": False, "unsupportedKinds": sorted(requested_kinds)})
            issues.append({"severity": "error" if deliverable["required"] else "warning", "code": "adapter_unknown", "message": f"No adapter registered for {target}"})
            continue
        supported = set(adapter["supportedKinds"])
        unsupported = requested_kinds - supported
        editable_missing = requested_kinds - set(adapter["editableKinds"]) if deliverable["editable"] else set()
        unsupported_features = sorted(preview_feature_gaps) if target == "video/mp4" else []
        if voice_requested and target == "video/mp4":
            unsupported_features.append("voice_audio")
        buildable = adapter["status"] == "available" and not unsupported and not editable_missing and not unsupported_features
        capabilities_report.append({
            "deliverableId": deliverable["id"], "target": target,
            "status": adapter["status"], "buildable": buildable,
            "unsupportedKinds": sorted(unsupported),
            "nonEditableKinds": sorted(editable_missing),
            "unsupportedFeatures": unsupported_features,
        })
        if unsupported or editable_missing or unsupported_features:
            issues.append({"severity": "error" if deliverable["required"] and spec["policies"].get("unsupportedFeature", "error") == "error" else "warning", "code": "capability_gap", "message": f"{target}: unsupported {sorted(unsupported)}, non-editable {sorted(editable_missing)}, unavailable features {unsupported_features}"})
        elif adapter["status"] != "available":
            issues.append({"severity": "info", "code": "adapter_planned", "message": f"{target}: adapter is planned and cannot build output yet"})
    return {
        "projectId": spec["project"]["id"],
        "schemaVersion": spec["schemaVersion"],
        "canvas": spec["canvas"],
        "sources": [{"id": s["id"], "sha256": s.get("sha256")} for s in spec["sources"]],
        "scenes": scenes,
        "requestedKinds": sorted(requested_kinds),
        "capabilities": capabilities_report,
        "issues": issues,
        "buildable": all(c["buildable"] for c in capabilities_report if next(d for d in spec["deliverables"] if d["id"] == c["deliverableId"])["required"]),
    }
