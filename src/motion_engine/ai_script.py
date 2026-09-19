"""Generate an Illustrator job for static, editable scene artboards."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .validation import validate


class AIExportError(ValueError):
    pass


def make_ai_script(spec: dict[str, Any], script_path: str | Path,
                   ai_path: str | Path, report_path: str | Path) -> Path:
    errors = validate(spec)
    if errors:
        raise AIExportError(f"invalid MotionSpec: {errors[0]}")
    if spec["assets"] or spec["datasets"]:
        raise AIExportError("initial Illustrator adapter supports no external assets or datasets")
    if spec["policies"]["disclosures"]:
        raise AIExportError("initial Illustrator adapter does not support policy disclosures")
    if any(scene["animations"] for scene in spec["timeline"]):
        raise AIExportError("Illustrator static artboards cannot preserve animation")
    if len(spec["timeline"]) > 100:
        raise AIExportError("Illustrator supports at most 100 artboards")
    for scene in spec["timeline"]:
        if scene["transitionIn"] != ("start" if scene is spec["timeline"][0] else "cut"):
            raise AIExportError("initial Illustrator adapter supports only scene cuts")
        for element in scene["elements"]:
            if element["kind"] not in ("text", "shape"):
                raise AIExportError(f"initial Illustrator adapter does not support {element['kind']}")
            if element["startFrame"] != scene["startFrame"] or element["endFrameExclusive"] != scene["endFrameExclusive"]:
                raise AIExportError(f"element {element['id']} must cover its whole static scene")
            if not element.get("bounds"):
                raise AIExportError(f"element {element['id']} needs bounds")
            if element.get("zIndex", 0):
                raise AIExportError("initial Illustrator adapter uses array order, not zIndex")
            if element["kind"] == "shape":
                if set(element["params"]) - {"color", "shape"} or element["params"].get("shape", "rect") != "rect":
                    raise AIExportError(f"shape {element['id']} supports solid rectangles only")
            else:
                if not element.get("text") or "\n" in element["text"]["value"]:
                    raise AIExportError(f"text {element['id']} must be a single nonempty line")
                if set(element["params"]) - {"color", "fontSize"}:
                    raise AIExportError(f"text {element['id']} has unsupported parameters")
                if element["text"].get("direction", spec["project"].get("direction", "ltr")) == "rtl":
                    raise AIExportError("initial Illustrator adapter has not verified RTL text")
                if element["text"].get("align", "left") not in ("left", "start"):
                    raise AIExportError(f"text {element['id']} supports left alignment only")
    script, output, report = (Path(path).resolve() for path in (script_path, ai_path, report_path))
    if len({script, output, report}) != 3:
        raise AIExportError("script, report, and AI must have distinct paths")
    if any(path.exists() for path in (script, output, report)):
        raise AIExportError("script, report, and AI output paths must not already exist")
    for path in (script, output, report):
        path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"spec": spec, "ai": output.as_posix(), "report": report.as_posix()},
                         ensure_ascii=True, separators=(",", ":"))
    script.write_text("var job = " + payload + ";\n" + _SCRIPT, encoding="utf-8")
    return script


_SCRIPT = r'''
(function () {
    var output = new File(job.ai);
    var report = new File(job.report);
    var doc = null;
    function finish(message) { report.open("w"); report.write(message); report.close(); }
    function rgb(value) {
        if (!/^#[0-9a-fA-F]{6}$/.test(value)) throw new Error("invalid color: " + value);
        var color = new RGBColor();
        color.red = parseInt(value.substr(1, 2), 16);
        color.green = parseInt(value.substr(3, 2), 16);
        color.blue = parseInt(value.substr(5, 2), 16);
        return color;
    }
    function fontFor(family, weight) {
        var wanted = weight >= 600 ? "Bold" : "Regular";
        var matches = [];
        for (var i = 0; i < app.textFonts.length; i++) {
            var font = app.textFonts[i];
            if (font.family === family && font.style === wanted) matches.push(font);
        }
        if (matches.length !== 1) throw new Error("font must resolve uniquely: " + family + " " + wanted);
        return matches[0];
    }
    function findNamed(collection, name) {
        for (var i = 0; i < collection.length; i++) if (collection[i].name === name) return collection[i];
        return null;
    }
    try {
        if (app.documents.length !== 0) throw new Error("Illustrator has an open document");
        if (output.exists) throw new Error("AI output already exists");
        var spec = job.spec;
        var width = spec.canvas.width, height = spec.canvas.height;
        doc = app.documents.add(DocumentColorSpace.RGB, width, height);
        var artboards = doc.artboards;
        var expectations = [];
        for (var s = 0; s < spec.timeline.length; s++) {
            var scene = spec.timeline[s];
            var left = s * (width + 100);
            var rect = [left, 0, left + width, -height];
            if (s === 0) artboards[0].artboardRect = rect;
            else artboards.add(rect);
            artboards[s].name = scene.id;
            var layer = s === 0 ? doc.layers[0] : doc.layers.add();
            layer.name = scene.id;
            var background = layer.pathItems.rectangle(0, left, width, height);
            background.name = "__background";
            background.filled = true;
            background.fillColor = rgb(spec.canvas.background || "#000000");
            background.stroked = false;
            var expected = {name: scene.id, elements: []};
            for (var e = 0; e < scene.elements.length; e++) {
                var element = scene.elements[e], b = element.bounds, item;
                if (element.kind === "shape") {
                    item = layer.pathItems.rectangle(-b.y, left + b.x, b.width, b.height);
                    item.filled = true;
                    item.fillColor = rgb(element.params.color || "#FFFFFF");
                    item.stroked = false;
                } else {
                    item = layer.textFrames.add();
                    item.contents = element.text.value;
                    var size = element.params.fontSize || Math.max(1, Math.min(b.height * 0.52, 90));
                    item.position = [left + b.x, -b.y - size];
                    item.textRange.characterAttributes.size = size;
                    item.textRange.characterAttributes.fillColor = rgb(element.params.color || "#FFFFFF");
                    item.textRange.characterAttributes.textFont = fontFor(element.text.fontFamily, element.text.fontWeight || 400);
                }
                item.name = element.id;
                expected.elements.push({name: element.id, kind: element.kind,
                    text: element.kind === "text" ? element.text.value : null,
                    fontFamily: element.kind === "text" ? element.text.fontFamily : null});
            }
            expectations.push(expected);
        }
        var options = new IllustratorSaveOptions();
        options.pdfCompatible = true;
        doc.saveAs(output, options);
        doc.close(SaveOptions.DONOTSAVECHANGES);
        doc = null;
        doc = app.open(output);
        if (doc.artboards.length !== expectations.length) throw new Error("reopened artboard count mismatch");
        for (var a = 0; a < expectations.length; a++) {
            var check = expectations[a];
            if (doc.artboards[a].name !== check.name) throw new Error("reopened artboard name mismatch: " + check.name);
            var board = doc.artboards[a].artboardRect;
            if (Math.abs(board[2] - board[0] - width) > 0.01 ||
                Math.abs(board[1] - board[3] - height) > 0.01)
                throw new Error("reopened artboard size mismatch: " + check.name);
            var layer = findNamed(doc.layers, check.name);
            if (!layer) throw new Error("reopened layer missing: " + check.name);
            if (!findNamed(layer.pathItems, "__background"))
                throw new Error("reopened background missing: " + check.name);
            for (var n = 0; n < check.elements.length; n++) {
                var wanted = check.elements[n];
                var item = findNamed(wanted.kind === "text" ? layer.textFrames : layer.pathItems, wanted.name);
                if (!item) throw new Error("reopened editable object missing: " + wanted.name);
                if (wanted.kind === "text" && item.contents !== wanted.text)
                    throw new Error("reopened text mismatch: " + wanted.name);
                if (wanted.kind === "text" && item.textRange.characterAttributes.textFont.family !== wanted.fontFamily)
                    throw new Error("reopened font mismatch: " + wanted.name);
            }
        }
        finish("PASS|" + app.version + "|artboards=" + doc.artboards.length);
    } catch (error) {
        finish("FAIL|" + app.version + "|" + error.toString());
    } finally {
        if (doc !== null) doc.close(SaveOptions.DONOTSAVECHANGES);
    }
})();
'''
