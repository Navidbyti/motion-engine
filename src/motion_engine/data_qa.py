"""Exact direct-copy chart data checks against CSV/XLSX source cells."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .ingest import ingest
from .revisions import RevisionError, resolve_local_file


CELL_RANGE = re.compile(r"^(?:(?:'((?:[^']|'')+)')!)?([A-Z]+)([1-9]\d*):([A-Z]+)([1-9]\d*)$")


def _issue(code: str, severity: str, message: str, target_id: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message, "targetId": target_id}


def _locations(reference: str, count: int, is_xlsx: bool) -> list[str]:
    match = CELL_RANGE.fullmatch(reference)
    if not match:
        raise ValueError("expected a one-column range such as B2:B4 or 'Sheet'!B2:B4")
    sheet, start_col, start_row, end_col, end_row = match.groups()
    start, end = int(start_row), int(end_row)
    if start_col != end_col or end < start or end - start + 1 != count:
        raise ValueError(f"source range {reference!r} does not match {count} dataset rows")
    if is_xlsx and sheet is None:
        raise ValueError("XLSX ranges need a quoted sheet name")
    if not is_xlsx and sheet is not None:
        raise ValueError("CSV ranges cannot contain a sheet name")
    prefix = f"'{sheet}'!" if sheet is not None else ""
    return [f"{prefix}{start_col}{row}" for row in range(start, end + 1)]


def _equal(source: Any, expected: Any, declared_type: str) -> bool:
    if declared_type in ("integer", "number"):
        try:
            return Decimal(str(source)) == Decimal(str(expected))
        except (InvalidOperation, TypeError):
            return False
    if declared_type == "boolean" and isinstance(source, str):
        return source.lower() in ("true", "false") and (source.lower() == "true") is expected
    return source == expected


def check_chart_data(spec: dict[str, Any], spec_dir: str | Path, severity: str) -> list[dict[str, str]]:
    sources = {item["id"]: item for item in spec["sources"]}
    datasets = {item["id"]: item for item in spec["datasets"]}
    chart_dataset_ids = {element["dataBinding"]["datasetId"]
                         for scene in spec["timeline"] for element in scene["elements"]
                         if element["kind"].startswith("chart.") and element.get("dataBinding")}
    issues = []
    if not chart_dataset_ids:
        return [_issue("chart_data_absent", "warning", "No bound chart dataset exists for exact-data QA", "chart.data_exact")]
    evidence_cache: dict[str, dict[str, dict[str, Any]]] = {}
    for dataset_id in sorted(chart_dataset_ids):
        dataset = datasets.get(dataset_id)
        if not dataset:
            issues.append(_issue("chart_dataset_missing", severity, f"Dataset {dataset_id!r} is missing", dataset_id))
            continue
        transform = dataset.get("transform", {})
        mapping = transform.get("columnSources", {})
        if set(transform) - {"columnSources"}:
            issues.append(_issue("data_transform_unverified", severity, "Only direct-copy columns can be compared automatically", dataset_id))
            continue
        for column in dataset["columns"]:
            field = column["name"]
            reference = mapping.get(field)
            if not isinstance(reference, dict) or not reference.get("sourceId") or not reference.get("location"):
                issues.append(_issue("data_mapping_missing", severity, f"Column {field!r} has no exact source-cell mapping", dataset_id))
                continue
            source_id = reference["sourceId"]
            source = sources.get(source_id)
            if not source:
                issues.append(_issue("data_source_missing", severity, f"Source {source_id!r} is missing", dataset_id))
                continue
            if source_id not in {item["sourceId"] for item in dataset["sourceRefs"]}:
                issues.append(_issue("data_source_unlinked", severity, f"Source {source_id!r} is not cited by dataset {dataset_id!r}", dataset_id))
                continue
            suffix = Path(source["uri"]).suffix.lower()
            if suffix not in (".csv", ".xlsx"):
                issues.append(_issue("data_source_unsupported", severity, "Exact cell comparison supports CSV and XLSX", dataset_id))
                continue
            try:
                locations = _locations(reference["location"], len(dataset["rows"]), suffix == ".xlsx")
                if source_id not in evidence_cache:
                    path = resolve_local_file(source, spec_dir, "source")
                    bundle = ingest(path, source_id=source_id)
                    if bundle["issues"]:
                        raise ValueError(f"source has extraction issues: {bundle['issues']}")
                    evidence_cache[source_id] = {item["location"]: item for item in bundle["evidence"]}
                evidence = evidence_cache[source_id]
            except (OSError, RevisionError, ValueError) as exc:
                issues.append(_issue("data_source_unverifiable", severity, str(exc), dataset_id))
                continue
            for row_index, location in enumerate(locations):
                record = evidence.get(location)
                if record is None:
                    issues.append(_issue("data_cell_missing", severity, f"Source cell {location} is missing", dataset_id))
                    continue
                actual = record["metadata"].get("cachedValue") if record["kind"] == "formula" else record["value"]
                if actual is None:
                    issues.append(_issue("data_cell_uncalculated", severity, f"Source cell {location} has no calculated value", dataset_id))
                elif not _equal(actual, dataset["rows"][row_index][field], column["type"]):
                    issues.append(_issue("data_value_mismatch", severity, f"Dataset {dataset_id}.{field}[{row_index}] differs from {source_id}:{location}", dataset_id))
    return issues
