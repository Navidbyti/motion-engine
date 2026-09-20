import copy
import io
import json
import shutil
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.cli import main
from motion_engine.rendering import FrameRenderer
from motion_engine.revisions import file_sha256, freeze_revision, spec_sha256
from motion_engine.scene_revisions import SceneRevisionError, revise_scene
from motion_engine.validation import load_spec


def _project(tmp_path, name):
    spec = load_spec(ROOT / "examples" / f"{name}.motion.json")
    for item in spec["sources"] + spec["assets"]:
        destination = tmp_path / item["uri"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "examples" / item["uri"], destination)
    base = tmp_path / "base.motion.json"
    base.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    return spec, base


def _request(tmp_path, spec, scene_id, element_id, asset):
    request = {"baseSpecSha256": spec_sha256(spec), "sceneId": scene_id,
               "userPrompt": "Replace the shot", "operations": [
                   {"op": "set_asset", "elementId": element_id, "value": asset}]}
    path = tmp_path / "edit.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    return request, path


def test_image_shot_replacement_preserves_other_elements_and_changes_pixels(tmp_path):
    spec, _ = _project(tmp_path, "image-card")
    before = copy.deepcopy(spec)
    replacement = tmp_path / "assets" / "replacement.png"
    Image.new("RGB", (400, 225), "#E86044").save(replacement)
    asset = {"id": "replacement", "kind": "image", "status": "available",
             "uri": "assets/replacement.png", "sha256": file_sha256(replacement),
             "license": "MIT", "approved": True}
    request, path = _request(tmp_path, spec, "card_scene", "plate", asset)
    revised = revise_scene(spec, request, request_path=path, output_path=tmp_path / "next.motion.json")
    assert spec == before
    assert revised["timeline"][0]["elements"][1] == spec["timeline"][0]["elements"][1]
    assert revised["timeline"][0]["elements"][0]["assetId"] == "replacement"
    assert revised["assets"][-1]["sourceRefs"][-1]["sourceId"].startswith("revision_")
    assert freeze_revision(revised, tmp_path)["revisionSha256"]
    original_frame = FrameRenderer(spec, scale=0.25, asset_root=tmp_path).render_frame(45)
    revised_frame = FrameRenderer(revised, scale=0.25, asset_root=tmp_path).render_frame(45)
    assert ImageChops.difference(original_frame, revised_frame).getbbox()


def test_video_shot_replacement_renders_new_version(tmp_path):
    pytest.importorskip("imageio_ffmpeg")
    spec, base = _project(tmp_path, "director-plate")
    old = tmp_path / "assets" / "moving-landscape.zip"
    new = tmp_path / "assets" / "replacement.zip"
    with ZipFile(old) as source, ZipFile(new, "w") as target:
        for name in source.namelist():
            data = source.read(name)
            if name.startswith("frames/") and name.endswith(".png"):
                with Image.open(io.BytesIO(data)) as frame:
                    changed = Image.new("RGB", frame.size, "#C33225")
                buffer = io.BytesIO()
                changed.save(buffer, format="PNG")
                data = buffer.getvalue()
            target.writestr(name, data)
    asset = {"id": "new_plate", "kind": "video.frames", "status": "available",
             "uri": "assets/replacement.zip", "sha256": file_sha256(new),
             "license": "MIT", "approved": True}
    _, path = _request(tmp_path, spec, "scene_1", "visual_1", asset)
    output = tmp_path / "next.motion.json"
    render = tmp_path / "next-preview"
    assert main(["revise-and-render", str(base), str(path), "--output-spec", str(output),
                 "--output-dir", str(render), "--scale", "0.5"]) == 0
    revised = load_spec(output)
    assert revised["timeline"][0]["elements"][1]["assetId"] == "new_plate"
    assert revised["timeline"][0]["elements"][3] == spec["timeline"][0]["elements"][3]
    assert (render / "preview.mp4").is_file()
    assert ImageChops.difference(FrameRenderer(spec, asset_root=tmp_path).render_frame(8),
                                 FrameRenderer(revised, asset_root=tmp_path).render_frame(8)).getbbox()


def test_asset_swap_rejects_hash_license_kind_and_frame_rate(tmp_path):
    spec, _ = _project(tmp_path, "director-plate")
    asset = copy.deepcopy(spec["assets"][0])
    asset["id"] = "candidate"
    request, path = _request(tmp_path, spec, "scene_1", "visual_1", asset)
    for field, bad, message in [
        ("sha256", "0" * 64, "SHA-256 mismatch"),
        ("license", "", "approved, licensed"),
        ("approved", False, "approved, licensed"),
        ("kind", "image", "video.frames"),
    ]:
        wrong = copy.deepcopy(request)
        wrong["operations"][0]["value"][field] = bad
        path.write_text(json.dumps(wrong), encoding="utf-8")
        with pytest.raises(SceneRevisionError, match=message):
            revise_scene(spec, wrong, request_path=path, output_path=tmp_path / "next.motion.json")
    portrait = tmp_path / "assets" / "moving-portrait.zip"
    shutil.copyfile(ROOT / "examples/assets/moving-portrait.zip", portrait)
    asset.update({"uri": "assets/moving-portrait.zip", "sha256": file_sha256(portrait)})
    request["operations"][0]["value"] = asset
    path.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(SceneRevisionError, match="frame rate"):
        revise_scene(spec, request, request_path=path, output_path=tmp_path / "next.motion.json")
    short = tmp_path / "assets" / "short.zip"
    with ZipFile(tmp_path / "assets" / "moving-landscape.zip") as source, ZipFile(short, "w") as target:
        manifest = json.loads(source.read("manifest.json"))
        manifest["frameCount"] = 12
        target.writestr("manifest.json", json.dumps(manifest))
        for frame in range(12):
            name = f"frames/{frame:06d}.png"
            target.writestr(name, source.read(name))
    asset.update({"uri": "assets/short.zip", "sha256": file_sha256(short)})
    path.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(SceneRevisionError, match="shorter than the selected scene"):
        revise_scene(spec, request, request_path=path, output_path=tmp_path / "next.motion.json")
