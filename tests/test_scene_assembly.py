import copy
import json
import sys
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from motion_engine.cli import main
from motion_engine.rendering import render_preview
from motion_engine.runs import frames_tree_sha256, verify_render_run
from motion_engine.scene_assembly import SceneAssemblyError, assemble_scene_modules
from motion_engine.scene_modules import render_scene_modules
from motion_engine.validation import load_spec


def test_assembly_matches_direct_full_frame_render(tmp_path):
    spec = load_spec(ROOT / "examples/prompt-en.motion.json")
    modules = tmp_path / "modules"
    assembled = tmp_path / "assembled"
    direct = tmp_path / "direct"
    render_scene_modules(spec, modules, mp4=False, scale=0.1)
    report = assemble_scene_modules(spec, [modules], assembled, mp4=False, scale=0.1, revision_sha256="a" * 64)
    render_preview(spec, direct, mp4=False, scale=0.1, revision_sha256="a" * 64)

    assert report["outputs"][0]["treeSha256"] == frames_tree_sha256(direct / "frames", 120)
    assert verify_render_run(assembled)["assembly"]["scenes"][1]["sceneId"] == "scene_2"


def test_assembly_reuses_unchanged_scene_and_selects_revised_scene(tmp_path):
    base = load_spec(ROOT / "examples/prompt-en.motion.json")
    revised = copy.deepcopy(base)
    revised["timeline"][1]["elements"][0]["text"]["value"] = "A revised second scene"
    base_modules = tmp_path / "base"
    revised_modules = tmp_path / "revised"
    render_scene_modules(base, base_modules, mp4=False, scale=0.1)
    render_scene_modules(revised, revised_modules, mp4=False, scale=0.1, scene_ids=["scene_2"])

    report = assemble_scene_modules(
        revised, [base_modules, revised_modules], tmp_path / "mixed", mp4=False, scale=0.1
    )
    direct = tmp_path / "direct-revised"
    render_preview(revised, direct, mp4=False, scale=0.1)
    assert report["outputs"][0]["treeSha256"] == frames_tree_sha256(direct / "frames", 120)
    selections = report["assembly"]["scenes"]
    base_manifest = json.loads((base_modules / "scene-modules.json").read_text(encoding="utf-8"))
    revised_manifest = json.loads((revised_modules / "scene-modules.json").read_text(encoding="utf-8"))
    assert selections[0]["framesSha256"] == base_manifest["modules"][0]["outputs"][0]["treeSha256"]
    assert selections[1]["framesSha256"] == revised_manifest["modules"][0]["outputs"][0]["treeSha256"]

    with pytest.raises(SceneAssemblyError, match="no compatible module for scene scene_2"):
        assemble_scene_modules(revised, [base_modules], tmp_path / "stale", mp4=False, scale=0.1)
    assert not (tmp_path / "stale").exists()


def test_assembly_rejects_tampered_module_before_output(tmp_path):
    spec = load_spec(ROOT / "examples/prompt-en.motion.json")
    modules = tmp_path / "modules"
    render_scene_modules(spec, modules, mp4=False, scale=0.1)
    frame = modules / "000-scene_1-scene" / "frames" / "000000.png"
    frame.write_bytes(frame.read_bytes() + b"tampered")
    with pytest.raises(SceneAssemblyError, match="does not match"):
        assemble_scene_modules(spec, [modules], tmp_path / "assembled", mp4=False, scale=0.1)
    assert not (tmp_path / "assembled").exists()


def test_audio_assembly_preserves_exact_project_sample_count(tmp_path):
    spec = load_spec(ROOT / "examples/audio-card.motion.json")
    modules = tmp_path / "modules"
    assembled = tmp_path / "assembled"
    render_scene_modules(spec, modules, mp4=False, scale=0.1, asset_root=ROOT / "examples")
    assemble_scene_modules(spec, [modules], assembled, mp4=False, scale=0.1)
    with wave.open(str(assembled / "mix.wav"), "rb") as stream:
        assert stream.getnframes() == 96_000
        assert (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) == (1, 2, 48_000)


def test_assemble_scenes_cli_produces_verified_render_run(tmp_path):
    modules = tmp_path / "modules"
    output = tmp_path / "output"
    assert main([
        "render-scenes", str(ROOT / "examples/prompt-en.motion.json"),
        "--output-dir", str(modules), "--frames-only", "--scale", "0.1",
    ]) == 0
    assert main([
        "assemble-scenes", str(ROOT / "examples/prompt-en.motion.json"),
        "--modules", str(modules), "--output-dir", str(output),
        "--frames-only", "--scale", "0.1",
    ]) == 0
    assert verify_render_run(output)["frameCount"] == 120
