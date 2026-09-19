import copy
import sys
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.qa import qa_report
from motion_engine.validation import load_spec


def test_public_csv_chart_matches_every_mapped_cell():
    spec = load_spec(ROOT / "examples/weather.motion.json")
    issues = qa_report(spec, ROOT / "examples")["issues"]
    assert not any(issue["code"].startswith("data_") for issue in issues)


def test_changed_chart_value_and_missing_mapping_fail(tmp_path):
    spec = copy.deepcopy(load_spec(ROOT / "examples/weather.motion.json"))
    spec["datasets"][0]["rows"][0]["temperatureC"] = 32
    issues = qa_report(spec, ROOT / "examples")["issues"]
    assert any(issue["code"] == "data_value_mismatch" for issue in issues)
    spec["datasets"][0]["rows"][0]["temperatureC"] = 31
    del spec["datasets"][0]["transform"]["columnSources"]["temperatureC"]
    issues = qa_report(spec, ROOT / "examples")["issues"]
    assert any(issue["code"] == "data_mapping_missing" for issue in issues)
    spec["datasets"][0]["transform"]["columnSources"]["temperatureC"] = {"sourceId": "weather_csv", "location": "B2:B4"}
    spec["datasets"][0]["sourceRefs"] = []
    issues = qa_report(spec, ROOT / "examples")["issues"]
    assert any(issue["code"] == "data_source_unlinked" for issue in issues)


def test_xlsx_chart_cells_match_and_changes_fail(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Data"
    sheet.append(["city", "temperatureC"])
    for row in (("Cairo", 31), ("Rabat", 24), ("Tunis", 28)):
        sheet.append(row)
    source = tmp_path / "data.xlsx"
    workbook.save(source)
    spec = copy.deepcopy(load_spec(ROOT / "examples/weather.motion.json"))
    spec["sources"][0]["uri"] = "data.xlsx"
    spec["sources"][0]["mediaType"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    for reference in spec["datasets"][0]["transform"]["columnSources"].values():
        reference["location"] = f"'Data'!{reference['location']}"
    issues = qa_report(spec, tmp_path)["issues"]
    assert not any(issue["code"].startswith("data_") for issue in issues)
    sheet["B2"] = 99
    workbook.save(source)
    issues = qa_report(spec, tmp_path)["issues"]
    assert any(issue["code"] == "data_value_mismatch" for issue in issues)


def test_decimal_derived_chart_values_are_checked_without_eval(tmp_path):
    (tmp_path / "data.csv").write_text("year,nominal,fx\n2024,100,3\n2025,60,3\n", encoding="utf-8")
    spec = copy.deepcopy(load_spec(ROOT / "examples/weather.motion.json"))
    spec["sources"][0]["uri"] = "data.csv"
    spec["datasets"][0] = {
        "id": "temperatures",
        "columns": [{"name": "year", "type": "string"}, {"name": "nominal", "type": "number"},
                    {"name": "fx", "type": "number"}, {"name": "usd", "type": "number"}],
        "rows": [{"year": "2024", "nominal": 100, "fx": 3, "usd": 33.33},
                 {"year": "2025", "nominal": 60, "fx": 3, "usd": 20}],
        "sourceRefs": [{"sourceId": "weather_csv", "location": "A2:C3"}],
        "transform": {
            "columnSources": {"year": {"sourceId": "weather_csv", "location": "A2:A3"},
                              "nominal": {"sourceId": "weather_csv", "location": "B2:B3"},
                              "fx": {"sourceId": "weather_csv", "location": "C2:C3"}},
            "expressions": {"usd": {"op": "round", "places": 2, "value": {
                "op": "divide", "left": {"column": "nominal"}, "right": {"column": "fx"}}}},
        },
    }
    spec["timeline"][0]["elements"][1]["dataBinding"]["field"] = "usd"
    spec["timeline"][0]["elements"][1]["params"]["categoryField"] = "year"
    issues = qa_report(spec, tmp_path)["issues"]
    assert not any(issue["code"].startswith("data_") for issue in issues)
    spec["datasets"][0]["rows"][0]["usd"] = 24.99
    issues = qa_report(spec, tmp_path)["issues"]
    assert any(issue["code"] == "data_derived_mismatch" for issue in issues)
    spec["datasets"][0]["transform"]["expressions"]["usd"]["value"]["right"] = {"constant": "0"}
    issues = qa_report(spec, tmp_path)["issues"]
    assert any(issue["code"] == "data_expression_invalid" for issue in issues)
    spec["datasets"][0]["transform"]["expressions"]["usd"] = {"op": "python", "value": "1+1"}
    issues = qa_report(spec, tmp_path)["issues"]
    assert any(issue["code"] == "data_expression_invalid" for issue in issues)
