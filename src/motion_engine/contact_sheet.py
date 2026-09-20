"""Verified, paginated scene contact sheets for agent and producer review."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageOps

from .revisions import freeze_revision, file_sha256, spec_sha256
from .runs import verify_render_run
from .validation import validate


class ContactSheetError(ValueError):
    pass


def make_contact_sheet(spec: dict[str, Any], spec_dir: str | Path,
                       render_dir: str | Path, output_dir: str | Path) -> dict[str, Any]:
    errors = validate(spec)
    if errors:
        raise ContactSheetError("MotionSpec is invalid: " + "; ".join(errors))
    revision = freeze_revision(spec, spec_dir)
    render = verify_render_run(render_dir)
    if (render.get("specSha256") != spec_sha256(spec)
        or render.get("revisionSha256") != revision["revisionSha256"]
        or render.get("frameCount") != spec["canvas"]["durationFrames"]):
        raise ContactSheetError("render does not match the current MotionSpec and input revision")
    output = Path(output_dir).resolve()
    if output.exists():
        raise ContactSheetError("contact sheet output already exists; choose a new directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    rows_per_page = 12
    cell_w, cell_h, thumb_w, thumb_h = 312, 218, 288, 162
    page_width = cell_w * 3 + 16
    root = Path(render_dir).resolve()
    sheets = []
    scenes = []
    with tempfile.TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as temporary:
        staging = Path(temporary)
        for page_start in range(0, len(spec["timeline"]), rows_per_page):
            subset = spec["timeline"][page_start:page_start + rows_per_page]
            canvas = Image.new("RGB", (page_width, cell_h * len(subset) + 16), "#111827")
            draw = ImageDraw.Draw(canvas)
            for row, scene in enumerate(subset):
                first, end = scene["startFrame"], scene["endFrameExclusive"]
                selected = list(dict.fromkeys((first, (first + end - 1) // 2, end - 1)))
                scenes.append({"sceneId": scene["id"], "startFrame": first,
                               "endFrameExclusive": end, "sampledFrames": selected,
                               "sheet": f"sheet-{page_start // rows_per_page + 1:03d}.png", "row": row})
                for column, frame in enumerate(selected):
                    x, y = 16 + cell_w * column, 16 + cell_h * row
                    path = root / "frames" / f"{frame:06d}.png"
                    try:
                        with Image.open(path) as source:
                            if source.size != (render["width"], render["height"]) or source.format != "PNG":
                                raise ContactSheetError(f"frame {frame} dimensions or format differ from render manifest")
                            preview = ImageOps.contain(source.convert("RGB"), (thumb_w, thumb_h), Image.Resampling.LANCZOS)
                    except (OSError, ValueError) as exc:
                        raise ContactSheetError(f"frame {frame} cannot be decoded") from exc
                    canvas.paste(preview, (x + (thumb_w - preview.width) // 2, y))
                    draw.text((x, y + thumb_h + 5), f"{scene['id']}  frame {frame}", fill="#F9FAFB")
            name = f"sheet-{page_start // rows_per_page + 1:03d}.png"
            path = staging / name
            canvas.save(path)
            sheets.append({"path": name, "sha256": file_sha256(path), "sceneCount": len(subset)})
        report = {"formatVersion": 1, "projectId": spec["project"]["id"],
                  "specSha256": revision["specSha256"],
                  "revisionSha256": revision["revisionSha256"],
                  "renderIdempotencyKey": render["idempotencyKey"],
                  "sheets": sheets, "scenes": scenes}
        (staging / "contact-sheet.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        staging.rename(output)
    return report
