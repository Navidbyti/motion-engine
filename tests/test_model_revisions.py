import io
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine import cli
from motion_engine.cli import main
from motion_engine.model_revisions import ModelRevisionError, suggest_scene_revision
from motion_engine.revisions import freeze_revision, spec_sha256
from motion_engine.validation import load_spec


def _response(proposal):
    return io.BytesIO(json.dumps({"status": "completed", "output": [{"type": "message", "content": [
        {"type": "output_text", "text": json.dumps(proposal)}]}]}).encode())


def test_model_converts_scene_prompt_to_hash_bound_text_edit(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    spec = load_spec(ROOT / "examples/director-plate.motion.json")
    proposal = {"unsupportedReason": "", "operations": [{"action": "text", "elementId": "title_1",
        "text": "A different title", "color": "", "startScale": 1, "endScale": 1, "easing": "linear"}]}
    calls = []

    def fake_transport(request, timeout):
        calls.append(json.loads(request.data))
        return _response(proposal)

    result = suggest_scene_revision(spec, "scene_1", "Change the title to A different title",
                                    model="test-model", transport=fake_transport)
    assert result["baseSpecSha256"] == spec_sha256(spec)
    assert result["operations"] == [{"op": "set_text", "elementId": "title_1", "value": "A different title"}]
    assert calls[0]["text"]["format"]["strict"] is True
    assert calls[0]["model"] == "test-model"


def test_model_rejects_unsupported_requested_edit(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    spec = load_spec(ROOT / "examples/director-plate.motion.json")
    proposal = {"unsupportedReason": "Creating a new 3D asset is not available", "operations": []}
    with pytest.raises(ModelRevisionError, match="unsupported requested edit"):
        suggest_scene_revision(spec, "scene_1", "Replace the object with a new 3D model",
                               model="test-model", transport=lambda request, timeout: _response(proposal))


def test_prompt_revision_command_renders_new_version(tmp_path, monkeypatch):
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
    monkeypatch.setattr(cli, "suggest_scene_revision", lambda *args, **kwargs: request)
    output_spec = tmp_path / "second.motion.json"
    render_dir = tmp_path / "second-preview"
    args = ["prompt-revise", str(base), "--scene-id", "scene_1", "--instruction", "Change the title",
            "--model", "simulated-model", "--output-request", str(tmp_path / "revision.json"),
            "--output-spec", str(output_spec), "--output-dir", str(render_dir), "--scale", "0.5"]
    assert main(args) == 0
    assert (render_dir / "preview.mp4").is_file()
    revised = load_spec(output_spec)
    assert revised["timeline"][0]["elements"][-1]["text"]["value"] == "A new moving idea"
    assert freeze_revision(revised, tmp_path)["revisionSha256"]
    assert main(args) == 2
