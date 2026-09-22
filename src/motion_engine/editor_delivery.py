"""Build and verify a local editor handoff with review and supported native adapters."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .ae_script import AEExportError, make_ae_script
from .ai_script import AIExportError, make_ai_script
from .packaging import PackageError, package_preview, verify_preview_bundle
from .premiere_xml import PremiereXMLExportError, make_premiere_xml
from .ps_script import PSExportError, make_ps_script
from .revisions import file_sha256
from .review_site import ReviewSiteError, make_review_site
from .validation import load_spec


class EditorDeliveryError(ValueError):
    pass


def _files(root: Path) -> list[dict[str, str]]:
    return [{"path": path.relative_to(root).as_posix(), "sha256": file_sha256(path)}
            for path in sorted(root.rglob("*"))
            if path.is_file() and path.name != "editor-delivery.json"]


def make_editor_delivery(spec_path: str | Path, module_dirs: list[str | Path], render_dir: str | Path,
                         output_dir: str | Path, *, scale: float = 0.5,
                         font_dirs: list[str | Path] | None = None) -> dict[str, Any]:
    destination = Path(output_dir).resolve()
    if destination.exists():
        raise EditorDeliveryError(f"editor delivery already exists: {destination}")
    destination.mkdir(parents=True)
    try:
        source_package = destination / "source-package"
        package = package_preview(spec_path, render_dir, source_package)
        packaged_spec_path = source_package / package["specPath"]
        spec = load_spec(packaged_spec_path)
        review = make_review_site(spec, module_dirs, destination / "review", render_dir=source_package / "render",
                                  scale=scale, font_dirs=font_dirs,
                                  revision_sha256=package["revisionSha256"])
        native = destination / "native"
        native.mkdir()
        adapters: list[dict[str, str]] = []

        def attempt(name: str, action: Callable[[], Any], artifact: str, instructions: str) -> None:
            try:
                action()
                adapters.append({"application": name, "status": "prepared", "artifact": artifact,
                                 "instructions": instructions})
            except (AEExportError, AIExportError, PSExportError, PremiereXMLExportError, OSError, ValueError) as exc:
                adapters.append({"application": name, "status": "unsupported_for_this_project",
                                 "artifact": "", "instructions": str(exc)})

        attempt("After Effects", lambda: make_ae_script(
            spec, native / "after-effects-build.jsx", native / "motion-engine.aep",
            native / "after-effects-report.json", asset_root=packaged_spec_path.parent),
            "native/after-effects-build.jsx", "Run the JSX in After Effects. It creates motion-engine.aep and a verification report.")
        attempt("Premiere Pro", lambda: make_premiere_xml(
            spec, source_package / "render", native / "premiere-timeline.xml"),
            "native/premiere-timeline.xml", "Import the XML into Premiere Pro, then save the project as a .prproj.")
        attempt("Photoshop", lambda: make_ps_script(
            spec, native / "photoshop-build.jsx", native / "motion-engine.psd", native / "photoshop-report.json"),
            "native/photoshop-build.jsx", "Run the JSX in Photoshop to create the layered PSD and verification report.")
        attempt("Illustrator", lambda: make_ai_script(
            spec, native / "illustrator-build.jsx", native / "motion-engine.ai", native / "illustrator-report.json"),
            "native/illustrator-build.jsx", "Run the JSX in Illustrator to create the editable AI file and verification report.")
        prepared = [item for item in adapters if item["status"] == "prepared"]
        guide = [
            "# Editor delivery", "", f"Project: **{spec['project']['title']}**", "",
            "## Review", "", "Open `review/index.html` and watch the complete cut, then each scene. "
            "Copy a scene prompt into the same Codex, Claude, or Antigravity task to request a revision.", "",
            "## Manual editing", "", "Use the prepared adapter below. Run JSX files from the matching Adobe application. "
            "Premiere XML is imported through File > Import. Save the native project under a new filename after editing.", "",
        ]
        for item in adapters:
            guide.extend([f"- **{item['application']} — {item['status']}**: {item['instructions']}"])
        guide.extend(["", "## Source and QA", "", "`source-package/` contains the verified MotionSpec, inputs, preview, revision, and QA report. "
                      "Manual Adobe changes are not synchronized back into MotionSpec yet, so complete prompt revisions before final manual finishing.", ""])
        (destination / "OPEN_ME.md").write_text("\n".join(guide), encoding="utf-8")
        manifest = {"formatVersion": 1, "kind": "editor_delivery", "producerVersion": __version__,
                    "projectId": spec["project"]["id"], "specSha256": package["specSha256"],
                    "revisionSha256": package["revisionSha256"], "qaStatus": package["qaStatus"],
                    "review": "review/index.html", "preparedAdapterCount": len(prepared),
                    "adapters": adapters, "files": _files(destination)}
        (destination / "editor-delivery.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        verify_editor_delivery(destination)
        return manifest
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def verify_editor_delivery(output_dir: str | Path) -> dict[str, Any]:
    root = Path(output_dir).resolve()
    try:
        manifest = json.loads((root / "editor-delivery.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EditorDeliveryError("missing or invalid editor-delivery.json") from exc
    if manifest.get("kind") != "editor_delivery" or manifest.get("formatVersion") != 1:
        raise EditorDeliveryError("unsupported editor delivery format")
    if manifest.get("files") != _files(root):
        raise EditorDeliveryError("editor delivery files or hashes differ from the manifest")
    package = verify_preview_bundle(root / "source-package")
    if package["revisionSha256"] != manifest.get("revisionSha256"):
        raise EditorDeliveryError("source package revision differs from editor delivery")
    if not (root / "review" / "index.html").is_file():
        raise EditorDeliveryError("review interface is missing")
    return manifest
