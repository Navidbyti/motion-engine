"""Portable, content-verified preview bundles for local review."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from . import __version__
from .qa import qa_report
from .revisions import file_sha256, freeze_revision, resolve_local_file
from .runs import verify_render_run
from .validation import load_spec, validate


class PackageError(ValueError):
    pass


def _inside(root: Path, relative: str) -> Path:
    path = Path(relative)
    if not relative or path.is_absolute() or ".." in path.parts or ":" in relative or "\\" in relative:
        raise PackageError(f"unsafe package path {relative!r}")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise PackageError(f"package path escapes bundle: {relative!r}")
    return resolved


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _file_records(root: Path) -> list[dict[str, str]]:
    records = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise PackageError(f"bundle contains a symlink: {path}")
        if path.is_file() and path != root / "package-manifest.json":
            records.append({"path": path.relative_to(root).as_posix(), "sha256": file_sha256(path)})
    return records


def _verify_contact_sheet(review_dir: str | Path, revision: dict[str, Any],
                          render: dict[str, Any]) -> dict[str, Any]:
    root = Path(review_dir).resolve()
    try:
        report = json.loads((root / "contact-sheet.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PackageError("missing or invalid contact-sheet report") from exc
    if (report.get("specSha256") != revision["specSha256"]
            or report.get("revisionSha256") != revision["revisionSha256"]
            or report.get("renderIdempotencyKey") != render["idempotencyKey"]):
        raise PackageError("contact sheet does not match the current preview revision")
    sheets = report.get("sheets")
    if not isinstance(sheets, list) or not sheets:
        raise PackageError("contact-sheet report contains no sheets")
    expected = {"contact-sheet.json"}
    for item in sheets:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise PackageError("contact-sheet report has an invalid sheet record")
        path = _inside(root, item["path"])
        if not path.is_file() or file_sha256(path) != item.get("sha256"):
            raise PackageError(f"contact sheet {item['path']!r} is missing or changed")
        expected.add(path.relative_to(root).as_posix())
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    if actual != expected:
        raise PackageError("contact-sheet directory contains unverified files")
    return report


def package_preview(spec_path: str | Path, render_dir: str | Path, output_dir: str | Path,
                    review_dir: str | Path | None = None) -> dict[str, Any]:
    """Copy verified inputs and a completed preview without claiming native deliverables."""
    spec_path = Path(spec_path).resolve()
    spec = load_spec(spec_path)
    errors = validate(spec)
    if errors:
        raise PackageError(f"MotionSpec is invalid: {errors}")
    unsupported = [item["target"] for item in spec["deliverables"] if item["required"] and item["target"] != "video/mp4"]
    if unsupported:
        raise PackageError(f"required deliverables need native adapters before packaging: {unsupported}")
    revision = freeze_revision(spec, spec_path.parent)
    render = verify_render_run(render_dir)
    if render["specSha256"] != revision["specSha256"] or render["revisionSha256"] != revision["revisionSha256"]:
        raise PackageError("preview render does not match the current MotionSpec revision")
    if any(item["target"] == "video/mp4" and item["required"] for item in spec["deliverables"]):
        if not any(item["kind"] == "video/mp4" for item in render["outputs"]):
            raise PackageError("required MP4 is absent from the preview render")
    qa = qa_report(spec, spec_path.parent, render_dir)
    if qa["status"] == "failed":
        raise PackageError("QA failed; inspect the report before packaging")

    destination = Path(output_dir).resolve()
    if destination.exists():
        raise PackageError(f"package output {destination} already exists")
    protected_roots = [Path(render_dir).resolve()]
    if review_dir is not None:
        protected_roots.append(Path(review_dir).resolve())
    if any(destination.is_relative_to(root) for root in protected_roots):
        raise PackageError("package output cannot be inside its render or review input")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        project = staging / "project"
        project.mkdir()
        copy_spec = _inside(project, spec_path.name)
        shutil.copy2(spec_path, copy_spec)
        copied: dict[Path, str] = {}
        for item in [*spec["sources"], *(asset for asset in spec["assets"] if asset["status"] == "available")]:
            source = resolve_local_file(item, spec_path.parent, "input")
            target = _inside(project, item["uri"])
            if target == copy_spec:
                raise PackageError("input path collides with MotionSpec filename")
            digest = file_sha256(source)
            if target in copied:
                if copied[target] != digest:
                    raise PackageError(f"conflicting inputs share package path {item['uri']!r}")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied[target] = digest
        render_root = staging / "render"
        render_root.mkdir()
        shutil.copy2(Path(render_dir) / "render-manifest.json", render_root / "render-manifest.json")
        for item in render["outputs"]:
            relative = item["path"]
            source = _inside(Path(render_dir).resolve(), relative)
            target = _inside(render_root, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            if item["kind"] == "png_sequence":
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
        _write_json(staging / "revision.json", revision)
        _write_json(staging / "qa-report.json", qa)
        review = None
        if review_dir is not None:
            review = _verify_contact_sheet(review_dir, revision, render)
            review_root = staging / "review"
            shutil.copytree(Path(review_dir).resolve(), review_root)
        manifest = {
            "formatVersion": 1, "kind": "preview_bundle", "producerVersion": __version__,
            "projectId": spec["project"]["id"], "specPath": copy_spec.relative_to(staging).as_posix(),
            "specSha256": revision["specSha256"], "revisionSha256": revision["revisionSha256"],
            "qaStatus": qa["status"], "reviewPath": "review/contact-sheet.json" if review else None,
            "files": _file_records(staging),
        }
        _write_json(staging / "package-manifest.json", manifest)
        verify_preview_bundle(staging)
        staging.rename(destination)
        return manifest
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def verify_preview_bundle(output_dir: str | Path) -> dict[str, Any]:
    root = Path(output_dir).resolve()
    try:
        manifest = json.loads((root / "package-manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PackageError("missing or invalid package manifest") from exc
    if manifest.get("kind") != "preview_bundle" or manifest.get("formatVersion") != 1:
        raise PackageError("unsupported package format")
    listed = manifest.get("files")
    if not isinstance(listed, list) or listed != _file_records(root):
        raise PackageError("package files or hashes differ from manifest")
    spec_path = _inside(root, manifest["specPath"])
    spec = load_spec(spec_path)
    errors = validate(spec)
    if errors:
        raise PackageError(f"packaged MotionSpec is invalid: {errors}")
    revision = freeze_revision(spec, spec_path.parent)
    saved_revision = json.loads((root / "revision.json").read_text(encoding="utf-8"))
    if (revision != saved_revision or revision["revisionSha256"] != manifest["revisionSha256"]
            or revision["specSha256"] != manifest["specSha256"]):
        raise PackageError("packaged source revision differs from manifest")
    render = verify_render_run(root / "render")
    if render["revisionSha256"] != revision["revisionSha256"] or render["specSha256"] != revision["specSha256"]:
        raise PackageError("packaged render revision differs from inputs")
    qa = json.loads((root / "qa-report.json").read_text(encoding="utf-8"))
    if qa["status"] != manifest["qaStatus"] or qa["revisionSha256"] != revision["revisionSha256"]:
        raise PackageError("packaged QA report differs from revision")
    review_path = manifest.get("reviewPath")
    if review_path is not None:
        review_file = _inside(root, review_path)
        if review_file.name != "contact-sheet.json":
            raise PackageError("package review path must name contact-sheet.json")
        _verify_contact_sheet(review_file.parent, revision, render)
    return manifest
