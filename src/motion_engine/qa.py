"""Initial source, policy, and preview integrity gates."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .revisions import RevisionError, freeze_revision, spec_sha256
from .runs import RunError, verify_render_run


def _issue(code: str, severity: str, message: str, target_id: str | None = None) -> dict[str, str]:
    item = {"code": code, "severity": severity, "message": message}
    if target_id:
        item["targetId"] = target_id
    return item


def _safe_area_issues(spec: dict[str, Any], severity: str) -> list[dict[str, str]]:
    canvas = spec["canvas"]
    inset = canvas.get("safeArea", {"top": 0, "right": 0, "bottom": 0, "left": 0})
    left, top = inset["left"], inset["top"]
    right, bottom = canvas["width"] - inset["right"], canvas["height"] - inset["bottom"]
    items = [element for scene in spec["timeline"] for element in scene["elements"] if element["kind"] == "text"]
    items += spec["policies"]["disclosures"]
    issues = []
    for item in items:
        bounds = item.get("bounds")
        if not bounds:
            issues.append(_issue("text_bounds_missing", severity, "Text has no bounds for safe-area review", item["id"]))
        elif (bounds["x"] < left or bounds["y"] < top or
              bounds["x"] + bounds["width"] > right or bounds["y"] + bounds["height"] > bottom):
            issues.append(_issue("text_outside_safe_area", severity, "Text bounds extend outside the canvas safe area", item["id"]))
    return issues


def qa_report(spec: dict[str, Any], spec_dir: str | Path, render_dir: str | Path | None = None) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    revision = None
    try:
        revision = freeze_revision(spec, spec_dir)
    except (OSError, RevisionError) as exc:
        issues.append(_issue("input_integrity", "error", str(exc)))

    assets = {asset["id"]: asset for asset in spec["assets"]}
    for scene in spec["timeline"]:
        for element in scene["elements"]:
            asset_id = element.get("assetId")
            if asset_id and assets.get(asset_id, {}).get("status") != "available":
                issues.append(_issue("asset_unavailable", "error", f"Referenced asset {asset_id!r} is unavailable", element["id"]))
    for dataset in spec["datasets"]:
        if not dataset["sourceRefs"]:
            issues.append(_issue("data_provenance_missing", "warning", "Dataset has no source references", dataset["id"]))

    for rule in spec["policies"]["qa"]:
        name, severity = rule["rule"], rule["severity"]
        if name == "text.within_safe_area":
            issues.extend(_safe_area_issues(spec, severity))
        elif name == "disclosure.full_duration":
            for disclosure in spec["policies"]["disclosures"]:
                if disclosure["startFrame"] != 0 or disclosure["endFrameExclusive"] != spec["canvas"]["durationFrames"]:
                    issues.append(_issue("disclosure_timing", severity, "Disclosure must span the full project", disclosure["id"]))
        elif name == "text.visual_review":
            issues.append(_issue("visual_review_required", "error" if severity == "error" else "warning", "Typography and language need human review", rule["id"]))
        else:
            issues.append(_issue("qa_rule_unimplemented", "error" if severity == "error" else "warning", f"QA rule {name!r} is not implemented", rule["id"]))

    if render_dir is not None:
        try:
            render = verify_render_run(render_dir)
            if render["specSha256"] != spec_sha256(spec) or not revision or render["revisionSha256"] != revision["revisionSha256"]:
                issues.append(_issue("render_revision_mismatch", "error", "Render does not match the current MotionSpec and inputs"))
            if render["frameCount"] != spec["canvas"]["durationFrames"]:
                issues.append(_issue("render_frame_count", "error", "Render frame count differs from MotionSpec"))
            for render_issue in render.get("issues", []):
                issues.append(_issue(render_issue["code"], "warning", render_issue["message"]))
        except (OSError, RunError, KeyError, TypeError) as exc:
            issues.append(_issue("render_integrity", "error", str(exc)))

    status = "failed" if any(i["severity"] == "error" for i in issues) else "needs_review" if any(i["severity"] == "warning" for i in issues) else "passed"
    return {
        "projectId": spec["project"]["id"], "specSha256": spec_sha256(spec),
        "revisionSha256": revision["revisionSha256"] if revision else None,
        "scope": "spec_and_render" if render_dir is not None else "spec_only",
        "status": status, "issues": issues,
    }
