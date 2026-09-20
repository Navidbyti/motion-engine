import json
import sys
from pathlib import Path

import pytest
from PIL import ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.cli import main
from motion_engine import cli
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


def test_director_research_and_missing_asset_are_explicit(tmp_path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Create a researched explainer about a historical claim.", encoding="utf-8")
    proposal = json.loads((ROOT / "examples/director-abstract.plan.json").read_text(encoding="utf-8"))
    proposal["researchRequired"] = True
    with pytest.raises(DirectorError, match="research-required"):
        compile_director_plan(prompt, tmp_path / "draft.json", proposal,
                              project_id="draft", width=320, height=180, fps=24)
    proposal["researchRequired"] = False
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


def test_first_draft_orchestrates_model_plan_spec_and_video(tmp_path, monkeypatch):
    pytest.importorskip("imageio_ffmpeg")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Make a colorful two-scene title video.", encoding="utf-8")
    proposal = json.loads((ROOT / "examples/director-abstract.plan.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(cli, "suggest_director_plan", lambda text, **kwargs: proposal)
    plan_file = tmp_path / "plan.json"
    spec_file = tmp_path / "first.motion.json"
    render_dir = tmp_path / "render"
    args = ["first-draft", str(prompt), "--model", "simulated-model", "--project-id", "first",
            "--output-plan", str(plan_file), "--output-spec", str(spec_file),
            "--output-dir", str(render_dir), "--width", "320", "--height", "180",
            "--fps", "24", "--scale", "0.5"]
    assert main(args) == 0
    assert (render_dir / "preview.mp4").is_file()
    assert freeze_revision(load_spec(spec_file), tmp_path)["revisionSha256"]
    assert main(args) == 2
