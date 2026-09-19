"""CLI for ingestion, MotionSpec validation, inspection, and planning."""
from __future__ import annotations

import argparse
import json
import sys

from .validation import load_spec, validate
from .ingest import ingest
from .planning import load_capabilities, plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="motion-engine")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "inspect", "plan"):
        command = sub.add_parser(name)
        command.add_argument("spec")
        if name == "plan":
            command.add_argument("--capabilities", help="Optional adapter capability manifest JSON")
            command.add_argument("--output", help="Write plan JSON to this file")
            command.add_argument("--require-buildable", action="store_true", help="Fail until every required target has a working adapter")
    ingestion = sub.add_parser("ingest")
    ingestion.add_argument("source")
    ingestion.add_argument("--source-id")
    ingestion.add_argument("--limit", type=int, default=100_000)
    ingestion.add_argument("--output", help="Write evidence JSON to this file")
    args = parser.parse_args(argv)
    try:
        if args.command == "ingest":
            result = ingest(args.source, args.source_id, args.limit)
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
    else:
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
