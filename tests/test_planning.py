import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.planning import load_capabilities, plan
from motion_engine.validation import load_spec, validate_semantics


def test_public_examples_make_general_frame_plans():
    hello = load_spec(ROOT / "examples/hello.motion.json")
    weather = load_spec(ROOT / "examples/weather.motion.json")
    for spec in (hello, weather):
        assert validate_semantics(spec) == []
        result = plan(spec)
        assert result["canvas"]["durationFrames"] == spec["canvas"]["durationFrames"]
        assert result["scenes"][0]["beats"][-1]["endFrameExclusive"] == spec["canvas"]["durationFrames"]
        assert not result["buildable"]
        assert all(issue["severity"] != "error" for issue in result["issues"])
    assert plan(hello)["requestedKinds"] == ["text"]
    assert plan(weather)["requestedKinds"] == ["chart.bar", "text"]


def test_capability_manifest_can_add_a_working_target(tmp_path):
    manifest = tmp_path / "capabilities.json"
    manifest.write_text(json.dumps({"targets": [{"target": "video/mp4", "status": "available", "supportedKinds": ["text", "chart.bar"], "editableKinds": [], "version": "test-only"}]}), encoding="utf-8")
    capabilities = load_capabilities(manifest)
    for name in ("hello", "weather"):
        spec = load_spec(ROOT / "examples" / f"{name}.motion.json")
        assert plan(spec, capabilities)["buildable"]


def test_required_unknown_kind_is_reported():
    spec = copy.deepcopy(load_spec(ROOT / "examples/weather.motion.json"))
    spec["timeline"][0]["elements"][1]["kind"] = "plugin.unknown"
    result = plan(spec)
    assert not result["buildable"]
    assert any(issue["code"] == "capability_gap" and issue["severity"] == "error" for issue in result["issues"])
