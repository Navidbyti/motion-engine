"""Deterministic PNG and optional MP4 previews for supported MotionSpec elements.

This is a preview backend. It does not create editable Adobe projects or mix audio.
Unsupported elements fail before the first frame is written.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps, features

from .preview_contract import PREVIEW_ANIMATIONS_BY_KIND, PREVIEW_EASING, PREVIEW_KINDS, PREVIEW_PARAMS


class RenderError(ValueError):
    pass


def _rgb(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or len(value) != 7 or value[0] != "#":
        raise RenderError(f"invalid color {value!r}; expected #RRGGBB")
    try:
        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
    except ValueError as exc:
        raise RenderError(f"invalid color {value!r}") from exc


def _localize_digits(value: str, policy: str | None, locale: str) -> str:
    if policy == "locale":
        policy = "persian" if locale.lower().startswith("fa") else "arabic_indic" if locale.lower().startswith("ar") else "latin"
    if policy in (None, "none"):
        return value
    latin = "0123456789"
    persian = "۰۱۲۳۴۵۶۷۸۹"
    arabic = "٠١٢٣٤٥٦٧٨٩"
    target = {"latin": latin, "persian": persian, "arabic_indic": arabic}.get(policy)
    if target is None:
        raise RenderError(f"unsupported digit policy {policy!r}")
    return value.translate(str.maketrans(persian + arabic + latin, target * 3))


def _easing(value: float, name: str | None) -> float:
    if name in (None, "linear"):
        return value
    if name == "ease_out":
        return 1 - (1 - value) ** 3
    if name == "ease_in":
        return value ** 3
    if name == "ease_in_out":
        return value * value * (3 - 2 * value)
    if name == "hold":
        return 0
    raise RenderError(f"unsupported easing {name!r}")


def _interpolate(keyframes: list[dict[str, Any]], frame: int) -> float:
    if frame <= keyframes[0]["frame"]:
        return float(keyframes[0]["value"])
    for left, right in zip(keyframes, keyframes[1:]):
        if frame <= right["frame"]:
            if frame == right["frame"]:
                return float(right["value"])
            span = right["frame"] - left["frame"]
            t = _easing((frame - left["frame"]) / span, right.get("easing"))
            return float(left["value"]) + (float(right["value"]) - float(left["value"])) * t
    return float(keyframes[-1]["value"])


class FrameRenderer:
    def __init__(self, spec: dict[str, Any], scale: float = 1.0,
                 font_dirs: list[str | Path] | None = None,
                 asset_root: str | Path | None = None):
        if not 0 < scale <= 1:
            raise RenderError("scale must be greater than 0 and at most 1")
        self.spec = spec
        self.scale = scale
        canvas = spec["canvas"]
        self.width = max(1, round(canvas["width"] * scale))
        self.height = max(1, round(canvas["height"] * scale))
        self.duration = canvas["durationFrames"]
        self.background = _rgb(canvas.get("background", "#000000"))
        self.datasets = {d["id"]: d for d in spec["datasets"]}
        self.assets = {a["id"]: a for a in spec["assets"]}
        self.asset_root = Path(asset_root or ".").resolve()
        self.image_cache: dict[str, Image.Image] = {}
        self.font_dirs = [Path(p) for p in (font_dirs or [])]
        self.font_dirs += [Path("C:/Windows/Fonts"), Path("/usr/share/fonts"), Path("/Library/Fonts"), Path.home() / ".local/share/fonts"]
        self.font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}
        self.issues: list[dict[str, str]] = []
        self.animations: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for scene_index, scene in enumerate(spec["timeline"]):
            if scene.get("transitionIn") not in (None, "start" if scene_index == 0 else "cut"):
                raise RenderError(f"unsupported preview transition {scene['transitionIn']!r}")
            if any(beat.get("voice", {}).get("value", "").strip() for beat in scene["beats"]):
                raise RenderError("voice audio is not supported by the preview renderer")
            element_kinds = {element["id"]: element["kind"] for element in scene["elements"]}
            for element in scene["elements"]:
                if element["kind"] not in PREVIEW_KINDS:
                    raise RenderError(f"unsupported preview element {element['kind']!r} ({element['id']})")
                extra_params = set(element["params"]) - PREVIEW_PARAMS[element["kind"]]
                if extra_params:
                    raise RenderError(f"element {element['id']} has unsupported preview parameters {sorted(extra_params)}")
                if element["kind"] == "shape" and element["params"].get("shape", "rect") != "rect":
                    raise RenderError(f"shape {element['id']} supports rectangles only")
                if element["kind"] == "image":
                    if element["params"].get("fit", "contain") not in ("contain", "cover", "stretch"):
                        raise RenderError(f"image {element['id']} has unsupported fit mode")
                    self._load_image(element)
                if "bounds" not in element:
                    raise RenderError(f"preview element {element['id']} requires bounds")
                if element["kind"] == "text" and "text" not in element:
                    raise RenderError(f"text element {element['id']} requires text")
                if element["kind"].startswith("chart.") and "dataBinding" not in element:
                    raise RenderError(f"chart element {element['id']} requires dataBinding")
            for animation in scene["animations"]:
                kind = element_kinds.get(animation["targetId"])
                if kind is None or animation["property"] not in PREVIEW_ANIMATIONS_BY_KIND.get(kind, set()):
                    raise RenderError(f"unsupported preview animation {animation['property']!r} on {animation['targetId']}")
                if any(keyframe.get("easing", "linear") not in PREVIEW_EASING for keyframe in animation["keyframes"]):
                    raise RenderError(f"unsupported preview easing on {animation['targetId']}")
                self.animations.setdefault(animation["targetId"], {})[animation["property"]] = animation["keyframes"]
        if not features.check("raqm") and any(
            e.get("text", {}).get("direction") == "rtl" for s in spec["timeline"] for e in s["elements"]
        ):
            raise RenderError("Pillow with libraqm is required for right-to-left text preview")

    def _font(self, family: str, size: int) -> ImageFont.FreeTypeFont:
        key = (family.lower(), size)
        if key in self.font_cache:
            return self.font_cache[key]
        candidates = [family, family + ".ttf"]
        family_normalized = family.lower().replace(" ", "")
        for folder in self.font_dirs:
            if folder.is_dir():
                for path in folder.glob("*.ttf"):
                    if path.stem.lower().replace(" ", "") == family_normalized:
                        candidates.insert(0, str(path))
        for name in candidates:
            try:
                font = ImageFont.truetype(name, size, layout_engine=ImageFont.Layout.RAQM if features.check("raqm") else ImageFont.Layout.BASIC)
                self.font_cache[key] = font
                return font
            except OSError:
                continue
        for fallback in ("DejaVuSans.ttf", "Arial.ttf", "arial.ttf"):
            try:
                font = ImageFont.truetype(fallback, size, layout_engine=ImageFont.Layout.RAQM if features.check("raqm") else ImageFont.Layout.BASIC)
                self.font_cache[key] = font
                self.issues.append({"code": "font_substitution", "message": f"{family} unavailable; preview used {fallback}"})
                return font
            except OSError:
                continue
        raise RenderError(f"font {family!r} unavailable and no preview fallback found")

    def _bounds(self, value: dict[str, float]) -> tuple[int, int, int, int]:
        x, y = round(value["x"] * self.scale), round(value["y"] * self.scale)
        w, h = round(value["width"] * self.scale), round(value["height"] * self.scale)
        return x, y, max(1, w), max(1, h)

    def _load_image(self, element: dict[str, Any]) -> Image.Image:
        asset_id = element.get("assetId")
        if asset_id in self.image_cache:
            return self.image_cache[asset_id]
        asset = self.assets.get(asset_id)
        if not asset or asset.get("status") != "available":
            raise RenderError(f"image {element['id']} requires an available asset")
        uri = asset.get("uri", "")
        relative = Path(uri)
        if not uri or relative.is_absolute() or ".." in relative.parts or ":" in uri:
            raise RenderError(f"image asset {asset_id} needs a portable relative file URI")
        path = (self.asset_root / relative).resolve()
        if not path.is_relative_to(self.asset_root) or not path.is_file():
            raise RenderError(f"image asset {asset_id} is missing or outside asset root")
        expected = asset.get("sha256")
        if not expected:
            raise RenderError(f"image asset {asset_id} requires sha256")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RenderError(f"image asset {asset_id} hash mismatch")
        try:
            with Image.open(path) as source:
                if source.format not in ("PNG", "JPEG", "WEBP"):
                    raise RenderError(f"image asset {asset_id} format is unsupported")
                if source.width * source.height > 50_000_000:
                    raise RenderError(f"image asset {asset_id} exceeds 50 megapixels")
                image = ImageOps.exif_transpose(source).convert("RGBA")
        except (OSError, ValueError) as exc:
            raise RenderError(f"image asset {asset_id} cannot be decoded: {exc}") from exc
        self.image_cache[asset_id] = image
        return image

    def _property(self, element_id: str, property_name: str, frame: int, default: float) -> float:
        keyframes = self.animations.get(element_id, {}).get(property_name)
        return _interpolate(keyframes, frame) if keyframes else default

    def _text(self, image: Image.Image, element: dict[str, Any], frame: int) -> None:
        text = element["text"]
        value = _localize_digits(text["value"], text.get("digitPolicy"), text.get("locale", self.spec["project"]["locale"]))
        x, y, w, h = self._bounds(element["bounds"])
        font_size = max(1, round(element["params"].get("fontSize", min(90, element["bounds"]["height"] * 0.52)) * self.scale))
        font = self._font(text.get("fontFamily", "DejaVu Sans"), font_size)
        direction = text.get("direction", self.spec["project"].get("direction", "auto"))
        if direction == "auto":
            direction = None
        if direction == "rtl" and not features.check("raqm"):
            raise RenderError("right-to-left text needs libraqm")
        if direction == "ltr" and not features.check("raqm"):
            direction = None
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        bbox = draw.textbbox((0, 0), value, font=font, direction=direction)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if text_w > w or text_h > h:
            raise RenderError(f"text {element['id']} overflows its bounds at frame {frame}")
        align = text.get("align", "start")
        if align == "start":
            align = "right" if direction == "rtl" else "left"
        elif align == "end":
            align = "left" if direction == "rtl" else "right"
        text_x = x if align == "left" else x + (w - text_w) // 2 if align == "center" else x + w - text_w
        text_y = y + (h - text_h) // 2
        opacity = max(0.0, min(1.0, self._property(element["id"], "opacity", frame, 1.0)))
        color = _rgb(element["params"].get("color", "#FFFFFF"))
        draw.text((text_x - bbox[0], text_y - bbox[1]), value, font=font, direction=direction, fill=(*color, round(255 * opacity)))
        image.paste(overlay, (0, 0), overlay)

    def _shape(self, image: Image.Image, element: dict[str, Any], frame: int) -> None:
        x, y, w, h = self._bounds(element["bounds"])
        opacity = max(0.0, min(1.0, self._property(element["id"], "opacity", frame, 1.0)))
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        color = _rgb(element["params"].get("color", "#FFFFFF"))
        ImageDraw.Draw(overlay).rectangle((x, y, x + w, y + h), fill=(*color, round(255 * opacity)))
        image.paste(overlay, (0, 0), overlay)

    def _image(self, image: Image.Image, element: dict[str, Any], frame: int) -> None:
        source = self._load_image(element)
        x, y, w, h = self._bounds(element["bounds"])
        fit = element["params"].get("fit", "contain")
        if fit == "stretch":
            rendered = source.resize((w, h), Image.Resampling.LANCZOS)
        else:
            ratio = min(w / source.width, h / source.height) if fit == "contain" else max(w / source.width, h / source.height)
            scaled = source.resize((max(1, round(source.width * ratio)), max(1, round(source.height * ratio))), Image.Resampling.LANCZOS)
            rendered = scaled if fit == "contain" else scaled.crop(((scaled.width - w) // 2, (scaled.height - h) // 2, (scaled.width - w) // 2 + w, (scaled.height - h) // 2 + h))
        opacity = max(0.0, min(1.0, self._property(element["id"], "opacity", frame, 1.0)))
        if opacity < 1:
            rendered = rendered.copy()
            rendered.putalpha(rendered.getchannel("A").point(lambda a: round(a * opacity)))
        position = (x + (w - rendered.width) // 2, y + (h - rendered.height) // 2)
        image.paste(rendered, position, rendered)

    def _chart(self, image: Image.Image, element: dict[str, Any], frame: int) -> None:
        binding = element["dataBinding"]
        dataset = self.datasets[binding["datasetId"]]
        field = binding["field"]
        rows = dataset["rows"]
        if not rows:
            raise RenderError(f"chart {element['id']} has no data")
        values = [row[field] for row in rows]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
            raise RenderError(f"chart {element['id']} requires finite numeric values")
        params = element["params"]
        minimum = float(params.get("minimum", min(0, *values)))
        maximum = float(params.get("maximum", max(values)))
        if not maximum > minimum:
            raise RenderError(f"chart {element['id']} needs maximum greater than minimum")
        x, y, w, h = self._bounds(element["bounds"])
        left, top, right, bottom = x + round(30 * self.scale), y + round(25 * self.scale), x + w - round(25 * self.scale), y + h - round(80 * self.scale)
        if bottom <= top or right <= left:
            raise RenderError(f"chart {element['id']} bounds too small")
        draw = ImageDraw.Draw(image)
        color = _rgb(params.get("color", "#FFFFFF"))
        baseline = _rgb(params.get("baselineColor", "#6B7280"))
        draw.line((left, bottom, right, bottom), fill=baseline, width=max(1, round(2 * self.scale)))
        reveal = max(0.0, min(1.0, self._property(element["id"], "reveal", frame, 1.0)))
        category_field = params.get("categoryField")
        if category_field and any(category_field not in row for row in rows):
            raise RenderError(f"chart {element['id']} categoryField {category_field!r} is absent from data")
        font = self._font(params.get("labelFontFamily", "DejaVu Sans"), max(8, round(28 * self.scale)))
        if element["kind"] == "chart.bar":
            slot = (right - left) / len(rows)
            bar_width = max(1, round(slot * float(params.get("barWidthFraction", 0.62))))
            for index, (row, value) in enumerate(zip(rows, values)):
                height = max(0, round((value - minimum) / (maximum - minimum) * (bottom - top) * reveal))
                center = left + (index + 0.5) * slot
                draw.rectangle((round(center - bar_width / 2), bottom - height, round(center + bar_width / 2), bottom), fill=color)
                if category_field:
                    label = str(row[category_field])
                    draw.text((center, bottom + round(12 * self.scale)), label, font=font, fill=(255, 255, 255), anchor="mt")
        else:
            points = []
            for index, value in enumerate(values):
                px = left + index * (right - left) / max(1, len(values) - 1)
                py = bottom - (value - minimum) / (maximum - minimum) * (bottom - top)
                points.append((px, py))
            if len(points) == 1:
                draw.ellipse((points[0][0] - 3, points[0][1] - 3, points[0][0] + 3, points[0][1] + 3), fill=color)
            else:
                position = reveal * (len(points) - 1)
                complete = int(position)
                visible = points[:complete + 1]
                if complete < len(points) - 1:
                    fraction = position - complete
                    start, end = points[complete], points[complete + 1]
                    visible.append((start[0] + (end[0] - start[0]) * fraction, start[1] + (end[1] - start[1]) * fraction))
                if len(visible) >= 2:
                    draw.line(visible, fill=color, width=max(1, round(5 * self.scale)), joint="curve")

    def render_frame(self, frame: int) -> Image.Image:
        if not 0 <= frame < self.duration:
            raise RenderError(f"frame {frame} outside [0, {self.duration})")
        image = Image.new("RGB", (self.width, self.height), self.background)
        scene = next(s for s in self.spec["timeline"] if s["startFrame"] <= frame < s["endFrameExclusive"])
        for element in sorted(scene["elements"], key=lambda e: e.get("zIndex", 0)):
            if not element["startFrame"] <= frame < element["endFrameExclusive"]:
                continue
            kind = element["kind"]
            if kind == "text":
                self._text(image, element, frame)
            elif kind == "shape":
                self._shape(image, element, frame)
            elif kind == "image":
                self._image(image, element, frame)
            else:
                self._chart(image, element, frame)
        for disclosure in self.spec["policies"]["disclosures"]:
            if disclosure["startFrame"] <= frame < disclosure["endFrameExclusive"]:
                self._text(image, {"id": disclosure["id"], "text": disclosure["text"], "bounds": disclosure.get("bounds", {"x": 20, "y": self.spec["canvas"]["height"] - 100, "width": self.spec["canvas"]["width"] - 40, "height": 80}), "params": {"color": "#FFFFFF"}}, frame)
        return image


def _ffmpeg_executable() -> str:
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        raise RenderError("FFmpeg is required for MP4; install it on PATH or install imageio-ffmpeg") from exc


def render_preview(spec: dict[str, Any], output_dir: str | Path, *, mp4: bool | None = None,
                   scale: float = 1.0, font_dirs: list[str | Path] | None = None,
                   max_frames: int = 10_000, asset_root: str | Path | None = None) -> dict[str, Any]:
    if mp4 is None:
        mp4 = any(d["target"] == "video/mp4" and d["required"] for d in spec["deliverables"])
    duration = spec["canvas"]["durationFrames"]
    if duration > max_frames:
        raise RenderError(f"{duration} frames exceeds safety limit {max_frames}; increase it explicitly")
    renderer = FrameRenderer(spec, scale=scale, font_dirs=font_dirs, asset_root=asset_root)
    if mp4 and (renderer.width % 2 or renderer.height % 2):
        raise RenderError("MP4 preview dimensions must be even; choose another scale")
    output = Path(output_dir).resolve()
    if output.exists():
        raise RenderError(f"output path {output} already exists; choose a new directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as temporary:
        staging = Path(temporary)
        frames_dir = staging / "frames"
        frames_dir.mkdir()
        for frame in range(duration):
            renderer.render_frame(frame).save(frames_dir / f"{frame:06d}.png")
        outputs = [{"kind": "png_sequence", "path": str(output / "frames"), "frameCount": duration}]
        if mp4:
            video = staging / "preview.mp4"
            rate = spec["canvas"]["frameRate"]
            command = [
                _ffmpeg_executable(), "-hide_banner", "-loglevel", "error", "-y",
                "-framerate", f"{rate['numerator']}/{rate['denominator']}",
                "-i", str(frames_dir / "%06d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(video),
            ]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            if completed.returncode:
                raise RenderError(f"FFmpeg failed: {completed.stderr.strip()}")
            outputs.append({"kind": "video/mp4", "path": str(output / "preview.mp4")})
        fingerprint = hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        report = {
            "projectId": spec["project"]["id"],
            "specSha256": fingerprint,
            "frameCount": duration,
            "width": renderer.width,
            "height": renderer.height,
            "frameRate": spec["canvas"]["frameRate"],
            "outputs": outputs,
            "issues": list({(i["code"], i["message"]): i for i in renderer.issues}.values()),
            "note": "Deterministic preview only; no audio or editable Adobe project.",
        }
        (staging / "render-manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        staging.rename(output)
        return report
