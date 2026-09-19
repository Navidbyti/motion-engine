"""Content-addressed local preview run records and integrity verification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import __version__
from .revisions import canonical_bytes, file_sha256


class RunError(ValueError):
    pass


def render_key(spec_hash: str, revision_hash: str | None, *, mp4: bool, scale: float,
               font_dirs: list[str | Path] | None = None) -> str:
    payload = {
        "stage": "render-preview", "specSha256": spec_hash,
        "revisionSha256": revision_hash, "producerVersion": __version__,
        "options": {"mp4": mp4, "scale": scale, "fontDirs": [str(Path(path).resolve()) for path in (font_dirs or [])]},
    }
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def frames_tree_sha256(frames_dir: str | Path, expected_count: int) -> str:
    directory = Path(frames_dir)
    files = sorted(directory.iterdir()) if directory.is_dir() else []
    expected = [f"{frame:06d}.png" for frame in range(expected_count)]
    if [path.name for path in files] != expected or not all(path.is_file() and not path.is_symlink() for path in files):
        raise RunError(f"frame sequence in {directory} is incomplete or has unexpected files")
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode("ascii") + b"\0" + bytes.fromhex(file_sha256(path)))
    return digest.hexdigest()


def verify_render_run(output_dir: str | Path) -> dict[str, Any]:
    root = Path(output_dir).resolve()
    path = root / "render-manifest.json"
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RunError(f"missing or invalid render manifest in {root}") from exc
    if report.get("status") != "succeeded" or not report.get("idempotencyKey"):
        raise RunError("render manifest is not a completed run")
    outputs = report.get("outputs", [])
    if not any(item.get("kind") == "png_sequence" for item in outputs):
        raise RunError("render manifest has no frame sequence")
    for item in outputs:
        relative = Path(item.get("path", ""))
        if not relative.parts or relative.is_absolute() or ".." in relative.parts or ":" in str(relative):
            raise RunError("render manifest contains an unsafe artifact path")
        artifact = (root / relative).resolve()
        if not artifact.is_relative_to(root):
            raise RunError("render artifact escapes the output directory")
        if item["kind"] == "png_sequence":
            if item.get("frameCount") != report["frameCount"]:
                raise RunError("frame count mismatch in render manifest")
            actual = frames_tree_sha256(artifact, report["frameCount"])
            if item.get("treeSha256") != actual:
                raise RunError("frame sequence hash mismatch")
        elif item["kind"] in ("video/mp4", "audio/wav"):
            if not artifact.is_file() or item.get("sha256") != file_sha256(artifact):
                raise RunError("MP4 hash mismatch")
        else:
            raise RunError(f"unknown render artifact kind {item['kind']!r}")
    return report
