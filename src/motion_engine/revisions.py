"""Canonical MotionSpec hashes and verified local input revision manifests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class RevisionError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    """Stable UTF-8 JSON for this MotionSpec version, independent of key order and whitespace."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def spec_sha256(spec: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(spec)).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verified_file(item: dict[str, Any], root: Path, kind: str) -> dict[str, Any]:
    uri = item.get("uri", "")
    relative = Path(uri)
    if not uri or relative.is_absolute() or ".." in relative.parts or ":" in uri or "\\" in uri:
        raise RevisionError(f"{kind} {item['id']}: expected a portable relative file URI")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise RevisionError(f"{kind} {item['id']}: file is missing or outside the MotionSpec directory")
    actual = file_sha256(path)
    declared = item.get("sha256")
    if declared and declared != actual:
        raise RevisionError(f"{kind} {item['id']}: SHA-256 mismatch")
    return {"id": item["id"], "uri": uri, "sha256": actual, "verified": True}


def freeze_revision(spec: dict[str, Any], spec_dir: str | Path) -> dict[str, Any]:
    """Bind the exact spec and all available local inputs without changing either."""
    root = Path(spec_dir).resolve()
    sources = sorted((_verified_file(item, root, "source") for item in spec["sources"]), key=lambda x: x["id"])
    assets = []
    for item in spec["assets"]:
        if item["status"] == "available":
            assets.append({**_verified_file(item, root, "asset"), "status": "available"})
        else:
            assets.append({"id": item["id"], "status": item["status"], "verified": False})
    assets.sort(key=lambda x: x["id"])
    payload = {
        "formatVersion": 1,
        "projectId": spec["project"]["id"],
        "schemaVersion": spec["schemaVersion"],
        "specSha256": spec_sha256(spec),
        "sources": sources,
        "assets": assets,
    }
    return {**payload, "revisionSha256": hashlib.sha256(canonical_bytes(payload)).hexdigest()}
