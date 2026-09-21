import copy
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.asset_requests import AssetRequestError, resolve_asset_requests
from motion_engine.cli import main
from motion_engine.rendering import FrameRenderer
from motion_engine.revisions import file_sha256, freeze_revision
from motion_engine.validation import load_spec


def _project(tmp_path, name):
    prompt = tmp_path / "prompt.txt"
    shutil.copyfile(ROOT / "examples" / "assets" / f"{name}.txt", prompt)
    proposal = json.loads((ROOT / "examples" / f"{name}.plan.json").read_text(encoding="utf-8"))
    return prompt, proposal


def test_image_request_resolves_then_compiles_and_renders(tmp_path):
    prompt, proposal = _project(tmp_path, "director-abstract")
    scene = proposal["scenes"][0]
    scene.update({"visual": "asset", "assetId": "replacement_image", "motion": "zoom",
                  "subtitle": "A small spark"})
    proposal["assetRequests"] = [{"id": "replacement_image", "kind": "image",
                                  "description": "A colorful moving idea", "durationFrames": scene["durationFrames"]}]
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(proposal), encoding="utf-8")
    image = tmp_path / "assets" / "plate.png"
    image.parent.mkdir()
    shutil.copyfile(ROOT / "examples/assets/synthetic-plate.png", image)
    catalog = [{"id": "replacement_image", "kind": "image", "status": "available",
                "uri": "assets/plate.png", "sha256": file_sha256(image),
                "license": "MIT", "approved": True}]
    catalog_path = tmp_path / "assets.json"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    resolved_path = tmp_path / "resolved.json"
    assert main(["resolve-assets", str(plan), "--assets", str(catalog_path),
                 "--output", str(resolved_path), "--fps", "24"]) == 0
    assert json.loads(resolved_path.read_text(encoding="utf-8"))["assetRequests"] == []
    spec_path = tmp_path / "draft.motion.json"
    assert main(["compile-director", str(prompt), str(resolved_path), "--output", str(spec_path),
                 "--project-id", "resolved_image", "--assets", str(catalog_path),
                 "--width", "320", "--height", "180", "--fps", "24"]) == 0
    spec = load_spec(spec_path)
    first_scene = spec["timeline"][0]
    title = next(item["bounds"] for item in first_scene["elements"] if item["id"] == "title_1")
    subtitle = next(item["bounds"] for item in first_scene["elements"] if item["id"] == "subtitle_1")
    assert title["y"] + title["height"] <= subtitle["y"]
    assert FrameRenderer(spec, asset_root=tmp_path).render_frame(12).size == (320, 180)
    assert freeze_revision(spec, tmp_path)["revisionSha256"]
    assert main(["resolve-assets", str(plan), "--assets", str(catalog_path),
                 "--output", str(resolved_path), "--fps", "24"]) == 2


def test_video_request_requires_matching_frames_and_provenance(tmp_path):
    _, proposal = _project(tmp_path, "director-plate")
    proposal["assetRequests"] = [{"id": "moving_plate", "kind": "video",
                                  "description": "A moving blue form", "durationFrames": 24}]
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(proposal), encoding="utf-8")
    zip_file = tmp_path / "assets" / "moving-landscape.zip"
    zip_file.parent.mkdir()
    shutil.copyfile(ROOT / "examples/assets/moving-landscape.zip", zip_file)
    catalog = json.loads((ROOT / "examples/director-plate.assets.json").read_text(encoding="utf-8"))
    catalog_path = tmp_path / "assets.json"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    resolved = resolve_asset_requests(plan, catalog_path, tmp_path / "resolved.json", fps=24)
    assert resolved["assetRequests"] == []
    proposal["assetRequests"][0]["kind"] = "3d"
    plan.write_text(json.dumps(proposal), encoding="utf-8")
    with pytest.raises(AssetRequestError, match="3D generation provenance"):
        resolve_asset_requests(plan, catalog_path, tmp_path / "resolved.json", fps=24)
    proposal["assetRequests"][0].update({"kind": "video", "durationFrames": 25})
    plan.write_text(json.dumps(proposal), encoding="utf-8")
    with pytest.raises(AssetRequestError, match="shorter"):
        resolve_asset_requests(plan, catalog_path, tmp_path / "resolved.json", fps=24)
    assert file_sha256(zip_file) == catalog[0]["sha256"]


def test_asset_request_rejects_missing_or_altered_media(tmp_path):
    _, proposal = _project(tmp_path, "director-plate")
    proposal["assetRequests"] = [{"id": "moving_plate", "kind": "video",
                                  "description": "An exact clip", "durationFrames": 24}]
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(proposal), encoding="utf-8")
    catalog = json.loads((ROOT / "examples/director-plate.assets.json").read_text(encoding="utf-8"))
    catalog_path = tmp_path / "assets.json"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    with pytest.raises(AssetRequestError, match="missing or outside"):
        resolve_asset_requests(plan, catalog_path, tmp_path / "resolved.json", fps=24)
    media = tmp_path / "assets" / "moving-landscape.zip"
    media.parent.mkdir()
    shutil.copyfile(ROOT / "examples/assets/moving-landscape.zip", media)
    altered = copy.deepcopy(catalog)
    altered[0]["sha256"] = "0" * 64
    catalog_path.write_text(json.dumps(altered), encoding="utf-8")
    with pytest.raises(AssetRequestError, match="SHA-256 mismatch"):
        resolve_asset_requests(plan, catalog_path, tmp_path / "resolved.json", fps=24)


def test_narration_request_resolves_against_reviewed_wav(tmp_path):
    _, proposal = _project(tmp_path, "director-abstract")
    proposal["scenes"] = proposal["scenes"][:1]
    proposal["scenes"][0].update({"durationFrames": 24, "voice": "A short narrated scene.",
                                   "audioAssetId": "narration"})
    proposal["assetRequests"] = [{"id": "narration", "kind": "audio",
                                   "description": "Approved narration take", "durationFrames": 24}]
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(proposal), encoding="utf-8")
    audio = tmp_path / "assets/demo-tone.wav"
    audio.parent.mkdir()
    shutil.copyfile(ROOT / "examples/assets/demo-tone.wav", audio)
    catalog = [{"id": "narration", "kind": "audio", "status": "available",
                "uri": "assets/demo-tone.wav", "sha256": file_sha256(audio),
                "license": "CC0-1.0", "approved": True}]
    catalog_path = tmp_path / "assets.json"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    resolved = resolve_asset_requests(plan, catalog_path, tmp_path / "resolved.json", fps=24)
    assert resolved["assetRequests"] == []
    assert resolved["scenes"][0]["audioAssetId"] == "narration"
