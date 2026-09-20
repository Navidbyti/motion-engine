"""Optional OpenAI Responses planner for the portable director-plan contract."""
from __future__ import annotations

import json
import os
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ModelDirectorError(ValueError):
    pass


SCENE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "durationFrames": {"type": "integer"},
        "visual": {"type": "string", "enum": ["typography", "shape", "asset"]},
        "assetId": {"type": "string"},
        "title": {"type": "string"},
        "subtitle": {"type": "string"},
        "background": {"type": "string"},
        "accent": {"type": "string"},
        "motion": {"type": "string", "enum": ["none", "fade", "zoom"]},
    },
    "required": ["durationFrames", "visual", "assetId", "title", "subtitle", "background", "accent", "motion"],
}
DIRECTOR_PLAN_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "locale": {"type": "string"},
        "direction": {"type": "string", "enum": ["ltr", "rtl"]},
        "researchRequired": {"type": "boolean"},
        "scenes": {"type": "array", "items": SCENE_SCHEMA},
    },
    "required": ["title", "locale", "direction", "researchRequired", "scenes"],
}


def suggest_director_plan(prompt: str, *, model: str, asset_catalog: list[dict[str, Any]] | None = None,
                          transport: Callable[..., Any] | None = None) -> dict[str, Any]:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise ModelDirectorError("OPENAI_API_KEY is required for this optional planner")
    if not isinstance(model, str) or not model.strip():
        raise ModelDirectorError("provide an explicit model ID")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 50_000:
        raise ModelDirectorError("prompt must contain 1 to 50,000 characters")
    catalog = [{"id": asset.get("id"), "kind": asset.get("kind")}
               for asset in (asset_catalog or [])]
    system = (
        "You direct a complete first motion-graphics draft. Return only a director plan matching the schema. "
        "Plan every scene, in order, with 12-900 frames each and at most 30 scenes. "
        "Use typography and rectangles for abstract visuals. Use asset only when an exact listed asset ID fits; "
        "never invent an asset ID. Use zoom only on an asset scene. Colors must be #RRGGBB. "
        "Keep quoted user copy exact. If the prompt requires factual research, verifies motives, dates, "
        "causation, statistics, or a contested premise, set researchRequired=true and do not invent claims. "
        "A research-required plan is held until a separate evidence stage validates it. "
        "For non-asset scenes set assetId to an empty string. Use none, fade, or zoom motion. "
        "Write concise on-screen text that fits comfortably in the supplied canvas."
    )
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps({"prompt": prompt, "availableAssets": catalog}, ensure_ascii=False)},
        ],
        "text": {"format": {"type": "json_schema", "name": "motion_director_plan",
                            "strict": True, "schema": DIRECTOR_PLAN_SCHEMA}},
    }
    request = Request("https://api.openai.com/v1/responses",
                      data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      method="POST")
    try:
        with (transport or urlopen)(request, timeout=120) as stream:
            response = json.load(stream)
    except HTTPError as exc:
        raise ModelDirectorError(f"model planner HTTP {exc.code}; check model access and API configuration") from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise ModelDirectorError(f"model planner could not complete: {type(exc).__name__}") from exc
    if response.get("status") != "completed":
        raise ModelDirectorError(f"model planner status {response.get('status')!r}; no plan was accepted")
    outputs = [content.get("text") for item in response.get("output", []) if item.get("type") == "message"
               for content in item.get("content", []) if content.get("type") == "output_text"]
    if len(outputs) != 1 or not isinstance(outputs[0], str):
        raise ModelDirectorError("model planner returned no single structured text result")
    try:
        proposal = json.loads(outputs[0])
    except json.JSONDecodeError as exc:
        raise ModelDirectorError("model planner returned invalid JSON") from exc
    from jsonschema import Draft202012Validator
    errors = list(Draft202012Validator(DIRECTOR_PLAN_SCHEMA).iter_errors(proposal))
    if errors:
        raise ModelDirectorError("model planner returned a plan outside the director schema")
    return proposal
