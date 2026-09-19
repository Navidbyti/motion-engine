"""Generate a narrow Photoshop JSX job for a static, layered PSD."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .validation import validate


class PSExportError(ValueError):
    pass


def make_ps_script(spec: dict[str, Any], script_path: str | Path,
                   psd_path: str | Path, report_path: str | Path) -> Path:
    errors = validate(spec)
    if errors:
        raise PSExportError(f"invalid MotionSpec: {errors[0]}")
    if len(spec["timeline"]) != 1:
        raise PSExportError("initial Photoshop adapter supports one static scene per PSD")
    if spec["assets"] or spec["datasets"]:
        raise PSExportError("initial Photoshop adapter supports no external assets or datasets")
    if spec["policies"]["disclosures"]:
        raise PSExportError("initial Photoshop adapter does not support policy disclosures")
    scene = spec["timeline"][0]
    if scene["animations"]:
        raise PSExportError("Photoshop static PSD cannot preserve animation")
    if scene["transitionIn"] != "start":
        raise PSExportError("initial Photoshop adapter supports only a scene start")
    for element in scene["elements"]:
        if element["kind"] not in ("text", "shape"):
            raise PSExportError(f"initial Photoshop adapter does not support {element['kind']}")
        if element["startFrame"] != scene["startFrame"] or element["endFrameExclusive"] != scene["endFrameExclusive"]:
            raise PSExportError(f"element {element['id']} must cover its whole static scene")
        if not element.get("bounds"):
            raise PSExportError(f"element {element['id']} needs bounds")
        bounds = element["bounds"]
        if (bounds["x"] < 0 or bounds["y"] < 0 or
                bounds["x"] + bounds["width"] > spec["canvas"]["width"] or
                bounds["y"] + bounds["height"] > spec["canvas"]["height"]):
            raise PSExportError(f"element {element['id']} must fit inside its PSD canvas")
        if element.get("zIndex", 0):
            raise PSExportError("initial Photoshop adapter uses array order, not zIndex")
        if element["kind"] == "shape":
            if set(element["params"]) - {"color", "shape"} or element["params"].get("shape", "rect") != "rect":
                raise PSExportError(f"shape {element['id']} supports solid rectangles only")
        else:
            if not element.get("text") or not element["text"]["value"].strip() or "\n" in element["text"]["value"]:
                raise PSExportError(f"text {element['id']} must be a single nonempty line")
            if set(element["params"]) - {"color", "fontSize"}:
                raise PSExportError(f"text {element['id']} has unsupported parameters")
            if not element["text"].get("fontFamily"):
                raise PSExportError(f"text {element['id']} needs an explicit installed font family")
            if element["text"].get("direction", spec["project"].get("direction", "ltr")) != "ltr":
                raise PSExportError("initial Photoshop adapter supports explicit LTR text only")
            if element["text"].get("align", "left") not in ("left", "start"):
                raise PSExportError(f"text {element['id']} supports left alignment only")
            if element["text"].get("digitPolicy", "none") != "none":
                raise PSExportError(f"text {element['id']} has an unsupported digit policy")
    script, output, report = (Path(path).resolve() for path in (script_path, psd_path, report_path))
    if len({script, output, report}) != 3:
        raise PSExportError("script, report, and PSD must have distinct paths")
    if any(path.exists() for path in (script, output, report)):
        raise PSExportError("script, report, and PSD output paths must not already exist")
    for path in (script, output, report):
        path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"spec": spec, "psd": output.as_posix(), "report": report.as_posix()},
                         ensure_ascii=True, separators=(",", ":"))
    script.write_text("var job = " + payload + ";\n" + _SCRIPT, encoding="utf-8")
    return script


_SCRIPT = r'''
(function () {
    var output = new File(job.psd), report = new File(job.report);
    var doc = null, oldUnits = app.preferences.rulerUnits;
    function finish(message) { report.open("w"); report.write(message); report.close(); }
    function color(value) {
        if (!/^#[0-9a-fA-F]{6}$/.test(value)) throw new Error("invalid color: " + value);
        var result = new SolidColor();
        result.rgb.hexValue = value.substr(1);
        return result;
    }
    function fontFor(family, weight) {
        var style = weight >= 600 ? "Bold" : "Regular", matches = [];
        for (var i = 0; i < app.fonts.length; i++) {
            var font = app.fonts[i];
            if (font.family === family && font.style === style) matches.push(font);
        }
        if (matches.length !== 1) throw new Error("font must resolve uniquely: " + family + " " + style);
        return matches[0].postScriptName;
    }
    function findLayer(name) {
        for (var i = 0; i < doc.artLayers.length; i++) if (doc.artLayers[i].name === name) return doc.artLayers[i];
        return null;
    }
    try {
        if (app.documents.length !== 0) throw new Error("Photoshop has an open document");
        if (output.exists) throw new Error("PSD output already exists");
        app.preferences.rulerUnits = Units.PIXELS;
        var spec = job.spec, scene = spec.timeline[0];
        doc = app.documents.add(UnitValue(spec.canvas.width, "px"),
            UnitValue(spec.canvas.height, "px"), 72, spec.project.id,
            NewDocumentMode.RGB, DocumentFill.TRANSPARENT);
        // The PSD carries the source mapping even when the JSX job is moved.
        var provenance = {projectId: spec.project.id, sceneId: scene.id,
            sceneSourceRefs: scene.sourceRefs, elements: []};
        var background = doc.artLayers.add();
        background.name = "__background";
        doc.selection.select([[0, 0], [spec.canvas.width, 0],
            [spec.canvas.width, spec.canvas.height], [0, spec.canvas.height]]);
        doc.selection.fill(color(spec.canvas.background || "#000000"));
        doc.selection.deselect();
        var expected = [];
        for (var e = 0; e < scene.elements.length; e++) {
            var element = scene.elements[e], b = element.bounds;
            var layer = doc.artLayers.add();
            layer.name = element.id;
            if (element.kind === "shape") {
                doc.selection.select([[b.x, b.y], [b.x + b.width, b.y],
                    [b.x + b.width, b.y + b.height], [b.x, b.y + b.height]]);
                doc.selection.fill(color(element.params.color || "#FFFFFF"));
                doc.selection.deselect();
            } else {
                layer.kind = LayerKind.TEXT;
                layer.textItem.contents = element.text.value;
                var size = element.params.fontSize || Math.max(1, Math.min(b.height * 0.52, 90));
                layer.textItem.position = [b.x, b.y + size];
                layer.textItem.size = size;
                layer.textItem.color = color(element.params.color || "#FFFFFF");
                layer.textItem.font = fontFor(element.text.fontFamily, element.text.fontWeight || 400);
            }
            expected.push({name: element.id, kind: element.kind,
                text: element.kind === "text" ? element.text.value : null,
                font: element.kind === "text" ? layer.textItem.font : null});
            provenance.elements.push({id: element.id, sourceRefs: element.sourceRefs || []});
        }
        var caption = JSON.stringify(provenance);
        doc.info.caption = caption;
        var options = new PhotoshopSaveOptions();
        options.layers = true;
        options.embedColorProfile = true;
        doc.saveAs(output, options, true);
        doc.close(SaveOptions.DONOTSAVECHANGES);
        doc = null;
        doc = app.open(output);
        if (doc.width.value !== spec.canvas.width || doc.height.value !== spec.canvas.height)
            throw new Error("reopened PSD dimensions mismatch");
        if (doc.info.caption !== caption) throw new Error("reopened source provenance mismatch");
        if (!findLayer("__background")) throw new Error("reopened background layer missing");
        for (var n = 0; n < expected.length; n++) {
            var item = expected[n], actual = findLayer(item.name);
            if (!actual) throw new Error("reopened layer missing: " + item.name);
            if (item.kind === "text") {
                if (actual.kind !== LayerKind.TEXT || actual.textItem.contents !== item.text)
                    throw new Error("reopened editable text mismatch: " + item.name);
                if (actual.textItem.font !== item.font)
                    throw new Error("reopened font mismatch: " + item.name);
            } else if (actual.kind !== LayerKind.NORMAL) {
                throw new Error("reopened rectangle layer type mismatch: " + item.name);
            }
        }
        finish("PASS|" + app.version + "|layers=" + doc.artLayers.length);
    } catch (error) {
        finish("FAIL|" + app.version + "|" + error.toString());
    } finally {
        if (doc !== null) doc.close(SaveOptions.DONOTSAVECHANGES);
        app.preferences.rulerUnits = oldUnits;
    }
})();
'''
