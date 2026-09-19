"""Small public CLI for inspecting and validating MotionSpec."""
from __future__ import annotations

import argparse
import json
import sys

from .validation import load_spec, validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="motion-engine")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "inspect"):
        command = sub.add_parser(name)
        command.add_argument("spec")
    args = parser.parse_args(argv)
    try:
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
    else:
        print(json.dumps({
            "id": spec["project"]["id"],
            "title": spec["project"]["title"],
            "locale": spec["project"]["locale"],
            "canvas": spec["canvas"],
            "scenes": len(spec["timeline"]),
            "beats": sum(len(s["beats"]) for s in spec["timeline"]),
            "deliverables": [d["target"] for d in spec["deliverables"]],
        }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
