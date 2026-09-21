import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageChops, features

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.rendering import FrameRenderer, RenderError, _format_chart_value, _localize_digits, render_preview
from motion_engine.planning import plan
from motion_engine.validation import load_spec


def changed(left, right):
    return ImageChops.difference(left, right).getbbox() is not None


def test_text_and_rtl_bar_chart_change_at_declared_frames():
    hello = FrameRenderer(load_spec(ROOT / "examples/hello.motion.json"), scale=0.2)
    frame_0 = hello.render_frame(0)
    background = Image.new("RGB", frame_0.size, (16, 24, 32))
    assert not changed(frame_0, background)
    assert changed(hello.render_frame(20), frame_0)
    assert changed(hello.render_frame(60), hello.render_frame(20))
    weather_spec = load_spec(ROOT / "examples/weather.motion.json")
    if features.check("raqm"):
        weather = FrameRenderer(weather_spec, scale=0.2)
        assert changed(weather.render_frame(60), weather.render_frame(24))
        assert weather.render_frame(60).size == (216, 216)
    else:
        with pytest.raises(RenderError, match="libraqm"):
            FrameRenderer(weather_spec, scale=0.2)


def test_line_chart_is_data_driven():
    spec = copy.deepcopy(load_spec(ROOT / "examples/weather.motion.json"))
    spec["project"]["direction"] = "ltr"
    spec["timeline"][0]["elements"][0]["text"].update({"value": "Weather", "direction": "ltr"})
    spec["timeline"][0]["elements"][1]["kind"] = "chart.line"
    del spec["timeline"][0]["elements"][1]["params"]["categoryField"]
    renderer = FrameRenderer(spec, scale=0.2)
    assert changed(renderer.render_frame(60), renderer.render_frame(24))


def test_chart_value_format_is_bounded_and_deterministic():
    assert _format_chart_value(31, 0) == "31"
    assert _format_chart_value(2.345, 2) == "2.35"
    with pytest.raises(RenderError, match="decimals"):
        _format_chart_value(1, 7)


def test_chart_handles_negative_values_around_zero_baseline():
    spec = copy.deepcopy(load_spec(ROOT / "examples/weather.motion.json"))
    spec["project"]["direction"] = "ltr"
    spec["timeline"][0]["elements"][0]["text"].update({"value": "Range", "direction": "ltr"})
    chart = spec["timeline"][0]["elements"][1]
    spec["datasets"][0]["rows"][0]["temperatureC"] = -10
    chart["params"].update({"minimum": -20, "maximum": 40, "tickCount": 4, "showValues": True})
    chart["dataBinding"]["format"] = {"unit": "°C", "decimals": 0}
    FrameRenderer(spec, scale=0.5).render_frame(60)


def test_digit_policy_is_local_to_each_text_item():
    assert _localize_digits("2026", "persian", "en-US") == "۲۰۲۶"
    assert _localize_digits("۲۰۲۶", "latin", "fa-IR") == "2026"
    assert _localize_digits("2026", "locale", "ar-EG") == "٢٠٢٦"
    assert _localize_digits("2026", None, "fa-IR") == "2026"


def test_ltr_text_renders_without_raqm(monkeypatch):
    original_check = features.check
    monkeypatch.setattr(features, "check", lambda name: False if name == "raqm" else original_check(name))
    renderer = FrameRenderer(load_spec(ROOT / "examples/hello.motion.json"), scale=0.2)
    assert renderer.render_frame(20).getbbox() is not None


def test_explicit_lines_and_opt_in_wrapping_respect_bounds():
    spec = copy.deepcopy(load_spec(ROOT / "examples/hello.motion.json"))
    title = spec["timeline"][0]["elements"][0]
    title["text"]["value"] = "A longer line of text that wraps into several rows"
    title["bounds"] = {"x": 160, "y": 220, "width": 700, "height": 300}
    title["params"]["fontSize"] = 64
    title["params"]["wrap"] = True
    renderer = FrameRenderer(spec, scale=1)
    assert changed(renderer.render_frame(20), Image.new("RGB", (1920, 1080), (16, 24, 32)))
    title["params"]["wrap"] = False
    with pytest.raises(RenderError, match="overflows"):
        FrameRenderer(spec).render_frame(20)
    title["text"]["value"] = "A longer line\nof text"
    FrameRenderer(spec).render_frame(20)
    title["text"]["value"] = "UnbreakableWordMuchLongerThanTheTextBox"
    title["params"]["wrap"] = True
    with pytest.raises(RenderError, match="unbreakable word"):
        FrameRenderer(spec).render_frame(20)


