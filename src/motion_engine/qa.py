"""Initial source, policy, and preview integrity gates."""
from __future__ import annotations

from array import array
from pathlib import Path
import sys
from typing import Any
import wave

from .revisions import RevisionError, freeze_revision, resolve_local_file, spec_sha256
from .runs import RunError, verify_render_run
from .data_qa import check_chart_data
from .claims import verify_claims


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


def _audio_mix_issues(spec: dict[str, Any], render: dict[str, Any], render_dir: str | Path) -> list[dict[str, str]]:
    has_audio = any(element["kind"] == "audio" for scene in spec["timeline"] for element in scene["elements"])
    output = next((item for item in render["outputs"] if item["kind"] == "audio/wav"), None)
    if has_audio and output is None:
        return [_issue("audio_mix_missing", "error", "Render has audio elements but no WAV mix")]
    if output is None:
        return []
    issues = []
    rate = spec["canvas"]["frameRate"]
    numerator = spec["canvas"]["durationFrames"] * 48_000 * rate["denominator"]
    expected_samples = (2 * numerator + rate["numerator"]) // (2 * rate["numerator"])
    try:
        with wave.open(str(Path(render_dir).resolve() / output["path"]), "rb") as stream:
            if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getnframes()) != (1, 2, 48_000, expected_samples):
                return [_issue("audio_mix_format", "error", "WAV mix format or duration differs from the project")]
            peak = 0
            while data := stream.readframes(8192):
                samples = array("h")
                samples.frombytes(data)
                if sys.byteorder != "little":
                    samples.byteswap()
                peak = max(peak, max((abs(value) for value in samples), default=0))
    except (OSError, EOFError, wave.Error, ValueError) as exc:
        return [_issue("audio_mix_invalid", "error", f"WAV mix cannot be decoded: {exc}")]
    if peak < 64:
        issues.append(_issue("audio_mix_silent", "warning", "WAV mix is silent or nearly silent; review the audio"))
    if peak >= 32_112:
        issues.append(_issue("audio_mix_near_clipping", "warning", "WAV mix peak is within 0.2 dB of clipping"))
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
        elif name == "chart.data_exact":
            if revision:
                issues.extend(check_chart_data(spec, spec_dir, severity))
            else:
                issues.append(_issue("data_source_unverifiable", severity, "Source revision did not verify", rule["id"]))
        elif name == "claim.semantic_review":
            ledger_source = next((source for source in spec["sources"] if source["id"] == "claim_ledger"), None)
            if ledger_source is None:
                issues.append(_issue("claim_ledger_missing", "error", "Factual draft has no claim ledger"))
            else:
                try:
                    ledger_path = resolve_local_file(ledger_source, spec_dir, "claim ledger")
                    result = verify_claims(ledger_path)
                    if result["status"] != "source_linked":
                        issues.append(_issue("claim_sources_invalid", "error", "Claim ledger source links no longer verify"))
                    else:
                        import json
                        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
                        locations = {f"/claims/{index}" for index in range(len(ledger["claims"]))}
                        for scene in spec["timeline"]:
                            refs = [ref for ref in scene.get("sourceRefs", [])
                                    if ref["sourceId"] == "claim_ledger" and ref["location"] in locations]
                            if not refs:
                                issues.append(_issue("claim_link_missing", "error", "Scene has no current claim mapping", scene["id"]))
                        issues.append(_issue("claim_semantic_review_required", "warning",
                                             "A producer must review claim wording, source quality, and support before factual release"))
                except (OSError, ValueError, KeyError, TypeError, RevisionError) as exc:
                    issues.append(_issue("claim_sources_invalid", "error", str(exc)))
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
            issues.extend(_audio_mix_issues(spec, render, render_dir))
        except (OSError, RunError, KeyError, TypeError) as exc:
            issues.append(_issue("render_integrity", "error", str(exc)))

    status = "failed" if any(i["severity"] == "error" for i in issues) else "needs_review" if any(i["severity"] == "warning" for i in issues) else "passed"
    return {
        "projectId": spec["project"]["id"], "specSha256": spec_sha256(spec),
        "revisionSha256": revision["revisionSha256"] if revision else None,
        "scope": "spec_and_render" if render_dir is not None else "spec_only",
        "status": status, "issues": issues,
    }
