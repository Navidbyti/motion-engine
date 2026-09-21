import json
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from motion_engine.director import DirectorError, compile_director_plan
from motion_engine.planning import plan
from motion_engine.rendering import FrameRenderer
from motion_engine.validation import validate


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name,size", [
    ("card-horizontal", (640, 360)),
    ("card-vertical", (360, 640)),
])
def test_director_fade_through_background_is_frame_exact(tmp_path, name, size):
    proposal = json.loads((ROOT / "examples" / f"{name}.plan.json").read_text(encoding="utf-8"))
    proposal["scenes"][1].update({"transition": "fade", "transitionFrames": 12})
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Make two cards with a soft scene transition.", encoding="utf-8")
    spec = compile_director_plan(prompt, tmp_path / "draft.motion.json", proposal,
                                 project_id="transition_cards", width=size[0], height=size[1], fps=24)
    assert not validate(spec)
    assert plan(spec)["buildable"]
    renderer = FrameRenderer(spec, scale=0.25, asset_root=tmp_path)
    background = Image.new("RGB", (renderer.width, renderer.height), renderer.background)
    for frame, opacity in ((17, 1), (18, 6 / 7), (23, 1 / 7),
                           (24, 1 / 7), (29, 6 / 7), (30, 1)):
        scene = spec["timeline"][0 if frame < 24 else 1]
        raw = renderer._scene_frame(scene, frame)
        expected = raw if opacity == 1 else Image.blend(background, raw, opacity)
        assert ImageChops.difference(renderer.render_frame(frame), expected).getbbox() is None


@pytest.mark.parametrize("transition,frames,message", [
    ("fade", None, "needs 2 to 120"),
    ("cut", 8, "cut cannot"),
    ("wipe", None, "unsupported"),
])
def test_director_rejects_incomplete_or_unknown_transitions(tmp_path, transition, frames, message):
    proposal = json.loads((ROOT / "examples/card-horizontal.plan.json").read_text(encoding="utf-8"))
    proposal["scenes"][1]["transition"] = transition
    if frames is not None:
        proposal["scenes"][1]["transitionFrames"] = frames
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Make two cards.", encoding="utf-8")
    with pytest.raises(DirectorError, match=message):
        compile_director_plan(prompt, tmp_path / "draft.motion.json", proposal,
                              project_id="bad_transition", width=640, height=360, fps=24)


def test_fade_window_must_fit_both_adjacent_scenes(tmp_path):
    proposal = json.loads((ROOT / "examples/card-horizontal.plan.json").read_text(encoding="utf-8"))
    proposal["scenes"][1].update({"transition": "fade", "transitionFrames": 25})
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Make two cards.", encoding="utf-8")
    with pytest.raises(DirectorError, match="invalid"):
        compile_director_plan(prompt, tmp_path / "draft.motion.json", proposal,
                              project_id="long_transition", width=640, height=360, fps=24)
