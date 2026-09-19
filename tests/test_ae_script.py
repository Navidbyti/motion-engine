import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.ae_script import AEExportError, make_ae_script
from motion_engine.validation import load_spec


def _paths(tmp_path):
    return (tmp_path / "build.jsx", tmp_path / "result.aep", tmp_path / "report.txt")


@pytest.mark.parametrize("fixture", ["ae-card.motion.json", "ae-vertical.motion.json", "ae-shapes.motion.json", "ae-image.motion.json"])
def test_ae_script_embeds_text_project_and_reopen_checks(tmp_path, fixture):
    spec = load_spec(ROOT / "examples" / fixture)
    script, aep, report = _paths(tmp_path)
    assert make_ae_script(spec, script, aep, report, asset_root=ROOT / "examples") == script
    content = script.read_text(encoding="utf-8")
    payload = json.loads(content.removeprefix("var job = ").split(";\n", 1)[0])
    assert payload["spec"] == spec
    assert payload["aep"] == aep.as_posix()
    assert "app.project.save(outputFile)" in content
    assert "app.open(outputFile)" in content
    assert "reopened font mismatch" in content
    assert "reopened beat marker mismatch" in content
    if fixture == "ae-shapes.motion.json":
        assert "ADBE Vector Shape - Rect" in content
        assert "ADBE Vector Fill Color" in content
    if fixture == "ae-image.motion.json":
        assert payload["imageAssets"][0]["id"] == "synthetic_plate"
        assert "reopened image link missing" in content
    with pytest.raises(AEExportError, match="already exist"):
        make_ae_script(spec, script, aep, report, asset_root=ROOT / "examples")


def test_ae_script_rejects_unimplemented_features_and_path_collision(tmp_path):
    source = load_spec(ROOT / "examples/ae-card.motion.json")
    script, aep, report = _paths(tmp_path)
    with pytest.raises(AEExportError, match="distinct paths"):
        make_ae_script(source, script, script, report)
    spec = copy.deepcopy(source)
    spec["timeline"][0]["elements"][0]["kind"] = "chart.bar"
    with pytest.raises(AEExportError, match="does not support chart.bar"):
        make_ae_script(spec, script, aep, report)
    spec = copy.deepcopy(source)
    spec["timeline"][0]["animations"][0]["keyframes"][1]["easing"] = "ease_out"
    with pytest.raises(AEExportError, match="linear opacity"):
        make_ae_script(spec, script, aep, report)
    spec = copy.deepcopy(source)
    spec["timeline"][0]["elements"][0]["zIndex"] = 2
    with pytest.raises(AEExportError, match="zIndex"):
        make_ae_script(spec, script, aep, report)


def test_ae_image_import_rejects_changed_hash(tmp_path):
    spec = load_spec(ROOT / "examples/ae-image.motion.json")
    spec["assets"][0]["sha256"] = "0" * 64
    with pytest.raises(AEExportError, match="SHA-256 mismatch"):
        make_ae_script(spec, *_paths(tmp_path), asset_root=ROOT / "examples")
