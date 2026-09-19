"""MotionSpec structure and cross-reference validation.

JSON Schema handles shape and local types. These checks handle relationships
across scenes, frames, data tables, and assets that JSON Schema cannot express
concisely. Source text is always data, never an instruction to this program.
"""
from __future__ import annotations

import json
import math
import re
from datetime import date
from importlib import resources
from pathlib import Path
from typing import Any


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value is not allowed: {value}")


def load_spec(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as stream:
        value = json.load(stream, parse_constant=_reject_constant)
    if not isinstance(value, dict):
        raise ValueError("MotionSpec root must be an object")
    return value


def load_schema() -> dict[str, Any]:
    with resources.files("motion_engine").joinpath("MotionSpec.schema.json").open(
        "r", encoding="utf-8"
    ) as stream:
        return json.load(stream)


def validate_schema(spec: dict[str, Any]) -> list[str]:
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise RuntimeError(
            'Install dependencies with: python -m pip install -e ".[dev]"'
        ) from exc
    validator = Draft202012Validator(load_schema())
    return [f"{'.'.join(map(str, error.absolute_path)) or '$'}: {error.message}"
            for error in sorted(validator.iter_errors(spec), key=lambda e: list(map(str, e.absolute_path)))]


def _matches_column_type(value: Any, declared: str) -> bool:
    if declared == "string":
        return isinstance(value, str)
    if declared == "boolean":
        return isinstance(value, bool)
    if declared == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if declared == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        try:
            return math.isfinite(value)
        except OverflowError:
            return False
    if declared == "date":
        if not isinstance(value, str):
            return False
        try:
            date.fromisoformat(value)
            return True
        except ValueError:
            return False
    if declared == "timecode":
        return isinstance(value, str) and re.fullmatch(r"\d{2,}:[0-5]\d:[0-5]\d:\d{2,}", value) is not None
    return False


def validate_semantics(spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    seen: dict[str, str] = {}

    def register(identifier: str, where: str) -> None:
        if identifier in seen:
            errors.append(f"duplicate id {identifier!r}: {seen[identifier]} and {where}")
        seen[identifier] = where

    for collection in ("sources", "assets", "datasets", "deliverables"):
        for index, item in enumerate(spec.get(collection, [])):
            register(item["id"], f"{collection}[{index}]")
    for index, item in enumerate(spec.get("policies", {}).get("disclosures", [])):
        register(item["id"], f"disclosures[{index}]")
    for index, scene in enumerate(spec.get("timeline", [])):
        register(scene["id"], f"timeline[{index}]")
        for child in ("elements", "beats"):
            for child_index, item in enumerate(scene.get(child, [])):
                register(item["id"], f"timeline[{index}].{child}[{child_index}]")

    sources = {x["id"] for x in spec.get("sources", [])}
    assets = {x["id"] for x in spec.get("assets", [])}
    datasets = {x["id"]: x for x in spec.get("datasets", [])}
    duration = spec.get("canvas", {}).get("durationFrames", 0)

    def check_refs(obj: Any, where: str) -> None:
        if isinstance(obj, dict):
            for ref_key in ("sourceRefs",):
                for ref in obj.get(ref_key, []):
                    if ref.get("sourceId") not in sources:
                        errors.append(f"{where}: unknown source {ref.get('sourceId')!r}")
            for key, value in obj.items():
                if key != "sourceRefs":
                    check_refs(value, f"{where}.{key}")
        elif isinstance(obj, list):
            for index, value in enumerate(obj):
                check_refs(value, f"{where}[{index}]")

    check_refs(spec, "$")
    for dataset in datasets.values():
        fields = [c["name"] for c in dataset["columns"]]
        columns = {c["name"]: c for c in dataset["columns"]}
        if len(fields) != len(set(fields)):
            errors.append(f"dataset {dataset['id']}: duplicate column name")
        for index, row in enumerate(dataset["rows"]):
            extra = set(row) - set(fields)
            missing = set(fields) - set(row)
            if extra or missing:
                errors.append(f"dataset {dataset['id']} row {index}: extra {sorted(extra)}, missing {sorted(missing)}")
            for field, value in row.items():
                column = columns.get(field)
                if column and not _matches_column_type(value, column["type"]):
                    errors.append(f"dataset {dataset['id']} row {index} field {field}: expected {column['type']}, got {value!r}")

    timeline = spec.get("timeline", [])
    cursor = 0
    for scene in timeline:
        start, end = scene["startFrame"], scene["endFrameExclusive"]
        if start != cursor or end <= start or end > duration:
            errors.append(f"scene {scene['id']}: invalid or non-contiguous range [{start}, {end}) after {cursor}")
        cursor = end
        elements = {x["id"]: x for x in scene["elements"]}
        for element in scene["elements"]:
            e_start, e_end = element["startFrame"], element["endFrameExclusive"]
            if not (start <= e_start < e_end <= end):
                errors.append(f"element {element['id']}: outside scene range")
            if element.get("assetId") and element["assetId"] not in assets:
                errors.append(f"element {element['id']}: unknown asset {element['assetId']}")
            binding = element.get("dataBinding")
            if binding:
                dataset = datasets.get(binding["datasetId"])
                if dataset is None:
                    errors.append(f"element {element['id']}: unknown dataset {binding['datasetId']}")
                else:
                    column = next((c for c in dataset["columns"] if c["name"] == binding["field"]), None)
                    if column is None:
                        errors.append(f"element {element['id']}: unknown field {binding['field']}")
                    elif element["kind"] in ("chart.bar", "chart.line"):
                        if column["type"] not in ("integer", "number"):
                            errors.append(f"element {element['id']}: chart field {binding['field']} must be numeric")
                        if not dataset["rows"]:
                            errors.append(f"element {element['id']}: chart dataset {dataset['id']} is empty")
                        values = [row.get(binding["field"]) for row in dataset["rows"]]
                        if values and all(_matches_column_type(value, "number") for value in values):
                            params = element["params"]
                            minimum = params.get("minimum", min(0, *values))
                            maximum = params.get("maximum", max(values))
                            if not _matches_column_type(minimum, "number") or not _matches_column_type(maximum, "number") or maximum <= minimum:
                                errors.append(f"element {element['id']}: chart maximum must exceed minimum and both must be finite numbers")
                            elif any(value < minimum or value > maximum for value in values):
                                errors.append(f"element {element['id']}: chart range clips source values")
        beat_cursor = start
        for beat in scene["beats"]:
            b_start, b_end = beat["startFrame"], beat["endFrameExclusive"]
            if b_start != beat_cursor or b_end <= b_start or b_end > end:
                errors.append(f"beat {beat['id']}: invalid or non-contiguous range")
            beat_cursor = b_end
            for element_id in beat.get("elementIds", []):
                if element_id not in elements:
                    errors.append(f"beat {beat['id']}: unknown element {element_id}")
        if scene["beats"] and beat_cursor != end:
            errors.append(f"scene {scene['id']}: beats do not reach scene end")
        for animation in scene["animations"]:
            element = elements.get(animation["targetId"])
            if element is None:
                errors.append(f"scene {scene['id']}: unknown animation target {animation['targetId']}")
                continue
            frames = [k["frame"] for k in animation["keyframes"]]
            if frames != sorted(set(frames)) or any(
                f < element["startFrame"] or f >= element["endFrameExclusive"] for f in frames
            ):
                errors.append(f"animation {animation['targetId']}.{animation['property']}: invalid keyframes")
    if cursor != duration:
        errors.append(f"timeline ends at frame {cursor}, expected {duration}")
    for disclosure in spec.get("policies", {}).get("disclosures", []):
        if not (0 <= disclosure["startFrame"] < disclosure["endFrameExclusive"] <= duration):
            errors.append(f"disclosure {disclosure['id']}: outside canvas duration")
    return errors


def validate(spec: dict[str, Any]) -> list[str]:
    shape_errors = validate_schema(spec)
    if shape_errors:
        return shape_errors
    return validate_semantics(spec)
