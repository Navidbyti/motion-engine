import copy
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.cli import main
from motion_engine.revisions import RevisionError, freeze_revision, spec_sha256
from motion_engine.validation import load_spec


@pytest.mark.parametrize("name", ["hello", "weather", "image-card"])
def test_public_sources_freeze_with_verified_hashes(name):
    path = ROOT / "examples" / f"{name}.motion.json"
    spec = load_spec(path)
    first = freeze_revision(spec, path.parent)
    second = freeze_revision(spec, path.parent)
    assert first == second
    assert first["specSha256"] == spec_sha256(spec)
    assert len(first["revisionSha256"]) == 64
    assert first["sources"] and all(source["verified"] for source in first["sources"])
    assert all(asset["verified"] for asset in first["assets"])


def test_spec_hash_ignores_json_key_order_and_whitespace():
    spec = load_spec(ROOT / "examples/hello.motion.json")
    reordered = json.loads(json.dumps(spec, ensure_ascii=False, indent=4))
    reordered = {key: reordered[key] for key in reversed(list(reordered))}
    assert spec_sha256(spec) == spec_sha256(reordered)


def test_changed_source_is_rejected(tmp_path):
    original = ROOT / "examples/hello.motion.json"
    spec = copy.deepcopy(load_spec(original))
    (tmp_path / "assets").mkdir()
    source = tmp_path / "assets/hello-script.md"
    shutil.copyfile(ROOT / "examples/assets/hello-script.md", source)
    expected = freeze_revision(spec, tmp_path)["sources"][0]["sha256"]
    spec["sources"][0]["sha256"] = expected
    source.write_text("changed", encoding="utf-8")
    with pytest.raises(RevisionError, match="SHA-256 mismatch"):
        freeze_revision(spec, tmp_path)


def test_changed_asset_is_rejected(tmp_path):
    spec = copy.deepcopy(load_spec(ROOT / "examples/image-card.motion.json"))
    spec["sources"] = []
    (tmp_path / "assets").mkdir()
    shutil.copyfile(ROOT / "examples/assets/synthetic-plate.png", tmp_path / "assets/synthetic-plate.png")
    assert freeze_revision(spec, tmp_path)["assets"][0]["verified"]
    (tmp_path / "assets/synthetic-plate.png").write_bytes(b"changed image")
    with pytest.raises(RevisionError, match="SHA-256 mismatch"):
        freeze_revision(spec, tmp_path)


def test_source_cannot_escape_spec_directory():
    spec = copy.deepcopy(load_spec(ROOT / "examples/hello.motion.json"))
    spec["sources"][0]["uri"] = "../private.txt"
    with pytest.raises(RevisionError, match="portable relative file URI"):
        freeze_revision(spec, ROOT / "examples")


def test_freeze_cli_writes_manifest(tmp_path):
    output = tmp_path / "revision.json"
    assert main(["freeze", str(ROOT / "examples/hello.motion.json"), "--output", str(output)]) == 0
    frozen = json.loads(output.read_text(encoding="utf-8"))
    assert frozen["projectId"] == "hello"
    assert frozen["sources"][0]["verified"]
    assert main(["freeze", str(ROOT / "examples/hello.motion.json"), "--output", str(output)]) == 2
    assert json.loads(output.read_text(encoding="utf-8")) == frozen


def test_cli_render_binds_revision(tmp_path):
    spec_path = ROOT / "examples/image-card.motion.json"
    output = tmp_path / "rendered"
    assert main(["render", str(spec_path), "--output-dir", str(output), "--frames-only", "--scale", "0.1"]) == 0
    manifest = json.loads((output / "render-manifest.json").read_text(encoding="utf-8"))
    assert manifest["revisionSha256"] == freeze_revision(load_spec(spec_path), spec_path.parent)["revisionSha256"]
