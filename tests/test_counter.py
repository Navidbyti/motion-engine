import json
from pathlib import Path

import pytest
from PIL import ImageChops

from motion_engine.director import DirectorError, compile_director_plan
from motion_engine.planning import plan
from motion_engine.qa import qa_report
from motion_engine.rendering import FrameRenderer, RenderError
from motion_engine.validation import validate


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("size", [(640, 360), (360, 640)])
def test_director_counter_is_structured_animated_and_renderable(tmp_path, size):
    proposal = json.loads((ROOT / "examples/card-horizontal.plan.json").read_text(encoding="utf-8"))
    proposal["scenes"] = [proposal["scenes"][0]]
    proposal["scenes"][0].update({
        "visual": "counter", "title": "Ten years", "subtitle": "Assets tracked",
        "counterValue": 1250.5, "counterStartValue": 1000,
        "counterDecimals": 1, "counterPrefix": "$", "counterSuffix": "M", "motion": "rise",
    })
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Show assets increasing to $1250.5M.", encoding="utf-8")
    spec = compile_director_plan(prompt, tmp_path / "counter.motion.json", proposal,
                                 project_id="counter_card", width=size[0], height=size[1], fps=30)
    assert not validate(spec)
    assert plan(spec)["buildable"]
    scene = spec["timeline"][0]
    counter = next(element for element in scene["elements"] if element["kind"] == "counter")
    assert counter["params"]["endValue"] == 1250.5
    assert {item["value"] for item in scene["beats"][0]["onScreen"]} >= {"$1250.5M"}
    track = next(item for item in scene["animations"] if item["targetId"] == counter["id"])
    assert track["property"] == "value"
    assert track["keyframes"][0]["value"] == 1000
    assert track["keyframes"][-1]["value"] == 1250.5
    renderer = FrameRenderer(spec, scale=0.25, asset_root=tmp_path)
    assert ImageChops.difference(renderer.render_frame(0), renderer.render_frame(23)).getbbox()


@pytest.mark.parametrize("changes,message", [
    ({"counterValue": float("inf")}, "counter values"),
    ({"counterDecimals": 7}, "counter values"),
    ({"counterPrefix": "x" * 33}, "counter values"),
])
def test_director_rejects_invalid_counter_fields(tmp_path, changes, message):
    proposal = json.loads((ROOT / "examples/card-horizontal.plan.json").read_text(encoding="utf-8"))
    proposal["scenes"] = [proposal["scenes"][0]]
    proposal["scenes"][0].update({"visual": "counter", "counterValue": 10, **changes})
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Show a number.", encoding="utf-8")
    with pytest.raises(DirectorError, match=message):
        compile_director_plan(prompt, tmp_path / "counter.motion.json", proposal,
                              project_id="bad_counter", width=640, height=360, fps=30)


def test_counter_rejects_nonfinite_animation_before_render(tmp_path):
    proposal = json.loads((ROOT / "examples/card-horizontal.plan.json").read_text(encoding="utf-8"))
    proposal["scenes"] = [proposal["scenes"][0]]
    proposal["scenes"][0].update({"visual": "counter", "counterValue": 10})
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Show a number.", encoding="utf-8")
    spec = compile_director_plan(prompt, tmp_path / "counter.motion.json", proposal,
                                 project_id="bad_counter_track", width=640, height=360, fps=30)
    track = next(item for item in spec["timeline"][0]["animations"] if item["property"] == "value")
    track["keyframes"][-1]["value"] = float("nan")
    assert "animation_value:value:counter_1" in plan(spec)["capabilities"][0]["unsupportedFeatures"]
    with pytest.raises(RenderError, match="finite numbers"):
        FrameRenderer(spec, asset_root=tmp_path)


def test_counter_bounds_participate_in_text_safe_area_qa(tmp_path):
    proposal = json.loads((ROOT / "examples/card-horizontal.plan.json").read_text(encoding="utf-8"))
    proposal["scenes"] = [proposal["scenes"][0]]
    proposal["scenes"][0].update({"visual": "counter", "counterValue": 10})
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Show a number.", encoding="utf-8")
    spec = compile_director_plan(prompt, tmp_path / "counter.motion.json", proposal,
                                 project_id="counter_qa", width=640, height=360, fps=30)
    counter = next(element for element in spec["timeline"][0]["elements"] if element["kind"] == "counter")
    counter["bounds"]["x"] = 0
    spec["policies"]["qa"] = [{"id": "safe", "rule": "text.within_safe_area", "severity": "error"}]
    report = qa_report(spec, tmp_path)
    assert any(issue.get("targetId") == counter["id"] and issue["code"] == "text_outside_safe_area"
               for issue in report["issues"])
