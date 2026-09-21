"""Resolve a director plan's requested shots against inspected local media."""
from __future__ import annotations

import copy
import json
import re
import wave
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from PIL import Image

from .director_schema import DIRECTOR_PLAN_SCHEMA
from .frame_assets import FrameArchive, FrameAssetError
from .revisions import RevisionError, file_sha256, resolve_local_file


class AssetRequestError(ValueError):
    pass


def resolve_asset_requests(plan_path: str | Path, catalog_path: str | Path,
                           output_path: str | Path, *, fps: int) -> dict[str, Any]:
    plan_file, catalog_file, output = (Path(item).resolve() for item in (plan_path, catalog_path, output_path))
    if (plan_file.parent != output.parent or catalog_file.parent != output.parent
        or len({plan_file, catalog_file, output}) != 3):
        raise AssetRequestError("plan, asset catalog, and new plan must be distinct files in one directory")
    if output.exists():
        raise AssetRequestError("resolved plan output already exists")
    if fps not in (24, 25, 30, 50, 60):
        raise AssetRequestError("frame rate must be 24, 25, 30, 50, or 60")
    proposal = json.loads(plan_file.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(DIRECTOR_PLAN_SCHEMA).iter_errors(proposal))
    if errors:
        raise AssetRequestError("director plan is outside its schema: " + errors[0].message)
    requests = proposal["assetRequests"]
    if not requests:
        raise AssetRequestError("director plan has no pending asset requests")
    catalog = json.loads(catalog_file.read_text(encoding="utf-8"))
    if not isinstance(catalog, list) or any(not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in catalog):
        raise AssetRequestError("asset catalog must contain asset records with IDs")
    assets = {item["id"]: item for item in catalog}
    if len(assets) != len(catalog):
        raise AssetRequestError("asset catalog has duplicate IDs")
    requested_ids = [request["id"] for request in requests]
    if len(requested_ids) != len(set(requested_ids)):
        raise AssetRequestError("director plan has duplicate asset requests")
    for request in requests:
        asset_id = request["id"]
        asset = assets.get(asset_id)
        if asset is None:
            raise AssetRequestError(f"asset request {asset_id}: no matching catalog record")
        soundtrack_use = (request["kind"] == "audio"
                          and proposal.get("soundtrack", {}).get("assetId") == asset_id)
        scenes = ((proposal["scenes"] if soundtrack_use else
                   [scene for scene in proposal["scenes"] if scene.get("audioAssetId") == asset_id])
                  if request["kind"] == "audio" else
                  [scene for scene in proposal["scenes"] if scene["visual"] == "asset" and scene["assetId"] == asset_id])
        if not scenes:
            raise AssetRequestError(f"asset request {asset_id}: no scene uses this asset ID")
        expected_kind = "image" if request["kind"] == "image" else "audio" if request["kind"] == "audio" else "video.frames"
        if (asset.get("kind") != expected_kind or asset.get("status") != "available"
            or asset.get("approved") is not True or not isinstance(asset.get("license"), str)
            or not asset["license"].strip() or not isinstance(asset.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", asset["sha256"])):
            raise AssetRequestError(f"asset request {asset_id}: needs an approved, licensed, hashed {expected_kind} asset")
        generation = asset.get("generation")
        if request["kind"] == "3d" and (not isinstance(generation, dict) or generation.get("technique") != "3d"):
            raise AssetRequestError(f"asset request {asset_id}: 3D shot needs explicit 3D generation provenance")
        try:
            file = resolve_local_file(asset, output.parent, "asset")
        except RevisionError as exc:
            raise AssetRequestError(str(exc)) from exc
        if file_sha256(file) != asset["sha256"]:
            raise AssetRequestError(f"asset request {asset_id}: SHA-256 mismatch")
        if expected_kind == "image":
            try:
                with Image.open(file) as image:
                    if image.format not in ("PNG", "JPEG", "WEBP") or image.width * image.height > 50_000_000:
                        raise AssetRequestError(f"asset request {asset_id}: image format or dimensions are unsupported")
                    image.verify()
            except (OSError, ValueError) as exc:
                raise AssetRequestError(f"asset request {asset_id}: image cannot be decoded") from exc
        elif expected_kind == "video.frames":
            try:
                archive = FrameArchive(asset, output.parent, {"numerator": fps, "denominator": 1})
                needed = max(request["durationFrames"], *(scene["durationFrames"] for scene in scenes))
                if archive.frame_count < needed:
                    raise AssetRequestError(f"asset request {asset_id}: plate is shorter than the requested scene")
                archive.frame(0)
                archive.frame(needed - 1)
            except FrameAssetError as exc:
                raise AssetRequestError(f"asset request {asset_id}: {exc}") from exc
        else:
            needed_frames = max(request["durationFrames"],
                                sum(scene["durationFrames"] for scene in scenes) if soundtrack_use else
                                max(scene["durationFrames"] for scene in scenes))
            try:
                with wave.open(str(file), "rb") as audio:
                    needed_samples = round(needed_frames * 48_000 / fps)
                    if (file.suffix.lower() != ".wav" or audio.getcomptype() != "NONE"
                            or audio.getnchannels() != 1 or audio.getsampwidth() != 2
                            or audio.getframerate() != 48_000 or audio.getnframes() < needed_samples):
                        raise AssetRequestError(f"asset request {asset_id}: audio needs a mono 16-bit PCM WAV at 48 kHz covering the requested duration")
            except (OSError, EOFError, wave.Error) as exc:
                raise AssetRequestError(f"asset request {asset_id}: audio cannot be decoded") from exc
    resolved = copy.deepcopy(proposal)
    resolved["assetRequests"] = []
    return resolved
