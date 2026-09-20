"""Convert a source video into a deterministic, frame-addressable plate."""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from PIL import Image

from .frame_assets import FrameArchive
from .revisions import file_sha256
from .rendering import _ffmpeg_executable


class VideoImportError(ValueError):
    pass


def import_video(source: str | Path, output: str | Path, *, numerator: int,
                 denominator: int, frame_count: int, start_ms: int = 0) -> dict:
    source_path = Path(source).resolve()
    output_path = Path(output).resolve()
    if not source_path.is_file() or source_path.suffix.lower() not in (".mp4", ".mov", ".webm", ".mkv"):
        raise VideoImportError("source must be an existing MP4, MOV, WebM, or MKV file")
    if output_path.suffix.lower() != ".zip" or output_path.exists():
        raise VideoImportError("output must be a new .zip path")
    if (not isinstance(numerator, int) or not isinstance(denominator, int)
        or not isinstance(frame_count, int) or not isinstance(start_ms, int)
        or isinstance(numerator, bool) or isinstance(denominator, bool)
        or isinstance(frame_count, bool) or isinstance(start_ms, bool)
        or not 1 <= numerator <= 120_000 or not 1 <= denominator <= 1001
        or not 1 <= frame_count <= 10_000 or start_ms < 0):
        raise VideoImportError("invalid frame rate, count, or start offset")
    if source_path.stat().st_size > 2_000_000_000:
        raise VideoImportError("source video exceeds the 2 GB import limit")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rate = {"numerator": numerator, "denominator": denominator}
    with tempfile.TemporaryDirectory(prefix=f".{output_path.stem}-", dir=output_path.parent) as temporary:
        staging = Path(temporary)
        frames_dir = staging / "frames"
        frames_dir.mkdir()
        command = [
            _ffmpeg_executable(), "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(source_path),
            "-ss", f"{start_ms / 1000:.3f}", "-map", "0:v:0", "-an",
            "-vf", f"fps={numerator}/{denominator}", "-frames:v", str(frame_count),
            "-start_number", "0", "-c:v", "png", "-pix_fmt", "rgba", str(frames_dir / "%06d.png"),
        ]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=300)
        except subprocess.TimeoutExpired as exc:
            raise VideoImportError("FFmpeg video import timed out") from exc
        if completed.returncode:
            raise VideoImportError(f"FFmpeg video import failed: {completed.stderr.strip()}")
        frames = sorted(frames_dir.glob("*.png"))
        expected = [frames_dir / f"{index:06d}.png" for index in range(frame_count)]
        if frames != expected:
            raise VideoImportError(f"video yielded {len(frames)} frames; expected exactly {frame_count}")
        dimensions = None
        for index, path in enumerate(frames):
            try:
                with Image.open(path) as image:
                    if image.format != "PNG":
                        raise VideoImportError(f"decoded frame {index} is not PNG")
                    if dimensions is None:
                        dimensions = image.size
                    if image.size != dimensions or image.width * image.height > 50_000_000:
                        raise VideoImportError(f"decoded frame {index} dimensions are inconsistent or too large")
                    image.verify()
            except OSError as exc:
                raise VideoImportError(f"decoded frame {index} is unreadable") from exc
        assert dimensions is not None
        manifest = {"formatVersion": 1, "width": dimensions[0], "height": dimensions[1],
                    "frameRate": rate, "frameCount": frame_count}
        archive_path = staging / "plate.zip"
        with ZipFile(archive_path, "w") as archive:
            for name, content in [("manifest.json", json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8"))]:
                info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                archive.writestr(info, content)
            for index, path in enumerate(frames):
                info = ZipInfo(f"frames/{index:06d}.png", date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())
        digest = file_sha256(archive_path)
        FrameArchive({"id": "imported", "kind": "video.frames", "status": "available",
                      "uri": "plate.zip", "sha256": digest}, staging, rate)
        archive_path.replace(output_path)
    return {"asset": {"kind": "video.frames", "status": "available", "uri": output_path.name,
                      "sha256": digest}, "sourceSha256": file_sha256(source_path),
            "transform": {"startMs": start_ms, "frameRate": rate, "frameCount": frame_count},
            "width": dimensions[0], "height": dimensions[1]}
