import copy
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from motion_engine.packaging import PackageError, package_preview, verify_preview_bundle
from motion_engine.cli import main
from motion_engine.rendering import render_preview
from motion_engine.revisions import freeze_revision
from motion_engine.validation import load_spec


@pytest.mark.parametrize("example", ["hello.motion.json", "image-card.motion.json"])
def test_preview_bundle_reopens_with_verified_sources_and_render(tmp_path, example):
    spec_path = ROOT / "examples" / example
    spec = load_spec(spec_path)
    revision = freeze_revision(spec, spec_path.parent)
    render_preview(spec, tmp_path / "render", mp4=True, scale=0.1,
                   asset_root=spec_path.parent, revision_sha256=revision["revisionSha256"])
    bundle = tmp_path / "bundle"
    manifest = package_preview(spec_path, tmp_path / "render", bundle)
    assert manifest["kind"] == "preview_bundle"
    assert manifest["revisionSha256"] == revision["revisionSha256"]
    input_file = "hello-script.md" if example == "hello.motion.json" else "synthetic-plate.png"
    assert (bundle / "project/assets" / input_file).is_file()
    assert (bundle / "render/preview.mp4").is_file()
    assert verify_preview_bundle(bundle) == manifest
    assert main(["verify-package", str(bundle)]) == 0
    relocated = tmp_path / "relocated"
    shutil.copytree(bundle, relocated)
    assert verify_preview_bundle(relocated) == manifest
    with pytest.raises(PackageError, match="already exists"):
        package_preview(spec_path, tmp_path / "render", bundle)
    (bundle / "project/assets" / input_file).write_text("changed", encoding="utf-8")
    with pytest.raises(PackageError, match="hashes differ"):
        verify_preview_bundle(bundle)


def test_preview_package_rejects_unbuilt_required_native_target(tmp_path):
    spec_path = ROOT / "examples/hello.motion.json"
    spec = copy.deepcopy(load_spec(spec_path))
    spec["deliverables"][1]["required"] = True
    custom = tmp_path / "hello.motion.json"
    custom.write_text(__import__("json").dumps(spec), encoding="utf-8")
    with pytest.raises(PackageError, match="native adapters"):
        package_preview(custom, tmp_path / "missing-render", tmp_path / "bundle")
    assert not (tmp_path / "bundle").exists()
