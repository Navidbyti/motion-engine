import json
import shutil
from pathlib import Path

import pytest

from motion_engine.cli import main
from motion_engine.doctor import doctor_report
from motion_engine.editor_delivery import EditorDeliveryError, verify_editor_delivery
from motion_engine.project_workspace import WorkspaceError, init_project


ROOT = Path(__file__).parents[1]


def test_doctor_returns_safe_actionable_checks(tmp_path):
    report = doctor_report(tmp_path)
    assert report["motionEngineVersion"]
    assert {"python", "ffmpeg", "complex_text", "workspace", "adobe"} == {
        item["id"] for item in report["checks"]
    }
    assert all("key" not in json.dumps(item).casefold() for item in report["checks"])
    assert report["status"] in {"ready", "blocked"}


def test_init_project_is_clear_and_non_destructive(tmp_path):
    project = tmp_path / "Client Reel"
    result = init_project(project, "Create a complete 30 second reel from my script.")
    assert result["projectId"] == "client-reel"
    assert (project / "REQUEST.md").is_file()
    assert (project / "prompt.txt").read_text(encoding="utf-8") == "Create a complete 30 second reel from my script.\n"
    assert (project / "assets").is_dir()
    assert (project / "sources").is_dir()
    assert (project / "versions").is_dir()
    state = json.loads((project / "project.json").read_text(encoding="utf-8"))
    assert state["status"] == "brief_created"
    with pytest.raises(WorkspaceError, match="already exists"):
        init_project(project, "Do not overwrite me")


def test_produce_builds_complete_verified_editor_handoff(tmp_path):
    pytest.importorskip("imageio_ffmpeg")
    work = tmp_path / "alpha"
    init_project(work, "Make an abstract motion graphic.", project_id="alpha-test")
    prompt = work / "prompt.txt"
    proposal = work / "plan.json"
    shutil.copy2(ROOT / "examples/assets/director-abstract.txt", prompt)
    shutil.copy2(ROOT / "examples/director-abstract.plan.json", proposal)
    result = main(["produce", str(prompt), str(proposal), "--project-id", "alpha-test",
                   "--name", "v1", "--width", "270", "--height", "480", "--scale", "0.25"])
    assert result == 0
    delivery = work / "v1-editor-delivery"
    manifest = verify_editor_delivery(delivery)
    assert manifest["qaStatus"] == "passed"
    assert (delivery / "OPEN_ME.md").is_file()
    assert (delivery / "review/index.html").is_file()
    assert (work / "v1-preview/preview.mp4").is_file()
    state = json.loads((work / "project.json").read_text(encoding="utf-8"))
    assert state["currentVersion"] == "v1"
    assert state["artifacts"]["review"] == "v1-review/index.html"
    with pytest.raises(EditorDeliveryError, match="files or hashes"):
        (delivery / "OPEN_ME.md").write_text("changed", encoding="utf-8")
        verify_editor_delivery(delivery)
