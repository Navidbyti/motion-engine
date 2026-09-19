import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.ai_script import AIExportError, make_ai_script
from motion_engine.validation import load_spec


@pytest.mark.parametrize("fixture,boards", [
    ("ai-card.motion.json", 1), ("ai-vertical.motion.json", 2),
])
def test_ai_script_has_reopen_checks_for_editable_artboards(tmp_path, fixture, boards):
    spec = load_spec(ROOT / "examples" / fixture)
    script, output, report = (tmp_path / name for name in ("build.jsx", "result.ai", "report.txt"))
    assert make_ai_script(spec, script, output, report) == script
    content = script.read_text(encoding="utf-8")
    payload = json.loads(content.removeprefix("var job = ").split(";\n", 1)[0])
    assert payload["spec"] == spec
    assert len(payload["spec"]["timeline"]) == boards
    assert "doc.saveAs(output, options)" in content
    assert "doc = app.open(output)" in content
    assert "reopened artboard size mismatch" in content
    assert "reopened font mismatch" in content
    assert "reopened background missing" in content
    with pytest.raises(AIExportError, match="already exist"):
        make_ai_script(spec, script, output, report)


def test_ai_script_rejects_motion_and_unsupported_artwork(tmp_path):
    source = load_spec(ROOT / "examples/ai-card.motion.json")
    paths = (tmp_path / "build.jsx", tmp_path / "result.ai", tmp_path / "report.txt")
    with pytest.raises(AIExportError, match="distinct paths"):
        make_ai_script(source, paths[0], paths[0], paths[2])
    spec = copy.deepcopy(source)
    spec["timeline"][0]["animations"] = [{"targetId": "title", "property": "opacity", "keyframes": [
        {"frame": 0, "value": 0}, {"frame": 12, "value": 1}]}]
    with pytest.raises(AIExportError, match="cannot preserve animation"):
        make_ai_script(spec, *paths)
    spec = copy.deepcopy(source)
    spec["timeline"][0]["elements"][0]["kind"] = "chart.bar"
    with pytest.raises(AIExportError, match="does not support chart.bar"):
        make_ai_script(spec, *paths)
    spec = copy.deepcopy(source)
    spec["timeline"][0]["elements"][0]["startFrame"] = 10
    with pytest.raises(AIExportError, match="whole static scene"):
        make_ai_script(spec, *paths)
