import hashlib
import json
from pathlib import Path

import pytest

from motion_engine.cli import main
from motion_engine.drafting import draft_text
from motion_engine.rendering import render_preview
from motion_engine.validation import validate


@pytest.mark.parametrize("lines,locale,size", [
    (["Begin here", "Pause, then continue"], "en-US", (640, 360)),
    (["Bonjour à tous", "Une autre scène"], "fr-FR", (360, 640)),
])
def test_literal_draft_preserves_lines_and_citations(tmp_path, lines, locale, size):
    source = tmp_path / "prompt.txt"
    source.write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    spec = draft_text(source, tmp_path / "draft.motion.json", project_id="prompt_demo",
                      locale=locale, width=size[0], height=size[1], frames_per_line=4)
    assert not validate(spec)
    assert spec["canvas"]["durationFrames"] == 8
    assert spec["sources"][0]["uri"] == "prompt.txt"
    assert spec["sources"][0]["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert [scene["elements"][0]["text"]["value"] for scene in spec["timeline"]] == lines
    assert [scene["elements"][0]["sourceRefs"][0]["location"] for scene in spec["timeline"]] == ["line:1", "line:3"]


def test_draft_cli_to_video_preview(tmp_path):
    source = tmp_path / "prompt.txt"
    source.write_text("A first frame\nA second frame\n", encoding="utf-8")
    output = tmp_path / "draft.motion.json"
    assert main(["draft-text", str(source), "--output", str(output), "--project-id", "demo",
                 "--locale", "en-US", "--width", "640", "--height", "360",
                 "--frames-per-line", "4"]) == 0
    spec = json.loads(output.read_text(encoding="utf-8"))
    result = render_preview(spec, tmp_path / "render", mp4=True, scale=0.5,
                            asset_root=tmp_path)
    assert result["frameCount"] == 8
    assert (tmp_path / "render" / "preview.mp4").is_file()
    assert main(["draft-text", str(source), "--output", str(output), "--project-id", "demo",
                 "--locale", "en-US"]) == 2


def test_draft_rejects_unsupported_or_unportable_sources(tmp_path):
    pdf = tmp_path / "input.pdf"
    pdf.write_bytes(b"not a real pdf")
    with pytest.raises(ValueError, match="plain UTF-8"):
        draft_text(pdf, tmp_path / "draft.motion.json", project_id="demo", locale="en-US")
    outside = tmp_path.parent / (tmp_path.name + "-external") / "prompt.txt"
    outside.parent.mkdir()
    outside.write_text("Hello", encoding="utf-8")
    with pytest.raises(ValueError, match="portable links"):
        draft_text(outside, tmp_path / "draft.motion.json", project_id="demo", locale="en-US")
    empty = tmp_path / "empty.txt"
    empty.write_text("\n\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no nonblank"):
        draft_text(empty, tmp_path / "draft.motion.json", project_id="demo", locale="en-US")


@pytest.mark.parametrize("name", ["prompt-en", "prompt-fr"])
def test_committed_prompt_fixtures_keep_exact_source_links(name):
    root = Path(__file__).resolve().parents[1] / "examples"
    source = root / "assets" / f"{name}.txt"
    spec = json.loads((root / f"{name}.motion.json").read_text(encoding="utf-8"))
    lines = [line for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert not validate(spec)
    assert spec["sources"][0]["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert [scene["elements"][0]["text"]["value"] for scene in spec["timeline"]] == lines
