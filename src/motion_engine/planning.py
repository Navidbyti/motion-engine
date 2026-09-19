"""Compile a validated MotionSpec into a frame plan and capability report."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BASELINE_KINDS = {
    "text", "shape", "image", "video", "audio", "chart.bar", "chart.line",
    "chart.scatter", "card", "counter", "table", "disclosure", "composition",
}


def default_capabilities() -> dict[str, dict[str, Any]]:
    """All output adapters are planned, not available, at milestone M1."""
    return {
        target: {"status": "planned", "supportedKinds": sorted(BASELINE_KINDS), "editableKinds": sorted(BASELINE_KINDS) if target.startswith("adobe.") else []}
        for target in ("video/mp4", "adobe.after_effects", "adobe.premiere", "adobe.photoshop", "adobe.illustrator")
    }


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
    for scene in spec["timeline"]:
        elements = []
        for element in scene["elements"]:
            requested_kinds.add(element["kind"])
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
        buildable = adapter["status"] == "available" and not unsupported and not editable_missing
        capabilities_report.append({
            "deliverableId": deliverable["id"], "target": target,
            "status": adapter["status"], "buildable": buildable,
            "unsupportedKinds": sorted(unsupported),
            "nonEditableKinds": sorted(editable_missing),
        })
        if unsupported or editable_missing:
            issues.append({"severity": "error" if deliverable["required"] and spec["policies"].get("unsupportedFeature", "error") == "error" else "warning", "code": "capability_gap", "message": f"{target}: unsupported {sorted(unsupported)}, non-editable {sorted(editable_missing)}"})
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
