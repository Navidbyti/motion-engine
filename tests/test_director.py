import json
import sys
from pathlib import Path

import pytest
from PIL import ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.cli import main
from motion_engine.director import DirectorError, compile_director_plan
from motion_engine.planning import plan
from motion_engine.rendering import FrameRenderer
from motion_engine.revisions import freeze_revision
from motion_engine.validation import load_spec, validate


@pytest.mark.parametrize("name,assets_file,duration", [
    ("director-abstract", None, 48),
    ("director-plate", "director-plate.assets.json", 24),
])
def test_public_director_plans_compile_to_whole_renderable_drafts(name, assets_file, duration):
    examples = ROOT / "examples"
    proposal_file = examples / f"{name}.plan.json"
    proposal = json.loads(proposal_file.read_text(encoding="utf-8"))
    assets = json.loads((examples / assets_file).read_text(encoding="utf-8")) if assets_file else None
    spec = compile_director_plan(examples / "assets" / f"{name}.txt",
                                 examples / f"{name}.motion.json", proposal,
                                 project_id=name.replace("-", "_"), width=320, height=180,
                                 fps=24, assets=assets, proposal_path=proposal_file)
    assert spec == load_spec(examples / f"{name}.motion.json")
    assert not validate(spec)
    assert plan(spec)["capabilities"][0]["buildable"]
    assert freeze_revision(spec, examples)["revisionSha256"]
    renderer = FrameRenderer(spec, asset_root=examples)
    assert renderer.duration == duration
    assert ImageChops.difference(renderer.render_frame(0), renderer.render_frame(duration - 1)).getbbox()


def test_shape_accent_sits_between_title_and_subtitle():
    spec = load_spec(ROOT / "examples/director-abstract.motion.json")
    scene = next(scene for scene in spec["timeline"] if any(e["id"] == "accent_2" for e in scene["elements"]))
    elements = {item["id"]: item for item in scene["elements"]}
    title, accent, subtitle = (elements[name]["bounds"] for name in ("title_2", "accent_2", "subtitle_2"))
    assert title["y"] + title["height"] <= accent["y"]
    assert accent["y"] + accent["height"] <= subtitle["y"]


