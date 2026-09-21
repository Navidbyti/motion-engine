import hashlib
import json
import math
import struct
import wave
from pathlib import Path

import pytest

from motion_engine.asset_catalog import build_asset_catalog
from motion_engine.director import DirectorError, compile_director_plan
from motion_engine.planning import plan
from motion_engine.rendering import render_preview
from motion_engine.revisions import freeze_revision
from motion_engine.validation import validate


ROOT = Path(__file__).resolve().parents[1]


def _tone(path: Path, frames: int = 48_000) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(48_000)
        output.writeframes(b"".join(struct.pack("<h", round(4000 * math.sin(index * 2 * math.pi * 220 / 48_000)))
                                    for index in range(frames)))


def _project(tmp_path: Path) -> tuple[Path, dict]:
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Make a narrated motion card.", encoding="utf-8")
    proposal = json.loads((ROOT / "examples/director-abstract.plan.json").read_text(encoding="utf-8"))
    proposal["scenes"] = proposal["scenes"][:1]
    proposal["scenes"][0].update({"durationFrames": 24, "voice": "A narrated motion card.",
                                   "audioAssetId": "narration"})
    return prompt, proposal


def test_director_catalogs_and_renders_scene_narration(tmp_path):
    pytest.importorskip("imageio_ffmpeg")
    assets = tmp_path / "assets"
    assets.mkdir()
    audio = assets / "voice.wav"
    _tone(audio)
    effect = assets / "whoosh.wav"
    _tone(effect, frames=12_000)
    manifest = tmp_path / "asset-manifest.json"
    manifest.write_text(json.dumps([{"id": "narration", "kind": "audio", "uri": "assets/voice.wav",
                                     "license": "CC0-1.0", "approved": True},
                                    {"id": "whoosh", "kind": "audio", "uri": "assets/whoosh.wav",
                                     "license": "CC0-1.0", "approved": True,
                                     "generation": {"technique": "sound"}}]), encoding="utf-8")
    catalog = build_asset_catalog(manifest, tmp_path / "assets.json", fps=24)
    assert catalog[0]["sha256"] == hashlib.sha256(audio.read_bytes()).hexdigest()
    prompt, proposal = _project(tmp_path)
    proposal["scenes"][0]["soundEffects"] = [
        {"assetId": "whoosh", "startFrameOffset": 3, "durationFrames": 6, "gainDb": -6}
    ]
    spec_path = tmp_path / "draft.motion.json"
    spec = compile_director_plan(prompt, spec_path, proposal, project_id="narrated",
                                 width=320, height=180, fps=24, assets=catalog)
    assert not validate(spec)
    assert plan(spec)["buildable"]
    scene = spec["timeline"][0]
    narration = next(element for element in scene["elements"] if element["kind"] == "audio")
    assert narration["assetId"] == "narration"
    effect_element = next(element for element in scene["elements"] if element["id"] == "sfx_1_1")
    assert (effect_element["startFrame"], effect_element["endFrameExclusive"]) == (3, 9)
    assert effect_element["params"]["gainDb"] == -6
    assert scene["beats"][0]["voice"]["value"] == "A narrated motion card."
    revision = freeze_revision(spec, tmp_path)
    result = render_preview(spec, tmp_path / "preview", scale=0.2, asset_root=tmp_path,
                            revision_sha256=revision["revisionSha256"])
    assert any(item["kind"] == "audio/wav" for item in result["outputs"])
    assert (tmp_path / "preview/preview.mp4").is_file()


def test_director_rejects_unpaired_or_short_narration(tmp_path):
    prompt, proposal = _project(tmp_path)
    proposal["scenes"][0]["audioAssetId"] = ""
    with pytest.raises(DirectorError, match="supplied together"):
        compile_director_plan(prompt, tmp_path / "draft.motion.json", proposal,
                              project_id="narrated", width=320, height=180, fps=24)
    audio = tmp_path / "short.wav"
    _tone(audio, frames=10)
    catalog = [{"id": "narration", "kind": "audio", "status": "available", "uri": "short.wav",
                "sha256": hashlib.sha256(audio.read_bytes()).hexdigest(), "license": "CC0-1.0", "approved": True}]
    proposal["scenes"][0]["audioAssetId"] = "narration"
    with pytest.raises(DirectorError, match="scene-length"):
        compile_director_plan(prompt, tmp_path / "draft.motion.json", proposal,
                              project_id="narrated", width=320, height=180, fps=24, assets=catalog)


