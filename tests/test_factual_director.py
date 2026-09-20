import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.cli import main
from motion_engine.director import DirectorError, compile_director_plan
from motion_engine.qa import qa_report
from motion_engine.revisions import freeze_revision, spec_sha256
from motion_engine.scene_revisions import revise_scene
from motion_engine.validation import load_spec


def _factual_project(tmp_path):
    claims = tmp_path / "claims"
    claims.mkdir()
    for name in ("northbridge.ledger.json", "northbridge.plan.json", "northbridge.prompt.txt",
                 "observatory.txt", "weather-office.txt"):
        shutil.copyfile(ROOT / "examples" / "claims" / name, claims / name)
    prompt = tmp_path / "prompt.txt"
    shutil.copyfile(claims / "northbridge.prompt.txt", prompt)
    proposal = json.loads((claims / "northbridge.plan.json").read_text(encoding="utf-8"))
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(proposal), encoding="utf-8")
    return prompt, plan, claims / "northbridge.ledger.json", proposal


def test_researched_plan_produces_source_bound_reviewable_preview(tmp_path):
    pytest.importorskip("imageio_ffmpeg")
    prompt, plan, ledger, _ = _factual_project(tmp_path)
    spec_path = tmp_path / "draft.motion.json"
    render_dir = tmp_path / "preview"
    assert main(["first-draft", str(prompt), str(plan), "--project-id", "northbridge",
                 "--claims", str(ledger), "--output-spec", str(spec_path),
                 "--output-dir", str(render_dir), "--width", "320", "--height", "180",
                 "--fps", "24", "--scale", "0.5"]) == 0
    spec = load_spec(spec_path)
    assert (render_dir / "preview.mp4").is_file()
    assert any(source["id"] == "claim_ledger" for source in spec["sources"])
    assert sum(source["id"].startswith("claim_source_") for source in spec["sources"]) == 2
    assert spec["timeline"][0]["sourceRefs"][1]["location"] == "/claims/0"
    assert spec["timeline"][1]["sourceRefs"][1]["location"] == "/claims/1"
    assert freeze_revision(spec, tmp_path)["revisionSha256"]
    report = qa_report(spec, tmp_path, render_dir)
    assert report["status"] == "needs_review"
    assert any(issue["code"] == "claim_semantic_review_required" for issue in report["issues"])


def test_factual_plan_rejects_missing_or_wrong_claim_links(tmp_path):
    prompt, plan, ledger, proposal = _factual_project(tmp_path)
    output = tmp_path / "draft.motion.json"
    with pytest.raises(DirectorError, match="needs a claim ledger"):
        compile_director_plan(prompt, output, proposal, project_id="northbridge", width=320, height=180, fps=24)
    proposal["scenes"][0]["claimIds"] = ["invented_claim"]
    with pytest.raises(DirectorError, match="unknown claim ID"):
        compile_director_plan(prompt, output, proposal, project_id="northbridge", width=320, height=180, fps=24,
                              claim_ledger_path=ledger)
    proposal["scenes"][0]["claimIds"] = []
    with pytest.raises(DirectorError, match="needs at least one cited claim"):
        compile_director_plan(prompt, output, proposal, project_id="northbridge", width=320, height=180, fps=24,
                              claim_ledger_path=ledger)


def test_factual_text_revision_invalidates_scene_claim_mapping(tmp_path):
    prompt, plan, ledger, proposal = _factual_project(tmp_path)
    spec = compile_director_plan(prompt, tmp_path / "draft.motion.json", proposal,
                                 project_id="northbridge", width=320, height=180, fps=24,
                                 proposal_path=plan, claim_ledger_path=ledger)
    request = {"baseSpecSha256": spec_sha256(spec), "sceneId": "scene_1",
               "operations": [{"op": "set_text", "elementId": "title_1", "value": "A changed factual headline"}]}
    path = tmp_path / "edit.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    revised = revise_scene(spec, request, request_path=path, output_path=tmp_path / "next.motion.json")
    assert revised["timeline"][1] == spec["timeline"][1]
    report = qa_report(revised, tmp_path)
    assert report["status"] == "failed"
    assert any(issue["code"] == "claim_link_missing" and issue["targetId"] == "scene_1" for issue in report["issues"])
