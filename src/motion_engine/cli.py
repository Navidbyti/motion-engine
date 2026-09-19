"""CLI for ingestion, MotionSpec validation, inspection, and planning."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="motion-engine")
    sub = parser.add_subparsers(dest="command", required=True)
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
    bundle = sub.add_parser("package-preview")
    bundle.add_argument("spec")
    bundle.add_argument("--render-dir", required=True)
    bundle.add_argument("--output-dir", required=True)
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
        if args.command == "ingest":
            result = ingest(args.source, args.source_id, args.limit)
            _emit(result, args.output)
            return 0
        if args.command == "package-preview":
            print(json.dumps(package_preview(args.spec, args.render_dir, args.output_dir), ensure_ascii=False, indent=2))
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
    except (OSError, ValueError, RuntimeError) as exc:
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
    elif args.command == "qa":
        result = qa_report(spec, Path(args.spec).resolve().parent, args.render_dir)
        _emit(result, args.output)
        if result["status"] != "passed":
            return 1
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
