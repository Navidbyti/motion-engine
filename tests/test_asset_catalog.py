import hashlib
import json
import shutil
from pathlib import Path

import pytest

from motion_engine.asset_catalog import AssetCatalogError, build_asset_catalog
from motion_engine.cli import main
from motion_engine.director import compile_director_plan
from motion_engine.validation import validate


ROOT = Path(__file__).resolve().parents[1]


def test_public_asset_manifest_builds_two_media_kinds(tmp_path):
    source = ROOT / "examples"
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    for name in ("synthetic-plate.png", "moving-landscape.zip"):
        shutil.copyfile(source / "assets" / name, assets_dir / name)
    manifest_path = tmp_path / "asset-catalog.manifest.json"
    shutil.copyfile(source / "asset-catalog.manifest.json", manifest_path)
    catalog = build_asset_catalog(manifest_path, tmp_path / "assets.json", fps=24)
    assert [item["kind"] for item in catalog] == ["image", "video.frames"]


@pytest.mark.parametrize("kind,source_name,asset_id,plan_name,prompt_name", [
    ("image", "synthetic-plate.png", "still", "director-abstract", "director-abstract"),
    ("video.frames", "moving-landscape.zip", "moving_plate", "director-plate", "director-plate"),
])
def test_catalog_public_media_compiles_into_director_plan(tmp_path, kind, source_name, asset_id,
                                                          plan_name, prompt_name):
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    media = assets_dir / source_name
    shutil.copyfile(ROOT / "examples/assets" / source_name, media)
    manifest = [{"id": asset_id, "kind": kind, "uri": f"assets/{source_name}",
                 "license": "MIT", "approved": True}]
    manifest_path = tmp_path / "asset-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    catalog_path = tmp_path / "assets.json"
    assert main(["catalog-assets", str(manifest_path), "--output", str(catalog_path), "--fps", "24"]) == 0
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert catalog[0]["sha256"] == hashlib.sha256(media.read_bytes()).hexdigest()
    assert catalog[0]["status"] == "available"
    assert main(["catalog-assets", str(manifest_path), "--output", str(catalog_path), "--fps", "24"]) == 2
    prompt = tmp_path / "prompt.txt"
    prompt.write_text((ROOT / "examples/assets" / f"{prompt_name}.txt").read_text(encoding="utf-8"), encoding="utf-8")
    proposal = json.loads((ROOT / "examples" / f"{plan_name}.plan.json").read_text(encoding="utf-8"))
    if kind == "image":
        proposal["scenes"][0]["visual"] = "asset"
        proposal["scenes"][0]["assetId"] = asset_id
    spec = compile_director_plan(prompt, tmp_path / "draft.motion.json", proposal,
                                 project_id="catalog_fixture", assets=catalog,
                                 width=320, height=180, fps=24)
    assert not validate(spec)


@pytest.mark.parametrize("changes,message", [
    ({"approved": False}, "approved"),
    ({"license": ""}, "license"),
    ({"uri": "../outside.png"}, "portable relative"),
    ({"generation": {"technique": "3d"}}, "moving frame plate"),
])
def test_catalog_rejects_unreviewed_or_unportable_media(tmp_path, changes, message):
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    shutil.copyfile(ROOT / "examples/assets/synthetic-plate.png", assets_dir / "still.png")
    item = {"id": "still", "kind": "image", "uri": "assets/still.png",
            "license": "MIT", "approved": True, **changes}
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps([item]), encoding="utf-8")
    with pytest.raises(AssetCatalogError, match=message):
        build_asset_catalog(manifest_path, tmp_path / "catalog.json", fps=24)


def test_catalog_rejects_wrong_frame_rate(tmp_path):
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    shutil.copyfile(ROOT / "examples/assets/moving-landscape.zip", assets_dir / "plate.zip")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps([{"id": "plate", "kind": "video.frames", "uri": "assets/plate.zip",
                                          "license": "MIT", "approved": True}]), encoding="utf-8")
    with pytest.raises(AssetCatalogError, match="frame rate"):
        build_asset_catalog(manifest_path, tmp_path / "catalog.json", fps=30)
