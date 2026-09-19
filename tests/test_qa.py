import copy
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.cli import main
from motion_engine.qa import qa_report
from motion_engine.rendering import render_preview
from motion_engine.revisions import freeze_revision
from motion_engine.validation import load_spec


def test_public_qa_reports_only_claim_implemented_checks():
    hello = load_spec(ROOT / "examples/hello.motion.json")
    assert qa_report(hello, ROOT / "examples")["status"] == "passed"
    weather = load_spec(ROOT / "examples/weather.motion.json")
    report = qa_report(weather, ROOT / "examples")
    assert report["status"] == "needs_review"
    assert not any(issue["code"].startswith("data_") for issue in report["issues"])
    image_card = copy.deepcopy(load_spec(ROOT / "examples/image-card.motion.json"))
    image_card["policies"]["qa"].append({"id": "future_check", "rule": "future.rule", "severity": "info"})
    assert qa_report(image_card, ROOT / "examples")["status"] == "needs_review"


def test_safe_area_and_disclosure_timing_fail_with_targets():
    spec = copy.deepcopy(load_spec(ROOT / "examples/hello.motion.json"))
    spec["timeline"][0]["elements"][0]["bounds"]["x"] = 0
    spec["policies"]["qa"].append({"id": "full_disclosure", "rule": "disclosure.full_duration", "severity": "error"})
    spec["policies"]["disclosures"].append({"id": "notice", "text": {"value": "Notice"}, "startFrame": 10, "endFrameExclusive": 90,
                                             "bounds": {"x": 100, "y": 900, "width": 1000, "height": 50}})
    issues = qa_report(spec, ROOT / "examples")["issues"]
    assert any(issue["code"] == "text_outside_safe_area" and issue["targetId"] == "title" for issue in issues)
    assert any(issue["code"] == "disclosure_timing" and issue["targetId"] == "notice" for issue in issues)


def test_render_qa_detects_tampered_frame(tmp_path):
    path = ROOT / "examples/image-card.motion.json"
    spec = load_spec(path)
    revision = freeze_revision(spec, path.parent)
    output = tmp_path / "render"
    render_preview(spec, output, mp4=False, scale=0.1, asset_root=path.parent,
                   revision_sha256=revision["revisionSha256"])
    first = qa_report(spec, path.parent, output)
    assert not any(issue["severity"] == "error" for issue in first["issues"])
    frame = output / "frames/000020.png"
    with Image.open(frame) as image:
        changed = image.copy()
    changed.putpixel((0, 0), (255, 0, 0))
    changed.save(frame)
    later = qa_report(spec, path.parent, output)
    assert later["status"] == "failed"
    assert any(issue["code"] == "render_integrity" for issue in later["issues"])


def test_qa_cli_exit_code_tracks_review_gate():
    assert main(["qa", str(ROOT / "examples/hello.motion.json")]) == 0
    assert main(["qa", str(ROOT / "examples/weather.motion.json")]) == 1


def test_unavailable_asset_and_missing_data_provenance_are_visible():
    spec = copy.deepcopy(load_spec(ROOT / "examples/image-card.motion.json"))
    spec["assets"][0]["status"] = "pending"
    spec["datasets"] = [{"id": "draft_values", "columns": [{"name": "value", "type": "number"}],
                         "rows": [{"value": 1}], "sourceRefs": []}]
    report = qa_report(spec, ROOT / "examples")
    assert report["status"] == "failed"
    assert any(issue["code"] == "asset_unavailable" for issue in report["issues"])
    assert any(issue["code"] == "data_provenance_missing" for issue in report["issues"])
