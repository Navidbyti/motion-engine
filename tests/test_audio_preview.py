import copy
import hashlib
import struct
import subprocess
import sys
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.planning import plan
from motion_engine.rendering import FrameRenderer, RenderError, _ffmpeg_executable, render_preview
from motion_engine.runs import verify_render_run
from motion_engine.validation import load_spec, validate


def _tone(path: Path, samples: int, channels: int = 1):
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(channels)
        stream.setsampwidth(2)
        stream.setframerate(48_000)
        stream.writeframes(struct.pack("<" + "h" * samples * channels, *([3000] * samples * channels)))


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