def test_multiline_rtl_text_uses_raqm_when_available():
    if not features.check("raqm"):
        pytest.skip("Pillow libraqm is unavailable")
    spec = copy.deepcopy(load_spec(ROOT / "examples/weather.motion.json"))
    heading = spec["timeline"][0]["elements"][0]
    heading["text"]["value"] = "درجات الحرارة\nخلال العام"
    heading["bounds"]["height"] = 180
    heading["params"]["fontSize"] = 46
    FrameRenderer(spec, scale=1).render_frame(0)


def test_unsupported_content_fails_before_frame_writing(tmp_path):
    spec = copy.deepcopy(load_spec(ROOT / "examples/hello.motion.json"))
    spec["timeline"][0]["elements"][0]["kind"] = "shader"
    with pytest.raises(RenderError, match="unsupported preview element"):
        render_preview(spec, tmp_path / "out", scale=0.1)
    assert not (tmp_path / "out").exists()


def test_png_sequence_has_exact_frame_count(tmp_path):
    spec = load_spec(ROOT / "examples/hello.motion.json")
    result = render_preview(spec, tmp_path / "hello", mp4=False, scale=0.1)
    frames = sorted((tmp_path / "hello" / "frames").glob("*.png"))
    assert len(frames) == 90
    assert frames[0].name == "000000.png"
    assert frames[-1].name == "000089.png"
    assert result["frameCount"] == 90
    assert result["outputs"][0]["frameCount"] == 90
    assert json.loads((tmp_path / "hello" / "render-manifest.json").read_text(encoding="utf-8"))["specSha256"] == result["specSha256"]


def test_optional_mp4_encode(tmp_path):
    ffmpeg = pytest.importorskip("imageio_ffmpeg")
    spec = load_spec(ROOT / "examples/hello.motion.json")
    result = render_preview(spec, tmp_path / "encoded", scale=0.1)
    video = tmp_path / "encoded" / "preview.mp4"
    assert video.is_file() and video.stat().st_size > 1000
    assert result["outputs"][1]["kind"] == "video/mp4"
    decoded = ffmpeg.read_frames(str(video))
    metadata = next(decoded)
    assert metadata["fps"] == 30
    assert sum(1 for _ in decoded) == 90


def test_voice_is_reported_as_unsupported():
    spec = copy.deepcopy(load_spec(ROOT / "examples/hello.motion.json"))
    spec["timeline"][0]["beats"][0]["voice"] = {"value": "Spoken line"}
    result = plan(spec)
    assert not result["buildable"]
    assert "voice_audio" in result["capabilities"][0]["unsupportedFeatures"]
    with pytest.raises(RenderError, match="voice audio"):
        FrameRenderer(spec, scale=0.1)


def test_unknown_visual_parameter_is_not_silently_ignored():
    spec = copy.deepcopy(load_spec(ROOT / "examples/hello.motion.json"))
    spec["timeline"][0]["elements"][0]["params"]["dropShadow"] = True
    result = plan(spec)
    assert not result["buildable"]
    assert "parameter:dropShadow" in result["capabilities"][0]["unsupportedFeatures"]
    with pytest.raises(RenderError, match="unsupported preview parameters"):
        FrameRenderer(spec, scale=0.1)


@pytest.mark.parametrize("change,expected", [
    ("transition", "transition:fade"),
    ("animation", "animation:reveal:title"),
])
def test_unsupported_motion_is_reported_before_rendering(change, expected):
    spec = copy.deepcopy(load_spec(ROOT / "examples/hello.motion.json"))
    if change == "transition":
        spec["timeline"][0]["transitionIn"] = "fade"
    else:
        spec["timeline"][0]["animations"][0]["property"] = "reveal"
    result = plan(spec)
    assert expected in result["capabilities"][0]["unsupportedFeatures"]
    with pytest.raises(RenderError, match="unsupported preview"):
        FrameRenderer(spec, scale=0.1)


