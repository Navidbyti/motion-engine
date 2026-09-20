import json
import shutil
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.cli import main
from motion_engine.contact_sheet import ContactSheetError, make_contact_sheet
from motion_engine.revisions import file_sha256
from motion_engine.validation import load_spec


@pytest.mark.parametrize("name", ["director-abstract", "director-plate"])
def test_verified_scene_contact_sheet_from_public_drafts(tmp_path, name):
    spec = load_spec(ROOT / "examples" / f"{name}.motion.json")
    for item in spec["sources"] + spec["assets"]:
        destination = tmp_path / item["uri"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "examples" / item["uri"], destination)
    spec_path = tmp_path / "draft.motion.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    render_dir = tmp_path / "render"
    assert main(["render", str(spec_path), "--output-dir", str(render_dir),
                 "--frames-only", "--scale", "0.5"]) == 0
    output = tmp_path / "review"
    assert main(["contact-sheet", str(spec_path), "--render-dir", str(render_dir),
                 "--output-dir", str(output)]) == 0
    report = json.loads((output / "contact-sheet.json").read_text(encoding="utf-8"))
    assert len(report["scenes"]) == len(spec["timeline"])
    assert report["scenes"][0]["sampledFrames"][0] == 0
    assert report["scenes"][-1]["sampledFrames"][-1] == spec["canvas"]["durationFrames"] - 1
    for sheet in report["sheets"]:
        path = output / sheet["path"]
        assert file_sha256(path) == sheet["sha256"]
        with Image.open(path) as image:
            assert image.width == 952
            assert image.height > 200
    assert main(["contact-sheet", str(spec_path), "--render-dir", str(render_dir),
                 "--output-dir", str(output)]) == 2
    spec["project"]["title"] = "Changed since render"
    with pytest.raises(ContactSheetError, match="does not match"):
        make_contact_sheet(spec, tmp_path, render_dir, tmp_path / "other-review")


def test_contact_sheet_paginates_longer_draft(tmp_path):
    source = tmp_path / "script.txt"
    source.write_text("\n".join(f"Card {index:02d}" for index in range(13)), encoding="utf-8")
    spec_path = tmp_path / "draft.motion.json"
    assert main(["draft-text", str(source), "--output", str(spec_path),
                 "--project-id", "cards", "--locale", "en-US",
                 "--width", "320", "--height", "320",
                 "--frames-per-line", "12"]) == 0
    render_dir = tmp_path / "render"
    assert main(["render", str(spec_path), "--output-dir", str(render_dir),
                 "--frames-only", "--scale", "0.25"]) == 0
    report = make_contact_sheet(load_spec(spec_path), tmp_path, render_dir, tmp_path / "review")
    assert [page["sceneCount"] for page in report["sheets"]] == [12, 1]
    assert [scene["row"] for scene in report["scenes"]][-2:] == [11, 0]
    assert report["scenes"][-1]["sampledFrames"] == [144, 149, 155]
