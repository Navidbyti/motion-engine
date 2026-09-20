import copy
import hashlib
import json
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.planning import plan
from motion_engine.qa import qa_report
from motion_engine.rendering import FrameRenderer, RenderError, _ffmpeg_executable, render_preview
from motion_engine.revisions import freeze_revision
from motion_engine.revisions import spec_sha256
from motion_engine.runs import verify_render_run
from motion_engine.scene_revisions import SceneRevisionError, revise_scene
from motion_engine.validation import load_spec, validate


def _tone(path: Path, samples: int, channels: int = 1, amplitude: int = 3000):
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(channels)
        stream.setsampwidth(2)
        stream.setframerate(48_000)
        stream.writeframes(struct.pack("<" + "h" * samples * channels, *([amplitude] * samples * channels)))


def _with_audio(tmp_path: Path, samples: int = 48_000, channels: int = 1):
    audio = tmp_path / "voice.wav"
    _tone(audio, samples, channels)
    spec = copy.deepcopy(load_spec(ROOT / "examples/hello.motion.json"))
    spec["assets"] = [{"id": "voice_asset", "kind": "audio", "status": "available", "uri": "voice.wav",
                       "sha256": hashlib.sha256(audio.read_bytes()).hexdigest()}]
    scene = spec["timeline"][0]
    scene["elements"].append({"id": "voice_track", "kind": "audio", "startFrame": 30,
                              "endFrameExclusive": 60, "assetId": "voice_asset", "params": {"gainDb": 0}})
    scene["beats"][1]["elementIds"].append("voice_track")
    return spec, audio


def test_wav_audio_aligns_to_exact_frames_and_mpx_has_audio(tmp_path):
    spec, _ = _with_audio(tmp_path)
    assert validate(spec) == []
    assert plan(spec)["buildable"]
    result = render_preview(spec, tmp_path / "render", asset_root=tmp_path, scale=0.1, mp4=True)
    assert any(item["kind"] == "audio/wav" for item in result["outputs"])
    assert verify_render_run(tmp_path / "render") == result
    with wave.open(str(tmp_path / "render/mix.wav"), "rb") as stream:
        data = stream.readframes(stream.getnframes())
        assert stream.getnframes() == 144_000
    samples = struct.unpack("<" + "h" * 144_000, data)
    assert max(abs(value) for value in samples[:48_000]) == 0
    assert samples[48_000] == 3000
    assert max(abs(value) for value in samples[96_000:]) == 0
    probe = subprocess.run([_ffmpeg_executable(), "-hide_banner", "-i", str(tmp_path / "render/preview.mp4")],
                           capture_output=True, text=True, check=False)
    assert "Audio: aac" in probe.stderr
    imageio_ffmpeg = pytest.importorskip("imageio_ffmpeg")
    decoder = imageio_ffmpeg.read_frames(str(tmp_path / "render/preview.mp4"))
    next(decoder)
    assert sum(1 for _ in decoder) == 90


def test_audio_rejects_short_incompatible_and_changed_assets(tmp_path):
    spec, path = _with_audio(tmp_path, samples=10)
    with pytest.raises(RenderError, match="shorter"):
        FrameRenderer(spec, asset_root=tmp_path)
    _tone(path, 48_000, channels=2)
    spec["assets"][0]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(RenderError, match="mono 16-bit"):
        FrameRenderer(spec, asset_root=tmp_path)
    _tone(path, 48_000)
    with pytest.raises(RenderError, match="matching WAV hash"):
        FrameRenderer(spec, asset_root=tmp_path)


def test_overlapping_audio_tracks_fail_on_clipping(tmp_path):
    spec, path = _with_audio(tmp_path)
    _tone(path, 48_000)
    for index in range(11):
        element = copy.deepcopy(spec["timeline"][0]["elements"][-1])
        element["id"] = f"extra_audio_{index}"
        spec["timeline"][0]["elements"].append(element)
    with pytest.raises(RenderError, match="mix clips"):
        render_preview(spec, tmp_path / "bad", asset_root=tmp_path, scale=0.1, mp4=False)
    assert not (tmp_path / "bad").exists()


@pytest.mark.parametrize("amplitude,expected_issue", [
    (3000, None),
    (0, "audio_mix_silent"),
    (32600, "audio_mix_near_clipping"),
])
def test_render_audio_qa_flags_silence_and_near_clipping(tmp_path, amplitude, expected_issue):
    spec, path = _with_audio(tmp_path)
    _tone(path, 48_000, amplitude=amplitude)
    spec["assets"][0]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    source = tmp_path / "assets/hello-script.md"
    source.parent.mkdir()
    shutil.copyfile(ROOT / "examples/assets/hello-script.md", source)
    revision = freeze_revision(spec, tmp_path)
    render_preview(spec, tmp_path / "render", asset_root=tmp_path, scale=0.1, mp4=False,
                   revision_sha256=revision["revisionSha256"])
    report = qa_report(spec, tmp_path, tmp_path / "render")
    audio_issues = [issue["code"] for issue in report["issues"] if issue["code"].startswith("audio_")]
    assert audio_issues == ([expected_issue] if expected_issue else [])


def test_scoped_audio_gain_edit_changes_mix_and_keeps_timing(tmp_path):
    spec, _ = _with_audio(tmp_path)
    request = {"baseSpecSha256": spec_sha256(spec), "sceneId": "opening",
               "userPrompt": "Lower only the voice by six decibels",
               "operations": [{"op": "set_audio_gain", "elementId": "voice_track", "value": -6}]}
    request_path = tmp_path / "gain.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    revised = revise_scene(spec, request, request_path=request_path, output_path=tmp_path / "next.motion.json")
    voice_before = spec["timeline"][0]["elements"][-1]
    voice_after = revised["timeline"][0]["elements"][-1]
    assert voice_after["params"]["gainDb"] == -6
    assert voice_after["startFrame"] == voice_before["startFrame"]
    assert voice_after["endFrameExclusive"] == voice_before["endFrameExclusive"]
    assert voice_after["assetId"] == voice_before["assetId"]
    render_preview(spec, tmp_path / "before", asset_root=tmp_path, scale=0.1, mp4=False)
    render_preview(revised, tmp_path / "after", asset_root=tmp_path, scale=0.1, mp4=False)
    with wave.open(str(tmp_path / "before/mix.wav"), "rb") as stream:
        before = struct.unpack("<h", stream.readframes(1 + 48_000)[-2:])[0]
    with wave.open(str(tmp_path / "after/mix.wav"), "rb") as stream:
        after = struct.unpack("<h", stream.readframes(1 + 48_000)[-2:])[0]
    assert before == 3000
    assert 1450 <= after <= 1550


@pytest.mark.parametrize("value", [True, -61, 13, "-6"])
def test_audio_gain_edit_rejects_invalid_values(tmp_path, value):
    spec, _ = _with_audio(tmp_path)
    request = {"baseSpecSha256": spec_sha256(spec), "sceneId": "opening",
               "operations": [{"op": "set_audio_gain", "elementId": "voice_track", "value": value}]}
    request_path = tmp_path / "invalid-gain.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(SceneRevisionError, match="-60 to 12 dB"):
        revise_scene(spec, request, request_path=request_path, output_path=tmp_path / "next.motion.json")