@pytest.mark.parametrize("name,size", [
    ("card-horizontal", (640, 360)),
    ("card-vertical", (360, 640)),
])
def test_card_layout_public_fixtures_render_with_contrasting_text(tmp_path, name, size):
    from jsonschema import Draft202012Validator

    from motion_engine.director_schema import DIRECTOR_PLAN_SCHEMA

    examples = ROOT / "examples"
    proposal = json.loads((examples / f"{name}.plan.json").read_text(encoding="utf-8"))
    assert not list(Draft202012Validator(DIRECTOR_PLAN_SCHEMA).iter_errors(proposal))
    prompt = tmp_path / "prompt.txt"
    prompt.write_text((examples / "assets" / f"{name}.txt").read_text(encoding="utf-8"), encoding="utf-8")
    spec = compile_director_plan(prompt, tmp_path / "card.motion.json", proposal,
                                 project_id="card_study", width=size[0], height=size[1], fps=24)
    assert not validate(spec)
    for scene, source in zip(spec["timeline"], proposal["scenes"]):
        card = next(element for element in scene["elements"] if element["id"].startswith("card_"))
        texts = [element for element in scene["elements"] if element["kind"] == "text"]
        assert card["params"]["color"] == source["accent"]
        assert all(card["bounds"]["x"] < item["bounds"]["x"]
                   and item["bounds"]["x"] + item["bounds"]["width"]
                   < card["bounds"]["x"] + card["bounds"]["width"] for item in texts)
        assert all(item["params"]["color"] in ("#000000", "#FFFFFF") for item in texts)
        channels = [int(source["accent"][index:index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
                  for value in channels]
        luminance = sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
        assert all(((luminance + 0.05) / 0.05 if item["params"]["color"] == "#000000"
                    else 1.05 / (luminance + 0.05)) >= 4.5 for item in texts)
        if source["motion"] == "rise":
            title_y = next(animation for animation in scene["animations"]
                           if animation["targetId"].startswith("title_") and animation["property"] == "y")
            assert title_y["keyframes"][0]["value"] > title_y["keyframes"][-1]["value"]
            assert any(animation["property"] == "opacity" and animation["targetId"].startswith("title_")
                       for animation in scene["animations"])
    renderer = FrameRenderer(spec, asset_root=tmp_path)
    assert ImageChops.difference(renderer.render_frame(12), renderer.render_frame(36)).getbbox()


def test_card_layout_rejects_asset_only_zoom(tmp_path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Show a card", encoding="utf-8")
    proposal = json.loads((ROOT / "examples/card-horizontal.plan.json").read_text(encoding="utf-8"))
    proposal["scenes"][0]["motion"] = "zoom"
    with pytest.raises(DirectorError, match="zoom needs an image"):
        compile_director_plan(prompt, tmp_path / "card.motion.json", proposal,
                              project_id="card_study", width=640, height=360, fps=24)


def test_slide_motion_moves_title_from_offscreen(tmp_path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("A short title with a slide entrance.", encoding="utf-8")
    proposal = json.loads((ROOT / "examples/director-abstract.plan.json").read_text(encoding="utf-8"))
    proposal["scenes"][0]["motion"] = "slide"
    spec = compile_director_plan(prompt, tmp_path / "slide.motion.json", proposal,
                                 project_id="slide_title", width=320, height=180, fps=24)
    title_track = next(animation for animation in spec["timeline"][0]["animations"]
                       if animation["targetId"] == "title_1" and animation["property"] == "x")
    assert title_track["keyframes"][0]["value"] < 0
    assert title_track["keyframes"][-1]["value"] == spec["canvas"]["safeArea"]["left"]
    renderer = FrameRenderer(spec, asset_root=tmp_path)
    assert ImageChops.difference(renderer.render_frame(0), renderer.render_frame(20)).getbbox()
    proposal["direction"] = "rtl"
    rtl = compile_director_plan(prompt, tmp_path / "rtl.motion.json", proposal,
                                project_id="slide_rtl", width=320, height=180, fps=24)
    rtl_track = next(animation for animation in rtl["timeline"][0]["animations"]
                     if animation["targetId"] == "title_1" and animation["property"] == "x")
    assert rtl_track["keyframes"][0]["value"] == 320


def test_director_research_and_missing_asset_are_explicit(tmp_path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Create a researched explainer about a historical claim.", encoding="utf-8")
    proposal = json.loads((ROOT / "examples/director-abstract.plan.json").read_text(encoding="utf-8"))
    proposal["researchRequired"] = True
    with pytest.raises(DirectorError, match="research-required"):
        compile_director_plan(prompt, tmp_path / "draft.json", proposal,
                              project_id="draft", width=320, height=180, fps=24)
    proposal["researchRequired"] = False
    proposal["assetRequests"] = [{"id": "coin", "kind": "3d",
                                  "description": "A rotating metallic coin in depth", "durationFrames": 90}]
    with pytest.raises(DirectorError, match="unresolved visual assets"):
        compile_director_plan(prompt, tmp_path / "draft.json", proposal,
                              project_id="draft", width=320, height=180, fps=24)
    proposal["assetRequests"] = []
    proposal["scenes"][0]["visual"] = "asset"
    proposal["scenes"][0]["assetId"] = "coin_plate"
    with pytest.raises(DirectorError, match="unavailable asset"):
        compile_director_plan(prompt, tmp_path / "draft.json", proposal,
                              project_id="draft", width=320, height=180, fps=24)


def test_director_cli_compiles_and_refuses_overwrite(tmp_path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Make a colorful two-scene title video.", encoding="utf-8")
    proposal_file = tmp_path / "plan.json"
    proposal_file.write_text((ROOT / "examples/director-abstract.plan.json").read_text(encoding="utf-8"), encoding="utf-8")
    output = tmp_path / "draft.motion.json"
    command = ["compile-director", str(prompt), str(proposal_file), "--output", str(output),
               "--project-id", "colorful", "--width", "320", "--height", "180", "--fps", "24"]
    assert main(command) == 0
    assert main(command) == 2
    assert not validate(load_spec(output))


def test_first_draft_orchestrates_agent_plan_spec_and_video(tmp_path):
    pytest.importorskip("imageio_ffmpeg")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Make a colorful two-scene title video.", encoding="utf-8")
    plan_file = tmp_path / "plan.json"
    plan_file.write_text((ROOT / "examples/director-abstract.plan.json").read_text(encoding="utf-8"), encoding="utf-8")
    spec_file = tmp_path / "first.motion.json"
    render_dir = tmp_path / "render"
    review_dir = tmp_path / "review"
    args = ["first-draft", str(prompt), str(plan_file), "--project-id", "first",
            "--output-spec", str(spec_file),
            "--output-dir", str(render_dir), "--review-dir", str(review_dir),
            "--width", "320", "--height", "180",
            "--fps", "24", "--scale", "0.5"]
    assert main(args) == 0
    assert (render_dir / "preview.mp4").is_file()
    qa = json.loads((render_dir / "qa.json").read_text(encoding="utf-8"))
    assert qa["status"] in ("passed", "needs_review")
    assert not any(issue["severity"] == "error" for issue in qa["issues"])
    assert (review_dir / "sheet-001.png").is_file()
    assert len(json.loads((review_dir / "contact-sheet.json").read_text(encoding="utf-8"))["scenes"]) == 2
    assert freeze_revision(load_spec(spec_file), tmp_path)["revisionSha256"]
    assert main(args) == 2
