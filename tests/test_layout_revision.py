import copy
import json
import shutil
import sys
from pathlib import Path

import pytest
from PIL import ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.cli import main
from motion_engine.rendering import FrameRenderer
from motion_engine.revisions import freeze_revision, spec_sha256
from motion_engine.scene_revisions import SceneRevisionError, revise_scene
from motion_engine.validation import load_spec


def _setup(tmp_path, fixture, scene, element, operations):
    spec = load_spec(ROOT / "examples" / f"{fixture}.motion.json")
    for item in spec["sources"] + spec["assets"]:
        destination = tmp_path / item["uri"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "examples" / item["uri"], destination)
    base = tmp_path / "base.motion.json"
    base.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    request = {"baseSpecSha256": spec_sha256(spec), "sceneId": scene,
               "userPrompt": "Polish this scene", "operations": [
                   {"op": action, "elementId": element, "value": value}
                   for action, value in operations]}
    path = tmp_path / "edit.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    return spec, base, request, path


def test_move_title_bounds_changes_only_selected_scene(tmp_path):
    new_bounds = {"x": 24, "y": 20, "width": 272, "height": 63}
    spec, _, request, path = _setup(tmp_path, "director-abstract", "scene_1", "title_1",
                                    [("set_bounds", new_bounds)])
    original = copy.deepcopy(spec)
    revised = revise_scene(spec, request, request_path=path, output_path=tmp_path / "next.motion.json")
    assert spec == original
    assert revised["timeline"][1] == original["timeline"][1]
    assert revised["timeline"][0]["elements"][1]["bounds"] == new_bounds
    assert revised["timeline"][0]["elements"][1]["sourceRefs"][-1]["sourceId"].startswith("revision_")
    assert freeze_revision(revised, tmp_path)["revisionSha256"]
    before = FrameRenderer(spec, asset_root=tmp_path).render_frame(8)
    after = FrameRenderer(revised, asset_root=tmp_path).render_frame(8)
    assert ImageChops.difference(before, after).getbbox()


def test_fade_title_and_move_image_in_one_version(tmp_path):
    new_bounds = {"x": 100, "y": 40, "width": 400, "height": 225}
    opacity = [{"frame": 0, "value": 0}, {"frame": 20, "value": 1, "easing": "ease_out"}]
    spec, base, request, path = _setup(tmp_path, "image-card", "card_scene", "caption",
                                       [("set_opacity", opacity)])
    request["operations"].append({"op": "set_bounds", "elementId": "plate", "value": new_bounds})
    path.write_text(json.dumps(request), encoding="utf-8")
    output = tmp_path / "next.motion.json"
    assert main(["revise-scene", str(base), str(path), "--output", str(output)]) == 0
    revised = load_spec(output)
    assert revised["timeline"][0]["elements"][0]["bounds"] == new_bounds
    assert any(a["targetId"] == "caption" and a["property"] == "opacity" and a["keyframes"] == opacity
               for a in revised["timeline"][0]["animations"])
    assert ImageChops.difference(FrameRenderer(spec, asset_root=tmp_path).render_frame(0),
                                 FrameRenderer(revised, asset_root=tmp_path).render_frame(0)).getbbox()
    assert freeze_revision(revised, tmp_path)["revisionSha256"]


@pytest.mark.parametrize("action,value,message", [
    ("set_bounds", {"x": -1, "y": 20, "width": 20, "height": 20}, "fit inside the canvas"),
    ("set_bounds", {"x": 0, "y": 0, "width": True, "height": 20}, "finite numbers"),
    ("set_opacity", [{"frame": 0, "value": 1.5}], "unsupported"),
    ("set_opacity", [{"frame": 0, "value": 0}, {"frame": 0, "value": 1}], "unique and sorted"),
])
def test_layout_revision_rejects_invalid_geometry_or_opacity(tmp_path, action, value, message):
    spec, _, request, path = _setup(tmp_path, "image-card", "card_scene", "caption", [(action, value)])
    with pytest.raises(SceneRevisionError, match=message):
        revise_scene(spec, request, request_path=path, output_path=tmp_path / "next.motion.json")
