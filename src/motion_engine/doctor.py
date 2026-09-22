"""Local readiness checks with safe, shareable output."""
from __future__ import annotations

import os
import platform
import sys
import tempfile
from pathlib import Path
from typing import Any

from PIL import features

from . import __version__
from .rendering import RenderError, _ffmpeg_executable


def _check(check_id: str, status: str, summary: str, detail: str = "") -> dict[str, str]:
    return {"id": check_id, "status": status, "summary": summary, "detail": detail}


def _adobe_apps() -> list[str]:
    if os.name != "nt":
        return []
    roots = [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")]
    found: set[str] = set()
    names = ("After Effects", "Premiere Pro", "Photoshop", "Illustrator")
    for value in roots:
        root = Path(value) / "Adobe" if value else None
        if root and root.is_dir():
            for child in root.iterdir():
                for name in names:
                    if name.casefold() in child.name.casefold():
                        found.add(child.name)
    return sorted(found)


def doctor_report(workspace: str | Path | None = None) -> dict[str, Any]:
    """Return core readiness and optional integration information without secrets."""
    checks = []
    version_ok = sys.version_info >= (3, 11)
    checks.append(_check("python", "passed" if version_ok else "failed",
                         f"Python {platform.python_version()}", "Python 3.11 or newer is required."))
    try:
        ffmpeg = _ffmpeg_executable()
        checks.append(_check("ffmpeg", "passed", "FFmpeg is available", str(Path(ffmpeg).name)))
    except RenderError as exc:
        checks.append(_check("ffmpeg", "failed", "FFmpeg is unavailable", str(exc)))
    raqm = bool(features.check("raqm"))
    checks.append(_check("complex_text", "passed" if raqm else "warning",
                         "Complex text shaping is available" if raqm else "Complex text shaping is unavailable",
                         "Required for reliable RTL and complex-script previews."))
    target = Path(workspace or Path.cwd()).resolve()
    try:
        target.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix=".motion-engine-write-", dir=target, delete=True):
            pass
        checks.append(_check("workspace", "passed", "Workspace is writable", str(target)))
    except OSError as exc:
        checks.append(_check("workspace", "failed", "Workspace is not writable", str(exc)))
    adobe = _adobe_apps()
    checks.append(_check("adobe", "passed" if adobe else "optional",
                         "Adobe applications detected" if adobe else "No Adobe applications detected",
                         "; ".join(adobe) if adobe else "Preview rendering works without Adobe; native project creation is optional."))
    core_ids = {"python", "ffmpeg", "workspace"}
    ready = all(item["status"] == "passed" for item in checks if item["id"] in core_ids)
    return {
        "ok": ready,
        "status": "ready" if ready else "blocked",
        "motionEngineVersion": __version__,
        "platform": platform.system(),
        "checks": checks,
        "nextAction": "Start or continue a production." if ready else "Fix failed checks, then run doctor again.",
    }
