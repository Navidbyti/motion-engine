"""Generate a narrow, inspectable After Effects ExtendScript build job."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from PIL import Image

from .validation import validate
from .revisions import RevisionError, file_sha256, resolve_local_file


_AE_EASING = {"linear", "ease_out", "ease_in", "ease_in_out", "hold"}


def _ease(value: float, name: str) -> float:
    if name == "linear":
        return value
    if name == "ease_out":
        return 1 - (1 - value) ** 3
    if name == "ease_in":
        return value ** 3
    if name == "ease_in_out":
        return value * value * (3 - 2 * value)
    if name == "hold":
        return 0
    raise AEExportError(f"unsupported After Effects easing {name!r}")


def _animation_value(keys: list[dict[str, Any]], frame: int) -> float:
    if frame <= keys[0]["frame"]:
        return float(keys[0]["value"])
    for left, right in zip(keys, keys[1:]):
        if frame <= right["frame"]:
            if frame == right["frame"]:
                return float(right["value"])
            fraction = _ease((frame - left["frame"]) / (right["frame"] - left["frame"]),
                             right.get("easing", "linear"))
            return float(left["value"] + (right["value"] - left["value"]) * fraction)
    return float(keys[-1]["value"])


def _track_frames(keys: list[dict[str, Any]]) -> list[int]:
    if any(key.get("easing", "linear") != "linear" for key in keys):
        return list(range(keys[0]["frame"], keys[-1]["frame"] + 1))
    return [key["frame"] for key in keys]


class AEExportError(ValueError):
    pass


def make_ae_script(spec: dict[str, Any], script_path: str | Path,
                   aep_path: str | Path, report_path: str | Path,
                   asset_root: str | Path | None = None) -> Path:
    errors = validate(spec)
    if errors:
        raise AEExportError(f"invalid MotionSpec: {errors[0]}")
    if any(scene.get("transitionIn") != ("start" if index == 0 else "cut")
           for index, scene in enumerate(spec["timeline"])):
        raise AEExportError("initial After Effects adapter supports only scene cuts")
    if spec["policies"]["disclosures"]:
        raise AEExportError("initial After Effects adapter does not support policy disclosures")
    images = []
    for asset in spec["assets"]:
        if asset["kind"] != "image" or asset["status"] != "available" or not asset.get("sha256"):
            raise AEExportError(f"asset {asset['id']} must be an available hashed image")
        if not asset_root:
            raise AEExportError("image assets require a MotionSpec asset root")
        try:
            path = resolve_local_file(asset, asset_root, "asset")
        except RevisionError as exc:
            raise AEExportError(str(exc)) from exc
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            raise AEExportError(f"asset {asset['id']} must be PNG or JPEG for this After Effects adapter")
        if file_sha256(path) != asset["sha256"]:
            raise AEExportError(f"asset {asset['id']} SHA-256 mismatch")
        try:
            with Image.open(path) as picture:
                width, height = picture.size
                if picture.format not in ("PNG", "JPEG"):
                    raise AEExportError(f"asset {asset['id']} file content is not PNG or JPEG")
        except OSError as exc:
            raise AEExportError(f"asset {asset['id']} image cannot be decoded") from exc
        images.append({"id": asset["id"], "path": path.as_posix(), "width": width, "height": height})
    image_ids = {item["id"] for item in images}
    images_by_id = {item["id"]: item for item in images}
    if any(beat.get("voice", {}).get("value", "").strip()
           for scene in spec["timeline"] for beat in scene["beats"]):
        raise AEExportError("initial After Effects adapter does not support voice audio")
    beat_starts = [beat["startFrame"] for scene in spec["timeline"] for beat in scene["beats"]]
    if len(beat_starts) != len(set(beat_starts)):
        raise AEExportError("After Effects beat markers need unique start frames")
    position_tracks = {}
    opacity_tracks = {}
    scale_tracks = {}
    layer_order = []
    for scene in spec["timeline"]:
        layer_order.append(sorted(range(len(scene["elements"])),
                                  key=lambda index: scene["elements"][index].get("zIndex", 0)))
        scene_elements = {element["id"]: element for element in scene["elements"]}
        for element in scene["elements"]:
            if element["kind"] not in ("text", "shape", "image"):
                raise AEExportError(f"initial After Effects adapter does not support {element['kind']}")
            if not element.get("bounds"):
                raise AEExportError(f"element {element['id']} needs bounds")
            if element["kind"] == "text":
                if not element.get("text"):
                    raise AEExportError(f"text {element['id']} needs text")
                if set(element["params"]) - {"color", "fontSize", "wrap"} or not isinstance(element["params"].get("wrap", False), bool):
                    raise AEExportError(f"text {element['id']} has unsupported parameters")
                if element["text"].get("direction", spec["project"].get("direction", "ltr")) == "rtl":
                    raise AEExportError("initial After Effects adapter has not verified RTL text")
            elif element["kind"] == "shape":
                if set(element["params"]) - {"color", "shape"} or element["params"].get("shape", "rect") != "rect":
                    raise AEExportError(f"shape {element['id']} supports solid rectangles only")
            else:
                if element.get("assetId") not in image_ids:
                    raise AEExportError(f"image {element['id']} needs a verified image asset")
                if set(element["params"]) - {"fit"} or element["params"].get("fit", "contain") not in ("contain", "stretch"):
                    raise AEExportError(f"image {element['id']} supports contain or stretch only")
        for animation in scene["animations"]:
            prop = animation["property"]
            element = scene_elements.get(animation["targetId"])
            keys = animation["keyframes"]
            limit = (1 if prop == "opacity" else 3 if prop == "scale" else
                     spec["canvas"]["width" if prop == "x" else "height"] if prop in ("x", "y") else None)
            if (element is None or limit is None or not keys
                or any(key.get("easing", "linear") not in _AE_EASING
                       or not isinstance(key["value"], (int, float)) or isinstance(key["value"], bool)
                       or not math.isfinite(key["value"])
                       or not ((0 <= key["value"] <= 1) if prop == "opacity" else
                               (1 <= key["value"] <= 3) if prop == "scale" else
                               (-limit <= key["value"] <= limit))
                       or not element["startFrame"] <= key["frame"] < element["endFrameExclusive"]
                       for key in keys)
                or [key["frame"] for key in keys] != sorted({key["frame"] for key in keys})):
                raise AEExportError("initial After Effects adapter supports opacity, image scale, or x/y keyframes with known easing within the element window")
            if prop == "scale" and element["kind"] != "image":
                raise AEExportError("initial After Effects scale keyframes require an image element")
        for element in scene["elements"]:
            axes = {animation["property"]: animation["keyframes"] for animation in scene["animations"]
                    if animation["targetId"] == element["id"] and animation["property"] in ("x", "y")}
            if axes:
                frames = sorted({frame for keys in axes.values() for frame in _track_frames(keys)})
                position_tracks[scene["id"] + "/" + element["id"]] = [
                    {"frame": frame,
                     "value": [(_animation_value(axes["x"], frame) if "x" in axes else element["bounds"]["x"]) + element["bounds"]["width"] / 2,
                               (_animation_value(axes["y"], frame) if "y" in axes else element["bounds"]["y"]) + element["bounds"]["height"] / 2]}
                    for frame in frames]
            opacity = next((animation["keyframes"] for animation in scene["animations"]
                            if animation["targetId"] == element["id"] and animation["property"] == "opacity"), None)
            if opacity:
                opacity_tracks[scene["id"] + "/" + element["id"]] = [
                    {"frame": frame, "value": _animation_value(opacity, frame) * 100}
                    for frame in _track_frames(opacity)]
            scale = next((animation["keyframes"] for animation in scene["animations"]
                          if animation["targetId"] == element["id"] and animation["property"] == "scale"), None)
            if scale:
                asset = images_by_id[element["assetId"]]
                base_x = element["bounds"]["width"] / asset["width"] * 100
                base_y = element["bounds"]["height"] / asset["height"] * 100
                if element["params"].get("fit", "contain") == "contain":
                    base_x = base_y = min(base_x, base_y)
                scale_tracks[scene["id"] + "/" + element["id"]] = [
                    {"frame": frame,
                     "value": [base_x * _animation_value(scale, frame),
                               base_y * _animation_value(scale, frame)]}
                    for frame in _track_frames(scale)]
    output = Path(aep_path).resolve()
    report = Path(report_path).resolve()
    script = Path(script_path).resolve()
    if len({output, report, script}) != 3:
        raise AEExportError("script, report, and AEP must have distinct paths")
    if output.exists() or report.exists() or script.exists():
        raise AEExportError("script, report, and AEP output paths must not already exist")
    for path in (output, report, script):
        path.parent.mkdir(parents=True, exist_ok=True)
    job = {"spec": spec, "aep": output.as_posix(), "report": report.as_posix(),
           "imageAssets": images, "positionTracks": position_tracks,
           "opacityTracks": opacity_tracks, "scaleTracks": scale_tracks,
           "layerOrder": layer_order}
    payload = json.dumps(job, ensure_ascii=True, separators=(",", ":"))
    source = "var job = " + payload + ";\n" + _SCRIPT
    script.write_text(source, encoding="utf-8")
    return script


_SCRIPT = r'''
(function () {
    var reportFile = new File(job.report);
    var outputFile = new File(job.aep);
    var owned = false;
    function finish(text) { reportFile.open("w"); reportFile.write(text); reportFile.close(); }
    try {
        if (app.project.file || app.project.numItems > 0) throw new Error("After Effects has an open project");
        if (outputFile.exists) throw new Error("AEP output already exists");
        app.newProject();
        owned = true;
        var spec = job.spec;
        var rate = spec.canvas.frameRate.numerator / spec.canvas.frameRate.denominator;
        var duration = spec.canvas.durationFrames / rate;
        var master = app.project.items.addComp(spec.project.id + "_master", spec.canvas.width,
            spec.canvas.height, 1, duration, rate);
        master.bgColor = hexColor(spec.canvas.background || "#000000");
        var expected = [];
        var expectedBeats = [];
        var footageById = {};
        for (var f = 0; f < job.imageAssets.length; f++) {
            var imageAsset = job.imageAssets[f];
            var file = new File(imageAsset.path);
            if (!file.exists) throw new Error("image asset missing: " + imageAsset.id);
            var options = new ImportOptions(file);
            options.sequence = false;
            var footage = app.project.importFile(options);
            if (footage.width !== imageAsset.width || footage.height !== imageAsset.height)
                throw new Error("image dimensions changed: " + imageAsset.id);
            footageById[imageAsset.id] = footage;
        }
        for (var i = 0; i < spec.timeline.length; i++) {
            var scene = spec.timeline[i];
            var sceneComp = app.project.items.addComp(scene.id, spec.canvas.width, spec.canvas.height,
                1, (scene.endFrameExclusive - scene.startFrame) / rate, rate);
            sceneComp.bgColor = master.bgColor;
            var parent = master.layers.add(sceneComp);
            parent.name = scene.id;
            parent.startTime = scene.startFrame / rate;
            parent.inPoint = scene.startFrame / rate;
            parent.outPoint = scene.endFrameExclusive / rate;
            expected.push({name: scene.id, count: scene.elements.length});
            for (var q = 0; q < scene.beats.length; q++) {
                var beat = scene.beats[q];
                var marker = new MarkerValue(scene.id + "/" + beat.id);
                marker.duration = (beat.endFrameExclusive - beat.startFrame) / rate;
                master.markerProperty.setValueAtTime(beat.startFrame / rate, marker);
                expectedBeats.push({comment: marker.comment, start: beat.startFrame / rate,
                    duration: marker.duration});
            }
            for (var j = 0; j < scene.elements.length; j++) {
                var element = scene.elements[job.layerOrder[i][j]];
                var layer;
                if (element.kind === "text") {
                    var wrapped = element.params.wrap === true;
                    layer = wrapped ? sceneComp.layers.addBoxText([element.bounds.width, element.bounds.height]) :
                        sceneComp.layers.addText(element.text.value);
                    var tdProp = layer.property("Source Text");
                    var td = tdProp.value;
                    if (wrapped) {
                        td.text = element.text.value;
                        td.boxTextPos = [-element.bounds.width / 2, -element.bounds.height / 2];
                    }
                    td.fontSize = element.params.fontSize || Math.max(1, Math.min(element.bounds.height * 0.52, 90));
                    td.fillColor = hexColor(element.params.color || "#FFFFFF");
                    td.applyFill = true;
                    td.applyStroke = false;
                    var align = element.text.align || "left";
                    if (align === "center") td.justification = ParagraphJustification.CENTER_JUSTIFY;
                    else if (align === "right" || align === "end") td.justification = ParagraphJustification.RIGHT_JUSTIFY;
                    else td.justification = ParagraphJustification.LEFT_JUSTIFY;
                    if (element.text.fontFamily) {
                        var style = (element.text.fontWeight || 400) >= 600 ? "Bold" : "Regular";
                        var matches = app.fonts.getFontsByFamilyNameAndStyleName(element.text.fontFamily, style);
                        if (matches.length !== 1) throw new Error("font must resolve uniquely: " + element.text.fontFamily + " " + style);
                        td.fontObject = matches[0];
                    }
                    tdProp.setValue(td);
                } else if (element.kind === "shape") {
                    layer = sceneComp.layers.addShape();
                    var contents = layer.property("ADBE Root Vectors Group");
                    var rectangle = contents.addProperty("ADBE Vector Shape - Rect");
                    rectangle.property("ADBE Vector Rect Size").setValue([element.bounds.width, element.bounds.height]);
                    var fill = contents.addProperty("ADBE Vector Graphic - Fill");
                    fill.property("ADBE Vector Fill Color").setValue(hexColor(element.params.color || "#FFFFFF"));
                } else {
                    var footageItem = footageById[element.assetId];
                    layer = sceneComp.layers.add(footageItem);
                    var sx = element.bounds.width / footageItem.width * 100;
                    var sy = element.bounds.height / footageItem.height * 100;
                    if ((element.params.fit || "contain") === "contain") sx = sy = Math.min(sx, sy);
                    layer.property("Transform").property("Scale").setValue([sx, sy]);
                }
                layer.name = element.id;
                layer.comment = "MotionSpec:" + scene.id + "/" + element.id;
                layer.inPoint = (element.startFrame - scene.startFrame) / rate;
                layer.outPoint = (element.endFrameExclusive - scene.startFrame) / rate;
                layer.property("Transform").property("Position").setValue([
                    element.bounds.x + element.bounds.width / 2,
                    element.bounds.y + element.bounds.height / 2
                ]);
                var positionTrack = job.positionTracks[scene.id + "/" + element.id];
                if (positionTrack) {
                    var position = layer.property("Transform").property("Position");
                    for (var p = 0; p < positionTrack.length; p++)
                        position.setValueAtTime((positionTrack[p].frame - scene.startFrame) / rate,
                            positionTrack[p].value);
                    for (var p = 1; p <= position.numKeys; p++)
                        position.setInterpolationTypeAtKey(p, KeyframeInterpolationType.LINEAR,
                            KeyframeInterpolationType.LINEAR);
                }
                var opacityTrack = job.opacityTracks[scene.id + "/" + element.id];
                if (opacityTrack) {
                    var opacity = layer.property("Transform").property("Opacity");
                    for (var n = 0; n < opacityTrack.length; n++)
                        opacity.setValueAtTime((opacityTrack[n].frame - scene.startFrame) / rate,
                            opacityTrack[n].value);
                    for (var n = 1; n <= opacity.numKeys; n++)
                        opacity.setInterpolationTypeAtKey(n, KeyframeInterpolationType.LINEAR,
                            KeyframeInterpolationType.LINEAR);
                }
                var scaleTrack = job.scaleTracks[scene.id + "/" + element.id];
                if (scaleTrack) {
                    var scale = layer.property("Transform").property("Scale");
                    for (var s = 0; s < scaleTrack.length; s++)
                        scale.setValueAtTime((scaleTrack[s].frame - scene.startFrame) / rate,
                            scaleTrack[s].value);
                    for (var s = 1; s <= scale.numKeys; s++)
                        scale.setInterpolationTypeAtKey(s, KeyframeInterpolationType.LINEAR,
                            KeyframeInterpolationType.LINEAR);
                }
            }
        }
        app.project.save(outputFile);
        app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
        app.open(outputFile);
        var foundMaster = null;
        for (var a = 1; a <= app.project.numItems; a++) {
            var candidate = app.project.item(a);
            if (candidate instanceof CompItem && candidate.name === spec.project.id + "_master") foundMaster = candidate;
        }
        if (!foundMaster || foundMaster.numLayers !== expected.length ||
            foundMaster.width !== spec.canvas.width || foundMaster.height !== spec.canvas.height ||
            Math.abs(foundMaster.duration - duration) > 0.0001) throw new Error("reopened master mismatch");
        if (foundMaster.markerProperty.numKeys !== expectedBeats.length)
            throw new Error("reopened beat marker count mismatch");
        for (var m = 0; m < expectedBeats.length; m++) {
            var actualMarker = foundMaster.markerProperty.keyValue(m + 1);
            if (actualMarker.comment !== expectedBeats[m].comment ||
                Math.abs(foundMaster.markerProperty.keyTime(m + 1) - expectedBeats[m].start) > 0.0001 ||
                Math.abs(actualMarker.duration - expectedBeats[m].duration) > 0.0001)
                throw new Error("reopened beat marker mismatch: " + expectedBeats[m].comment);
        }
        for (var b = 0; b < expected.length; b++) {
            var entry = expected[b];
            var sceneLayer = foundMaster.layer(expected.length - b);
            if (!sceneLayer || sceneLayer.name !== entry.name || sceneLayer.source.numLayers !== entry.count)
                throw new Error("reopened scene mismatch: " + entry.name);
            if (Math.abs(sceneLayer.inPoint - spec.timeline[b].startFrame / rate) > 0.0001 ||
                Math.abs(sceneLayer.outPoint - spec.timeline[b].endFrameExclusive / rate) > 0.0001)
                throw new Error("reopened scene timing mismatch: " + entry.name);
            var original = spec.timeline[b].elements;
            for (var c = 0; c < original.length; c++) {
                var reopenedText = sceneLayer.source.layer(original.length - c);
                var expectedElement = original[job.layerOrder[b][c]];
                if (!reopenedText || reopenedText.name !== expectedElement.id)
                    throw new Error("reopened element or layer order mismatch: " + expectedElement.id);
                if (Math.abs(reopenedText.inPoint - (expectedElement.startFrame - spec.timeline[b].startFrame) / rate) > 0.0001 ||
                    Math.abs(reopenedText.outPoint - (expectedElement.endFrameExclusive - spec.timeline[b].startFrame) / rate) > 0.0001)
                    throw new Error("reopened element timing mismatch: " + expectedElement.id);
                var positionTrack = job.positionTracks[spec.timeline[b].id + "/" + expectedElement.id];
                if (positionTrack) {
                    var reopenedPosition = reopenedText.property("Transform").property("Position");
                    if (reopenedPosition.numKeys !== positionTrack.length)
                        throw new Error("reopened position key count mismatch: " + expectedElement.id);
                    for (var p = 0; p < positionTrack.length; p++) {
                        var positionValue = reopenedPosition.keyValue(p + 1);
                        if (Math.abs(reopenedPosition.keyTime(p + 1) -
                                     (positionTrack[p].frame - spec.timeline[b].startFrame) / rate) > 0.0001 ||
                            Math.abs(positionValue[0] - positionTrack[p].value[0]) > 0.001 ||
                            Math.abs(positionValue[1] - positionTrack[p].value[1]) > 0.001)
                            throw new Error("reopened position key mismatch: " + expectedElement.id);
                    }
                }
                var opacityTrack = job.opacityTracks[spec.timeline[b].id + "/" + expectedElement.id];
                if (opacityTrack) {
                    var reopenedOpacity = reopenedText.property("Transform").property("Opacity");
                    if (reopenedOpacity.numKeys !== opacityTrack.length)
                        throw new Error("reopened opacity key count mismatch: " + expectedElement.id);
                    for (var o = 0; o < opacityTrack.length; o++)
                        if (Math.abs(reopenedOpacity.keyTime(o + 1) -
                                     (opacityTrack[o].frame - spec.timeline[b].startFrame) / rate) > 0.0001 ||
                            Math.abs(reopenedOpacity.keyValue(o + 1) - opacityTrack[o].value) > 0.001)
                            throw new Error("reopened opacity key mismatch: " + expectedElement.id);
                }
                var scaleTrack = job.scaleTracks[spec.timeline[b].id + "/" + expectedElement.id];
                if (scaleTrack) {
                    var reopenedScale = reopenedText.property("Transform").property("Scale");
                    if (reopenedScale.numKeys !== scaleTrack.length)
                        throw new Error("reopened scale key count mismatch: " + expectedElement.id);
                    for (var s = 0; s < scaleTrack.length; s++) {
                        var scaleValue = reopenedScale.keyValue(s + 1);
                        if (Math.abs(reopenedScale.keyTime(s + 1) -
                                     (scaleTrack[s].frame - spec.timeline[b].startFrame) / rate) > 0.0001 ||
                            Math.abs(scaleValue[0] - scaleTrack[s].value[0]) > 0.001 ||
                            Math.abs(scaleValue[1] - scaleTrack[s].value[1]) > 0.001)
                            throw new Error("reopened scale key mismatch: " + expectedElement.id);
                    }
                }
                if (expectedElement.kind === "text") {
                    var reopenedDocument = reopenedText.property("Source Text").value;
                    if (reopenedDocument.text !== expectedElement.text.value)
                        throw new Error("reopened text mismatch: " + expectedElement.id);
                    if (expectedElement.text.fontFamily && reopenedDocument.fontObject.familyName !== expectedElement.text.fontFamily)
                        throw new Error("reopened font mismatch: " + expectedElement.id);
                    if (reopenedDocument.boxText !== (expectedElement.params.wrap === true))
                        throw new Error("reopened text box type mismatch: " + expectedElement.id);
                    if (expectedElement.params.wrap === true &&
                        (Math.abs(reopenedDocument.boxTextSize[0] - expectedElement.bounds.width) > 0.001 ||
                         Math.abs(reopenedDocument.boxTextSize[1] - expectedElement.bounds.height) > 0.001 ||
                         Math.abs(reopenedDocument.boxTextPos[0] + expectedElement.bounds.width / 2) > 0.001 ||
                         Math.abs(reopenedDocument.boxTextPos[1] + expectedElement.bounds.height / 2) > 0.001))
                        throw new Error("reopened text box geometry mismatch: " + expectedElement.id);
                } else if (expectedElement.kind === "shape") {
                    var shape = reopenedText.property("ADBE Root Vectors Group").property("ADBE Vector Shape - Rect");
                    if (!shape || Math.abs(shape.property("ADBE Vector Rect Size").value[0] - expectedElement.bounds.width) > 0.001 ||
                        Math.abs(shape.property("ADBE Vector Rect Size").value[1] - expectedElement.bounds.height) > 0.001)
                        throw new Error("reopened rectangle mismatch: " + expectedElement.id);
                } else {
                    var linked = reopenedText.source;
                    if (!(linked instanceof FootageItem) || linked.footageMissing ||
                        !linked.mainSource.file || !linked.mainSource.file.exists)
                        throw new Error("reopened image link missing: " + expectedElement.id);
                    var assetInfo = null;
                    for (var z = 0; z < job.imageAssets.length; z++)
                        if (job.imageAssets[z].id === expectedElement.assetId) assetInfo = job.imageAssets[z];
                    if (!assetInfo || linked.width !== assetInfo.width || linked.height !== assetInfo.height)
                        throw new Error("reopened image dimensions mismatch: " + expectedElement.id);
                }
            }
        }
        finish("PASS|" + app.version + "|" + spec.project.id + "|" + expected.length);
        app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
    } catch (error) {
        finish("FAIL|" + error.toString());
        if (owned) try { app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES); } catch (ignored) {}
    }
    function hexColor(value) {
        return [parseInt(value.substr(1, 2), 16) / 255,
                parseInt(value.substr(3, 2), 16) / 255,
                parseInt(value.substr(5, 2), 16) / 255];
    }
}());
'''
