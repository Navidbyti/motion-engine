"""Source data must be typed before a chart or renderer uses it."""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.validation import load_spec, validate_semantics


@pytest.mark.parametrize("value,expected", [
    (True, "expected number"),
    ("31", "expected number"),
    (float("nan"), "expected number"),
    (None, "expected number"),
])
def test_weather_dataset_rejects_untyped_chart_values(value, expected):
    spec = copy.deepcopy(load_spec(ROOT / "examples/weather.motion.json"))
    spec["datasets"][0]["rows"][0]["temperatureC"] = value
    assert any(expected in error and "row 0" in error for error in validate_semantics(spec))


def test_chart_binding_rejects_text_column_and_clipped_range():
    spec = copy.deepcopy(load_spec(ROOT / "examples/weather.motion.json"))
    spec["timeline"][0]["elements"][1]["dataBinding"]["field"] = "city"
    assert any("must be numeric" in error for error in validate_semantics(spec))
    spec["timeline"][0]["elements"][1]["dataBinding"]["field"] = "temperatureC"
    spec["timeline"][0]["elements"][1]["params"]["maximum"] = 25
    assert any("clips source values" in error for error in validate_semantics(spec))


def test_empty_chart_and_bad_axis_fail_validation():
    spec = copy.deepcopy(load_spec(ROOT / "examples/weather.motion.json"))
    spec["datasets"][0]["rows"] = []
    assert any("is empty" in error for error in validate_semantics(spec))
    spec["datasets"][0]["rows"] = [{"city": "Cairo", "temperatureC": 31}]
    spec["timeline"][0]["elements"][1]["params"]["minimum"] = 40
    assert any("maximum must exceed minimum" in error for error in validate_semantics(spec))


def test_generic_dataset_column_types_are_checked():
    spec = copy.deepcopy(load_spec(ROOT / "examples/hello.motion.json"))
    spec["datasets"] = [{
        "id": "records", "columns": [
            {"name": "name", "type": "string"}, {"name": "count", "type": "integer"},
            {"name": "approved", "type": "boolean"}, {"name": "day", "type": "date"},
            {"name": "mark", "type": "timecode"},
        ],
        "rows": [{"name": "A", "count": 3, "approved": True, "day": "2026-09-19", "mark": "00:00:03:12"}],
        "sourceRefs": [{"sourceId": "script", "location": "line:1"}],
    }]
    assert validate_semantics(spec) == []
    spec["datasets"][0]["rows"][0]["count"] = 3.5
    spec["datasets"][0]["rows"][0]["day"] = "2026-99-99"
    errors = validate_semantics(spec)
    assert any("field count: expected integer" in error for error in errors)
    assert any("field day: expected date" in error for error in errors)
