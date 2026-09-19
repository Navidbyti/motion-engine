import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.cli import main
from motion_engine.review import make_review, verify_review


def _write(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _evidence(source_id, code):
    return {"source": {"id": source_id, "sha256": "a" * 64},
            "evidence": [{"location": "line:1", "value": "Sample"}],
            "issues": [{"code": code, "message": f"Review {code}"}]}


def test_review_combines_source_issues_with_project_questions_and_requires_decisions(tmp_path):
    brief = _write(tmp_path / "brief.json", _evidence("brief", "reading_order"))
    script = _write(tmp_path / "script.json", _evidence("script", "language_uncertain"))
    requirements = _write(tmp_path / "requirements.json", {"items": [
        {"kind": "permission", "code": "music_rights", "message": "Confirm music rights", "sourceId": None},
        {"kind": "approval", "code": "quote", "message": "Approve exact quote", "sourceId": "script",
         "evidenceLocations": ["line:1"]},
        {"kind": "missing_input", "code": "logo", "message": "Supply licensed logo"},
    ]})
    review = make_review([brief, script], requirements)
    assert len(review["items"]) == 5
    assert len({item["id"] for item in review["items"]}) == 5
    assert review["items"][3]["evidenceLocations"] == ["line:1"]
    assert all(item["status"] == "pending" for item in review["items"])
    path = _write(tmp_path / "review.json", review)
    assert verify_review(path, [brief, script], requirements)["status"] == "failed"

    for item in review["items"]:
        item["status"] = "resolved"
        decision = {"ambiguity": "clarified", "missing_input": "provided", "permission": "approved", "approval": "approved"}[item["kind"]]
        item["resolution"] = {"decision": decision, "reviewer": "Fixture reviewer", "reason": "Checked fixture"}
    _write(path, review)
    assert verify_review(path, [brief, script], requirements) == {"status": "passed", "itemCount": 5, "errors": []}
    review["items"][2]["resolution"]["decision"] = "denied"
    _write(path, review)
    assert verify_review(path, [brief, script], requirements)["status"] == "failed"
    changed = _evidence("script", "different_issue")
    _write(script, changed)
    assert verify_review(path, [brief, script], requirements)["status"] == "failed"


def test_review_rejects_unknown_citation_duplicate_sources_and_tampering(tmp_path):
    evidence = _write(tmp_path / "source.json", _evidence("source", "check"))
    invalid = _write(tmp_path / "bad.json", {"items": [
        {"kind": "approval", "code": "quote", "message": "Approve quote", "sourceId": "source",
         "evidenceLocations": ["line:999"]},
    ]})
    with pytest.raises(ValueError, match="unknown evidence location"):
        make_review([evidence], invalid)
    with pytest.raises(ValueError, match="duplicate source ID"):
        make_review([evidence, evidence])
    review = make_review([evidence])
    review["items"][0]["message"] = "Changed after review"
    path = _write(tmp_path / "review.json", review)
    assert "changed identity" in " ".join(verify_review(path, [evidence])["errors"])


def test_review_cli_never_overwrites_existing_decisions(tmp_path, capsys):
    evidence = _write(tmp_path / "source.json", _evidence("source", "check"))
    review = tmp_path / "review.json"
    assert main(["make-review", str(evidence), "--output", str(review)]) == 0
    original = review.read_bytes()
    assert main(["make-review", str(evidence), "--output", str(review)]) == 2
    assert review.read_bytes() == original
    assert main(["verify-review", str(review), str(evidence)]) == 1
    assert "pending" in capsys.readouterr().out
