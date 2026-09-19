"""Structured, source-bound human review for extraction and project questions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


KINDS = {"ambiguity", "missing_input", "permission", "approval"}
IMMUTABLE_FIELDS = ("id", "kind", "code", "message", "sourceId", "evidenceLocations")
ACCEPTED_DECISIONS = {"ambiguity": "clarified", "missing_input": "provided",
                      "permission": "approved", "approval": "approved"}


def _read_object(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _identity(item: dict[str, Any], source_hash: str | None) -> str:
    identity = {field: item[field] for field in IMMUTABLE_FIELDS if field != "id"}
    identity["sourceSha256"] = source_hash
    encoded = json.dumps(identity, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:20]


def make_review(evidence_paths: list[str | Path], requirements_path: str | Path | None = None) -> dict[str, Any]:
    if not evidence_paths:
        raise ValueError("at least one evidence file is required")
    sources: list[dict[str, str]] = []
    items: list[dict[str, Any]] = []
    locations: dict[str, set[str]] = {}
    source_hashes: dict[str, str] = {}
    for path in evidence_paths:
        evidence = _read_object(path)
        source = evidence.get("source")
        if not isinstance(source, dict):
            raise ValueError(f"{path} has no source record")
        source_id, sha256 = source.get("id"), source.get("sha256")
        if not isinstance(source_id, str) or not source_id or not isinstance(sha256, str) or len(sha256) != 64:
            raise ValueError(f"{path} has an invalid source ID or SHA-256")
        if source_id in source_hashes:
            raise ValueError(f"duplicate source ID {source_id!r}")
        source_hashes[source_id] = sha256
        sources.append({"id": source_id, "sha256": sha256})
        records = evidence.get("evidence", [])
        issues = evidence.get("issues", [])
        if not isinstance(records, list) or not isinstance(issues, list):
            raise ValueError(f"{path} has invalid evidence or issues")
        locations[source_id] = {record["location"] for record in records if isinstance(record, dict) and isinstance(record.get("location"), str)}
        for issue in issues:
            if not isinstance(issue, dict) or not isinstance(issue.get("code"), str) or not isinstance(issue.get("message"), str):
                raise ValueError(f"{path} has an invalid issue")
            items.append({"kind": "ambiguity", "code": issue["code"], "message": issue["message"],
                          "sourceId": source_id, "evidenceLocations": []})
    if requirements_path is not None:
        requirements = _read_object(requirements_path).get("items")
        if not isinstance(requirements, list):
            raise ValueError("review requirements must contain an items list")
        for requirement in requirements:
            if not isinstance(requirement, dict):
                raise ValueError("review requirement must be an object")
            item = {field: requirement.get(field) for field in ("kind", "code", "message", "sourceId")}
            item["evidenceLocations"] = requirement.get("evidenceLocations", [])
            if item["kind"] not in KINDS or not all(isinstance(item[field], str) and item[field].strip() for field in ("code", "message")):
                raise ValueError("review requirement needs a valid kind, code, and message")
            if item["sourceId"] is not None and item["sourceId"] not in source_hashes:
                raise ValueError(f"unknown review source {item['sourceId']!r}")
            if not isinstance(item["evidenceLocations"], list) or any(not isinstance(location, str) for location in item["evidenceLocations"]):
                raise ValueError("evidenceLocations must be a list of strings")
            if item["evidenceLocations"] and item["sourceId"] is None:
                raise ValueError("evidenceLocations require a sourceId")
            if any(location not in locations[item["sourceId"]] for location in item["evidenceLocations"]):
                raise ValueError("review requirement references an unknown evidence location")
            items.append(item)
    seen: set[str] = set()
    for item in items:
        item["id"] = _identity(item, source_hashes.get(item["sourceId"]))
        if item["id"] in seen:
            raise ValueError(f"duplicate review item {item['id']}; distinguish its code or message")
        seen.add(item["id"])
        item["status"] = "pending"
        item["resolution"] = None
    return {"schemaVersion": 1, "sources": sources, "items": items}


def verify_review(review_path: str | Path, evidence_paths: list[str | Path],
                  requirements_path: str | Path | None = None) -> dict[str, Any]:
    actual = _read_object(review_path)
    expected = make_review(evidence_paths, requirements_path)
    errors: list[str] = []
    if actual.get("schemaVersion") != 1 or actual.get("sources") != expected["sources"]:
        errors.append("review version or source hashes differ from current evidence")
    actual_items = actual.get("items")
    if not isinstance(actual_items, list) or len(actual_items) != len(expected["items"]):
        errors.append("review items differ from current evidence or requirements")
        actual_items = []
    for index, (item, required) in enumerate(zip(actual_items, expected["items"]), 1):
        if not isinstance(item, dict) or set(item) != set(required) or any(item.get(field) != required[field] for field in IMMUTABLE_FIELDS):
            errors.append(f"review item {index} has changed identity or source evidence")
            continue
        if item.get("status") != "resolved":
            errors.append(f"review item {item['id']} is pending")
            continue
        resolution = item.get("resolution")
        if not isinstance(resolution, dict) or any(not isinstance(resolution.get(field), str) or not resolution[field].strip()
                                                   for field in ("decision", "reviewer", "reason")):
            errors.append(f"review item {item['id']} needs decision, reviewer, and reason")
        elif resolution["decision"] != ACCEPTED_DECISIONS[item["kind"]]:
            errors.append(f"review item {item['id']} requires decision {ACCEPTED_DECISIONS[item['kind']]!r}")
    return {"status": "passed" if not errors else "failed", "itemCount": len(expected["items"]), "errors": errors}