@pytest.mark.parametrize("example,fit", [("hello.motion.json", "contain"), ("weather.motion.json", "cover")])
def test_hashed_image_asset_renders_in_different_projects(tmp_path, example, fit):
    asset_path = tmp_path / "plate.png"
    Image.new("RGBA", (60, 20), (255, 0, 0, 255)).save(asset_path)
    spec = copy.deepcopy(load_spec(ROOT / "examples" / example))
    if example == "weather.motion.json" and not features.check("raqm"):
        spec["project"]["direction"] = "ltr"
        spec["timeline"][0]["elements"][0]["text"].update({"value": "Weather", "direction": "ltr"})
    spec["assets"].append({"id": "plate_asset", "kind": "image", "status": "available", "uri": "plate.png", "sha256": hashlib.sha256(asset_path.read_bytes()).hexdigest()})
    scene = spec["timeline"][0]
    scene["elements"].append({"id": "plate", "kind": "image", "startFrame": 0, "endFrameExclusive": scene["endFrameExclusive"], "bounds": {"x": 0, "y": 0, "width": 120, "height": 120}, "assetId": "plate_asset", "params": {"fit": fit}, "zIndex": -1})
    assert not plan(spec)["capabilities"][0]["unsupportedKinds"]
    renderer = FrameRenderer(spec, scale=1, asset_root=tmp_path)
    frame = renderer.render_frame(0)
    assert frame.getpixel((60, 60)) == (255, 0, 0)
    if fit == "contain":
        assert frame.getpixel((60, 1)) != (255, 0, 0)
    else:
        assert frame.getpixel((60, 1)) == (255, 0, 0)


@pytest.mark.parametrize("example", ["hello.motion.json", "image-card.motion.json"])
def test_image_zoom_is_frame_exact_and_clipped_to_its_bounds(tmp_path, example):
    plate = Image.new("RGB", (100, 100), (0, 0, 255))
    Image.Image.paste(plate, (255, 0, 0), (25, 25, 75, 75))
    plate.save(tmp_path / "zoom.png")
    spec = copy.deepcopy(load_spec(ROOT / "examples" / example))
    scene = spec["timeline"][0]
    end = scene["endFrameExclusive"]
    spec["assets"].append({"id": "zoom_asset", "kind": "image", "status": "available",
                           "uri": "zoom.png", "sha256": hashlib.sha256((tmp_path / "zoom.png").read_bytes()).hexdigest()})
    scene["elements"] = [{"id": "zoom_plate", "kind": "image", "startFrame": 0,
                              "endFrameExclusive": end, "bounds": {"x": 80, "y": 80, "width": 100, "height": 100},
                              "assetId": "zoom_asset", "params": {"fit": "contain"}, "zIndex": -1}]
    for beat in scene["beats"]:
        beat["elementIds"] = ["zoom_plate"]
    scene["animations"] = [{"targetId": "zoom_plate", "property": "scale",
                                "keyframes": [{"frame": 0, "value": 1},
                                              {"frame": end - 1, "value": 2, "easing": "linear"}]}]
    assert plan(spec)["capabilities"][0]["buildable"]
    renderer = FrameRenderer(spec, asset_root=tmp_path)
    assert renderer.render_frame(0).getpixel((90, 90)) == (0, 0, 255)
    assert renderer.render_frame(end - 1).getpixel((90, 90)) == (255, 0, 0)
    assert renderer.render_frame(end - 1).getpixel((79, 90)) == (16, 24, 32)

    scene["animations"][-1]["keyframes"][-1]["value"] = 0.5
    assert "animation_value:scale:zoom_plate" in plan(spec)["capabilities"][0]["unsupportedFeatures"]
    with pytest.raises(RenderError, match="scale keyframes"):
        FrameRenderer(spec, asset_root=tmp_path)


