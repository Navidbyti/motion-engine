"""Compile an agent-authored whole-video plan into a validated MotionSpec.

The plan is a proposal, not a source of truth. The compiler checks capabilities
and refuses ungrounded factual plans or assets that do not exist.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .planning import plan
from .claims import verify_claims
from .revisions import file_sha256, resolve_local_file
from .validation import validate


class DirectorError(ValueError):
    pass


def _card_text_color(hex_color: str) -> str:
    channels = [int(hex_color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
              for value in channels]
    luminance = sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    return "#000000" if (luminance + 0.05) / 0.05 >= 1.05 / (luminance + 0.05) else "#FFFFFF"


def compile_director_plan(prompt_path: str | Path, output_path: str | Path,
                          proposal: dict[str, Any], *, project_id: str,
                          width: int = 1080, height: int = 1920, fps: int = 30,
                          assets: list[dict[str, Any]] | None = None,
                          proposal_path: str | Path | None = None,
                          claim_ledger_path: str | Path | None = None) -> dict[str, Any]:
    prompt = Path(prompt_path).resolve()
    output = Path(output_path).resolve()
    try:
        prompt_uri = prompt.relative_to(output.parent).as_posix()
    except ValueError as exc:
        raise DirectorError("prompt must be inside the MotionSpec directory") from exc
    if not prompt.is_file() or prompt.suffix.lower() != ".txt":
        raise DirectorError("prompt must be an existing UTF-8 .txt file")
    try:
        prompt_text = prompt.read_text(encoding="utf-8-sig")
    except UnicodeError as exc:
        raise DirectorError("prompt must be valid UTF-8") from exc
    if not prompt_text.strip() or len(prompt_text) > 50_000:
        raise DirectorError("prompt must contain 1 to 50,000 characters")
    plan_source = None
    plan_ref = None
    if proposal_path is not None:
        plan_file = Path(proposal_path).resolve()
        try:
            plan_uri = plan_file.relative_to(output.parent).as_posix()
        except ValueError as exc:
            raise DirectorError("director plan file must be inside the MotionSpec directory") from exc
        if not plan_file.is_file() or json.loads(plan_file.read_text(encoding="utf-8")) != proposal:
            raise DirectorError("director plan does not match its source file")
        plan_source = {"id": "director_plan", "uri": plan_uri, "mediaType": "application/json",
                       "sha256": file_sha256(plan_file), "authority": ["direction"]}
        plan_ref = {"sourceId": "director_plan", "location": f"/scenes", "method": "desktop agent proposal", "confidence": 0.7}
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", project_id):
        raise DirectorError("invalid project ID")
    if width < 180 or height < 180 or fps not in (24, 25, 30, 50, 60):
        raise DirectorError("unsupported canvas or frame rate")
    required = {"title", "locale", "direction", "researchRequired", "assetRequests", "scenes"}
    if not isinstance(proposal, dict) or set(proposal) != required:
        raise DirectorError("director plan needs title, locale, direction, researchRequired, assetRequests, and scenes only")
    claim_source = None
    research_sources = []
    claim_locations = {}
    if proposal["researchRequired"] is True:
        if claim_ledger_path is None:
            raise DirectorError("research-required plan needs a claim ledger")
        ledger_file = Path(claim_ledger_path).resolve()
        try:
            ledger_uri = ledger_file.relative_to(output.parent).as_posix()
        except ValueError as exc:
            raise DirectorError("claim ledger must be inside the MotionSpec directory") from exc
        report = verify_claims(ledger_file)
        if report["status"] != "source_linked":
            raise DirectorError("claim ledger source links failed: " + "; ".join(issue["message"] for issue in report["issues"]))
        ledger = json.loads(ledger_file.read_text(encoding="utf-8"))
        claim_locations = {claim["id"]: f"/claims/{index}" for index, claim in enumerate(ledger["claims"])}
        claim_source = {"id": "claim_ledger", "uri": ledger_uri, "mediaType": "application/json",
                        "sha256": file_sha256(ledger_file), "authority": ["agent research ledger"]}
        for source in ledger["sources"]:
            source_file = (ledger_file.parent / source["uri"]).resolve()
            source_uri = source_file.relative_to(output.parent).as_posix()
            research_sources.append({"id": "claim_source_" + source["id"], "uri": source_uri,
                                     "mediaType": "text/plain", "sha256": source["sha256"],
                                     "authority": [source["publisher"]]})
    elif proposal["researchRequired"] is not False or claim_ledger_path is not None:
        raise DirectorError("claim ledger is only accepted for a research-required plan")
    if not isinstance(proposal["assetRequests"], list):
        raise DirectorError("assetRequests must be a list")
    if proposal["assetRequests"]:
        requests = [str(item.get("description", item)) for item in proposal["assetRequests"]]
        raise DirectorError("first draft needs unresolved visual assets: " + "; ".join(requests))
    if (not isinstance(proposal["title"], str) or not proposal["title"].strip()
        or not isinstance(proposal["locale"], str) or len(proposal["locale"]) < 2
        or proposal["direction"] not in ("ltr", "rtl")
        or not isinstance(proposal["scenes"], list) or not 1 <= len(proposal["scenes"]) <= 30):
        raise DirectorError("director plan metadata or scenes are invalid")
    asset_list = assets or []
    if not isinstance(asset_list, list) or any(not isinstance(asset, dict) or not isinstance(asset.get("id"), str)
                                              for asset in asset_list):
        raise DirectorError("asset catalog must be a list of asset records with IDs")
    asset_ids = {asset["id"]: asset for asset in asset_list}
    if len(asset_ids) != len(asset_list):
        raise DirectorError("duplicate asset ID")
    for asset in asset_list:
        if (asset.get("kind") not in ("image", "video.frames") or asset.get("status") != "available"
            or asset.get("approved") is not True or not isinstance(asset.get("license"), str)
            or not asset["license"].strip() or not asset.get("sha256")):
            raise DirectorError("director assets must be approved, licensed, available hashed images or frame plates")
        try:
            path = resolve_local_file(asset, output.parent, "asset")
        except ValueError as exc:
            raise DirectorError(str(exc)) from exc
        if file_sha256(path) != asset["sha256"]:
            raise DirectorError(f"asset {asset['id']} SHA-256 mismatch")
    inset = max(24, round(min(width, height) * 0.07))
    ref = {"sourceId": "user_prompt", "location": "entire prompt", "method": "desktop agent adaptation", "confidence": 0.7}
    timeline = []
    cursor = 0
    scene_keys = {"durationFrames", "visual", "assetId", "title", "subtitle", "background", "accent", "motion"}
    for index, scene in enumerate(proposal["scenes"], 1):
        if not isinstance(scene, dict) or not scene_keys <= set(scene) or set(scene) - scene_keys - {"claimIds"}:
            raise DirectorError(f"scene {index} has missing or unknown plan fields")
        scene_claim_ids = scene.get("claimIds", [])
        if not isinstance(scene_claim_ids, list) or any(not isinstance(item, str) for item in scene_claim_ids) or len(scene_claim_ids) != len(set(scene_claim_ids)):
            raise DirectorError(f"scene {index} claimIds must be a list of unique IDs")
        if proposal["researchRequired"] and not scene_claim_ids:
            raise DirectorError(f"scene {index} needs at least one cited claim")
        if any(item not in claim_locations for item in scene_claim_ids):
            raise DirectorError(f"scene {index} references an unknown claim ID")
        claim_refs = [{"sourceId": "claim_ledger", "location": claim_locations[item],
                       "method": "agent claim mapping", "confidence": 0.5} for item in scene_claim_ids]
        duration = scene["durationFrames"]
        if not isinstance(duration, int) or isinstance(duration, bool) or not 12 <= duration <= 900:
            raise DirectorError(f"scene {index} duration must be 12 to 900 frames")
        if not isinstance(scene["title"], str) or not isinstance(scene["subtitle"], str):
            raise DirectorError(f"scene {index} text must be strings")
        if not scene["title"].strip() and not scene["subtitle"].strip():
            raise DirectorError(f"scene {index} needs visible text")
        if any(len(scene[field]) > 500 for field in ("title", "subtitle")):
            raise DirectorError(f"scene {index} text is too long for this draft primitive")
        if any(not isinstance(scene[field], str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", scene[field])
               for field in ("background", "accent")):
            raise DirectorError(f"scene {index} colors must be #RRGGBB")
        visual, asset_id, motion = scene["visual"], scene["assetId"], scene["motion"]
        if not isinstance(asset_id, str):
            raise DirectorError(f"scene {index} asset ID must be a string")
        if visual not in ("typography", "shape", "card", "asset") or motion not in ("none", "fade", "zoom", "slide"):
            raise DirectorError(f"scene {index} visual or motion is unsupported")
        if visual == "asset" and asset_id not in asset_ids:
            raise DirectorError(f"scene {index} requests unavailable asset {asset_id!r}; generate or import it first")
        if visual != "asset" and asset_id != "":
            raise DirectorError(f"scene {index} has an asset ID without an asset visual")
        if motion == "zoom" and visual != "asset":
            raise DirectorError(f"scene {index} zoom needs an image or moving plate")
        start, end = cursor, cursor + duration
        scene_id = f"scene_{index}"
        elements = [{"id": f"background_{index}", "kind": "shape", "startFrame": start,
                     "endFrameExclusive": end,
                     "bounds": {"x": 0, "y": 0, "width": width, "height": height},
                     "params": {"shape": "rect", "color": scene["background"]}, "zIndex": -1}]
        animations = []
        if visual == "asset":
            asset = asset_ids[asset_id]
            element_id = f"visual_{index}"
            elements.append({"id": element_id, "kind": "image" if asset["kind"] == "image" else "video",
                             "startFrame": start, "endFrameExclusive": end,
                             "bounds": {"x": 0, "y": 0, "width": width, "height": height},
                             "assetId": asset_id, "params": {"fit": "cover"}, "zIndex": 0,
                             "sourceRefs": asset.get("sourceRefs", [])})
            if motion == "zoom":
                animations.append({"targetId": element_id, "property": "scale", "keyframes": [
                    {"frame": start, "value": 1}, {"frame": end - 1, "value": 1.15, "easing": "ease_in_out"}]})
            elements.append({"id": f"lower_third_{index}", "kind": "shape", "startFrame": start,
                             "endFrameExclusive": end,
                             "bounds": {"x": 0, "y": round(height * 0.62),
                                        "width": width, "height": height - round(height * 0.62)},
                             "params": {"shape": "rect", "color": scene["background"]}, "zIndex": 1})
        if visual == "shape":
            elements.append({"id": f"accent_{index}", "kind": "shape", "startFrame": start,
                             "endFrameExclusive": end,
                             "bounds": {"x": inset, "y": round(height * 0.59),
                                        "width": width - 2 * inset, "height": max(12, round(height * 0.06))},
                             "params": {"shape": "rect", "color": scene["accent"]}, "zIndex": 0})
        if visual == "card":
            elements.append({"id": f"card_{index}", "kind": "shape", "startFrame": start,
                             "endFrameExclusive": end,
                             "bounds": {"x": inset, "y": inset,
                                        "width": width - 2 * inset, "height": height - 2 * inset},
                             "params": {"shape": "rect", "color": scene["accent"]}, "zIndex": 0})
        for role, value in (("title", scene["title"]), ("subtitle", scene["subtitle"])):
            if not value.strip():
                continue
            element_id = f"{role}_{index}"
            title = role == "title"
            if visual == "asset":
                y = round(height * (0.62 if title else 0.80))
                box_h = round(height * (0.18 if title else 0.16))
            elif visual == "card":
                card_h = height - 2 * inset
                y = inset + round(card_h * (0.18 if title else 0.62))
                box_h = round(card_h * (0.36 if title else 0.22))
            else:
                y = round(height * (0.22 if title else 0.68))
                box_h = round(height * (0.35 if title else 0.18))
            text_x = 2 * inset if visual == "card" else inset
            text_width = width - 4 * inset if visual == "card" else width - 2 * inset
            elements.append({"id": element_id, "kind": "text", "startFrame": start,
                             "endFrameExclusive": end,
                             "bounds": {"x": text_x, "y": y, "width": text_width, "height": box_h},
                             "text": {"value": value, "locale": proposal["locale"],
                                      "direction": proposal["direction"], "fontFamily": "DejaVu Sans",
                                      "fontWeight": 700 if title else 400, "align": "center"},
                             "params": {"color": _card_text_color(scene["accent"]) if visual == "card" else "#FFFFFF",
                                        "fontSize": max(20, round(min(width, height) * (0.055 if title else 0.038))), "wrap": True},
                             "zIndex": 2, "sourceRefs": [ref, *claim_refs]})
            if motion == "fade":
                animations.append({"targetId": element_id, "property": "opacity", "keyframes": [
                    {"frame": start, "value": 0}, {"frame": start + min(10, duration - 1), "value": 1, "easing": "ease_out"}]})
            if motion == "slide":
                begin = start + (0 if title else min(4, duration - 2))
                finish = start + min(12 if title else 14, duration - 1)
                enter_x = -round(width - 2 * inset) if proposal["direction"] == "ltr" else width
                animations.append({"targetId": element_id, "property": "x", "keyframes": [
                    {"frame": begin, "value": enter_x},
                    {"frame": finish, "value": text_x, "easing": "ease_out"}]})
        timeline.append({"id": scene_id, "startFrame": start, "endFrameExclusive": end,
                         "transitionIn": "start" if index == 1 else "cut", "elements": elements,
                         "beats": [{"id": f"beat_{index}", "startFrame": start, "endFrameExclusive": end,
                                    "elementIds": [element["id"] for element in elements],
                                    "onScreen": [{"value": value, "locale": proposal["locale"]}
                                                 for value in (scene["title"], scene["subtitle"]) if value.strip()],
                                    "sourceRefs": [ref, *claim_refs]}],
                         "animations": animations, "sourceRefs": [ref, *claim_refs]
                         + ([{**plan_ref, "location": f"/scenes/{index - 1}"}] if plan_ref else [])})
        cursor = end
    if cursor > 10_000:
        raise DirectorError("first draft exceeds the 10,000-frame preview limit")
    spec = {"schemaVersion": "1.0.0",
            "project": {"id": project_id, "title": proposal["title"], "locale": proposal["locale"],
                        "direction": proposal["direction"],
                        "description": "Desktop-agent-directed first draft; review visuals, exact text, and source meaning."},
            "canvas": {"width": width, "height": height, "frameRate": {"numerator": fps, "denominator": 1},
                       "durationFrames": cursor, "colorSpace": "Rec.709", "background": "#101820",
                       "safeArea": {"top": inset, "right": inset, "bottom": inset, "left": inset}},
            "sources": [{"id": "user_prompt", "uri": prompt_uri, "mediaType": "text/plain",
                         "sha256": file_sha256(prompt), "authority": ["creative brief"]}]
                       + ([plan_source] if plan_source else [])
                       + ([claim_source] if claim_source else []) + research_sources,
            "assets": asset_list, "datasets": [], "timeline": timeline,
            "deliverables": [{"id": "preview", "target": "video/mp4", "profile": "preview",
                              "required": True, "editable": False}],
            "policies": {"qa": ([{"id": "claim_review", "rule": "claim.semantic_review", "severity": "warning"}]
                                   if claim_source else []),
                         "disclosures": [], "approvals": ["first draft visual review"],
                         "unsupportedFeature": "error"}}
    errors = validate(spec)
    if errors:
        raise DirectorError("compiled MotionSpec is invalid: " + "; ".join(errors))
    capability = plan(spec)["capabilities"][0]
    if not capability["buildable"]:
        raise DirectorError("first draft needs unsupported feature: " + str(capability["unsupportedFeatures"]))
    return spec
