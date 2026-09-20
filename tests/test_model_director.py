import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.model_director import ModelDirectorError, suggest_director_plan


def test_optional_model_planner_sends_strict_plan_schema_and_parses_response(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    proposal = json.loads((ROOT / "examples/director-abstract.plan.json").read_text(encoding="utf-8"))
    response = {"status": "completed", "output": [{"type": "message", "content": [
        {"type": "output_text", "text": json.dumps(proposal)}]}]}
    calls = []

    def fake_transport(request, timeout):
        calls.append((request, timeout))
        return io.BytesIO(json.dumps(response).encode())

    assert suggest_director_plan("Make a two-scene video", model="test-model",
                                 transport=fake_transport) == proposal
    request, timeout = calls[0]
    payload = json.loads(request.data)
    assert request.full_url == "https://api.openai.com/v1/responses"
    assert payload["model"] == "test-model" and timeout == 120
    assert payload["text"]["format"]["strict"] is True
    assert payload["text"]["format"]["schema"]["required"] == [
        "title", "locale", "direction", "researchRequired", "scenes"]


def test_optional_model_planner_requires_key_and_rejects_bad_output(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ModelDirectorError, match="OPENAI_API_KEY"):
        suggest_director_plan("Make a video", model="test-model")
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")

    def fake_transport(request, timeout):
        response = {"status": "completed", "output": [{"type": "message", "content": [
            {"type": "output_text", "text": '{"scenes": []}'}]}]}
        return io.BytesIO(json.dumps(response).encode())

    with pytest.raises(ModelDirectorError, match="outside the director schema"):
        suggest_director_plan("Make a video", model="test-model", transport=fake_transport)
