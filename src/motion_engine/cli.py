"""CLI for ingestion, MotionSpec validation, inspection, and planning."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .validation import load_spec, validate
from .ingest import ingest
from .planning import load_capabilities, plan
from .rendering import RenderError, render_preview
from .revisions import RevisionError, freeze_revision
from .revisions import spec_sha256
from .runs import RunError, render_key, verify_render_run
from .qa import qa_report
from .packaging import package_preview, verify_preview_bundle
from .data_import import import_dataset
from .ae_script import AEExportError, make_ae_script
from .ai_script import AIExportError, make_ai_script
from .ps_script import PSExportError, make_ps_script
from .premiere_xml import PremiereXMLExportError, make_premiere_xml
from .pdf_assets import extract_pdf_images
from .review import make_review, verify_review
from .drafting import draft_text
from .scene_revisions import SceneRevisionError, revise_scene
from .video_import import VideoImportError, import_video
from .director import DirectorError, compile_director_plan
from .director_schema import DIRECTOR_PLAN_SCHEMA
from .contact_sheet import ContactSheetError, make_contact_sheet
from .claims import verify_claims
from .asset_requests import AssetRequestError, resolve_asset_requests
from .asset_catalog import AssetCatalogError, build_asset_catalog
from .scene_modules import render_scene_modules
from .scene_assembly import SceneAssemblyError, assemble_scene_modules
from .review_site import ReviewSiteError, make_review_site
from .doctor import doctor_report
from .project_workspace import WorkspaceError, init_project
from .editor_delivery import EditorDeliveryError, make_editor_delivery, verify_editor_delivery


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="motion-engine")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="Print the installed Motion Engine build version")
    doctor = sub.add_parser("doctor", help="Check local preview and optional Adobe readiness")
    doctor.add_argument("--workspace", help="Directory that must be writable")
    doctor.add_argument("--output", help="Write the shareable diagnostic report as JSON")
    project = sub.add_parser("init-project", help="Create a private, agent-ready production workspace")
    project.add_argument("output_dir")
    request_group = project.add_mutually_exclusive_group(required=True)
    request_group.add_argument("--request", help="The user's complete production request")
    request_group.add_argument("--request-file", help="UTF-8 file containing the production request")
    project.add_argument("--project-id")
    for name in ("validate", "inspect", "plan", "render", "freeze", "qa"):
        command = sub.add_parser(name)
        command.add_argument("spec")
        if name == "plan":
            command.add_argument("--capabilities", help="Optional adapter capability manifest JSON")
            command.add_argument("--output", help="Write plan JSON to this file")
            command.add_argument("--require-buildable", action="store_true", help="Fail until every required target has a working adapter")
        if name == "freeze":
            command.add_argument("--output", help="Write a verified revision manifest JSON")
        if name == "qa":
            command.add_argument("--render-dir", help="Check an existing preview render as well as the spec")
            command.add_argument("--output", help="Write the QA report JSON")
        if name == "render":
            command.add_argument("--output-dir", required=True)
            command.add_argument("--resume", action="store_true", help="Reuse a completed output only if its revision and artifacts verify")
            encode = command.add_mutually_exclusive_group()
            encode.add_argument("--mp4", action="store_true", help="Encode an MP4 even if not required in MotionSpec")
            encode.add_argument("--frames-only", action="store_true", help="Render PNG frames without MP4 encoding")
            command.add_argument("--scale", type=float, default=1.0, help="Preview scale from 0 to 1")
            command.add_argument("--font-dir", action="append", default=[], help="Additional directory containing licensed fonts")
            command.add_argument("--max-frames", type=int, default=10_000)
    ingestion = sub.add_parser("ingest")
    ingestion.add_argument("source")
    ingestion.add_argument("--source-id")
    ingestion.add_argument("--limit", type=int, default=100_000)
    ingestion.add_argument("--output", help="Write evidence JSON to this file")
    draft = sub.add_parser("draft-text", help="Draft a cited MotionSpec with one scene per plain-text line")
    draft.add_argument("source", help="UTF-8 .txt source inside the output MotionSpec directory")
    draft.add_argument("--output", required=True, help="New MotionSpec JSON path")
    draft.add_argument("--project-id", required=True)
    draft.add_argument("--locale", required=True)
    draft.add_argument("--direction", choices=("ltr", "rtl"), default="ltr")
    draft.add_argument("--width", type=int, default=1080)
    draft.add_argument("--height", type=int, default=1920)
    draft.add_argument("--fps", type=int, default=30)
    draft.add_argument("--frames-per-line", type=int, default=60)
    draft.add_argument("--font-family", default="DejaVu Sans")
    draft.add_argument("--max-lines", type=int, default=40)
    video_import = sub.add_parser("import-video", help="Convert a source video to a hashed, exact-frame PNG plate ZIP")
    video_import.add_argument("source")
    video_import.add_argument("--output", required=True)
    video_import.add_argument("--fps-num", type=int, required=True)
    video_import.add_argument("--fps-den", type=int, default=1)
    video_import.add_argument("--frames", type=int, required=True)
    video_import.add_argument("--start-ms", type=int, default=0)
    director = sub.add_parser("compile-director", help="Compile a complete agent-authored scene plan into MotionSpec")
    director.add_argument("prompt", help="UTF-8 prompt file inside the MotionSpec output directory")
    director.add_argument("proposal", help="Director plan JSON inside the MotionSpec output directory")
    director.add_argument("--output", required=True)
    director.add_argument("--project-id", required=True)
    director.add_argument("--assets", help="Optional JSON list of available hashed assets")
    director.add_argument("--claims", help="Source-linked claim ledger for factual scenes")
    director.add_argument("--data-fragment", action="append", default=[], help="Imported dataset fragment JSON; repeat for more datasets")
    director.add_argument("--width", type=int, default=1080)
    director.add_argument("--height", type=int, default=1920)
    director.add_argument("--fps", type=int, default=30)
    director_schema = sub.add_parser("director-schema", help="Print the portable whole-video director-plan JSON Schema")
    director_schema.add_argument("--output", help="Write the schema to this file")
    scene_modules = sub.add_parser("render-scenes", help="Render independently reviewable modules for stable scene IDs")
    scene_modules.add_argument("spec")
    scene_modules.add_argument("--output-dir", required=True)
    scene_modules.add_argument("--scene-id", action="append", default=[], help="Render only this scene ID; repeat to select more")
    scene_modules.add_argument("--scale", type=float, default=0.5)
    scene_modules.add_argument("--font-dir", action="append", default=[])
    scene_modules.add_argument("--frames-only", action="store_true")
    scene_modules.add_argument("--max-frames", type=int, default=10_000)
    assembly = sub.add_parser("assemble-scenes", help="Verify scene modules and assemble a complete preview run")
    assembly.add_argument("spec")
    assembly.add_argument("--modules", action="append", required=True, help="Scene module directory; repeat for cached and revised sets")
    assembly.add_argument("--output-dir", required=True)
    assembly.add_argument("--scale", type=float, default=0.5)
    assembly.add_argument("--font-dir", action="append", default=[])
    assembly.add_argument("--frames-only", action="store_true")
    review_site = sub.add_parser("make-review-site", help="Build a portable local scene-review interface")
    review_site.add_argument("spec")
    review_site.add_argument("--modules", action="append", required=True)
    review_site.add_argument("--render-dir", help="Optional verified assembled preview run")
    review_site.add_argument("--output-dir", required=True)
    review_site.add_argument("--scale", type=float, default=0.5)
    review_site.add_argument("--font-dir", action="append", default=[])
    editor_delivery = sub.add_parser("make-editor-delivery", help="Create a verified review and Adobe handoff folder")
    editor_delivery.add_argument("spec")
    editor_delivery.add_argument("--modules", action="append", required=True)
    editor_delivery.add_argument("--render-dir", required=True)
    editor_delivery.add_argument("--output-dir", required=True)
    editor_delivery.add_argument("--scale", type=float, default=0.5)
    editor_delivery.add_argument("--font-dir", action="append", default=[])
    verify_delivery = sub.add_parser("verify-editor-delivery", help="Verify a complete editor handoff folder")
    verify_delivery.add_argument("directory")
    asset_resolver = sub.add_parser("resolve-assets", help="Match pending shot requests to inspected local assets")
    asset_resolver.add_argument("proposal")
    asset_resolver.add_argument("--assets", required=True, help="Catalog of available hashed assets")
    asset_resolver.add_argument("--output", required=True, help="New director plan with resolved requests")
    asset_resolver.add_argument("--fps", type=int, default=30)
    catalog = sub.add_parser("catalog-assets", help="Hash and inspect approved local media into a new asset catalog")
    catalog.add_argument("manifest", help="JSON list of local media records")
    catalog.add_argument("--output", required=True, help="New asset catalog JSON path beside the manifest")
    catalog.add_argument("--fps", type=int, default=30, help="Project frame rate for frame plates")
    first = sub.add_parser("first-draft", help="Compile and render an agent-authored plan for a prompt")
    first.add_argument("prompt", help="UTF-8 prompt inside the output MotionSpec directory")
    first.add_argument("proposal", help="Agent-authored plan JSON inside the output MotionSpec directory")
    first.add_argument("--project-id", required=True)
    first.add_argument("--output-spec", required=True)
    first.add_argument("--output-dir", required=True)
    first.add_argument("--review-dir", help="Create verified scene contact sheets in a new directory")
    first.add_argument("--package-dir", help="Create a verified preview review bundle in a new directory")
    first.add_argument("--assets", help="Optional JSON list of available hashed assets")
    first.add_argument("--claims", help="Source-linked claim ledger for factual scenes")
    first.add_argument("--data-fragment", action="append", default=[], help="Imported dataset fragment JSON; repeat for more datasets")
    first.add_argument("--width", type=int, default=1080)
    first.add_argument("--height", type=int, default=1920)
    first.add_argument("--fps", type=int, default=30)
    first.add_argument("--scale", type=float, default=0.5)
    produce = sub.add_parser("produce", help="Build a complete first-draft review and editor handoff in one command")
    produce.add_argument("prompt", help="UTF-8 prompt beside the director plan")
    produce.add_argument("proposal", help="Agent-authored director plan JSON beside the prompt")
    produce.add_argument("--project-id", required=True)
    produce.add_argument("--name", default="v1", help="New filename prefix for this production version")
    produce.add_argument("--assets")
    produce.add_argument("--claims")
    produce.add_argument("--data-fragment", action="append", default=[])
    produce.add_argument("--width", type=int, default=1080)
    produce.add_argument("--height", type=int, default=1920)
    produce.add_argument("--fps", type=int, default=30)
    produce.add_argument("--scale", type=float, default=0.5)
    produce.add_argument("--font-dir", action="append", default=[])
    produce.add_argument("--max-frames", type=int, default=10_000)
    revise_production = sub.add_parser("revise-production", help="Rerender one revised scene and rebuild the complete editor handoff")
    revise_production.add_argument("spec", help="Current MotionSpec")
    revise_production.add_argument("request", help="Hash-bound typed scene revision JSON beside the MotionSpec")
    revise_production.add_argument("--modules", action="append", required=True, help="Compatible prior scene modules; repeat for multiple caches")
    revise_production.add_argument("--name", required=True, help="New filename prefix, such as v2")
    revise_production.add_argument("--scale", type=float, default=0.5)
    revise_production.add_argument("--font-dir", action="append", default=[])
    revise_production.add_argument("--max-frames", type=int, default=10_000)
    revised_render = sub.add_parser("revise-and-render", help="Apply an agent-authored typed scene edit and render")
    revised_render.add_argument("spec")
    revised_render.add_argument("request", help="Agent-authored JSON request in the MotionSpec directory")
    revised_render.add_argument("--output-spec", required=True)
    revised_render.add_argument("--output-dir", required=True)
    revised_render.add_argument("--review-dir", help="Create verified scene contact sheets in a new directory")
    revised_render.add_argument("--package-dir", help="Create a verified preview review bundle in a new directory")
    revised_render.add_argument("--scale", type=float, default=0.5)
    revise = sub.add_parser("revise-scene", help="Apply a typed edit to one scene against an exact MotionSpec hash")
    revise.add_argument("spec")
    revise.add_argument("request", help="JSON revision request in the MotionSpec directory")
    revise.add_argument("--output", required=True, help="New MotionSpec JSON in the same directory as the base spec")
    pdf_images = sub.add_parser("extract-pdf-images")
    pdf_images.add_argument("source")
    pdf_images.add_argument("--output-dir", required=True)
    pdf_images.add_argument("--max-images", type=int, default=1000)
    pdf_images.add_argument("--max-total-bytes", type=int, default=100_000_000)
    review = sub.add_parser("make-review")
    review.add_argument("evidence", nargs="+", help="Evidence JSON files produced by ingest")
    review.add_argument("--requirements", help="Optional project review questions JSON")
    review.add_argument("--output", required=True, help="New review JSON file; existing decisions are never overwritten")
    verify = sub.add_parser("verify-review")
    verify.add_argument("review")
    verify.add_argument("evidence", nargs="+")
    verify.add_argument("--requirements")
    claims = sub.add_parser("verify-claims", help="Check claim excerpts against hashed local source snapshots")
    claims.add_argument("ledger")
    claims.add_argument("--output", help="Write the source-link report JSON")
    bundle = sub.add_parser("package-preview")
    bundle.add_argument("spec")
    bundle.add_argument("--render-dir", required=True)
    bundle.add_argument("--output-dir", required=True)
    bundle.add_argument("--review-dir", help="Include an existing verified contact sheet directory")
    contact = sub.add_parser("contact-sheet", help="Create scene overview sheets from a verified preview")
    contact.add_argument("spec")
    contact.add_argument("--render-dir", required=True)
    contact.add_argument("--output-dir", required=True)
    verify_bundle = sub.add_parser("verify-package")
    verify_bundle.add_argument("directory")
    ae = sub.add_parser("make-ae-script")
    ae.add_argument("spec")
    ae.add_argument("--output-script", required=True)
    ae.add_argument("--output-aep", required=True)
    ae.add_argument("--report", required=True)
    ai = sub.add_parser("make-ai-script")
    ai.add_argument("spec")
    ai.add_argument("--output-script", required=True)
    ai.add_argument("--output-ai", required=True)
    ai.add_argument("--report", required=True)
    ps = sub.add_parser("make-ps-script")
    ps.add_argument("spec")
    ps.add_argument("--output-script", required=True)
    ps.add_argument("--output-psd", required=True)
    ps.add_argument("--report", required=True)
    premiere = sub.add_parser("make-premiere-xml")
    premiere.add_argument("spec")
    premiere.add_argument("--render-dir", required=True, help="Completed, verified MP4 preview run")
    premiere.add_argument("--output-xml", required=True)
    data = sub.add_parser("import-data")
    data.add_argument("source")
    data.add_argument("--project-root", required=True, help="Directory where the future MotionSpec will live")
    data.add_argument("--dataset-id", required=True)
    data.add_argument("--source-id")
    data.add_argument("--sheet", help="Required XLSX sheet name")
    data.add_argument("--table-range", help="Explicit rectangle, such as A1:D12")
    data.add_argument("--type", action="append", default=[], help="Override inferred type as field:type")
    data.add_argument("--max-rows", type=int, default=10_000)
    data.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        if args.command == "version":
            print(__version__)
            return 0
        if args.command == "doctor":
            result = doctor_report(args.workspace)
            _emit(result, args.output)
            return 0 if result["ok"] else 1
        if args.command == "init-project":
            request = args.request
            if args.request_file:
                request = Path(args.request_file).read_text(encoding="utf-8-sig")
            print(json.dumps(init_project(args.output_dir, request, project_id=args.project_id), ensure_ascii=False, indent=2))
            return 0
        if args.command == "ingest":
            result = ingest(args.source, args.source_id, args.limit)
            _emit(result, args.output)
            return 0
        if args.command == "draft-text":
            if Path(args.output).exists():
                raise ValueError("draft output already exists; choose a new path")
            result = draft_text(args.source, args.output, project_id=args.project_id,
                                locale=args.locale, direction=args.direction,
                                width=args.width, height=args.height, frame_rate=args.fps,
                                frames_per_line=args.frames_per_line,
                                font_family=args.font_family, max_lines=args.max_lines)
            _emit(result, args.output)
            return 0
        if args.command == "import-video":
            print(json.dumps(import_video(args.source, args.output, numerator=args.fps_num,
                                          denominator=args.fps_den, frame_count=args.frames,
                                          start_ms=args.start_ms), ensure_ascii=False, indent=2))
            return 0
        if args.command == "compile-director":
            if Path(args.output).exists():
                raise DirectorError("director output already exists; choose a new MotionSpec path")
            with Path(args.proposal).open("r", encoding="utf-8") as stream:
                proposal = json.load(stream)
            asset_list = None
            if args.assets:
                with Path(args.assets).open("r", encoding="utf-8") as stream:
                    asset_list = json.load(stream)
            data_fragments = []
            for path in args.data_fragment:
                with Path(path).open("r", encoding="utf-8") as stream:
                    data_fragments.append(json.load(stream))
            result = compile_director_plan(args.prompt, args.output, proposal,
                                           project_id=args.project_id, width=args.width,
                                           height=args.height, fps=args.fps,
                                           assets=asset_list, proposal_path=args.proposal,
                                           claim_ledger_path=args.claims,
                                           data_fragments=data_fragments)
            _emit(result, args.output)
            return 0
        if args.command == "director-schema":
            _emit(DIRECTOR_PLAN_SCHEMA, args.output)
            return 0
        if args.command == "render-scenes":
            spec_path = Path(args.spec).resolve()
            spec = load_spec(spec_path)
            errors = validate(spec)
            if errors:
                raise RenderError("invalid MotionSpec: " + "; ".join(errors))
            revision = freeze_revision(spec, spec_path.parent)
            result = render_scene_modules(
                spec,
                args.output_dir,
                mp4=not args.frames_only,
                scale=args.scale,
                font_dirs=args.font_dir,
                asset_root=spec_path.parent,
                revision_sha256=revision["revisionSha256"],
                scene_ids=args.scene_id or None,
                max_frames=args.max_frames,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "assemble-scenes":
            spec_path = Path(args.spec).resolve()
            spec = load_spec(spec_path)
            errors = validate(spec)
            if errors:
                raise SceneAssemblyError("invalid MotionSpec: " + "; ".join(errors))
            revision = freeze_revision(spec, spec_path.parent)
            result = assemble_scene_modules(
                spec,
                args.modules,
                args.output_dir,
                mp4=not args.frames_only,
                scale=args.scale,
                font_dirs=args.font_dir,
                revision_sha256=revision["revisionSha256"],
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "make-review-site":
            spec_path = Path(args.spec).resolve()
            spec = load_spec(spec_path)
            errors = validate(spec)
            if errors:
                raise ReviewSiteError("invalid MotionSpec: " + "; ".join(errors))
            revision = freeze_revision(spec, spec_path.parent)
            result = make_review_site(
                spec,
                args.modules,
                args.output_dir,
                render_dir=args.render_dir,
                scale=args.scale,
                font_dirs=args.font_dir,
                revision_sha256=revision["revisionSha256"],
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "make-editor-delivery":
            result = make_editor_delivery(args.spec, args.modules, args.render_dir, args.output_dir,
                                          scale=args.scale, font_dirs=args.font_dir)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "verify-editor-delivery":
            print(json.dumps(verify_editor_delivery(args.directory), ensure_ascii=False, indent=2))
            return 0
        if args.command == "resolve-assets":
            result = resolve_asset_requests(args.proposal, args.assets, args.output, fps=args.fps)
            _emit(result, args.output)
            return 0
        if args.command == "catalog-assets":
            result = build_asset_catalog(args.manifest, args.output, fps=args.fps)
            _emit(result, args.output)
            return 0
        if args.command == "first-draft":
            plan_path = Path(args.proposal).resolve()
            spec_path = Path(args.output_spec).resolve()
            render_path = Path(args.output_dir).resolve()
            review_path = Path(args.review_dir).resolve() if args.review_dir else None
            package_path = Path(args.package_dir).resolve() if args.package_dir else None
            prompt_path = Path(args.prompt).resolve()
            if (plan_path.parent != spec_path.parent or prompt_path.parent != spec_path.parent
                    or len({plan_path, spec_path, render_path, prompt_path, review_path, package_path} - {None}) != (4 + bool(review_path) + bool(package_path))):
                raise DirectorError("prompt, plan, and MotionSpec must be distinct files in the same directory")
            if (not plan_path.is_file() or not prompt_path.is_file() or spec_path.exists() or render_path.exists()
                    or (review_path is not None and review_path.exists())
                    or (package_path is not None and package_path.exists())):
                raise DirectorError("prompt and plan must exist; spec and render outputs must be new paths")
            asset_list = None
            if args.assets:
                with Path(args.assets).open("r", encoding="utf-8") as stream:
                    asset_list = json.load(stream)
            with plan_path.open("r", encoding="utf-8") as stream:
                proposal = json.load(stream)
            data_fragments = []
            for path in args.data_fragment:
                with Path(path).open("r", encoding="utf-8") as stream:
                    data_fragments.append(json.load(stream))
            spec = compile_director_plan(args.prompt, spec_path, proposal,
                                         project_id=args.project_id, width=args.width,
                                         height=args.height, fps=args.fps,
                                         assets=asset_list, proposal_path=plan_path,
                                         claim_ledger_path=args.claims,
                                         data_fragments=data_fragments)
            _emit(spec, spec_path)
            revision = freeze_revision(spec, spec_path.parent)
            result = render_preview(spec, render_path, scale=args.scale,
                                    asset_root=spec_path.parent,
                                    revision_sha256=revision["revisionSha256"])
            quality = qa_report(spec, spec_path.parent, render_path)
            _emit(quality, render_path / "qa.json")
            sheets = make_contact_sheet(spec, spec_path.parent, render_path, review_path) if review_path else None
            bundle_manifest = package_preview(spec_path, render_path, package_path, review_path) if package_path else None
            print(json.dumps({"plan": str(plan_path), "spec": str(spec_path),
                              "render": str(render_path), "manifest": result,
                              "qa": str(render_path / "qa.json"), "qaStatus": quality["status"],
                              "contactSheet": str(review_path / "contact-sheet.json") if sheets else None,
                              "package": str(package_path) if bundle_manifest else None},
                             ensure_ascii=False, indent=2))
            return 0
        if args.command == "produce":
            prompt_path = Path(args.prompt).resolve()
            plan_path = Path(args.proposal).resolve()
            if prompt_path.parent != plan_path.parent:
                raise DirectorError("prompt and director plan must share a directory")
            if not args.name or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for character in args.name):
                raise DirectorError("production name may contain only letters, numbers, dot, dash, and underscore")
            root = prompt_path.parent
            spec_path = root / f"{args.name}.motion.json"
            modules_path = root / f"{args.name}-scenes"
            render_path = root / f"{args.name}-preview"
            review_path = root / f"{args.name}-review"
            delivery_path = root / f"{args.name}-editor-delivery"
            outputs = (spec_path, modules_path, render_path, review_path, delivery_path)
            if any(path.exists() for path in outputs):
                raise DirectorError("production outputs already exist; choose a new --name")
            with plan_path.open("r", encoding="utf-8") as stream:
                proposal = json.load(stream)
            asset_list = None
            if args.assets:
                with Path(args.assets).open("r", encoding="utf-8") as stream:
                    asset_list = json.load(stream)
            data_fragments = []
            for path in args.data_fragment:
                with Path(path).open("r", encoding="utf-8") as stream:
                    data_fragments.append(json.load(stream))
            spec = compile_director_plan(prompt_path, spec_path, proposal, project_id=args.project_id,
                                         width=args.width, height=args.height, fps=args.fps,
                                         assets=asset_list, proposal_path=plan_path,
                                         claim_ledger_path=args.claims, data_fragments=data_fragments)
            _emit(spec, spec_path)
            revision = freeze_revision(spec, root)
            modules = render_scene_modules(spec, modules_path, mp4=True, scale=args.scale,
                                           font_dirs=args.font_dir, asset_root=root,
                                           revision_sha256=revision["revisionSha256"], max_frames=args.max_frames)
            assembled = assemble_scene_modules(spec, [modules_path], render_path, mp4=True,
                                               scale=args.scale, font_dirs=args.font_dir,
                                               revision_sha256=revision["revisionSha256"])
            quality = qa_report(spec, root, render_path)
            _emit(quality, render_path / "qa.json")
            review = make_review_site(spec, [modules_path], review_path, render_dir=render_path,
                                      scale=args.scale, font_dirs=args.font_dir,
                                      revision_sha256=revision["revisionSha256"])
            delivery = make_editor_delivery(spec_path, [modules_path], render_path, delivery_path,
                                            scale=args.scale, font_dirs=args.font_dir)
            state_path = root / "project.json"
            if state_path.is_file():
                state = json.loads(state_path.read_text(encoding="utf-8"))
                if isinstance(state, dict) and state.get("projectId") == args.project_id:
                    state["currentVersion"] = args.name
                    state["status"] = "first_draft_ready"
                    state["artifacts"] = {"spec": spec_path.name, "preview": f"{render_path.name}/preview.mp4",
                                          "review": f"{review_path.name}/index.html",
                                          "editorDelivery": delivery_path.name}
                    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"ok": quality["status"] != "failed", "name": args.name,
                              "spec": str(spec_path), "sceneModules": str(modules_path),
                              "preview": str(render_path / "preview.mp4"),
                              "qa": str(render_path / "qa.json"), "qaStatus": quality["status"],
                              "review": str(review_path / "index.html"),
                              "editorDelivery": str(delivery_path),
                              "sceneCount": len(modules["modules"]),
                              "preparedAdapterCount": delivery["preparedAdapterCount"]}, ensure_ascii=False, indent=2))
            return 0 if quality["status"] != "failed" else 1
        if args.command == "revise-production":
            base_path = Path(args.spec).resolve()
            request_path = Path(args.request).resolve()
            if base_path.parent != request_path.parent:
                raise SceneRevisionError("base MotionSpec and revision request must share a directory")
            if not args.name or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for character in args.name):
                raise SceneRevisionError("production name may contain only letters, numbers, dot, dash, and underscore")
            root = base_path.parent
            spec_path = root / f"{args.name}.motion.json"
            modules_path = root / f"{args.name}-scenes"
            render_path = root / f"{args.name}-preview"
            review_path = root / f"{args.name}-review"
            delivery_path = root / f"{args.name}-editor-delivery"
            summary_path = root / f"{args.name}-revision-summary.json"
            outputs = (spec_path, modules_path, render_path, review_path, delivery_path, summary_path)
            if any(path.exists() for path in outputs):
                raise SceneRevisionError("revision production outputs already exist; choose a new --name")
            base = load_spec(base_path)
            errors = validate(base)
            if errors:
                raise SceneRevisionError("base MotionSpec is invalid: " + "; ".join(errors))
            with request_path.open("r", encoding="utf-8") as stream:
                request = json.load(stream)
            if not isinstance(request, dict):
                raise SceneRevisionError("revision request must be a JSON object")
            scene_id = request.get("sceneId")
            revised = revise_scene(base, request, request_path=request_path, output_path=spec_path)
            _emit(revised, spec_path)
            revision = freeze_revision(revised, root)
            changed_modules = render_scene_modules(
                revised, modules_path, mp4=True, scale=args.scale, font_dirs=args.font_dir,
                asset_root=root, revision_sha256=revision["revisionSha256"],
                scene_ids=[scene_id], max_frames=args.max_frames,
            )
            all_modules = [*args.modules, str(modules_path)]
            assemble_scene_modules(revised, all_modules, render_path, mp4=True,
                                   scale=args.scale, font_dirs=args.font_dir,
                                   revision_sha256=revision["revisionSha256"])
            quality = qa_report(revised, root, render_path)
            _emit(quality, render_path / "qa.json")
            make_review_site(revised, all_modules, review_path, render_dir=render_path,
                             scale=args.scale, font_dirs=args.font_dir,
                             revision_sha256=revision["revisionSha256"])
            delivery = make_editor_delivery(spec_path, all_modules, render_path, delivery_path,
                                            scale=args.scale, font_dirs=args.font_dir)
            reused = [scene["id"] for scene in revised["timeline"] if scene["id"] != scene_id]
            summary = {"formatVersion": 1, "kind": "production_revision",
                       "baseSpec": base_path.name, "baseSpecSha256": spec_sha256(base),
                       "newSpec": spec_path.name, "newSpecSha256": spec_sha256(revised),
                       "revisionSha256": revision["revisionSha256"], "request": request_path.name,
                       "sceneId": scene_id, "operationCount": len(request.get("operations", [])),
                       "rerenderedScenes": [scene_id], "reusedScenes": reused,
                       "qaStatus": quality["status"], "preview": f"{render_path.name}/preview.mp4",
                       "review": f"{review_path.name}/index.html", "editorDelivery": delivery_path.name}
            _emit(summary, summary_path)
            state_path = root / "project.json"
            if state_path.is_file():
                state = json.loads(state_path.read_text(encoding="utf-8"))
                if isinstance(state, dict) and state.get("projectId") == revised["project"]["id"]:
                    state["currentVersion"] = args.name
                    state["status"] = "revision_ready"
                    state["artifacts"] = {"spec": spec_path.name, "preview": summary["preview"],
                                          "review": summary["review"], "editorDelivery": delivery_path.name,
                                          "revisionSummary": summary_path.name}
                    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"ok": True, **summary,
                              "preparedAdapterCount": delivery["preparedAdapterCount"],
                              "renderedModuleCount": len(changed_modules["modules"])}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "revise-and-render":
            base_path = Path(args.spec).resolve()
            request_path = Path(args.request).resolve()
            spec_path = Path(args.output_spec).resolve()
            render_path = Path(args.output_dir).resolve()
            review_path = Path(args.review_dir).resolve() if args.review_dir else None
            package_path = Path(args.package_dir).resolve() if args.package_dir else None
            if base_path.parent != spec_path.parent or request_path.parent != spec_path.parent:
                raise SceneRevisionError("base spec, request, and new spec must share a directory")
            if len({base_path, request_path, spec_path, render_path, review_path, package_path} - {None}) != (4 + bool(review_path) + bool(package_path)) or not request_path.is_file() or any(
                path.exists() for path in (spec_path, render_path) + ((review_path,) if review_path else ()) + ((package_path,) if package_path else ())
            ):
                raise SceneRevisionError("revision request must exist; spec and render outputs must be new, distinct paths")
            base = load_spec(base_path)
            errors = validate(base)
            if errors:
                raise SceneRevisionError("base MotionSpec is invalid: " + "; ".join(errors))
            with request_path.open("r", encoding="utf-8") as stream:
                request = json.load(stream)
            if not isinstance(request, dict):
                raise SceneRevisionError("revision request must be a JSON object")
            revised = revise_scene(base, request, request_path=request_path, output_path=spec_path)
            _emit(revised, spec_path)
            revision = freeze_revision(revised, spec_path.parent)
            result = render_preview(revised, render_path, scale=args.scale,
                                    asset_root=spec_path.parent,
                                    revision_sha256=revision["revisionSha256"])
            quality = qa_report(revised, spec_path.parent, render_path)
            _emit(quality, render_path / "qa.json")
            sheets = make_contact_sheet(revised, spec_path.parent, render_path, review_path) if review_path else None
            bundle_manifest = package_preview(spec_path, render_path, package_path, review_path) if package_path else None
            print(json.dumps({"request": str(request_path), "spec": str(spec_path),
                              "render": str(render_path), "manifest": result,
                              "qa": str(render_path / "qa.json"), "qaStatus": quality["status"],
                              "contactSheet": str(review_path / "contact-sheet.json") if sheets else None,
                              "package": str(package_path) if bundle_manifest else None},
                             ensure_ascii=False, indent=2))
            return 0
        if args.command == "revise-scene":
            source_spec = Path(args.spec).resolve()
            output_spec = Path(args.output).resolve()
            if output_spec.parent != source_spec.parent:
                raise SceneRevisionError("new MotionSpec must be beside the base spec so source links remain portable")
            if output_spec.exists():
                raise SceneRevisionError("revised MotionSpec already exists; choose a new output path")
            spec = load_spec(source_spec)
            errors = validate(spec)
            if errors:
                raise SceneRevisionError("base MotionSpec is invalid: " + "; ".join(errors))
            with Path(args.request).open("r", encoding="utf-8") as stream:
                request = json.load(stream)
            if not isinstance(request, dict):
                raise SceneRevisionError("revision request must be a JSON object")
            result = revise_scene(spec, request, request_path=args.request, output_path=output_spec)
            _emit(result, output_spec)
            return 0
        if args.command == "extract-pdf-images":
            print(json.dumps(extract_pdf_images(args.source, args.output_dir,
                                                args.max_images, args.max_total_bytes),
                             ensure_ascii=False, indent=2))
            return 0
        if args.command == "make-review":
            if Path(args.output).exists():
                raise ValueError("review output already exists; existing decisions cannot be overwritten")
            _emit(make_review(args.evidence, args.requirements), args.output)
            return 0
        if args.command == "verify-review":
            result = verify_review(args.review, args.evidence, args.requirements)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "passed" else 1
        if args.command == "verify-claims":
            if args.output and Path(args.output).exists():
                raise ValueError("claim report output already exists; choose a new path")
            result = verify_claims(args.ledger)
            _emit(result, args.output)
            return 0 if result["status"] == "source_linked" else 1
        if args.command == "package-preview":
            print(json.dumps(package_preview(args.spec, args.render_dir, args.output_dir, args.review_dir), ensure_ascii=False, indent=2))
            return 0
        if args.command == "verify-package":
            print(json.dumps(verify_preview_bundle(args.directory), ensure_ascii=False, indent=2))
            return 0
        if args.command == "import-data":
            overrides = {}
            for item in args.type:
                if ":" not in item:
                    raise ValueError("--type must be field:type")
                field, declared_type = item.split(":", 1)
                if field in overrides:
                    raise ValueError(f"duplicate --type for {field!r}")
                overrides[field] = declared_type
            result = import_dataset(args.source, args.project_root, args.dataset_id,
                                    args.source_id, args.sheet, overrides, args.max_rows, args.table_range)
            _emit(result, args.output)
            return 0
        spec = load_spec(args.spec)
        errors = validate(spec)
    except (OSError, ValueError, RuntimeError, UnicodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False), file=sys.stderr)
        return 2
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    if args.command == "validate":
        print(json.dumps({"ok": True, "schemaVersion": spec["schemaVersion"]}))
    elif args.command == "inspect":
        print(json.dumps({
            "id": spec["project"]["id"],
            "title": spec["project"]["title"],
            "locale": spec["project"]["locale"],
            "canvas": spec["canvas"],
            "scenes": len(spec["timeline"]),
            "beats": sum(len(s["beats"]) for s in spec["timeline"]),
            "deliverables": [d["target"] for d in spec["deliverables"]],
        }, ensure_ascii=False, indent=2))
    elif args.command == "plan":
        try:
            result = plan(spec, load_capabilities(args.capabilities))
            _emit(result, args.output)
        except (OSError, ValueError) as exc:
            print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False), file=sys.stderr)
            return 2
        if any(issue["severity"] == "error" for issue in result["issues"]):
            return 1
        if args.require_buildable and not result["buildable"]:
            return 1
    elif args.command == "freeze":
        try:
            if args.output and Path(args.output).exists():
                raise RevisionError(f"revision output {args.output} already exists; choose a new path")
            _emit(freeze_revision(spec, Path(args.spec).resolve().parent), args.output)
        except (OSError, RevisionError) as exc:
            print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False), file=sys.stderr)
            return 2
    elif args.command == "make-ae-script":
        try:
            result = make_ae_script(spec, args.output_script, args.output_aep, args.report,
                                    asset_root=Path(args.spec).resolve().parent)
            print(json.dumps({"ok": True, "script": str(result), "aep": str(Path(args.output_aep).resolve()),
                              "report": str(Path(args.report).resolve())}, ensure_ascii=False, indent=2))
        except (OSError, AEExportError) as exc:
            print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False), file=sys.stderr)
            return 2
    elif args.command == "make-ai-script":
        try:
            result = make_ai_script(spec, args.output_script, args.output_ai, args.report)
            print(json.dumps({"ok": True, "script": str(result), "ai": str(Path(args.output_ai).resolve()),
                              "report": str(Path(args.report).resolve())}, ensure_ascii=False, indent=2))
        except (OSError, AIExportError) as exc:
            print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False), file=sys.stderr)
            return 2
    elif args.command == "make-ps-script":
        try:
            result = make_ps_script(spec, args.output_script, args.output_psd, args.report)
            print(json.dumps({"ok": True, "script": str(result), "psd": str(Path(args.output_psd).resolve()),
                              "report": str(Path(args.report).resolve())}, ensure_ascii=False, indent=2))
        except (OSError, PSExportError) as exc:
            print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False), file=sys.stderr)
            return 2
    elif args.command == "make-premiere-xml":
        try:
            result = make_premiere_xml(spec, args.render_dir, args.output_xml)
            print(json.dumps({"ok": True, "xml": str(result)}, ensure_ascii=False, indent=2))
        except (OSError, PremiereXMLExportError) as exc:
            print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False), file=sys.stderr)
            return 2
    elif args.command == "qa":
        result = qa_report(spec, Path(args.spec).resolve().parent, args.render_dir)
        _emit(result, args.output)
        if result["status"] != "passed":
            return 1
    elif args.command == "contact-sheet":
        try:
            result = make_contact_sheet(spec, Path(args.spec).resolve().parent,
                                        args.render_dir, args.output_dir)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except (OSError, ValueError, RunError, ContactSheetError) as exc:
            print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False), file=sys.stderr)
            return 2
    else:
        try:
            encode_mp4 = True if args.mp4 else False if args.frames_only else None
            if not 0 < args.scale <= 1:
                raise RenderError("scale must be greater than 0 and at most 1")
            spec_dir = Path(args.spec).resolve().parent
            revision = freeze_revision(spec, spec_dir)
            actual_mp4 = encode_mp4 if encode_mp4 is not None else any(d["target"] == "video/mp4" and d["required"] for d in spec["deliverables"])
            if args.resume and Path(args.output_dir).exists():
                result = verify_render_run(args.output_dir)
                expected = render_key(spec_sha256(spec), revision["revisionSha256"], mp4=actual_mp4,
                                      scale=args.scale, font_dirs=args.font_dir)
                if result["idempotencyKey"] != expected or result["revisionSha256"] != revision["revisionSha256"]:
                    raise RunError("existing render was built from different inputs or options")
            else:
                result = render_preview(spec, args.output_dir, mp4=encode_mp4, scale=args.scale,
                                        font_dirs=args.font_dir, max_frames=args.max_frames,
                                        asset_root=spec_dir, revision_sha256=revision["revisionSha256"])
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except (OSError, ValueError, RenderError, RunError) as exc:
            print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False), file=sys.stderr)
            return 2
    return 0


def _emit(value: dict, path: str | None) -> None:
    encoded = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path:
        from pathlib import Path
        Path(path).write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    raise SystemExit(main())
