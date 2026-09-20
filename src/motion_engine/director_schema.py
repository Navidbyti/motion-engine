"""Provider-neutral contract for agent-authored whole-video plans."""

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
        "claimIds": {"type": "array", "uniqueItems": True, "items": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_.-]*$"}},
    },
    "required": ["durationFrames", "visual", "assetId", "title", "subtitle", "background", "accent", "motion"],
}

DIRECTOR_PLAN_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object", "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "locale": {"type": "string"},
        "direction": {"type": "string", "enum": ["ltr", "rtl"]},
        "researchRequired": {"type": "boolean"},
        "assetRequests": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"id": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_.-]*$"},
                           "kind": {"type": "string", "enum": ["image", "video", "3d"]},
                           "description": {"type": "string", "minLength": 1},
                           "durationFrames": {"type": "integer", "minimum": 1}},
            "required": ["id", "kind", "description", "durationFrames"],
        }},
        "scenes": {"type": "array", "items": SCENE_SCHEMA},
    },
    "required": ["title", "locale", "direction", "researchRequired", "assetRequests", "scenes"],
}
