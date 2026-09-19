"""Generate a narrow, inspectable After Effects ExtendScript build job."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .validation import validate


class AEExportError(ValueError):
    pass


def make_ae_script(spec: dict[str, Any], script_path: str | Path,
                   aep_path: str | Path, report_path: str | Path) -> Path:
    errors = validate(spec)
    if errors:
        raise AEExportError(f"invalid MotionSpec: {errors[0]}")
    if any(scene.get("transitionIn") != ("start" if index == 0 else "cut")
           for index, scene in enumerate(spec["timeline"])):
        raise AEExportError("initial After Effects adapter supports only scene cuts")
    if spec["assets"] or spec["policies"]["disclosures"]:
        raise AEExportError("initial After Effects adapter does not support assets or policy disclosures")
    if any(beat.get("voice", {}).get("value", "").strip()
           for scene in spec["timeline"] for beat in scene["beats"]):
        raise AEExportError("initial After Effects adapter does not support voice audio")
    for scene in spec["timeline"]:
        for element in scene["elements"]:
            if element["kind"] not in ("text", "shape"):
                raise AEExportError(f"initial After Effects adapter does not support {element['kind']}")
            if not element.get("bounds"):
                raise AEExportError(f"element {element['id']} needs bounds")
            if element.get("zIndex", 0):
                raise AEExportError("initial After Effects adapter uses array order, not zIndex")
            if element["kind"] == "text":
                if not element.get("text"):
                    raise AEExportError(f"text {element['id']} needs text")
                if set(element["params"]) - {"color", "fontSize"}:
                    raise AEExportError(f"text {element['id']} has unsupported parameters")
                if element["text"].get("direction", spec["project"].get("direction", "ltr")) == "rtl":
                    raise AEExportError("initial After Effects adapter has not verified RTL text")
            else:
                if set(element["params"]) - {"color", "shape"} or element["params"].get("shape", "rect") != "rect":
                    raise AEExportError(f"shape {element['id']} supports solid rectangles only")
        for animation in scene["animations"]:
            if animation["property"] != "opacity" or any(
                key.get("easing", "linear") != "linear" or not isinstance(key["value"], (int, float))
                or not 0 <= key["value"] <= 1 for key in animation["keyframes"]
            ):
                raise AEExportError("initial After Effects adapter supports only linear opacity keyframes from 0 to 1")
    output = Path(aep_path).resolve()
    report = Path(report_path).resolve()
    script = Path(script_path).resolve()
    if len({output, report, script}) != 3:
        raise AEExportError("script, report, and AEP must have distinct paths")
    if output.exists() or report.exists() or script.exists():
        raise AEExportError("script, report, and AEP output paths must not already exist")
    for path in (output, report, script):
        path.parent.mkdir(parents=True, exist_ok=True)
    job = {"spec": spec, "aep": output.as_posix(), "report": report.as_posix()}
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
            for (var j = 0; j < scene.elements.length; j++) {
                var element = scene.elements[j];
                var layer;
                if (element.kind === "text") {
                    layer = sceneComp.layers.addText(element.text.value);
                    var tdProp = layer.property("Source Text");
                    var td = tdProp.value;
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
                } else {
                    layer = sceneComp.layers.addShape();
                    var contents = layer.property("ADBE Root Vectors Group");
                    var rectangle = contents.addProperty("ADBE Vector Shape - Rect");
                    rectangle.property("ADBE Vector Rect Size").setValue([element.bounds.width, element.bounds.height]);
                    var fill = contents.addProperty("ADBE Vector Graphic - Fill");
                    fill.property("ADBE Vector Fill Color").setValue(hexColor(element.params.color || "#FFFFFF"));
                }
                layer.name = element.id;
                layer.comment = "MotionSpec:" + scene.id + "/" + element.id;
                layer.inPoint = (element.startFrame - scene.startFrame) / rate;
                layer.outPoint = (element.endFrameExclusive - scene.startFrame) / rate;
                layer.property("Transform").property("Position").setValue([
                    element.bounds.x + element.bounds.width / 2,
                    element.bounds.y + element.bounds.height / 2
                ]);
                for (var k = 0; k < scene.animations.length; k++) {
                    var animation = scene.animations[k];
                    if (animation.targetId !== element.id) continue;
                    var opacity = layer.property("Transform").property("Opacity");
                    for (var n = 0; n < animation.keyframes.length; n++) {
                        var key = animation.keyframes[n];
                        opacity.setValueAtTime((key.frame - scene.startFrame) / rate, key.value * 100);
                    }
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
                if (!reopenedText || reopenedText.name !== original[c].id)
                    throw new Error("reopened element mismatch: " + original[c].id);
                if (Math.abs(reopenedText.inPoint - (original[c].startFrame - spec.timeline[b].startFrame) / rate) > 0.0001 ||
                    Math.abs(reopenedText.outPoint - (original[c].endFrameExclusive - spec.timeline[b].startFrame) / rate) > 0.0001)
                    throw new Error("reopened element timing mismatch: " + original[c].id);
                if (original[c].kind === "text") {
                    if (reopenedText.property("Source Text").value.text !== original[c].text.value)
                        throw new Error("reopened text mismatch: " + original[c].id);
                    if (original[c].text.fontFamily && reopenedText.property("Source Text").value.fontObject.familyName !== original[c].text.fontFamily)
                        throw new Error("reopened font mismatch: " + original[c].id);
                } else {
                    var shape = reopenedText.property("ADBE Root Vectors Group").property("ADBE Vector Shape - Rect");
                    if (!shape || Math.abs(shape.property("ADBE Vector Rect Size").value[0] - original[c].bounds.width) > 0.001 ||
                        Math.abs(shape.property("ADBE Vector Rect Size").value[1] - original[c].bounds.height) > 0.001)
                        throw new Error("reopened rectangle mismatch: " + original[c].id);
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
