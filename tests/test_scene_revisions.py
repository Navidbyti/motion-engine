import copy
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.cli import main
from motion_engine.revisions import freeze_revision, spec_sha256
from motion_engine.scene_revisions import SceneRevisionError, revise_scene
from motion_engine.validation import load_spec, validate


@pytest.mark.parametrize("fixture,scene_id,element_id,new_text", [
    ("prompt-en", "scene_1", "text_1", "A revised opening"),
    ("image-card", "card_scene", "caption", "A revised caption"),
])
def test_text_revision_is_scoped_and_cited(tmp_path, fixture, scene_id, element_id, new_text):
    spec = load_spec(ROOT / "examples" / f"{fixture}.motion.json")
    before = copy.deepcopy(spec)
    for item in spec["sources"] + spec["assets"]:
        if item.get("uri"):
            destination = tmp_path / item["uri"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / "examples" / item["uri"], destination)
    request = {"baseSpecSha256": spec_sha256(spec), "sceneId": scene_id,
               "operations": [{"op": "set_text", "elementId": element_id, "value": new_text}]}
    request_file = tmp_path / "revision.json"
    request_file.write_text(json.dumps(request), encoding="utf-8")
    revised = revise_scene(spec, request, request_path=request_file, output_path=tmp_path / "v2.motion.json")
    assert spec == before
    assert not validate(revised)
    assert revised["timeline"][0]["elements"][0 if fixture == "prompt-en" else 1]["text"]["value"] == new_text
    assert revised["timeline"][0]["elements"][0 if fixture == "prompt-en" else 1]["sourceRefs"][0]["sourceId"].startswith("revision_")
    if fixture == "prompt-en":
        assert revised["timeline"][1] == spec["timeline"][1]
        assert revised["timeline"][0]["beats"][0]["onScreen"][0]["value"] == new_text
    assert all(item["verified"] for item in freeze_revision(revised, tmp_path)["sources"])


def test_image_zoom_revision_and_cli_hash_conflict(tmp_path):
    spec = load_spec(ROOT / "examples/image-card.motion.json")
    for item in spec["sources"] + spec["assets"]:
        destination = tmp_path / item["uri"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "examples" / item["uri"], destination)
    base = tmp_path / "base.motion.json"
    base.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    request = {"baseSpecSha256": spec_sha256(spec), "sceneId": "card_scene", "operations": [
        {"op": "set_image_zoom", "elementId": "plate", "value": [
            {"frame": 0, "value": 1}, {"frame": 95, "value": 1.4, "easing": "ease_in_out"}]}]}
    request_file = tmp_path / "zoom.json"
    request_file.write_text(json.dumps(request), encoding="utf-8")
    output = tmp_path / "zoom.motion.json"
    assert main(["revise-scene", str(base), str(request_file), "--output", str(output)]) == 0
    revised = load_spec(output)
    assert revised["timeline"][0]["animations"][-1]["property"] == "scale"
    assert revised["timeline"][0]["elements"][1] == spec["timeline"][0]["elements"][1]
    assert freeze_revision(revised, tmp_path)["revisionSha256"]
    render_dir = tmp_path / "zoom-preview"
    assert main(["render", str(output), "--output-dir", str(render_dir), "--frames-only", "--scale", "0.1"]) == 0
    assert len(list((render_dir / "frames").glob("*.png"))) == 96
    assert main(["revise-scene", str(base), str(request_file), "--output", str(output)]) == 2
    with pytest.raises(SceneRevisionError, match="hash mismatch"):
        revise_scene(revised, request, request_path=request_file, output_path=tmp_path / "v3.motion.json")


def test_revision_rejects_unknown_or_invalid_operations(tmp_path):
    spec = load_spec(ROOT / "examples/image-card.motion.json")
    request_file = tmp_path / "edit.json"
    request = {"baseSpecSha256": spec_sha256(spec), "sceneId": "card_scene", "operations": [
        {"op": "set_image_zoom", "elementId": "plate", "value": [{"frame": 0, "value": 0.5}]}]}
    request_file.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(SceneRevisionError, match="unsupported"):
        revise_scene(spec, request, request_path=request_file, output_path=tmp_path / "v2.motion.json")
    request["operations"][0]["op"] = "replace_everything"
    request_file.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(SceneRevisionError, match="unsupported edit"):
        revise_scene(spec, request, request_path=request_file, output_path=tmp_path / "v2.motion.json")
