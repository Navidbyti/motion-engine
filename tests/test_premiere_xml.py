import copy
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from motion_engine.premiere_xml import PremiereXMLExportError, make_premiere_xml
from motion_engine.rendering import render_preview


ROOT = Path(__file__).resolve().parents[1]


def _tiny_spec():
    spec = json.loads((ROOT / "examples" / "ae-shapes.motion.json").read_text(encoding="utf-8"))
    spec["canvas"].update(width=64, height=64, durationFrames=4,
                          safeArea={"top": 0, "right": 0, "bottom": 0, "left": 0})
    spec["sources"] = []
    spec["deliverables"] = [{"id": "preview", "target": "video/mp4", "profile": "preview",
                             "required": True, "editable": False}]
    spec["policies"] = {"qa": [], "disclosures": [], "unsupportedFeature": "error"}
    first = spec["timeline"][0]
    first.update(startFrame=0, endFrameExclusive=2, transitionIn="start", sourceRefs=[])
    first["elements"] = [{"id": "box", "kind": "shape", "startFrame": 0,
                          "endFrameExclusive": 2, "bounds": {"x": 4, "y": 4, "width": 56, "height": 56},
                          "params": {"shape": "rect", "color": "#324B67"}}]
    first["beats"] = [{"id": "first_beat", "startFrame": 0, "endFrameExclusive": 2,
                       "elementIds": ["box"]}]
    first["animations"] = []
    second = copy.deepcopy(first)
    second.update(id="second", startFrame=2, endFrameExclusive=4, transitionIn="cut")
    second["elements"][0].update(id="box2", startFrame=2, endFrameExclusive=4)
    second["beats"][0].update(id="second_beat", startFrame=2, endFrameExclusive=4,
                              elementIds=["box2"])
    spec["timeline"] = [first, second]
    return spec


def test_xml_uses_verified_media_with_exact_scene_cuts_and_beats(tmp_path):
    spec = _tiny_spec()
    run_dir = tmp_path / "render"
    render_preview(spec, run_dir, mp4=True)
    output = make_premiere_xml(spec, run_dir, tmp_path / "timeline.xml")
    root = ET.parse(output).getroot()
    assert root.tag == "xmeml"
    clips = root.findall("./sequence/media/video/track/clipitem")
    assert [(int(c.findtext("start")), int(c.findtext("end")), int(c.findtext("in")))
            for c in clips] == [(0, 2, 0), (2, 4, 2)]
    assert all(Path(run_dir / "preview.mp4").as_uri() == c.findtext("file/pathurl") for c in clips)
    assert [(m.findtext("name"), m.findtext("in"), m.findtext("out"))
            for m in root.findall("./sequence/marker")] == [
                ("first_beat", "0", "2"), ("second_beat", "2", "4")]
    assert root.findtext("./sequence/media/video/format/samplecharacteristics/width") == "64"


def test_xml_rejects_changed_preview_and_unsupported_audio(tmp_path):
    spec = _tiny_spec()
    run_dir = tmp_path / "render"
    render_preview(spec, run_dir, mp4=True)
    (run_dir / "preview.mp4").write_bytes(b"changed")
    with pytest.raises(PremiereXMLExportError, match="hash mismatch"):
        make_premiere_xml(spec, run_dir, tmp_path / "timeline.xml")
    assert not (tmp_path / "timeline.xml").exists()

    audio = _tiny_spec()
    audio["timeline"][0]["elements"].append({"id": "tone_track", "kind": "audio",
        "startFrame": 0, "endFrameExclusive": 2, "assetId": "tone", "params": {"gainDb": 0}})
    audio["assets"].append({"id": "tone", "kind": "audio", "status": "available",
                            "uri": "assets/demo-tone.wav", "sha256": "0" * 64})
    with pytest.raises(PremiereXMLExportError, match="cannot preserve MotionSpec audio"):
        make_premiere_xml(audio, run_dir, tmp_path / "timeline.xml")