def test_image_rotation_is_clockwise_frame_exact_and_clipped(tmp_path):
    plate = Image.new("RGB", (100, 100), (0, 0, 255))
    Image.Image.paste(plate, (255, 0, 0), (0, 0, 100, 50))
    plate.save(tmp_path / "rotate.png")
    spec = copy.deepcopy(load_spec(ROOT / "examples" / "image-card.motion.json"))
    spec["assets"][0].update({"uri": "rotate.png", "sha256": hashlib.sha256((tmp_path / "rotate.png").read_bytes()).hexdigest()})
    scene = spec["timeline"][0]
    element = scene["elements"][0]
    element["bounds"] = {"x": 80, "y": 80, "width": 100, "height": 100}
    scene["animations"] = [{"targetId": element["id"], "property": "rotation", "keyframes": [
        {"frame": 0, "value": 0}, {"frame": 95, "value": 90, "easing": "linear"}]}]
    assert plan(spec)["capabilities"][0]["buildable"]
    renderer = FrameRenderer(spec, asset_root=tmp_path)
    assert renderer.render_frame(0).getpixel((90, 90)) == (255, 0, 0)
    rotated = renderer.render_frame(95)
    assert rotated.getpixel((90, 130)) == (0, 0, 255)
    assert rotated.getpixel((170, 130)) == (255, 0, 0)
    assert rotated.getpixel((79, 130)) == (16, 24, 32)
    scene["animations"][0]["keyframes"][-1]["value"] = 361
    assert "animation_value:rotation:plate" in plan(spec)["capabilities"][0]["unsupportedFeatures"]
    with pytest.raises(RenderError, match="rotation keyframes"):
        FrameRenderer(spec, asset_root=tmp_path)


def test_image_asset_hash_mismatch_stops_before_output(tmp_path):
    Image.new("RGB", (4, 4), (255, 0, 0)).save(tmp_path / "plate.png")
    spec = copy.deepcopy(load_spec(ROOT / "examples/hello.motion.json"))
    spec["assets"].append({"id": "plate_asset", "kind": "image", "status": "available", "uri": "plate.png", "sha256": "0" * 64})
    spec["timeline"][0]["elements"].append({"id": "plate", "kind": "image", "startFrame": 0, "endFrameExclusive": 90, "bounds": {"x": 0, "y": 0, "width": 30, "height": 30}, "assetId": "plate_asset", "params": {}})
    with pytest.raises(RenderError, match="hash mismatch"):
        render_preview(spec, tmp_path / "out", mp4=False, scale=0.1, asset_root=tmp_path)
    assert not (tmp_path / "out").exists()


def test_image_asset_cannot_escape_root(tmp_path):
    spec = copy.deepcopy(load_spec(ROOT / "examples/hello.motion.json"))
    spec["assets"].append({"id": "plate_asset", "kind": "image", "status": "available", "uri": "../plate.png", "sha256": "0" * 64})
    spec["timeline"][0]["elements"].append({"id": "plate", "kind": "image", "startFrame": 0, "endFrameExclusive": 90, "bounds": {"x": 0, "y": 0, "width": 30, "height": 30}, "assetId": "plate_asset", "params": {}})
    with pytest.raises(RenderError, match="portable relative file URI"):
        FrameRenderer(spec, asset_root=tmp_path)


def test_planner_rejects_missing_image_source():
    spec = copy.deepcopy(load_spec(ROOT / "examples/image-card.motion.json"))
    del spec["assets"][0]["sha256"]
    report = plan(spec)
    assert not report["buildable"]
    assert "image_asset:plate" in report["capabilities"][0]["unsupportedFeatures"]


def test_failed_render_leaves_no_partial_output(tmp_path):
    spec = copy.deepcopy(load_spec(ROOT / "examples/weather.motion.json"))
    spec["project"]["direction"] = "ltr"
    spec["timeline"][0]["elements"][0]["text"].update({"value": "Weather", "direction": "ltr"})
    spec["timeline"][0]["elements"][1]["params"]["maximum"] = 0
    with pytest.raises(RenderError, match="maximum greater than minimum"):
        render_preview(spec, tmp_path / "bad", mp4=False, scale=0.1)
    assert not (tmp_path / "bad").exists()
    assert not list(tmp_path.iterdir())
