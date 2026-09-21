"""Deterministic PNG and optional MP4 previews for supported MotionSpec elements.

This is a preview backend. It does not create editable Adobe projects.
Unsupported elements fail before the first frame is written.
"""
from __future__ import annotations

from array import array
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps, features

from .frame_assets import FrameArchive, FrameAssetError
from .preview_contract import PREVIEW_ANIMATIONS_BY_KIND, PREVIEW_EASING, PREVIEW_KINDS, PREVIEW_PARAMS
from .revisions import RevisionError, resolve_local_file, spec_sha256
from .runs import frames_tree_sha256, render_key
from .revisions import file_sha256
from . import __version__


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


def _format_chart_value(value: float, decimals: int) -> str:
    if not isinstance(decimals, int) or isinstance(decimals, bool) or not 0 <= decimals <= 6:
        raise RenderError("chart decimals must be an integer from 0 to 6")
    return f"{value:.{decimals}f}"


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
        self.video_cache: dict[str, FrameArchive] = {}
        self.audio_clips: list[dict[str, Any]] = []
        self.font_dirs = [Path(p) for p in (font_dirs or [])]
        self.font_dirs += [Path("C:/Windows/Fonts"), Path("/usr/share/fonts"), Path("/Library/Fonts"), Path.home() / ".local/share/fonts"]
        self.font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}
        self.issues: list[dict[str, str]] = []
        self.animations: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for scene_index, scene in enumerate(spec["timeline"]):
            transition = scene.get("transitionIn", "start" if scene_index == 0 else "cut")
            if transition not in (("start",) if scene_index == 0 else ("cut", "fade")):
                raise RenderError(f"unsupported preview transition {scene['transitionIn']!r}")
            transition_frames = scene.get("transitionFrames")
            if transition == "fade":
                previous = spec["timeline"][scene_index - 1]
                maximum = min(scene["endFrameExclusive"] - scene["startFrame"],
                              previous["endFrameExclusive"] - previous["startFrame"])
                if (not isinstance(transition_frames, int) or isinstance(transition_frames, bool)
                        or not 2 <= transition_frames <= min(120, maximum)):
                    raise RenderError(f"fade transition on {scene['id']} must fit both adjacent scenes")
            elif transition_frames is not None:
                raise RenderError(f"transitionFrames on {scene['id']} requires a fade")
            element_kinds = {element["id"]: element["kind"] for element in scene["elements"]}
            elements_by_id = {element["id"]: element for element in scene["elements"]}
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
                if element["kind"] == "video":
                    if element["params"].get("fit", "contain") not in ("contain", "cover", "stretch"):
                        raise RenderError(f"video {element['id']} has unsupported fit mode")
                    self._load_video(element)
                if element["kind"] == "audio":
                    self._load_audio(element)
                if element["kind"] == "counter":
                    self._validate_counter(element)
                if element["kind"] != "audio" and "bounds" not in element:
                    raise RenderError(f"preview element {element['id']} requires bounds")
                if element["kind"] == "text" and "text" not in element:
                    raise RenderError(f"text element {element['id']} requires text")
                if element["kind"].startswith("chart.") and "dataBinding" not in element:
                    raise RenderError(f"chart element {element['id']} requires dataBinding")
            for beat in scene["beats"]:
                if beat.get("voice", {}).get("value", "").strip():
                    linked = [elements_by_id.get(element_id) for element_id in beat.get("elementIds", [])]
                    if not any(element and element["kind"] == "audio"
                               and element["startFrame"] <= beat["startFrame"]
                               and element["endFrameExclusive"] >= beat["endFrameExclusive"]
                               for element in linked):
                        raise RenderError(f"voice audio for beat {beat['id']} needs a linked audio element covering its frame window")
            for animation in scene["animations"]:
                kind = element_kinds.get(animation["targetId"])
                if kind is None or animation["property"] not in PREVIEW_ANIMATIONS_BY_KIND.get(kind, set()):
                    raise RenderError(f"unsupported preview animation {animation['property']!r} on {animation['targetId']}")
                if any(keyframe.get("easing", "linear") not in PREVIEW_EASING for keyframe in animation["keyframes"]):
                    raise RenderError(f"unsupported preview easing on {animation['targetId']}")
                if animation["property"] == "scale" and any(
                    not isinstance(keyframe["value"], (int, float)) or isinstance(keyframe["value"], bool)
                    or not math.isfinite(keyframe["value"]) or not 1 <= keyframe["value"] <= 3
                    for keyframe in animation["keyframes"]
                ):
                    raise RenderError(f"visual {animation['targetId']} scale keyframes must be finite numbers from 1 to 3")
                if animation["property"] == "value" and any(
                    not isinstance(keyframe["value"], (int, float)) or isinstance(keyframe["value"], bool)
                    or not math.isfinite(keyframe["value"]) for keyframe in animation["keyframes"]
                ):
                    raise RenderError(f"counter {animation['targetId']} value keyframes must be finite numbers")
                if animation["property"] in ("x", "y"):
                    limit = canvas["width"] if animation["property"] == "x" else canvas["height"]
                    if any(not isinstance(keyframe["value"], (int, float)) or isinstance(keyframe["value"], bool)
                           or not math.isfinite(keyframe["value"]) or not -limit <= keyframe["value"] <= limit
                           for keyframe in animation["keyframes"]):
                        raise RenderError(f"visual {animation['targetId']} position keyframes exceed canvas range")
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

    def _bounds(self, value: dict[str, float], element_id: str | None = None,
                frame: int | None = None) -> tuple[int, int, int, int]:
        x_value = self._property(element_id, "x", frame, value["x"]) if element_id is not None and frame is not None else value["x"]
        y_value = self._property(element_id, "y", frame, value["y"]) if element_id is not None and frame is not None else value["y"]
        x, y = round(x_value * self.scale), round(y_value * self.scale)
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

    def _load_video(self, element: dict[str, Any]) -> FrameArchive:
        asset_id = element.get("assetId")
        if asset_id not in self.video_cache:
            asset = self.assets.get(asset_id)
            if not asset:
                raise RenderError(f"video {element['id']} requires a video.frames asset")
            try:
                self.video_cache[asset_id] = FrameArchive(asset, self.asset_root, self.spec["canvas"]["frameRate"])
            except FrameAssetError as exc:
                raise RenderError(str(exc)) from exc
        archive = self.video_cache[asset_id]
        offset = element["params"].get("sourceStartFrame", 0)
        needed = element["endFrameExclusive"] - element["startFrame"]
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0 or offset + needed > archive.frame_count:
            raise RenderError(f"video {element['id']} source frame range exceeds its plate")
        return archive

    def _load_audio(self, element: dict[str, Any]) -> None:
        asset = self.assets.get(element.get("assetId"))
        if not asset or asset.get("kind") != "audio" or asset.get("status") != "available" or not asset.get("sha256"):
            raise RenderError(f"audio {element['id']} requires an available hashed asset")
        if element["startFrame"] < 0 or element["endFrameExclusive"] > self.duration:
            raise RenderError(f"audio {element['id']} frame window is outside the project")
        try:
            path = resolve_local_file(asset, self.asset_root, "asset")
        except RevisionError as exc:
            raise RenderError(str(exc)) from exc
        if path.suffix.lower() != ".wav" or file_sha256(path) != asset["sha256"]:
            raise RenderError(f"audio {element['id']} needs a matching WAV hash")
        try:
            with wave.open(str(path), "rb") as source:
                if (source.getcomptype() != "NONE" or source.getnchannels() != 1 or
                        source.getsampwidth() != 2 or source.getframerate() != 48_000):
                    raise RenderError(f"audio {element['id']} needs mono 16-bit PCM WAV at 48 kHz")
                available = source.getnframes()
        except (OSError, EOFError, wave.Error) as exc:
            raise RenderError(f"audio {element['id']} cannot be decoded: {exc}") from exc
        rate = self.spec["canvas"]["frameRate"]
        count = _sample_for_frame(element["endFrameExclusive"], rate) - _sample_for_frame(element["startFrame"], rate)
        if available < count:
            raise RenderError(f"audio {element['id']} is shorter than its declared frame window")
        gain = element["params"].get("gainDb", 0)
        if not isinstance(gain, (int, float)) or isinstance(gain, bool) or not math.isfinite(gain) or not -60 <= gain <= 12:
            raise RenderError(f"audio {element['id']} gainDb must be between -60 and 12")
        self.audio_clips.append({"path": path, "element": element, "gain": 10 ** (gain / 20)})

    def _property(self, element_id: str, property_name: str, frame: int, default: float) -> float:
        keyframes = self.animations.get(element_id, {}).get(property_name)
        return _interpolate(keyframes, frame) if keyframes else default

    def _validate_counter(self, element: dict[str, Any]) -> None:
        params = element["params"]
        start, end, decimals = params.get("startValue", 0), params.get("endValue"), params.get("decimals", 0)
        if (not isinstance(start, (int, float)) or isinstance(start, bool) or not math.isfinite(start)
                or not isinstance(end, (int, float)) or isinstance(end, bool) or not math.isfinite(end)
                or not isinstance(decimals, int) or isinstance(decimals, bool) or not 0 <= decimals <= 6
                or not isinstance(params.get("prefix", ""), str) or len(params.get("prefix", "")) > 32
                or not isinstance(params.get("suffix", ""), str) or len(params.get("suffix", "")) > 32
                or params.get("align", "center") not in ("start", "center", "end")
                or not isinstance(params.get("fontFamily", "DejaVu Sans"), str)
                or not params.get("fontFamily", "DejaVu Sans").strip()
                or len(params.get("fontFamily", "DejaVu Sans")) > 128
                or not isinstance(params.get("fontSize", 48), (int, float))
                or isinstance(params.get("fontSize", 48), bool)
                or not math.isfinite(params.get("fontSize", 48)) or params.get("fontSize", 48) <= 0
                or params.get("digitPolicy") not in (None, "none", "locale", "latin", "persian", "arabic_indic")):
            raise RenderError(f"counter {element['id']} has invalid values or formatting")
        _rgb(params.get("color", "#FFFFFF"))

    def _counter(self, image: Image.Image, element: dict[str, Any], frame: int) -> None:
        params = element["params"]
        decimals = params.get("decimals", 0)
        value = self._property(element["id"], "value", frame, params["endValue"])
        if not math.isfinite(value):
            raise RenderError(f"counter {element['id']} produced a non-finite value")
        if abs(value) < 0.5 * (10 ** -decimals):
            value = 0.0
        formatted = f"{value:.{decimals}f}"
        formatted = _localize_digits(formatted, params.get("digitPolicy"), self.spec["project"]["locale"])
        proxy = {**element, "kind": "text",
                 "text": {"value": params.get("prefix", "") + formatted + params.get("suffix", ""),
                          "locale": self.spec["project"]["locale"],
                          "direction": self.spec["project"].get("direction", "ltr"),
                          "fontFamily": params.get("fontFamily", "DejaVu Sans"),
                          "fontWeight": 700, "align": params.get("align", "center")},
                 "params": {"color": params.get("color", "#FFFFFF"),
                            "fontSize": params.get("fontSize", min(90, element["bounds"]["height"] * 0.52)),
                            "wrap": False}}
        self._text(image, proxy, frame)

    def _text(self, image: Image.Image, element: dict[str, Any], frame: int) -> None:
        text = element["text"]
        value = _localize_digits(text["value"], text.get("digitPolicy"), text.get("locale", self.spec["project"]["locale"]))
        x, y, w, h = self._bounds(element["bounds"], element["id"], frame)
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
        wrap = element["params"].get("wrap", False)
        if not isinstance(wrap, bool):
            raise RenderError(f"text {element['id']} wrap must be a boolean")
        lines = []
        for authored_line in value.split("\n"):
            if not wrap:
                lines.append(authored_line)
                continue
            current = ""
            for word in authored_line.split(" "):
                candidate = word if not current else current + " " + word
                bbox = draw.textbbox((0, 0), candidate or " ", font=font, direction=direction)
                if bbox[2] - bbox[0] <= w:
                    current = candidate
                elif current:
                    word_box = draw.textbbox((0, 0), word or " ", font=font, direction=direction)
                    if word_box[2] - word_box[0] > w:
                        raise RenderError(f"text {element['id']} has an unbreakable word wider than its bounds")
                    lines.append(current)
                    current = word
                else:
                    raise RenderError(f"text {element['id']} has an unbreakable word wider than its bounds")
            lines.append(current)
        ascent, descent = font.getmetrics()
        line_height = max(1, math.ceil((ascent + descent) * 1.08))
        block_height = len(lines) * line_height
        if block_height > h:
            raise RenderError(f"text {element['id']} overflows its bounds at frame {frame}")
        align = text.get("align", "start")
        if align == "start":
            align = "right" if direction == "rtl" else "left"
        elif align == "end":
            align = "left" if direction == "rtl" else "right"
        opacity = max(0.0, min(1.0, self._property(element["id"], "opacity", frame, 1.0)))
        color = _rgb(element["params"].get("color", "#FFFFFF"))
        for index, line in enumerate(lines):
            if not line:
                continue
            bbox = draw.textbbox((0, 0), line, font=font, direction=direction)
            text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            if text_w > w or text_h > line_height:
                raise RenderError(f"text {element['id']} overflows its bounds at frame {frame}")
            text_x = x if align == "left" else x + (w - text_w) // 2 if align == "center" else x + w - text_w
            text_y = y + (h - block_height) // 2 + index * line_height + (line_height - text_h) // 2
            draw.text((text_x - bbox[0], text_y - bbox[1]), line, font=font, direction=direction, fill=(*color, round(255 * opacity)))
        image.paste(overlay, (0, 0), overlay)

    def _shape(self, image: Image.Image, element: dict[str, Any], frame: int) -> None:
        x, y, w, h = self._bounds(element["bounds"], element["id"], frame)
        opacity = max(0.0, min(1.0, self._property(element["id"], "opacity", frame, 1.0)))
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        color = _rgb(element["params"].get("color", "#FFFFFF"))
        gradient_end = element["params"].get("gradientEnd")
        if gradient_end is None:
            ImageDraw.Draw(overlay).rectangle((x, y, x + w, y + h), fill=(*color, round(255 * opacity)))
        else:
            end_color = _rgb(gradient_end)
            direction = element["params"].get("gradientDirection")
            if direction not in ("vertical", "horizontal"):
                raise RenderError(f"shape {element['id']} gradientDirection must be vertical or horizontal")
            length = h if direction == "vertical" else w
            strip = Image.new("RGBA", (1, length) if direction == "vertical" else (length, 1))
            pixels = []
            for position in range(length):
                ratio = position / max(1, length - 1)
                channels = tuple(round(left + (right - left) * ratio)
                                 for left, right in zip(color, end_color))
                pixels.append((*channels, round(255 * opacity)))
            strip.putdata(pixels)
            gradient = strip.resize((w, h))
            overlay.paste(gradient, (x, y), gradient)
        image.paste(overlay, (0, 0), overlay)

    def _image(self, image: Image.Image, element: dict[str, Any], frame: int) -> None:
        self._raster_layer(image, element, frame, self._load_image(element))

    def _video(self, image: Image.Image, element: dict[str, Any], frame: int) -> None:
        archive = self._load_video(element)
        source_frame = element["params"].get("sourceStartFrame", 0) + frame - element["startFrame"]
        try:
            source = archive.frame(source_frame)
        except FrameAssetError as exc:
            raise RenderError(str(exc)) from exc
        self._raster_layer(image, element, frame, source)

    def _raster_layer(self, image: Image.Image, element: dict[str, Any], frame: int,
                      source: Image.Image) -> None:
        x, y, w, h = self._bounds(element["bounds"], element["id"], frame)
        fit = element["params"].get("fit", "contain")
        if fit == "stretch":
            rendered = source.resize((w, h), Image.Resampling.LANCZOS)
        else:
            ratio = min(w / source.width, h / source.height) if fit == "contain" else max(w / source.width, h / source.height)
            scaled = source.resize((max(1, round(source.width * ratio)), max(1, round(source.height * ratio))), Image.Resampling.LANCZOS)
            rendered = scaled if fit == "contain" else scaled.crop(((scaled.width - w) // 2, (scaled.height - h) // 2, (scaled.width - w) // 2 + w, (scaled.height - h) // 2 + h))
        zoom = self._property(element["id"], "scale", frame, 1.0)
        if zoom != 1:
            rendered = rendered.resize((max(1, round(rendered.width * zoom)),
                                        max(1, round(rendered.height * zoom))), Image.Resampling.LANCZOS)
            viewport = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            viewport.paste(rendered, ((w - rendered.width) // 2, (h - rendered.height) // 2))
            rendered = viewport
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
        value_format = binding.get("format", {})
        if not isinstance(value_format, dict) or set(value_format) - {"unit", "decimals"}:
            raise RenderError(f"chart {element['id']} has unsupported value format")
        unit = value_format.get("unit", "")
        decimals = value_format.get("decimals", 0)
        tick_count = params.get("tickCount", 5)
        show_values = params.get("showValues", False)
        if (not isinstance(unit, str) or len(unit) > 32
                or not isinstance(tick_count, int) or isinstance(tick_count, bool) or not 2 <= tick_count <= 10
                or not isinstance(show_values, bool)):
            raise RenderError(f"chart {element['id']} formatting is invalid")
        _format_chart_value(0, decimals)
        minimum = float(params.get("minimum", min(0, *values)))
        maximum = float(params.get("maximum", max(values)))
        if not maximum > minimum:
            raise RenderError(f"chart {element['id']} needs maximum greater than minimum")
        x, y, w, h = self._bounds(element["bounds"])
        left_margin = min(round(80 * self.scale), max(1, round(w * 0.25)))
        right_margin = min(round(25 * self.scale), max(1, round(w * 0.10)))
        top_margin = min(round(25 * self.scale), max(1, round(h * 0.10)))
        bottom_margin = min(round(80 * self.scale), max(1, round(h * 0.22)))
        left, top, right, bottom = (x + left_margin, y + top_margin,
                                    x + w - right_margin, y + h - bottom_margin)
        if bottom <= top or right <= left:
            raise RenderError(f"chart {element['id']} bounds too small")
        draw = ImageDraw.Draw(image)
        color = _rgb(params.get("color", "#FFFFFF"))
        baseline = _rgb(params.get("baselineColor", "#6B7280"))
        reveal = max(0.0, min(1.0, self._property(element["id"], "reveal", frame, 1.0)))
        category_field = params.get("categoryField")
        if category_field and any(category_field not in row for row in rows):
            raise RenderError(f"chart {element['id']} categoryField {category_field!r} is absent from data")
        font = self._font(params.get("labelFontFamily", "DejaVu Sans"), max(8, round(28 * self.scale)))
        axis_font = self._font(params.get("labelFontFamily", "DejaVu Sans"), max(7, round(22 * self.scale)))
        grid = tuple(round((channel + 255) / 2) for channel in baseline)
        for tick_index in range(tick_count):
            ratio = tick_index / (tick_count - 1)
            tick_value = minimum + ratio * (maximum - minimum)
            tick_y = bottom - ratio * (bottom - top)
            draw.line((left, tick_y, right, tick_y), fill=grid, width=max(1, round(self.scale)))
            draw.text((left - max(2, round(8 * self.scale)), tick_y),
                      _format_chart_value(tick_value, decimals), font=axis_font,
                      fill=(255, 255, 255), anchor="rm")
        if unit:
            draw.text((left, top - max(2, round(5 * self.scale))), unit, font=axis_font,
                      fill=(255, 255, 255), anchor="lb")
        zero_ratio = (0 - minimum) / (maximum - minimum)
        zero_y = bottom - max(0.0, min(1.0, zero_ratio)) * (bottom - top)
        draw.line((left, zero_y, right, zero_y), fill=baseline, width=max(1, round(2 * self.scale)))
        if element["kind"] == "chart.bar":
            slot = (right - left) / len(rows)
            bar_width = max(1, round(slot * float(params.get("barWidthFraction", 0.62))))
            for index, (row, value) in enumerate(zip(rows, values)):
                center = left + (index + 0.5) * slot
                target_y = bottom - (value - minimum) / (maximum - minimum) * (bottom - top)
                value_y = zero_y + (target_y - zero_y) * reveal
                draw.rectangle((round(center - bar_width / 2), round(min(zero_y, value_y)),
                                round(center + bar_width / 2), round(max(zero_y, value_y))), fill=color)
                if category_field:
                    label = str(row[category_field])
                    draw.text((center, bottom + round(12 * self.scale)), label, font=font, fill=(255, 255, 255), anchor="mt")
                if show_values and reveal >= 0.999:
                    anchor = "mb" if value >= 0 else "mt"
                    offset = -max(2, round(5 * self.scale)) if value >= 0 else max(2, round(5 * self.scale))
                    draw.text((center, target_y + offset), _format_chart_value(value, decimals),
                              font=axis_font, fill=(255, 255, 255), anchor=anchor)
        else:
            points = []
            for index, value in enumerate(values):
                px = left + index * (right - left) / max(1, len(values) - 1)
                py = bottom - (value - minimum) / (maximum - minimum) * (bottom - top)
                points.append((px, py))
                if category_field:
                    draw.text((px, bottom + round(12 * self.scale)), str(rows[index][category_field]),
                              font=font, fill=(255, 255, 255), anchor="mt")
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
            if show_values and reveal >= 0.999:
                radius = max(2, round(4 * self.scale))
                for (px, py), value in zip(points, values):
                    draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=color)
                    draw.text((px, py - radius - max(2, round(4 * self.scale))),
                              _format_chart_value(value, decimals), font=axis_font,
                              fill=(255, 255, 255), anchor="mb")

    def _scene_frame(self, scene: dict[str, Any], frame: int) -> Image.Image:
        image = Image.new("RGB", (self.width, self.height), self.background)
        for element in sorted(scene["elements"], key=lambda e: e.get("zIndex", 0)):
            if not element["startFrame"] <= frame < element["endFrameExclusive"]:
                continue
            kind = element["kind"]
            if kind == "audio":
                continue
            if kind == "text":
                self._text(image, element, frame)
            elif kind == "counter":
                self._counter(image, element, frame)
            elif kind == "shape":
                self._shape(image, element, frame)
            elif kind == "image":
                self._image(image, element, frame)
            elif kind == "video":
                self._video(image, element, frame)
            else:
                self._chart(image, element, frame)
        return image

    def render_frame(self, frame: int) -> Image.Image:
        if not 0 <= frame < self.duration:
            raise RenderError(f"frame {frame} outside [0, {self.duration})")
        scene_index = next(index for index, scene in enumerate(self.spec["timeline"])
                           if scene["startFrame"] <= frame < scene["endFrameExclusive"])
        scene = self.spec["timeline"][scene_index]
        image = self._scene_frame(scene, frame)
        opacity = 1.0
        if scene.get("transitionIn") == "fade":
            incoming = scene["transitionFrames"] - scene["transitionFrames"] // 2
            local = frame - scene["startFrame"]
            if local < incoming:
                opacity = (local + 1) / (incoming + 1)
        if scene_index + 1 < len(self.spec["timeline"]):
            following = self.spec["timeline"][scene_index + 1]
            if following.get("transitionIn") == "fade":
                outgoing = following["transitionFrames"] // 2
                remaining = scene["endFrameExclusive"] - 1 - frame
                if remaining < outgoing:
                    opacity = min(opacity, (remaining + 1) / (outgoing + 1))
        if opacity < 1:
            background = Image.new("RGB", image.size, self.background)
            image = Image.blend(background, image, opacity)
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


def _sample_for_frame(frame: int, rate: dict[str, int]) -> int:
    numerator = frame * 48_000 * rate["denominator"]
    return (2 * numerator + rate["numerator"]) // (2 * rate["numerator"])


def _mix_audio(renderer: FrameRenderer, output: Path) -> None:
    rate = renderer.spec["canvas"]["frameRate"]
    total = _sample_for_frame(renderer.duration, rate)
    mixed = array("i", [0]) * total
    for clip in renderer.audio_clips:
        element = clip["element"]
        start = _sample_for_frame(element["startFrame"], rate)
        end = _sample_for_frame(element["endFrameExclusive"], rate)
        with wave.open(str(clip["path"]), "rb") as source:
            data = source.readframes(end - start)
        samples = array("h")
        samples.frombytes(data)
        if sys.byteorder != "little":
            samples.byteswap()
        if len(samples) != end - start:
            raise RenderError(f"audio {element['id']} changed or ended during mixing")
        for offset, value in enumerate(samples):
            mixed[start + offset] += round(value * clip["gain"])
    if any(value < -32768 or value > 32767 for value in mixed):
        raise RenderError("audio mix clips; lower one or more gainDb values")
    result = array("h", mixed)
    if sys.byteorder != "little":
        result.byteswap()
    with wave.open(str(output), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(48_000)
        stream.writeframes(result.tobytes())


def render_preview(spec: dict[str, Any], output_dir: str | Path, *, mp4: bool | None = None,
                   scale: float = 1.0, font_dirs: list[str | Path] | None = None,
                   max_frames: int = 10_000, asset_root: str | Path | None = None,
                   revision_sha256: str | None = None) -> dict[str, Any]:
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
        outputs = [{"kind": "png_sequence", "path": "frames", "frameCount": duration,
                    "treeSha256": frames_tree_sha256(frames_dir, duration)}]
        mix = None
        if renderer.audio_clips:
            mix = staging / "mix.wav"
            _mix_audio(renderer, mix)
            outputs.append({"kind": "audio/wav", "path": "mix.wav", "sha256": file_sha256(mix)})
        if mp4:
            video = staging / "preview.mp4"
            rate = spec["canvas"]["frameRate"]
            command = [
                _ffmpeg_executable(), "-hide_banner", "-loglevel", "error", "-y",
                "-framerate", f"{rate['numerator']}/{rate['denominator']}",
                "-i", str(frames_dir / "%06d.png"),
            ]
            if mix:
                command += ["-i", str(mix)]
            command += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
            if mix:
                command += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
            command += ["-movflags", "+faststart", str(video)]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            if completed.returncode:
                raise RenderError(f"FFmpeg failed: {completed.stderr.strip()}")
            outputs.append({"kind": "video/mp4", "path": "preview.mp4", "sha256": file_sha256(video)})
        spec_hash = spec_sha256(spec)
        report = {
            "status": "succeeded",
            "producerVersion": __version__,
            "idempotencyKey": render_key(spec_hash, revision_sha256, mp4=mp4, scale=scale, font_dirs=font_dirs),
            "renderOptions": {"mp4": mp4, "scale": scale, "fontDirs": [str(Path(path).resolve()) for path in (font_dirs or [])]},
            "projectId": spec["project"]["id"],
            "specSha256": spec_hash,
            "revisionSha256": revision_sha256,
            "frameCount": duration,
            "width": renderer.width,
            "height": renderer.height,
            "frameRate": spec["canvas"]["frameRate"],
            "outputs": outputs,
            "issues": list({(i["code"], i["message"]): i for i in renderer.issues}.values()),
            "note": "Deterministic preview only; no editable Adobe project."
                    if mix else "Deterministic silent preview only; no editable Adobe project.",
        }
        (staging / "render-manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        staging.rename(output)
        return report
