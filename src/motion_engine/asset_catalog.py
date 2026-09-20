"""Build a portable, verified asset catalog from an agent-reviewed manifest."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from PIL import Image

from .frame_assets import FrameArchive, FrameAssetError
from .revisions import RevisionError, file_sha256, resolve_local_file


class AssetCatalogError(ValueError):
    pass


def build_asset_catalog(manifest_path: str | Path, output_path: str | Path, *, fps: int) -> list[dict[str, Any]]:
    manifest_file, output_file = Path(manifest_path).resolve(), Path(output_path).resolve()
    if manifest_file.parent != output_file.parent or manifest_file == output_file:
        raise AssetCatalogError("manifest and catalog must be distinct files in one project directory")
    if output_file.exists():
        raise AssetCatalogError("asset catalog output already exists")
    if fps not in (24, 25, 30, 50, 60):
        raise AssetCatalogError("frame rate must be 24, 25, 30, 50, or 60")
    try:
        items = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AssetCatalogError("asset manifest is not readable JSON") from exc
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        raise AssetCatalogError("asset manifest needs 1 to 100 records")
    catalog = []
    seen = set()
    for index, item in enumerate(items):
        if (not isinstance(item, dict) or set(item) - {"id", "kind", "uri", "license", "approved", "generation"}
            or not {"id", "kind", "uri", "license", "approved"} <= set(item)):
            raise AssetCatalogError(f"asset {index}: expected id, kind, uri, license, and approved")
        asset_id = item["id"]
        if not isinstance(asset_id, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", asset_id) or asset_id in seen:
            raise AssetCatalogError(f"asset {index}: ID is invalid or duplicated")
        seen.add(asset_id)
        if (item["kind"] not in ("image", "video.frames") or item["approved"] is not True
            or not isinstance(item["license"], str) or not item["license"].strip()):
            raise AssetCatalogError(f"asset {asset_id}: needs an approved image or frame plate with a nonblank license")
        if not isinstance(item["uri"], str):
            raise AssetCatalogError(f"asset {asset_id}: URI must be a portable relative file path")
        generation = item.get("generation")
        if generation is not None and (not isinstance(generation, dict) or generation.get("technique") not in ("image", "video", "3d")):
            raise AssetCatalogError(f"asset {asset_id}: generation technique must be image, video, or 3d")
        if generation is not None and generation["technique"] == "3d" and item["kind"] != "video.frames":
            raise AssetCatalogError(f"asset {asset_id}: 3D generation needs a moving frame plate")
        try:
            file = resolve_local_file(item, output_file.parent, "asset")
        except RevisionError as exc:
            raise AssetCatalogError(str(exc)) from exc
        digest = file_sha256(file)
        record = {"id": asset_id, "kind": item["kind"], "status": "available", "uri": item["uri"],
                  "sha256": digest, "license": item["license"], "approved": True}
        if generation is not None:
            record["generation"] = generation
        if item["kind"] == "image":
            try:
                with Image.open(file) as image:
                    if image.format not in ("PNG", "JPEG", "WEBP") or image.width * image.height > 50_000_000:
                        raise AssetCatalogError(f"asset {asset_id}: image format or dimensions are unsupported")
                    image.verify()
            except (OSError, ValueError) as exc:
                raise AssetCatalogError(f"asset {asset_id}: image cannot be decoded") from exc
        else:
            try:
                archive = FrameArchive(record, output_file.parent, {"numerator": fps, "denominator": 1})
                for frame in (0, archive.frame_count // 2, archive.frame_count - 1):
                    archive.frame(frame)
            except FrameAssetError as exc:
                raise AssetCatalogError(f"asset {asset_id}: {exc}") from exc
        catalog.append(record)
    return catalog