def test_director_rejects_invalid_or_missing_sound_effect(tmp_path):
    prompt, proposal = _project(tmp_path)
    proposal["scenes"][0].pop("voice")
    proposal["scenes"][0].pop("audioAssetId")
    proposal["scenes"][0]["soundEffects"] = [
        {"assetId": "missing", "startFrameOffset": 0, "durationFrames": 4, "gainDb": 0}
    ]
    with pytest.raises(DirectorError, match="unavailable sound effect"):
        compile_director_plan(prompt, tmp_path / "missing.motion.json", proposal,
                              project_id="sound_design", width=320, height=180, fps=24)
    proposal["scenes"][0]["soundEffects"][0].update({"startFrameOffset": 22, "durationFrames": 4})
    with pytest.raises(DirectorError, match="outside the scene"):
        compile_director_plan(prompt, tmp_path / "outside.motion.json", proposal,
                              project_id="sound_design", width=320, height=180, fps=24)


def test_director_builds_faded_music_bed_and_ducks_narrated_scenes(tmp_path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Make a two-scene reel with narration and a continuous music bed.", encoding="utf-8")
    proposal = json.loads((ROOT / "examples/director-abstract.plan.json").read_text(encoding="utf-8"))
    proposal["scenes"][0].update({"voice": "The opening narration.", "audioAssetId": "narration"})
    proposal["soundtrack"] = {"assetId": "music", "gainDb": -12, "fadeInFrames": 4,
                              "fadeOutFrames": 6, "duckUnderNarrationDb": -9}
    narration = tmp_path / "narration.wav"
    music = tmp_path / "music.wav"
    _tone(narration, frames=48_000)
    _tone(music, frames=96_000)
    assets = [{"id": asset_id, "kind": "audio", "status": "available", "uri": path.name,
               "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
               "license": "CC0-1.0", "approved": True}
              for asset_id, path in (("narration", narration), ("music", music))]
    spec = compile_director_plan(prompt, tmp_path / "music.motion.json", proposal,
                                 project_id="music_reel", width=320, height=180, fps=24,
                                 assets=assets)
    first_music = next(element for element in spec["timeline"][0]["elements"]
                       if element["id"] == "music_1")
    second_music = next(element for element in spec["timeline"][1]["elements"]
                        if element["id"] == "music_2")
    assert first_music["params"] == {"gainDb": -21, "role": "music", "sourceStartFrame": 0,
                                      "fadeInFrames": 4, "fadeOutFrames": 0}
    assert second_music["params"] == {"gainDb": -12, "role": "music", "sourceStartFrame": 24,
                                       "fadeInFrames": 0, "fadeOutFrames": 6}
    assert next(element for element in spec["timeline"][0]["elements"]
                if element["id"] == "narration_1")["params"]["role"] == "narration"
    result = render_preview(spec, tmp_path / "music-preview", asset_root=tmp_path, scale=0.2, mp4=False)
    assert any(output["kind"] == "audio/wav" for output in result["outputs"])


def test_director_rejects_short_soundtrack_and_fades_outside_end_scenes(tmp_path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Make a reel with music.", encoding="utf-8")
    proposal = json.loads((ROOT / "examples/director-abstract.plan.json").read_text(encoding="utf-8"))
    proposal["soundtrack"] = {"assetId": "music", "gainDb": -12, "fadeInFrames": 25,
                              "fadeOutFrames": 4, "duckUnderNarrationDb": -9}
    music = tmp_path / "music.wav"
    _tone(music, frames=48_000)
    assets = [{"id": "music", "kind": "audio", "status": "available", "uri": "music.wav",
               "sha256": hashlib.sha256(music.read_bytes()).hexdigest(),
               "license": "CC0-1.0", "approved": True}]
    with pytest.raises(DirectorError, match="fades must fit"):
        compile_director_plan(prompt, tmp_path / "bad-fade.motion.json", proposal,
                              project_id="music_reel", width=320, height=180, fps=24, assets=assets)
    proposal["soundtrack"]["fadeInFrames"] = 4
    with pytest.raises(DirectorError, match="project-length"):
        compile_director_plan(prompt, tmp_path / "short-music.motion.json", proposal,
                              project_id="music_reel", width=320, height=180, fps=24, assets=assets)
