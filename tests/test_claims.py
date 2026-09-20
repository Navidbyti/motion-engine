import copy
import json
import shutil
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.claims import SCHEMA, verify_claims
from motion_engine.cli import main


def _fixture(tmp_path):
    example = ROOT / "examples" / "claims"
    for name in ("observatory.txt", "weather-office.txt", "northbridge.ledger.json"):
        shutil.copyfile(example / name, tmp_path / name)
    path = tmp_path / "northbridge.ledger.json"
    return path, json.loads(path.read_text(encoding="utf-8"))


def test_public_ledger_is_packaged_schema_valid_and_source_linked(tmp_path):
    path, ledger = _fixture(tmp_path)
    assert SCHEMA == json.loads((ROOT / "ClaimLedger.schema.json").read_text(encoding="utf-8"))
    assert not list(Draft202012Validator(SCHEMA).iter_errors(ledger))
    report = verify_claims(path)
    assert report["status"] == "source_linked"
    assert report["semanticReviewRequired"] is True
    assert report["sourceCount"] == report["claimCount"] == 2
    assert main(["verify-claims", str(path), "--output", str(tmp_path / "report.json")]) == 0
    assert main(["verify-claims", str(path), "--output", str(tmp_path / "report.json")]) == 2


def test_claims_reject_changed_source_and_fabricated_excerpt(tmp_path):
    path, ledger = _fixture(tmp_path)
    (tmp_path / "observatory.txt").write_text("Changed source text", encoding="utf-8")
    report = verify_claims(path)
    assert report["status"] == "failed"
    assert any(item["code"] == "source_invalid" for item in report["issues"])
    shutil.copyfile(ROOT / "examples/claims/observatory.txt", tmp_path / "observatory.txt")
    ledger["claims"][0]["evidence"][0]["quote"] = "A fabricated passage"
    path.write_text(json.dumps(ledger), encoding="utf-8")
    report = verify_claims(path)
    assert report["status"] == "failed"
    assert any(item["code"] == "quote_mismatch" for item in report["issues"])
    assert main(["verify-claims", str(path)]) == 1


def test_claims_reject_missing_support_unknown_source_and_bad_metadata(tmp_path):
    path, ledger = _fixture(tmp_path)
    ledger["claims"][0]["evidence"][0]["relation"] = "context"
    ledger["claims"][1]["evidence"][0]["sourceId"] = "missing"
    ledger["sources"][0]["publicationDate"] = "2020-99-99"
    ledger["sources"][1]["url"] = "file:///local/secret"
    ledger["claims"][1]["eventDate"] = "2020-99-99"
    ledger["claims"][1]["evidence"][1]["quote"] = " "
    path.write_text(json.dumps(ledger), encoding="utf-8")
    codes = {issue["code"] for issue in verify_claims(path)["issues"]}
    assert {"no_support", "unknown_source", "invalid_date", "invalid_url", "blank_evidence"} <= codes


def test_claims_distinguish_publication_event_and_retrieval_dates(tmp_path):
    path, ledger = _fixture(tmp_path)
    ledger["sources"][0]["retrievedDate"] = "2020-05-01"
    path.write_text(json.dumps(ledger), encoding="utf-8")
    assert any(issue["code"] == "date_order" for issue in verify_claims(path)["issues"])


def test_claims_reject_duplicate_ids_and_unsafe_paths(tmp_path):
    path, ledger = _fixture(tmp_path)
    ledger["claims"].append(copy.deepcopy(ledger["claims"][0]))
    ledger["sources"][0]["uri"] = "../outside.txt"
    path.write_text(json.dumps(ledger), encoding="utf-8")
    codes = {issue["code"] for issue in verify_claims(path)["issues"]}
    assert {"duplicate_claim", "source_invalid"} <= codes
