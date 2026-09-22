import json
import sys
import wave
from pathlib import Path

from PIL import ImageChops
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from motion_engine.rendering import FrameRenderer, RenderError
from motion_engine.scene_modules import render_scene_modules
from motion_engine.validation import load_spec
from motion_engine.cli import main


def test_scene_modules_preserve_global_frames_and_stable_ids(tmp_path):
    spec = load_spec(ROOT / "examples/prompt-en.motion.json")
    manifest = render_scene_modules(spec, tmp_path / "modules", mp4=False, scale=0.1)

    assert manifest["sceneCount"] == 2
    assert [item["sceneId"] for item in manifest["modules"]] == ["scene_1", "scene_2"]
    assert [item["frameCount"] for item in manifest["modules"]] == [60, 60]
    assert manifest["modules"][1]["globalStartFrame"] == 60
    saved = json.loads((tmp_path / "modules" / "scene-modules.json").read_text(encoding="utf-8"))
    assert saved["specSha256"] == manifest["specSha256"]

    renderer = FrameRenderer(spec, scale=0.1)
    first_scene_last = renderer.render_frame(59)
    second_scene_first = renderer.render_frame(60)
    assert ImageChops.difference(first_scene_last, second_scene_first).getbbox() is not None

    from PIL import Image
    with Image.open(tmp_path / "modules" / "000-scene_1-scene" / "frames" / "000059.png") as saved_first:
        assert ImageChops.difference(first_scene_last, saved_first.convert("RGB")).getbbox() is None
    with Image.open(tmp_path / "modules" / "001-scene_2-scene" / "frames" / "000000.png") as saved_second:
        assert ImageChops.difference(second_scene_first, saved_second.convert("RGB")).getbbox() is None


def test_scene_modules_can_render_one_requested_scene(tmp_path):
    spec = load_spec(ROOT / "examples/prompt-en.motion.json")
    manifest = render_scene_modules(
        spec, tmp_path / "one", mp4=False, scale=0.1, scene_ids=["scene_2"]
    )
    assert manifest["sceneCount"] == 1
    assert manifest["modules"][0]["sceneId"] == "scene_2"
    assert manifest["modules"][0]["order"] == 1
    assert len(list((tmp_path / "one" / "001-scene_2-scene" / "frames").glob("*.png"))) == 60


def test_scene_modules_reject_unknown_and_duplicate_ids(tmp_path):
    spec = load_spec(ROOT / "examples/prompt-en.motion.json")
    with pytest.raises(RenderError, match="unknown scene IDs"):
        render_scene_modules(spec, tmp_path / "unknown", mp4=False, scene_ids=["missing"])
    with pytest.raises(RenderError, match="duplicate scene IDs"):
        render_scene_modules(spec, tmp_path / "duplicates", mp4=False, scene_ids=["scene_1", "scene_1"])
    assert not (tmp_path / "unknown").exists()
    assert not (tmp_path / "duplicates").exists()
    with pytest.raises(RenderError, match="exceeds safety limit"):
        render_scene_modules(spec, tmp_path / "too-long", mp4=False, max_frames=119)
    assert not (tmp_path / "too-long").exists()


def test_render_scenes_cli_binds_revision_and_selects_scene(tmp_path):
    output = tmp_path / "cli-modules"
    assert main([
        "render-scenes", str(ROOT / "examples/prompt-en.motion.json"),
        "--output-dir", str(output), "--scene-id", "scene_2",
        "--frames-only", "--scale", "0.1",
    ]) == 0
    manifest = json.loads((output / "scene-modules.json").read_text(encoding="utf-8"))
    assert manifest["revisionSha256"]
    assert [item["sceneId"] for item in manifest["modules"]] == ["scene_2"]


def test_scene_module_audio_uses_exact_frame_derived_sample_count(tmp_path):
    spec = load_spec(ROOT / "examples/audio-card.motion.json")
    manifest = render_scene_modules(
        spec, tmp_path / "audio", mp4=False, scale=0.1, asset_root=ROOT / "examples"
    )
    mix = tmp_path / "audio" / manifest["modules"][0]["directory"] / "mix.wav"
    with wave.open(str(mix), "rb") as stream:
        assert stream.getframerate() == 48_000
        assert stream.getnframes() == 96_000
