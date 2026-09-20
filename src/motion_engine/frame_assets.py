"""Portable, hashed PNG-frame plates with exact frame indexing."""
from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from PIL import Image

from .revisions import RevisionError, file_sha256, resolve_local_file


class FrameAssetError(ValueError):
    pass


class FrameArchive:
    def __init__(self, asset: dict, root: str | Path, rate: dict[str, int]):
        if asset.get("kind") != "video.frames" or asset.get("status") != "available" or not asset.get("sha256"):
            raise FrameAssetError("video plate requires an available, hashed video.frames asset")
        try:
            self.path = resolve_local_file(asset, root, "asset")
        except RevisionError as exc:
            raise FrameAssetError(str(exc)) from exc
        if self.path.suffix.lower() != ".zip" or file_sha256(self.path) != asset["sha256"]:
            raise FrameAssetError(f"video plate {asset['id']} needs a matching ZIP hash")
        try:
            with ZipFile(self.path) as archive:
                names = archive.namelist()
                if not names or len(names) != len(set(names)) or "manifest.json" not in names:
                    raise FrameAssetError("video plate has duplicate entries or no manifest")
                if any(info.file_size > 100_000_000 for info in archive.infolist()):
                    raise FrameAssetError("video plate entry exceeds 100 MB")
                if archive.getinfo("manifest.json").file_size > 10_000:
                    raise FrameAssetError("video plate manifest is too large")
                manifest = json.loads(archive.read("manifest.json"))
                if not isinstance(manifest, dict) or set(manifest) != {"formatVersion", "width", "height", "frameRate", "frameCount"}:
                    raise FrameAssetError("video plate manifest fields are invalid")
                if manifest["formatVersion"] != 1 or manifest["frameRate"] != rate:
                    raise FrameAssetError("video plate frame rate must match the project exactly")
                width, height, count = manifest["width"], manifest["height"], manifest["frameCount"]
                if (not all(isinstance(n, int) and not isinstance(n, bool) for n in (width, height, count))
                    or not 1 <= width <= 8192 or not 1 <= height <= 8192 or width * height > 50_000_000
                    or not 1 <= count <= 10_000):
                    raise FrameAssetError("video plate dimensions or frame count exceed limits")
                expected = {"manifest.json"} | {f"frames/{index:06d}.png" for index in range(count)}
                if set(names) != expected:
                    raise FrameAssetError("video plate must contain exactly the declared numbered PNG frames")
        except (BadZipFile, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise FrameAssetError(f"video plate ZIP or manifest is invalid: {exc}") from exc
        self.width, self.height, self.frame_count = width, height, count
        self._cached_index = -1
        self._cached_image: Image.Image | None = None

    def frame(self, index: int) -> Image.Image:
        if not 0 <= index < self.frame_count:
            raise FrameAssetError(f"video plate frame {index} is outside [0, {self.frame_count})")
        if self._cached_index == index and self._cached_image is not None:
            return self._cached_image
        try:
            with ZipFile(self.path) as archive:
                data = archive.read(f"frames/{index:06d}.png")
            with Image.open(BytesIO(data)) as source:
                if source.format != "PNG" or source.size != (self.width, self.height):
                    raise FrameAssetError(f"video plate frame {index} has wrong format or dimensions")
                result = source.convert("RGBA")
        except (BadZipFile, OSError, ValueError, KeyError) as exc:
            raise FrameAssetError(f"video plate frame {index} cannot be decoded: {exc}") from exc
        self._cached_index, self._cached_image = index, result
        return result
