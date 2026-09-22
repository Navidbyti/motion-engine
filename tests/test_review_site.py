import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from motion_engine.cli import main
from motion_engine.review_site import ReviewSiteError, make_review_site
from motion_engine.scene_modules import render_scene_modules
from motion_engine.validation import load_spec


def test_review_site_contains_scene_controls_and_portable_media(tmp_path):
    spec = load_spec(ROOT / "examples/prompt-en.motion.json")
    modules = tmp_path / "modules"
    render_scene_modules(spec, modules, mp4=True, scale=0.1)
    result = make_review_site(spec, [modules], tmp_path / "site", scale=0.1, revision_sha256="a" * 64)

    html = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert result["sceneCount"] == 2
    assert "Revise scene ${scene.id}:" in html
    assert "Copy prompt" in html
    assert "scene_1" in html and "scene_2" in html
    assert (tmp_path / "site" / "media" / "scene-000" / "preview.mp4").is_file()
    assert (tmp_path / "site" / "media" / "scene-001" / "poster.png").is_file()
    assert str(tmp_path) not in html


def test_review_site_escapes_embedded_script_end_tags(tmp_path):
    spec = copy.deepcopy(load_spec(ROOT / "examples/prompt-en.motion.json"))
    spec["project"]["title"] = "</script><script>alert('x')</script>"
    modules = tmp_path / "modules"
    render_scene_modules(spec, modules, mp4=False, scale=0.1)
    make_review_site(spec, [modules], tmp_path / "site", scale=0.1)
    html = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert "</script><script>alert('x')</script>" not in html
    assert "<\\/script><script>alert('x')<\\/script>" in html


def test_review_site_rejects_stale_modules_without_partial_output(tmp_path):
    base = load_spec(ROOT / "examples/prompt-en.motion.json")
    modules = tmp_path / "modules"
    render_scene_modules(base, modules, mp4=False, scale=0.1)
    revised = copy.deepcopy(base)
    revised["timeline"][0]["elements"][0]["text"]["value"] = "Changed"
    with pytest.raises(ReviewSiteError, match="no compatible module for scene scene_1"):
        make_review_site(revised, [modules], tmp_path / "site", scale=0.1)
    assert not (tmp_path / "site").exists()


def test_make_review_site_cli(tmp_path):
    modules = tmp_path / "modules"
    site = tmp_path / "site"
    assert main([
        "render-scenes", str(ROOT / "examples/prompt-en.motion.json"),
        "--output-dir", str(modules),
        "--frames-only", "--scale", "0.1",
    ]) == 0
    assert main([
        "make-review-site", str(ROOT / "examples/prompt-en.motion.json"),
        "--modules", str(modules), "--output-dir", str(site), "--scale", "0.1",
    ]) == 0
    manifest = json.loads((site / "review-site.json").read_text(encoding="utf-8"))
    assert manifest["sceneCount"] == 2
