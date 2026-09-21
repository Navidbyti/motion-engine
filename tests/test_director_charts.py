import json
import shutil
from pathlib import Path

import pytest
from PIL import ImageChops

from motion_engine.cli import main
from motion_engine.data_import import import_dataset
from motion_engine.director import DirectorError, compile_director_plan
from motion_engine.planning import plan
from motion_engine.qa import qa_report
from motion_engine.rendering import FrameRenderer
from motion_engine.validation import load_spec, validate


ROOT = Path(__file__).resolve().parents[1]


def _project(tmp_path: Path, visual: str = "bar_chart") -> tuple[Path, dict, dict, Path]:
    assets = tmp_path / "assets"
    assets.mkdir()
    shutil.copyfile(ROOT / "examples/assets/weather.csv", assets / "weather.csv")
    fragment = import_dataset(assets / "weather.csv", tmp_path, "temperatures", "weather_csv")
    fragment_path = tmp_path / "weather.fragment.json"
    fragment_path.write_text(json.dumps(fragment), encoding="utf-8")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Compare three synthetic temperatures.", encoding="utf-8")
    proposal = json.loads((ROOT / "examples/card-horizontal.plan.json").read_text(encoding="utf-8"))
    proposal["scenes"] = [proposal["scenes"][0]]
    proposal["scenes"][0].update({
        "durationFrames": 48, "visual": visual, "title": "Temperature comparison",
        "subtitle": "Synthetic test data", "motion": "fade",
        "chartDatasetId": "temperatures", "chartValueField": "temperatureC",
        "chartCategoryField": "city", "chartMinimum": 0, "chartMaximum": 40,
    })
    return prompt, proposal, fragment, fragment_path


@pytest.mark.parametrize("visual,size", [
    ("bar_chart", (640, 360)),
    ("line_chart", (360, 640)),
])
def test_director_compiles_source_checked_charts_in_two_formats(tmp_path, visual, size):
    prompt, proposal, fragment, _ = _project(tmp_path, visual)
    spec = compile_director_plan(prompt, tmp_path / "chart.motion.json", proposal,
                                 project_id="data_chart", width=size[0], height=size[1], fps=24,
                                 data_fragments=[fragment])
    assert not validate(spec)
    assert plan(spec)["buildable"]
    chart = next(element for element in spec["timeline"][0]["elements"]
                 if element["kind"].startswith("chart."))
    assert chart["dataBinding"] == {"datasetId": "temperatures", "field": "temperatureC"}
    assert chart["sourceRefs"] == fragment["dataset"]["sourceRefs"]
    assert fragment["dataset"]["sourceRefs"][0] in spec["timeline"][0]["sourceRefs"]
    assert fragment["dataset"]["sourceRefs"][0] in spec["timeline"][0]["beats"][0]["sourceRefs"]
    assert any(rule["rule"] == "chart.data_exact" for rule in spec["policies"]["qa"])
    assert not any(issue["code"].startswith("data_") for issue in qa_report(spec, tmp_path)["issues"])
    renderer = FrameRenderer(spec, scale=0.25, asset_root=tmp_path)
    assert ImageChops.difference(renderer.render_frame(8), renderer.render_frame(30)).getbbox()


def test_first_draft_cli_accepts_imported_dataset_fragment(tmp_path):
    pytest.importorskip("imageio_ffmpeg")
    prompt, proposal, _, fragment_path = _project(tmp_path)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(proposal), encoding="utf-8")
    spec_path, render_path = tmp_path / "chart.motion.json", tmp_path / "preview"
    assert main(["first-draft", str(prompt), str(plan_path), "--project-id", "chart_cli",
                 "--output-spec", str(spec_path), "--output-dir", str(render_path),
                 "--data-fragment", str(fragment_path), "--width", "320", "--height", "180",
                 "--fps", "24", "--scale", "0.2"]) == 0
    assert (render_path / "preview.mp4").is_file()
    assert load_spec(spec_path)["datasets"][0]["id"] == "temperatures"
    assert json.loads((render_path / "qa.json").read_text(encoding="utf-8"))["status"] == "passed"


@pytest.mark.parametrize("change,message", [
    ({"chartDatasetId": "missing"}, "unavailable dataset"),
    ({"chartValueField": "city"}, "value field must be numeric"),
    ({"chartCategoryField": "missing"}, "category field is unavailable"),
    ({"chartMaximum": 25}, "clips values"),
])
def test_director_rejects_unavailable_or_misleading_chart_bindings(tmp_path, change, message):
    prompt, proposal, fragment, _ = _project(tmp_path)
    proposal["scenes"][0].update(change)
    with pytest.raises(DirectorError, match=message):
        compile_director_plan(prompt, tmp_path / "chart.motion.json", proposal,
                              project_id="bad_chart", width=640, height=360, fps=24,
                              data_fragments=[fragment])
