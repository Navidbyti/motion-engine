import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.ps_script import PSExportError, make_ps_script
from motion_engine.validation import load_spec


@pytest.mark.parametrize("fixture", ["ps-card.motion.json", "ps-vertical.motion.json"])
def test_ps_script_embeds_editable_reopen_and_source_checks(tmp_path, fixture):
    spec = load_spec(ROOT / "examples" / fixture)
    paths = (tmp_path / "build.jsx", tmp_path / "result.psd", tmp_path / "report.txt")
    assert make_ps_script(spec, *paths) == paths[0]
    content = paths[0].read_text(encoding="utf-8")
    payload = json.loads(content.removeprefix("var job = ").split(";\n", 1)[0])
    assert payload["spec"] == spec
    assert "doc.saveAs(output, options, true)" in content
    assert "doc = app.open(output)" in content
    assert "reopened source provenance mismatch" in content
    assert "reopened editable text mismatch" in content
    with pytest.raises(PSExportError, match="already exist"):
        make_ps_script(spec, *paths)


def test_ps_script_rejects_motion_multiple_scenes_and_unknown_primitive(tmp_path):
    source = load_spec(ROOT / "examples/ps-card.motion.json")
    paths = (tmp_path / "build.jsx", tmp_path / "result.psd", tmp_path / "report.txt")
    with pytest.raises(PSExportError, match="distinct paths"):
        make_ps_script(source, paths[0], paths[0], paths[2])
    spec = copy.deepcopy(source)
    spec["timeline"][0]["animations"] = [{"targetId": "title", "property": "opacity", "keyframes": [
        {"frame": 0, "value": 0}, {"frame": 12, "value": 1}]}]
    with pytest.raises(PSExportError, match="cannot preserve animation"):
        make_ps_script(spec, *paths)
    spec = copy.deepcopy(source)
    spec["timeline"][0]["elements"][0]["kind"] = "chart.bar"
    with pytest.raises(PSExportError, match="does not support chart.bar"):
        make_ps_script(spec, *paths)
    spec = load_spec(ROOT / "examples/ai-vertical.motion.json")
    with pytest.raises(PSExportError, match="one static scene"):
        make_ps_script(spec, *paths)
