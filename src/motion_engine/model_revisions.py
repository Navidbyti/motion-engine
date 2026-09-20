"""Turn a scene-level prompt into a bounded typed revision proposal."""
from __future__ import annotations

import json
import os
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator

from .revisions import spec_sha256


class ModelRevisionError(ValueError):
    pass


OPERATION_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "action": {"type": "string", "enum": ["text", "color", "zoom"]},
        "elementId": {"type": "string"},
        "text": {"type": "string"},
        "color": {"type": "string"},
        "startScale": {"type": "number"},
        "endScale": {"type": "number"},
        "easing": {"type": "string", "enum": ["linear", "ease_out", "ease_in", "ease_in_out"]},
    },
    "required": ["action", "elementId", "text", "color", "startScale", "endScale", "easing"],
}
REVISION_PROPOSAL_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "unsupportedReason": {"type": "string"},
        "operations": {"type": "array", "items": OPERATION_SCHEMA},
    },
    "required": ["unsupportedReason", "operations"],
}


def suggest_scene_revision(spec: dict[str, Any], scene_id: str, instruction: str, *,
                           model: str, transport: Callable[..., Any] | None = None) -> dict[str, Any]:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise ModelRevisionError("OPENAI_API_KEY is required for this optional planner")
    if not isinstance(model, str) or not model.strip():
        raise ModelRevisionError("provide an explicit model ID")
    if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 10_000:
        raise ModelRevisionError("revision prompt must contain 1 to 10,000 characters")
    scene = next((item for item in spec["timeline"] if item["id"] == scene_id), None)
    if scene is None:
        raise ModelRevisionError(f"unknown scene {scene_id!r}")
    elements = [{"id": e["id"], "kind": e["kind"], "startFrame": e["startFrame"],
                 "endFrameExclusive": e["endFrameExclusive"],
                 "text": e.get("text", {}).get("value"), "color": e.get("params", {}).get("color")}
                for e in scene["elements"]]
    system = (
        "Interpret a producer's prompt as edits to ONLY the supplied scene. Return one structured proposal. "
        "Allowed actions: text for a text element, color for a text/shape/chart element, zoom for an image/video element. "
        "Use exact element IDs. For text use the producer's exact requested copy when specified. "
        "For zoom choose startScale and endScale between 1 and 3; scene frame windows are assigned by the application. "
        "Unused text and color fields must be empty strings, unused scales must be 1, and unused easing must be linear. "
        "If the request needs an unavailable operation (new object, new scene, 3D change, transition, sound, factual research), "
        "set unsupportedReason to a concrete explanation and operations to an empty list. "
        "Do not invent facts, assets, or element IDs."
    )
    body = {
        "model": model,
        "input": [{"role": "system", "content": system},
                  {"role": "user", "content": json.dumps({"instruction": instruction,
                                                         "sceneId": scene_id, "elements": elements}, ensure_ascii=False)}],
        "text": {"format": {"type": "json_schema", "name": "motion_scene_revision",
                            "strict": True, "schema": REVISION_PROPOSAL_SCHEMA}},
    }
    request = Request("https://api.openai.com/v1/responses",
                      data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      method="POST")
    try:
        with (transport or urlopen)(request, timeout=120) as stream:
            response = json.load(stream)
    except HTTPError as exc:
        raise ModelRevisionError(f"model revision HTTP {exc.code}; check model access and API configuration") from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise ModelRevisionError(f"model revision could not complete: {type(exc).__name__}") from exc
    if response.get("status") != "completed":
        raise ModelRevisionError(f"model revision status {response.get('status')!r}")
    outputs = [part.get("text") for item in response.get("output", []) if item.get("type") == "message"
               for part in item.get("content", []) if part.get("type") == "output_text"]
    if len(outputs) != 1 or not isinstance(outputs[0], str):
        raise ModelRevisionError("model revision returned no single structured text result")
    try:
        proposal = json.loads(outputs[0])
    except json.JSONDecodeError as exc:
        raise ModelRevisionError("model revision returned invalid JSON") from exc
    if list(Draft202012Validator(REVISION_PROPOSAL_SCHEMA).iter_errors(proposal)):
        raise ModelRevisionError("model revision is outside the revision schema")
    if proposal["unsupportedReason"].strip():
        raise ModelRevisionError("unsupported requested edit: " + proposal["unsupportedReason"])
    if not 1 <= len(proposal["operations"]) <= 20:
        raise ModelRevisionError("model revision needs 1 to 20 supported operations")
    by_id = {e["id"]: e for e in scene["elements"]}
    operations = []
    for edit in proposal["operations"]:
        element = by_id.get(edit["elementId"])
        if element is None:
            raise ModelRevisionError(f"model revision named unknown element {edit['elementId']!r}")
        if edit["action"] == "text":
            if element["kind"] != "text" or not edit["text"].strip():
                raise ModelRevisionError("text edit needs a text element and replacement copy")
            operations.append({"op": "set_text", "elementId": element["id"], "value": edit["text"]})
        elif edit["action"] == "color":
            if element["kind"] not in ("text", "shape", "chart.bar", "chart.line"):
                raise ModelRevisionError("color edit targets an unsupported element")
            operations.append({"op": "set_color", "elementId": element["id"], "value": edit["color"]})
        else:
            if element["kind"] not in ("image", "video"):
                raise ModelRevisionError("zoom edit needs an image or video element")
            operations.append({"op": "set_visual_zoom", "elementId": element["id"], "value": [
                {"frame": element["startFrame"], "value": edit["startScale"]},
                {"frame": element["endFrameExclusive"] - 1, "value": edit["endScale"],
                 "easing": edit["easing"]}]})
    return {"baseSpecSha256": spec_sha256(spec), "sceneId": scene_id,
            "userPrompt": instruction, "operations": operations}
