import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.cli import main
from motion_engine.director_schema import DIRECTOR_PLAN_SCHEMA
from motion_engine.revisions import freeze_revision, spec_sha256
from motion_engine.validation import load_spec


def test_director_schema_is_provider_neutral_and_accepts_examples():
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(DIRECTOR_PLAN_SCHEMA)
    for name in ("director-abstract", "director-plate"):
        proposal = json.loads((ROOT / "examples" / f"{name}.plan.json").read_text(encoding="utf-8"))
        assert not list(validator.iter_errors(proposal))


def test_agent_revision_request_renders_new_version(tmp_path):
    pytest.importorskip("imageio_ffmpeg")
    original = load_spec(ROOT / "examples/director-plate.motion.json")
    for item in original["sources"] + original["assets"]:
        destination = tmp_path / item["uri"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "examples" / item["uri"], destination)
    base = tmp_path / "base.motion.json"
    base.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
    request = {"baseSpecSha256": spec_sha256(original), "sceneId": "scene_1",
               "userPrompt": "Change the title", "operations": [
                   {"op": "set_text", "elementId": "title_1", "value": "A new moving idea"}]}
    request_path = tmp_path / "revision.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    output_spec = tmp_path / "second.motion.json"
    render_dir = tmp_path / "second-preview"
    args = ["revise-and-render", str(base), str(request_path),
            "--output-spec", str(output_spec), "--output-dir", str(render_dir), "--scale", "0.5"]
    assert main(args) == 0
    assert (render_dir / "preview.mp4").is_file()
    revised = load_spec(output_spec)
    assert revised["timeline"][0]["elements"][-1]["text"]["value"] == "A new moving idea"
    assert freeze_revision(revised, tmp_path)["revisionSha256"]
    assert main(args) == 2
