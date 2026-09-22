"""Render immutable, independently reviewable scene modules from one MotionSpec."""
from __future__ import annotations

from array import array
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

from . import __version__
from .rendering import FrameRenderer, RenderError, _ffmpeg_executable, _mix_audio, _sample_for_frame
from .revisions import file_sha256, spec_sha256
from .runs import frames_tree_sha256


def _slice_mix(source: Path, output: Path, start: int, end: int, rate: dict[str, int]) -> None:
    first = _sample_for_frame(start, rate)
    last = _sample_for_frame(end, rate)
    with wave.open(str(source), "rb") as stream:
        stream.setpos(first)
        payload = stream.readframes(last - first)
    samples = array("h")
    samples.frombytes(payload)
    if sys.byteorder != "little":
        samples.byteswap()
    if len(samples) != last - first:
        raise RenderError("project audio mix changed or ended while slicing scene modules")
    if sys.byteorder != "little":
        samples.byteswap()
    with wave.open(str(output), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(48_000)
        stream.writeframes(samples.tobytes())


def render_scene_modules(
    spec: dict[str, Any],
    output_dir: str | Path,
    *,
    mp4: bool = True,
    scale: float = 0.5,
    font_dirs: list[str | Path] | None = None,
    asset_root: str | Path | None = None,
    revision_sha256: str | None = None,
    scene_ids: list[str] | None = None,
    max_frames: int = 10_000,
) -> dict[str, Any]:
    """Render selected scenes with global timing semantics and local frame numbering.

    Cross-scene fades are evaluated against the complete MotionSpec. Each module therefore
    shows the same boundary frames as a full render, while remaining independently cached
    and reviewable by its stable scene ID.
    """
    renderer = FrameRenderer(spec, scale=scale, font_dirs=font_dirs, asset_root=asset_root)
    if mp4 and (renderer.width % 2 or renderer.height % 2):
        raise RenderError("MP4 scene module dimensions must be even; choose another scale")
    requested = scene_ids or [scene["id"] for scene in spec["timeline"]]
    if len(requested) != len(set(requested)):
        raise RenderError("scene module request contains duplicate scene IDs")
    by_id = {scene["id"]: scene for scene in spec["timeline"]}
    missing = [scene_id for scene_id in requested if scene_id not in by_id]
    if missing:
        raise RenderError(f"unknown scene IDs: {missing}")
    requested_frames = sum(by_id[scene_id]["endFrameExclusive"] - by_id[scene_id]["startFrame"] for scene_id in requested)
    if requested_frames > max_frames:
        raise RenderError(f"{requested_frames} requested scene frames exceeds safety limit {max_frames}; increase it explicitly")
    output = Path(output_dir).resolve()
    if output.exists():
        raise RenderError(f"output path {output} already exists; choose a new directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    rate = spec["canvas"]["frameRate"]
    with tempfile.TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as temporary:
        staging = Path(temporary)
        full_mix = None
        if renderer.audio_clips:
            full_mix = staging / ".project-mix.wav"
            _mix_audio(renderer, full_mix)
        modules = []
        for scene_id in requested:
            scene = by_id[scene_id]
            timeline_order = spec["timeline"].index(scene)
            start = scene["startFrame"]
            end = scene["endFrameExclusive"]
            duration = end - start
            directory_name = f"{timeline_order:03d}-{scene_id}-scene"
            module_dir = staging / directory_name
            frames_dir = module_dir / "frames"
            frames_dir.mkdir(parents=True)
            for local_frame, global_frame in enumerate(range(start, end)):
                renderer.render_frame(global_frame).save(frames_dir / f"{local_frame:06d}.png")
            outputs: list[dict[str, Any]] = [{
                "kind": "png_sequence",
                "path": f"{directory_name}/frames",
                "frameCount": duration,
                "treeSha256": frames_tree_sha256(frames_dir, duration),
            }]
            mix = None
            if full_mix is not None:
                mix = module_dir / "mix.wav"
                _slice_mix(full_mix, mix, start, end, rate)
                outputs.append({"kind": "audio/wav", "path": f"{directory_name}/mix.wav", "sha256": file_sha256(mix)})
            if mp4:
                video = module_dir / "preview.mp4"
                command = [
                    _ffmpeg_executable(), "-hide_banner", "-loglevel", "error", "-y",
                    "-framerate", f"{rate['numerator']}/{rate['denominator']}",
                    "-i", str(frames_dir / "%06d.png"),
                ]
                if mix is not None:
                    command += ["-i", str(mix)]
                command += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
                if mix is not None:
                    command += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
                command += ["-movflags", "+faststart", str(video)]
                completed = subprocess.run(command, capture_output=True, text=True, check=False)
                if completed.returncode:
                    raise RenderError(f"FFmpeg failed for scene {scene_id}: {completed.stderr.strip()}")
                outputs.append({"kind": "video/mp4", "path": f"{directory_name}/preview.mp4", "sha256": file_sha256(video)})
            module = {
                "sceneId": scene_id,
                "order": timeline_order,
                "directory": directory_name,
                "globalStartFrame": start,
                "globalEndFrameExclusive": end,
                "frameCount": duration,
                "outputs": outputs,
            }
            (module_dir / "scene-manifest.json").write_text(
                json.dumps(module, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            modules.append(module)
        if full_mix is not None:
            full_mix.unlink()
        manifest = {
            "formatVersion": 1,
            "producerVersion": __version__,
            "projectId": spec["project"]["id"],
            "specSha256": spec_sha256(spec),
            "revisionSha256": revision_sha256,
            "width": renderer.width,
            "height": renderer.height,
            "frameRate": rate,
            "renderOptions": {
                "mp4": mp4,
                "scale": scale,
                "fontDirs": [str(Path(path).resolve()) for path in (font_dirs or [])],
                "maxFrames": max_frames,
            },
            "sceneCount": len(modules),
            "modules": modules,
            "issues": list({(issue["code"], issue["message"]): issue for issue in renderer.issues}.values()),
        }
        (staging / "scene-modules.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        staging.rename(output)
        return manifest
