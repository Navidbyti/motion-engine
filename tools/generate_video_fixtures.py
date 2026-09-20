"""Regenerate two small synthetic moving-plate archives; no external media."""
from __future__ import annotations

import io
import json
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from PIL import Image, ImageDraw


ASSETS = Path(__file__).resolve().parents[1] / "examples" / "assets"


def _write(archive: ZipFile, name: str, content: bytes) -> None:
    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    archive.writestr(info, content)


def build(name: str, width: int, height: int, frames: int, fps: int,
          color: tuple[int, int, int], title: str, locale: str) -> None:
    path = ASSETS / f"{name}.zip"
    manifest = {"formatVersion": 1, "width": width, "height": height,
                "frameRate": {"numerator": fps, "denominator": 1}, "frameCount": frames}
    with ZipFile(path, "w") as archive:
        _write(archive, "manifest.json", json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode())
        for index in range(frames):
            image = Image.new("RGB", (width, height), (14, 20, 33))
            radius = min(width, height) // 5
            center_x = round(width * (0.25 + 0.5 * index / (frames - 1)))
            center_y = round(height * 0.45)
            ImageDraw.Draw(image).ellipse((center_x - radius, center_y - radius,
                                           center_x + radius, center_y + radius), fill=color)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            _write(archive, f"frames/{index:06d}.png", buffer.getvalue())
    source_name = f"{name}-source.txt"
    source = f"Synthetic moving-plate fixture. Exact overlay: {title}\n".encode("utf-8")
    (ASSETS / source_name).write_bytes(source)
    margin = min(width, height) // 12
    text_height = max(40, min(height // 3, 80))
    source_ref = {"sourceId": "fixture_source", "location": "line 1", "method": "synthetic fixture"}
    spec = {
        "schemaVersion": "1.0.0",
        "project": {"id": name.replace("-", "_"), "title": title, "locale": locale, "direction": "ltr"},
        "canvas": {"width": width, "height": height, "frameRate": manifest["frameRate"],
                   "durationFrames": frames, "colorSpace": "Rec.709", "background": "#0E1421",
                   "safeArea": {"top": margin, "right": margin, "bottom": margin, "left": margin}},
        "sources": [{"id": "fixture_source", "uri": f"assets/{source_name}", "mediaType": "text/plain",
                     "sha256": hashlib.sha256(source).hexdigest(), "authority": ["text", "visual"], "license": "MIT"}],
        "assets": [{"id": "moving_plate", "kind": "video.frames", "status": "available",
                    "uri": f"assets/{path.name}", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "license": "MIT", "approved": True, "sourceRefs": [source_ref]}],
        "datasets": [],
        "timeline": [{"id": "scene_1", "startFrame": 0, "endFrameExclusive": frames,
                      "transitionIn": "start", "elements": [
                          {"id": "plate", "kind": "video", "startFrame": 0, "endFrameExclusive": frames,
                           "bounds": {"x": 0, "y": 0, "width": width, "height": height},
                           "assetId": "moving_plate", "params": {"fit": "cover", "sourceStartFrame": 0}},
                          {"id": "title", "kind": "text", "startFrame": 0, "endFrameExclusive": frames,
                           "bounds": {"x": margin, "y": height - margin - text_height,
                                      "width": width - 2 * margin, "height": text_height},
                           "text": {"value": title, "locale": locale, "fontFamily": "DejaVu Sans", "align": "center"},
                           "params": {"color": "#FFFFFF", "fontSize": max(18, min(width // 13, 28)), "wrap": True},
                           "sourceRefs": [source_ref]}],
                      "beats": [{"id": "beat_1", "startFrame": 0, "endFrameExclusive": frames,
                                 "elementIds": ["plate", "title"], "onScreen": [{"value": title, "locale": locale}]}],
                      "animations": [], "sourceRefs": [source_ref]}],
        "deliverables": [{"id": "preview", "target": "video/mp4", "profile": "preview",
                          "required": True, "editable": False}],
        "policies": {"qa": [], "disclosures": [], "unsupportedFeature": "error"},
    }
    (ASSETS.parent / f"{name}.motion.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    ASSETS.mkdir(parents=True, exist_ok=True)
    build("moving-landscape", 320, 180, 24, 24, (19, 196, 217), "A moving idea", "en-US")
    build("moving-portrait", 180, 320, 30, 30, (235, 107, 60), "Une idée en mouvement", "fr-FR")
