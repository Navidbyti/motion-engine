import copy
import hashlib
import json
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from PIL import ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.frame_assets import FrameArchive, FrameAssetError
from motion_engine.planning import plan
from motion_engine.rendering import FrameRenderer, RenderError, render_preview
from motion_engine.revisions import freeze_revision
from motion_engine.revisions import spec_sha256
from motion_engine.scene_revisions import revise_scene
from motion_engine.validation import load_spec, validate
from motion_engine.video_import import VideoImportError, import_video


@pytest.mark.parametrize("name,size,count", [
    ("moving-landscape", (320, 180), 24),
    ("moving-portrait", (180, 320), 30),
])
def test_public_moving_plates_overlay_exact_text_and_map_frames(name, size, count):
    spec = load_spec(ROOT / "examples" / f"{name}.motion.json")
    assert not validate(spec)
    assert plan(spec)["capabilities"][0]["buildable"]
    assert freeze_revision(spec, ROOT / "examples")["assets"][0]["verified"]
    renderer = FrameRenderer(spec, asset_root=ROOT / "examples")
    first, last = renderer.render_frame(0), renderer.render_frame(count - 1)
    assert first.size == last.size == size
    assert ImageChops.difference(first, last).getbbox() is not None
    assert spec["timeline"][0]["elements"][1]["text"]["value"] == spec["project"]["title"]


def test_video_plate_trim_uses_declared_source_start_frame():
    spec = copy.deepcopy(load_spec(ROOT / "examples/moving-landscape.motion.json"))
    element = spec["timeline"][0]["elements"][0]
    element["startFrame"] = 3
    element["endFrameExclusive"] = 20
    element["params"]["sourceStartFrame"] = 2
    renderer = FrameRenderer(spec, asset_root=ROOT / "examples")
    archive = FrameArchive(spec["assets"][0], ROOT / "examples", spec["canvas"]["frameRate"])
    rendered = renderer.render_frame(3).crop((0, 0, 320, 110))
    expected = archive.frame(2).convert("RGB").crop((0, 0, 320, 110))
    original = archive.frame(0).convert("RGB").crop((0, 0, 320, 110))
    assert ImageChops.difference(rendered, expected).getbbox() is None
    assert ImageChops.difference(rendered, original).getbbox() is not None
    element["params"]["sourceStartFrame"] = 10
    with pytest.raises(RenderError, match="source frame range"):
        FrameRenderer(spec, asset_root=ROOT / "examples")


def test_video_plate_bad_hash_and_rate_fail_before_output(tmp_path):
    spec = copy.deepcopy(load_spec(ROOT / "examples/moving-landscape.motion.json"))
    spec["assets"][0]["sha256"] = "0" * 64
    with pytest.raises(RenderError, match="matching ZIP hash"):
        render_preview(spec, tmp_path / "bad", asset_root=ROOT / "examples", mp4=False)
    assert not (tmp_path / "bad").exists()
    spec["assets"][0]["sha256"] = hashlib.sha256((ROOT / "examples/assets/moving-landscape.zip").read_bytes()).hexdigest()
    spec["canvas"]["frameRate"]["numerator"] = 30
    with pytest.raises(RenderError, match="frame rate"):
        FrameRenderer(spec, asset_root=ROOT / "examples")


def test_video_plate_missing_frame_is_rejected(tmp_path):
    source = ROOT / "examples/assets/moving-landscape.zip"
    target = tmp_path / "broken.zip"
    with ZipFile(source) as original, ZipFile(target, "w", compression=ZIP_DEFLATED) as broken:
        for name in original.namelist():
            if name != "frames/000010.png":
                broken.writestr(name, original.read(name))
    asset = {"id": "broken", "kind": "video.frames", "status": "available",
             "uri": "broken.zip", "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    with pytest.raises(FrameAssetError, match="exactly the declared"):
        FrameArchive(asset, tmp_path, {"numerator": 24, "denominator": 1})


def test_video_plate_zoom_can_be_revised_without_changing_title(tmp_path):
    spec = load_spec(ROOT / "examples/moving-landscape.motion.json")
    request = {"baseSpecSha256": spec_sha256(spec), "sceneId": "scene_1", "operations": [
        {"op": "set_visual_zoom", "elementId": "plate", "value": [
            {"frame": 0, "value": 1}, {"frame": 23, "value": 1.5, "easing": "ease_in_out"}]}]}
    request_file = tmp_path / "zoom.json"
    request_file.write_text(json.dumps(request), encoding="utf-8")
    revised = revise_scene(spec, request, request_path=request_file, output_path=tmp_path / "v2.motion.json")
    assert revised["timeline"][0]["elements"][1] == spec["timeline"][0]["elements"][1]
    assert revised["timeline"][0]["animations"][0]["property"] == "scale"
    assert plan(revised)["capabilities"][0]["buildable"]
    frame = FrameRenderer(revised, asset_root=ROOT / "examples").render_frame(23)
    assert ImageChops.difference(frame, FrameRenderer(spec, asset_root=ROOT / "examples").render_frame(23)).getbbox()


def test_import_video_round_trips_public_preview(tmp_path):
    pytest.importorskip("imageio_ffmpeg")
    spec = load_spec(ROOT / "examples/moving-landscape.motion.json")
    source = tmp_path / "source"
    render_preview(spec, source, asset_root=ROOT / "examples")
    plate = tmp_path / "imported.zip"
    report = import_video(source / "preview.mp4", plate, numerator=24, denominator=1, frame_count=24)
    assert report["transform"]["frameCount"] == 24
    assert report["asset"]["sha256"] == hashlib.sha256(plate.read_bytes()).hexdigest()
    archive = FrameArchive({"id": "imported", **report["asset"]}, tmp_path,
                           {"numerator": 24, "denominator": 1})
    assert archive.frame_count == 24 and archive.frame(12).size == (320, 180)
    with pytest.raises(VideoImportError, match="new .zip"):
        import_video(source / "preview.mp4", plate, numerator=24, denominator=1, frame_count=24)
