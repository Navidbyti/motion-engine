"""Verify cached scene modules and assemble an exact full preview run."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

from . import __version__
from .rendering import RenderError, _ffmpeg_executable, _sample_for_frame
from .revisions import file_sha256, spec_sha256
from .runs import RunError, frames_tree_sha256, render_key
from .scene_modules import scene_input_sha256


class SceneAssemblyError(ValueError):
    pass


def _safe_artifact(root: Path, relative_value: str) -> Path:
    relative = Path(relative_value)
    if not relative.parts or relative.is_absolute() or ".." in relative.parts or ":" in str(relative):
        raise SceneAssemblyError("scene module contains an unsafe artifact path")
    artifact = (root / relative).resolve()
    if not artifact.is_relative_to(root):
        raise SceneAssemblyError("scene module artifact escapes its module directory")
    return artifact


def _load_modules(directory: str | Path) -> tuple[Path, dict[str, Any]]:
    root = Path(directory).resolve()
    try:
        manifest = json.loads((root / "scene-modules.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SceneAssemblyError(f"missing or invalid scene module manifest in {root}") from exc
    if manifest.get("formatVersion") != 2 or not isinstance(manifest.get("modules"), list):
        raise SceneAssemblyError(f"unsupported scene module manifest in {root}")
    return root, manifest


def _verify_candidate(root: Path, module: dict[str, Any]) -> dict[str, Any]:
    try:
        frame_output = next(item for item in module["outputs"] if item["kind"] == "png_sequence")
        frames = _safe_artifact(root, frame_output["path"])
        actual_tree = frames_tree_sha256(frames, module["frameCount"])
        if frame_output.get("frameCount") != module["frameCount"] or frame_output.get("treeSha256") != actual_tree:
            raise SceneAssemblyError(f"scene {module['sceneId']} frame sequence does not match its manifest")
        audio_output = next((item for item in module["outputs"] if item["kind"] == "audio/wav"), None)
        audio = None
        if audio_output is not None:
            audio = _safe_artifact(root, audio_output["path"])
            if not audio.is_file() or audio_output.get("sha256") != file_sha256(audio):
                raise SceneAssemblyError(f"scene {module['sceneId']} audio does not match its manifest")
        return {
            "root": root,
            "module": module,
            "frames": frames,
            "framesSha256": actual_tree,
            "audio": audio,
            "audioSha256": audio_output.get("sha256") if audio_output else None,
        }
    except (KeyError, StopIteration, TypeError, RunError) as exc:
        raise SceneAssemblyError("scene module record is incomplete or invalid") from exc


def _write_joined_audio(selected: list[dict[str, Any]], output: Path, spec: dict[str, Any]) -> None:
    rate = spec["canvas"]["frameRate"]
    with wave.open(str(output), "wb") as destination:
        destination.setnchannels(1)
        destination.setsampwidth(2)
        destination.setframerate(48_000)
        for item in selected:
            module = item["module"]
            audio = item["audio"]
            if audio is None:
                raise SceneAssemblyError(f"scene {module['sceneId']} is missing its project audio slice")
            expected = _sample_for_frame(module["globalEndFrameExclusive"], rate) - _sample_for_frame(module["globalStartFrame"], rate)
            try:
                with wave.open(str(audio), "rb") as source:
                    if (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getnframes()) != (1, 2, 48_000, expected):
                        raise SceneAssemblyError(f"scene {module['sceneId']} audio format or duration is invalid")
                    destination.writeframes(source.readframes(expected))
            except (OSError, EOFError, wave.Error) as exc:
                raise SceneAssemblyError(f"scene {module['sceneId']} audio cannot be decoded") from exc


def assemble_scene_modules(
    spec: dict[str, Any],
    module_dirs: list[str | Path],
    output_dir: str | Path,
    *,
    mp4: bool = True,
    scale: float = 0.5,
    font_dirs: list[str | Path] | None = None,
    revision_sha256: str | None = None,
) -> dict[str, Any]:
    if not module_dirs:
        raise SceneAssemblyError("at least one scene module directory is required")
    if not 0 < scale <= 1:
        raise SceneAssemblyError("scale must be greater than 0 and at most 1")
    output = Path(output_dir).resolve()
    if output.exists():
        raise SceneAssemblyError(f"output path {output} already exists; choose a new directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    expected_options = {
        "scale": scale,
        "fontDirs": [str(Path(path).resolve()) for path in (font_dirs or [])],
    }
    candidates: dict[str, list[dict[str, Any]]] = {}
    source_manifests = []
    for directory in module_dirs:
        root, manifest = _load_modules(directory)
        if manifest.get("renderOptions", {}).get("scale") != expected_options["scale"] or manifest.get("renderOptions", {}).get("fontDirs") != expected_options["fontDirs"]:
            raise SceneAssemblyError(f"scene module render settings do not match assembly settings: {root}")
        source_manifests.append({"directory": root.name, "sha256": file_sha256(root / "scene-modules.json")})
        for module in manifest["modules"]:
            candidates.setdefault(module.get("sceneId"), []).append(_verify_candidate(root, module))

    selected = []
    has_audio = any(element["kind"] == "audio" for scene in spec["timeline"] for element in scene["elements"])
    for order, scene in enumerate(spec["timeline"]):
        expected_hash = scene_input_sha256(spec, scene["id"], scale=scale, font_dirs=font_dirs)
        matches = [item for item in candidates.get(scene["id"], []) if item["module"].get("sceneInputSha256") == expected_hash]
        if not matches:
            raise SceneAssemblyError(f"no compatible module for scene {scene['id']}; render that scene against the current MotionSpec")
        signatures = {(item["framesSha256"], item["audioSha256"]) for item in matches}
        if len(signatures) != 1:
            raise SceneAssemblyError(f"compatible modules for scene {scene['id']} disagree; remove the ambiguous module set")
        chosen = matches[0]
        module = chosen["module"]
        if (module.get("order") != order or module.get("globalStartFrame") != scene["startFrame"]
                or module.get("globalEndFrameExclusive") != scene["endFrameExclusive"]
                or module.get("frameCount") != scene["endFrameExclusive"] - scene["startFrame"]):
            raise SceneAssemblyError(f"scene {scene['id']} module timing does not match the current MotionSpec")
        if has_audio != (chosen["audio"] is not None):
            raise SceneAssemblyError(f"scene {scene['id']} audio presence does not match the current MotionSpec")
        selected.append(chosen)

    width = max(1, round(spec["canvas"]["width"] * scale))
    height = max(1, round(spec["canvas"]["height"] * scale))
    if mp4 and (width % 2 or height % 2):
        raise SceneAssemblyError("MP4 assembly dimensions must be even; choose another scale")
    with tempfile.TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as temporary:
        staging = Path(temporary)
        frames_dir = staging / "frames"
        frames_dir.mkdir()
        global_frame = 0
        selections = []
        for item in selected:
            module = item["module"]
            for local_frame in range(module["frameCount"]):
                shutil.copyfile(item["frames"] / f"{local_frame:06d}.png", frames_dir / f"{global_frame:06d}.png")
                global_frame += 1
            selections.append({
                "sceneId": module["sceneId"],
                "sceneInputSha256": module["sceneInputSha256"],
                "framesSha256": item["framesSha256"],
                "audioSha256": item["audioSha256"],
            })
        duration = spec["canvas"]["durationFrames"]
        if global_frame != duration:
            raise SceneAssemblyError("assembled scene modules do not fill the project duration")
        outputs: list[dict[str, Any]] = [{
            "kind": "png_sequence", "path": "frames", "frameCount": duration,
            "treeSha256": frames_tree_sha256(frames_dir, duration),
        }]
        mix = None
        if has_audio:
            mix = staging / "mix.wav"
            _write_joined_audio(selected, mix, spec)
            outputs.append({"kind": "audio/wav", "path": "mix.wav", "sha256": file_sha256(mix)})
        if mp4:
            video = staging / "preview.mp4"
            rate = spec["canvas"]["frameRate"]
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
                raise SceneAssemblyError(f"FFmpeg failed during scene assembly: {completed.stderr.strip()}")
            outputs.append({"kind": "video/mp4", "path": "preview.mp4", "sha256": file_sha256(video)})
        spec_hash = spec_sha256(spec)
        report = {
            "status": "succeeded",
            "producerVersion": __version__,
            "idempotencyKey": render_key(spec_hash, revision_sha256, mp4=mp4, scale=scale, font_dirs=font_dirs),
            "renderOptions": {"mp4": mp4, **expected_options},
            "projectId": spec["project"]["id"],
            "specSha256": spec_hash,
            "revisionSha256": revision_sha256,
            "frameCount": duration,
            "width": width,
            "height": height,
            "frameRate": spec["canvas"]["frameRate"],
            "outputs": outputs,
            "issues": [],
            "assembly": {"formatVersion": 1, "sourceManifests": source_manifests, "scenes": selections},
            "note": "Deterministic preview assembled from verified scene modules; no editable Adobe project.",
        }
        (staging / "render-manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        staging.rename(output)
        return report
