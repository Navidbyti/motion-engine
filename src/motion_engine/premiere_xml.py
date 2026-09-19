"""Build a narrow Final Cut Pro 7 XML timeline from a verified preview run."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .revisions import spec_sha256
from .runs import RunError, verify_render_run
from .validation import validate


class PremiereXMLExportError(ValueError):
    pass


def _element(parent: ET.Element, tag: str, value: Any) -> ET.Element:
    child = ET.SubElement(parent, tag)
    child.text = str(value)
    return child


def _rate(parent: ET.Element, fps: int) -> None:
    rate = ET.SubElement(parent, "rate")
    _element(rate, "timebase", fps)
    _element(rate, "ntsc", "FALSE")


def make_premiere_xml(spec: dict[str, Any], render_dir: str | Path,
                      output_xml: str | Path) -> Path:
    errors = validate(spec)
    if errors:
        raise PremiereXMLExportError(f"invalid MotionSpec: {errors[0]}")
    canvas = spec["canvas"]
    fps_pair = canvas["frameRate"]
    if fps_pair["denominator"] != 1 or fps_pair["numerator"] not in (24, 25, 30, 50, 60):
        raise PremiereXMLExportError("initial Premiere XML exporter supports integer 24/25/30/50/60 fps only")
    if any(element["kind"] == "audio" for scene in spec["timeline"] for element in scene["elements"]):
        raise PremiereXMLExportError("initial Premiere XML exporter cannot preserve MotionSpec audio")
    scenes = spec["timeline"]
    cursor = 0
    for index, scene in enumerate(scenes):
        if scene["startFrame"] != cursor or scene["transitionIn"] != ("start" if index == 0 else "cut"):
            raise PremiereXMLExportError("initial Premiere XML exporter supports contiguous scene cuts only")
        cursor = scene["endFrameExclusive"]
    if cursor != canvas["durationFrames"]:
        raise PremiereXMLExportError("scenes do not cover the full preview duration")

    try:
        run = verify_render_run(render_dir)
    except RunError as exc:
        raise PremiereXMLExportError(str(exc)) from exc
    if run["specSha256"] != spec_sha256(spec) or run["frameCount"] != canvas["durationFrames"]:
        raise PremiereXMLExportError("preview run does not match this MotionSpec revision")
    if run["frameRate"] != fps_pair:
        raise PremiereXMLExportError("preview frame rate does not match MotionSpec")
    mp4 = next((item for item in run["outputs"] if item["kind"] == "video/mp4"), None)
    if not mp4:
        raise PremiereXMLExportError("verified preview run has no MP4")
    media_path = (Path(render_dir).resolve() / mp4["path"]).resolve()
    destination = Path(output_xml).resolve()
    if destination.exists():
        raise PremiereXMLExportError(f"output XML already exists: {destination}")

    fps = fps_pair["numerator"]
    total = canvas["durationFrames"]
    root = ET.Element("xmeml", {"version": "5"})
    sequence = ET.SubElement(root, "sequence", {"id": "motion-engine-sequence"})
    _element(sequence, "name", spec["project"]["title"])
    _element(sequence, "duration", total)
    _rate(sequence, fps)
    media = ET.SubElement(sequence, "media")
    video = ET.SubElement(media, "video")
    format_element = ET.SubElement(video, "format")
    characteristics = ET.SubElement(format_element, "samplecharacteristics")
    _element(characteristics, "width", run["width"])
    _element(characteristics, "height", run["height"])
    _element(characteristics, "anamorphic", "FALSE")
    _element(characteristics, "pixelaspectratio", "square")
    _element(characteristics, "fielddominance", "none")
    _rate(characteristics, fps)
    track = ET.SubElement(video, "track")

    for number, scene in enumerate(scenes, start=1):
        start, end = scene["startFrame"], scene["endFrameExclusive"]
        clip = ET.SubElement(track, "clipitem", {"id": f"scene-{number}"})
        _element(clip, "name", scene["id"])
        _element(clip, "duration", total)
        _rate(clip, fps)
        _element(clip, "start", start)
        _element(clip, "end", end)
        _element(clip, "in", start)
        _element(clip, "out", end)
        file = ET.SubElement(clip, "file", {"id": f"preview-file-{number}"})
        _element(file, "name", media_path.name)
        _element(file, "pathurl", media_path.as_uri())
        _element(file, "duration", total)
        _rate(file, fps)
        file_media = ET.SubElement(file, "media")
        file_video = ET.SubElement(file_media, "video")
        _element(file_video, "duration", total)
        for beat in scene["beats"]:
            marker = ET.SubElement(sequence, "marker")
            _element(marker, "name", beat["id"])
            _element(marker, "in", beat["startFrame"])
            _element(marker, "out", beat["endFrameExclusive"])
            _element(marker, "comment", scene["id"])

    ET.indent(root, space="  ")
    destination.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(destination, encoding="utf-8", xml_declaration=True)
    return destination
