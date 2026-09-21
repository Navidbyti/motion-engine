"""Compile an agent-authored whole-video plan into a validated MotionSpec.

The plan is a proposal, not a source of truth. The compiler checks capabilities
and refuses ungrounded factual plans or assets that do not exist.
"""
from __future__ import annotations

import json
import math
import re
import wave
from pathlib import Path
from typing import Any

from .planning import plan
from .claims import verify_claims
from .revisions import file_sha256, resolve_local_file
from .validation import validate


class DirectorError(ValueError):
    pass


def _card_text_color(hex_color: str) -> str:
    channels = [int(hex_color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
              for value in channels]
    luminance = sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    return "#000000" if (luminance + 0.05) / 0.05 >= 1.05 / (luminance + 0.05) else "#FFFFFF"


def compile_director_plan(prompt_path: str | Path, output_path: str | Path,
                          proposal: dict[str, Any], *, project_id: str,
                          width: int = 1080, height: int = 1920, fps: int = 30,
                          assets: list[dict[str, Any]] | None = None,
                          proposal_path: str | Path | None = None,
                          claim_ledger_path: str | Path | None = None,
                          data_fragments: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    prompt = Path(prompt_path).resolve()
    output = Path(output_path).resolve()
    try:
        prompt_uri = prompt.relative_to(output.parent).as_posix()
    except ValueError as exc:
        raise DirectorError("prompt must be inside the MotionSpec directory") from exc
    if not prompt.is_file() or prompt.suffix.lower() != ".txt":
        raise DirectorError("prompt must be an existing UTF-8 .txt file")
    try:
        prompt_text = prompt.read_text(encoding="utf-8-sig")
    except UnicodeError as exc:
        raise DirectorError("prompt must be valid UTF-8") from exc
    if not prompt_text.strip() or len(prompt_text) > 50_000:
        raise DirectorError("prompt must contain 1 to 50,000 characters")
    plan_source = None
    plan_ref = None
    if proposal_path is not None:
        plan_file = Path(proposal_path).resolve()
        try:
            plan_uri = plan_file.relative_to(output.parent).as_posix()
        except ValueError as exc:
            raise DirectorError("director plan file must be inside the MotionSpec directory") from exc
        if not plan_file.is_file() or json.loads(plan_file.read_text(encoding="utf-8")) != proposal:
            raise DirectorError("director plan does not match its source file")
        plan_source = {"id": "director_plan", "uri": plan_uri, "mediaType": "application/json",
                       "sha256": file_sha256(plan_file), "authority": ["direction"]}
        plan_ref = {"sourceId": "director_plan", "location": f"/scenes", "method": "desktop agent proposal", "confidence": 0.7}
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", project_id):
        raise DirectorError("invalid project ID")
    if width < 180 or height < 180 or fps not in (24, 25, 30, 50, 60):
        raise DirectorError("unsupported canvas or frame rate")
    required = {"title", "locale", "direction", "researchRequired", "assetRequests", "scenes"}
    if not isinstance(proposal, dict) or not required <= set(proposal) or set(proposal) - required - {"fontFamily", "pacing", "soundtrack"}:
        raise DirectorError("director plan needs title, locale, direction, researchRequired, assetRequests, scenes, and supported optional fields only")
    font_family = proposal.get("fontFamily", "DejaVu Sans")
    if not isinstance(font_family, str) or not font_family.strip() or len(font_family) > 128:
        raise DirectorError("director fontFamily must be a nonempty font family name")
    claim_source = None
    research_sources = []
    claim_locations = {}
    if proposal["researchRequired"] is True:
        if claim_ledger_path is None:
            raise DirectorError("research-required plan needs a claim ledger")
        ledger_file = Path(claim_ledger_path).resolve()
        try:
            ledger_uri = ledger_file.relative_to(output.parent).as_posix()
        except ValueError as exc:
            raise DirectorError("claim ledger must be inside the MotionSpec directory") from exc
        report = verify_claims(ledger_file)
        if report["status"] != "source_linked":
            raise DirectorError("claim ledger source links failed: " + "; ".join(issue["message"] for issue in report["issues"]))
        ledger = json.loads(ledger_file.read_text(encoding="utf-8"))
        claim_locations = {claim["id"]: f"/claims/{index}" for index, claim in enumerate(ledger["claims"])}
        claim_source = {"id": "claim_ledger", "uri": ledger_uri, "mediaType": "application/json",
                        "sha256": file_sha256(ledger_file), "authority": ["agent research ledger"]}
        for source in ledger["sources"]:
            source_file = (ledger_file.parent / source["uri"]).resolve()
            source_uri = source_file.relative_to(output.parent).as_posix()
            research_sources.append({"id": "claim_source_" + source["id"], "uri": source_uri,
                                     "mediaType": "text/plain", "sha256": source["sha256"],
                                     "authority": [source["publisher"]]})
    elif proposal["researchRequired"] is not False or claim_ledger_path is not None:
        raise DirectorError("claim ledger is only accepted for a research-required plan")
    if not isinstance(proposal["assetRequests"], list):
        raise DirectorError("assetRequests must be a list")
    if proposal["assetRequests"]:
        requests = [str(item.get("description", item)) for item in proposal["assetRequests"]]
        raise DirectorError("first draft needs unresolved assets: " + "; ".join(requests))
    if (not isinstance(proposal["title"], str) or not proposal["title"].strip()
        or not isinstance(proposal["locale"], str) or len(proposal["locale"]) < 2
        or proposal["direction"] not in ("ltr", "rtl")
        or not isinstance(proposal["scenes"], list) or not 1 <= len(proposal["scenes"]) <= 30):
        raise DirectorError("director plan metadata or scenes are invalid")
    pacing = proposal.get("pacing")
    if pacing is not None:
        if (not isinstance(pacing, dict)
                or set(pacing) != {"profile", "targetDurationFrames", "toleranceFrames"}
                or pacing["profile"] not in ("shot", "reel", "explainer")
                or not isinstance(pacing["targetDurationFrames"], int)
                or isinstance(pacing["targetDurationFrames"], bool)
                or not 12 <= pacing["targetDurationFrames"] <= 10_000
                or not isinstance(pacing["toleranceFrames"], int)
                or isinstance(pacing["toleranceFrames"], bool)
                or not 0 <= pacing["toleranceFrames"] <= 900):
            raise DirectorError("director pacing contract is invalid")
        durations = [scene.get("durationFrames") for scene in proposal["scenes"] if isinstance(scene, dict)]
        if len(durations) != len(proposal["scenes"]) or any(not isinstance(value, int) or isinstance(value, bool) for value in durations):
            raise DirectorError("director pacing needs integer scene durations")
        total = sum(durations)
        if abs(total - pacing["targetDurationFrames"]) > pacing["toleranceFrames"]:
            raise DirectorError("director plan duration misses its pacing target")
        profile = pacing["profile"]
        if profile == "shot" and len(durations) != 1:
            raise DirectorError("shot pacing requires exactly one scene")
    asset_list = assets or []
    if not isinstance(asset_list, list) or any(not isinstance(asset, dict) or not isinstance(asset.get("id"), str)
                                              for asset in asset_list):
        raise DirectorError("asset catalog must be a list of asset records with IDs")
    asset_ids = {asset["id"]: asset for asset in asset_list}
    if len(asset_ids) != len(asset_list):
        raise DirectorError("duplicate asset ID")
    for asset in asset_list:
        if (asset.get("kind") not in ("image", "video.frames", "audio") or asset.get("status") != "available"
            or asset.get("approved") is not True or not isinstance(asset.get("license"), str)
            or not asset["license"].strip() or not asset.get("sha256")):
            raise DirectorError("director assets must be approved, licensed, available hashed supported media")
        try:
            path = resolve_local_file(asset, output.parent, "asset")
        except ValueError as exc:
            raise DirectorError(str(exc)) from exc
        if file_sha256(path) != asset["sha256"]:
            raise DirectorError(f"asset {asset['id']} SHA-256 mismatch")
    soundtrack = proposal.get("soundtrack")
    if soundtrack is not None:
        if (not isinstance(soundtrack, dict)
                or set(soundtrack) != {"assetId", "gainDb", "fadeInFrames", "fadeOutFrames",
                                      "duckUnderNarrationDb"}
                or not isinstance(soundtrack["gainDb"], (int, float))
                or isinstance(soundtrack["gainDb"], bool) or not math.isfinite(soundtrack["gainDb"])
                or not -60 <= soundtrack["gainDb"] <= 0
                or not isinstance(soundtrack["duckUnderNarrationDb"], (int, float))
                or isinstance(soundtrack["duckUnderNarrationDb"], bool)
                or not math.isfinite(soundtrack["duckUnderNarrationDb"])
                or not -60 <= soundtrack["duckUnderNarrationDb"] <= 0
                or not isinstance(soundtrack["fadeInFrames"], int)
                or isinstance(soundtrack["fadeInFrames"], bool) or soundtrack["fadeInFrames"] < 0
                or not isinstance(soundtrack["fadeOutFrames"], int)
                or isinstance(soundtrack["fadeOutFrames"], bool) or soundtrack["fadeOutFrames"] < 0):
            raise DirectorError("director soundtrack contract is invalid")
        durations = [scene.get("durationFrames") for scene in proposal["scenes"] if isinstance(scene, dict)]
        if (len(durations) != len(proposal["scenes"])
                or any(not isinstance(value, int) or isinstance(value, bool) or value < 1 for value in durations)):
            raise DirectorError("director soundtrack needs valid scene durations")
        if soundtrack["fadeInFrames"] > durations[0] or soundtrack["fadeOutFrames"] > durations[-1]:
            raise DirectorError("director soundtrack fades must fit the first and last scenes")
        music_asset = asset_ids.get(soundtrack["assetId"])
        if music_asset is None or music_asset.get("kind") != "audio":
            raise DirectorError(f"director soundtrack requests unavailable audio asset {soundtrack['assetId']!r}")
        try:
            with wave.open(str(resolve_local_file(music_asset, output.parent, "asset")), "rb") as audio:
                needed = round(sum(durations) * 48_000 / fps)
                if (audio.getcomptype() != "NONE" or audio.getnchannels() != 1
                        or audio.getsampwidth() != 2 or audio.getframerate() != 48_000
                        or audio.getnframes() < needed):
                    raise DirectorError("director soundtrack needs a project-length mono 16-bit PCM WAV at 48 kHz")
        except (OSError, EOFError, wave.Error) as exc:
            raise DirectorError("director soundtrack audio cannot be decoded") from exc
    data_sources: dict[str, dict[str, Any]] = {}
    datasets: dict[str, dict[str, Any]] = {}
    reserved_source_ids = {"user_prompt", "director_plan", "claim_ledger", *(item["id"] for item in research_sources)}
    for fragment_index, fragment in enumerate(data_fragments or []):
        if (not isinstance(fragment, dict) or set(fragment) != {"source", "dataset", "headerMapping"}
                or not isinstance(fragment["source"], dict) or not isinstance(fragment["dataset"], dict)):
            raise DirectorError(f"data fragment {fragment_index} is not an import-data result")
        source, dataset = fragment["source"], fragment["dataset"]
        source_id, dataset_id = source.get("id"), dataset.get("id")
        if (not isinstance(source_id, str) or not isinstance(dataset_id, str)
                or source_id in reserved_source_ids or dataset_id in datasets):
            raise DirectorError(f"data fragment {fragment_index} has a missing, reserved, or duplicate ID")
        existing = data_sources.get(source_id)
        if existing is not None and existing != source:
            raise DirectorError(f"data source {source_id!r} has conflicting records")
        try:
            source_file = resolve_local_file(source, output.parent, "data source")
        except ValueError as exc:
            raise DirectorError(str(exc)) from exc
        if not source.get("sha256") or file_sha256(source_file) != source["sha256"]:
            raise DirectorError(f"data source {source_id!r} SHA-256 mismatch")
        data_sources[source_id] = source
        datasets[dataset_id] = dataset
    inset = max(24, round(min(width, height) * 0.07))
    ref = {"sourceId": "user_prompt", "location": "entire prompt", "method": "desktop agent adaptation", "confidence": 0.7}
    timeline = []
    cursor = 0
    scene_keys = {"durationFrames", "visual", "assetId", "title", "subtitle", "background", "accent", "motion"}
    for index, scene in enumerate(proposal["scenes"], 1):
        if not isinstance(scene, dict) or not scene_keys <= set(scene) or set(scene) - scene_keys - {"claimIds", "voice", "audioAssetId", "transition", "transitionFrames", "counterValue", "counterStartValue", "counterDecimals", "counterPrefix", "counterSuffix", "chartDatasetId", "chartValueField", "chartCategoryField", "chartMinimum", "chartMaximum", "chartUnit", "chartDecimals", "chartTickCount", "purpose", "energy", "timing", "soundEffects", "backgroundSecondary", "backgroundGradient"}:
            raise DirectorError(f"scene {index} has missing or unknown plan fields")
        purpose, energy = scene.get("purpose"), scene.get("energy")
        if (("purpose" in scene) != ("energy" in scene)
                or ("purpose" in scene and (not isinstance(purpose, str) or not purpose.strip()
                                             or len(purpose) > 240
                                             or not isinstance(energy, int) or isinstance(energy, bool)
                                             or not 1 <= energy <= 5))
                or (pacing is not None and "purpose" not in scene)):
            raise DirectorError(f"scene {index} needs a purpose and energy from 1 to 5 for paced production")
        scene_claim_ids = scene.get("claimIds", [])
        if not isinstance(scene_claim_ids, list) or any(not isinstance(item, str) for item in scene_claim_ids) or len(scene_claim_ids) != len(set(scene_claim_ids)):
            raise DirectorError(f"scene {index} claimIds must be a list of unique IDs")
        if proposal["researchRequired"] and not scene_claim_ids:
            raise DirectorError(f"scene {index} needs at least one cited claim")
        if any(item not in claim_locations for item in scene_claim_ids):
            raise DirectorError(f"scene {index} references an unknown claim ID")
        claim_refs = [{"sourceId": "claim_ledger", "location": claim_locations[item],
                       "method": "agent claim mapping", "confidence": 0.5} for item in scene_claim_ids]
        duration = scene["durationFrames"]
        if not isinstance(duration, int) or isinstance(duration, bool) or not 12 <= duration <= 900:
            raise DirectorError(f"scene {index} duration must be 12 to 900 frames")
        timing = scene.get("timing")
        if pacing is not None and timing is None:
            raise DirectorError(f"scene {index} needs editorial entry, hold, and exit timing")
        if timing is not None:
            if (not isinstance(timing, dict)
                    or set(timing) != {"entryFrames", "holdFrames", "exitFrames"}
                    or not isinstance(timing["entryFrames"], int) or isinstance(timing["entryFrames"], bool)
                    or not isinstance(timing["holdFrames"], int) or isinstance(timing["holdFrames"], bool)
                    or not isinstance(timing["exitFrames"], int) or isinstance(timing["exitFrames"], bool)
                    or timing["entryFrames"] < 4 or timing["holdFrames"] < 1
                    or timing["exitFrames"] < 0 or timing["exitFrames"] == 1
                    or sum(timing.values()) != duration):
                raise DirectorError(f"scene {index} editorial timing must exactly fill its duration")
            entry_frames, exit_frames = timing["entryFrames"], timing["exitFrames"]
        else:
            entry_frames, exit_frames = min(12, duration - 1), 0
        if not isinstance(scene["title"], str) or not isinstance(scene["subtitle"], str):
            raise DirectorError(f"scene {index} text must be strings")
        if not scene["title"].strip() and not scene["subtitle"].strip() and scene["visual"] != "counter":
            raise DirectorError(f"scene {index} needs visible text")
        if any(len(scene[field]) > 500 for field in ("title", "subtitle")):
            raise DirectorError(f"scene {index} text is too long for this draft primitive")
        if any(not isinstance(scene[field], str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", scene[field])
               for field in ("background", "accent")):
            raise DirectorError(f"scene {index} colors must be #RRGGBB")
        background_secondary = scene.get("backgroundSecondary")
        background_gradient = scene.get("backgroundGradient")
        if ("backgroundSecondary" in scene) != ("backgroundGradient" in scene):
            raise DirectorError(f"scene {index} backgroundSecondary and backgroundGradient must be supplied together")
        if "backgroundSecondary" in scene and (not isinstance(background_secondary, str)
                                                or not re.fullmatch(r"#[0-9A-Fa-f]{6}", background_secondary)
                                                or background_gradient not in ("vertical", "horizontal")):
            raise DirectorError(f"scene {index} background gradient is invalid")
        visual, asset_id, motion = scene["visual"], scene["assetId"], scene["motion"]
        voice, audio_asset_id = scene.get("voice", ""), scene.get("audioAssetId", "")
        transition = scene.get("transition", "cut")
        transition_frames = scene.get("transitionFrames")
        if transition not in ("cut", "fade"):
            raise DirectorError(f"scene {index} transition is unsupported")
        if index == 1 and (transition != "cut" or transition_frames is not None):
            raise DirectorError("first director scene cannot declare an incoming transition")
        if transition == "cut" and transition_frames is not None:
            raise DirectorError(f"scene {index} cut cannot declare transitionFrames")
        if transition == "fade" and (not isinstance(transition_frames, int) or isinstance(transition_frames, bool)
                                      or not 2 <= transition_frames <= 120):
            raise DirectorError(f"scene {index} fade needs 2 to 120 transitionFrames")
        if not isinstance(voice, str) or not isinstance(audio_asset_id, str) or bool(voice.strip()) != bool(audio_asset_id):
            raise DirectorError(f"scene {index} voice and audioAssetId must be supplied together")
        if len(voice) > 5000:
            raise DirectorError(f"scene {index} voice is too long")
        if audio_asset_id:
            audio_asset = asset_ids.get(audio_asset_id)
            if audio_asset is None or audio_asset.get("kind") != "audio":
                raise DirectorError(f"scene {index} requests unavailable audio asset {audio_asset_id!r}")
            path = resolve_local_file(audio_asset, output.parent, "asset")
            try:
                with wave.open(str(path), "rb") as audio:
                    rate = audio.getframerate()
                    needed = round(duration * rate / fps)
                    if (path.suffix.lower() != ".wav" or audio.getcomptype() != "NONE"
                            or audio.getnchannels() != 1 or audio.getsampwidth() != 2
                            or rate != 48_000 or audio.getnframes() < needed):
                        raise DirectorError(f"scene {index} narration needs a scene-length mono 16-bit PCM WAV at 48 kHz")
            except (OSError, EOFError, wave.Error) as exc:
                raise DirectorError(f"scene {index} narration audio cannot be decoded") from exc
        sound_effects = scene.get("soundEffects", [])
        if not isinstance(sound_effects, list) or len(sound_effects) > 8:
            raise DirectorError(f"scene {index} soundEffects must be a list of at most eight cues")
        for cue_index, cue in enumerate(sound_effects, 1):
            if (not isinstance(cue, dict)
                    or set(cue) != {"assetId", "startFrameOffset", "durationFrames", "gainDb"}
                    or not isinstance(cue["assetId"], str)
                    or not isinstance(cue["startFrameOffset"], int) or isinstance(cue["startFrameOffset"], bool)
                    or not isinstance(cue["durationFrames"], int) or isinstance(cue["durationFrames"], bool)
                    or cue["startFrameOffset"] < 0 or cue["durationFrames"] < 1
                    or cue["startFrameOffset"] + cue["durationFrames"] > duration
                    or not isinstance(cue["gainDb"], (int, float)) or isinstance(cue["gainDb"], bool)
                    or not math.isfinite(cue["gainDb"]) or not -60 <= cue["gainDb"] <= 12):
                raise DirectorError(f"scene {index} sound effect {cue_index} is invalid or outside the scene")
            effect_asset = asset_ids.get(cue["assetId"])
            if effect_asset is None or effect_asset.get("kind") != "audio":
                raise DirectorError(f"scene {index} requests unavailable sound effect {cue['assetId']!r}")
            effect_path = resolve_local_file(effect_asset, output.parent, "asset")
            try:
                with wave.open(str(effect_path), "rb") as effect:
                    needed = cue["durationFrames"] * 48_000 // fps
                    if (effect_path.suffix.lower() != ".wav" or effect.getcomptype() != "NONE"
                            or effect.getnchannels() != 1 or effect.getsampwidth() != 2
                            or effect.getframerate() != 48_000 or effect.getnframes() < needed):
                        raise DirectorError(f"scene {index} sound effect {cue_index} needs enough mono 16-bit PCM WAV at 48 kHz")
            except (OSError, EOFError, wave.Error) as exc:
                raise DirectorError(f"scene {index} sound effect {cue_index} cannot be decoded") from exc
        if not isinstance(asset_id, str):
            raise DirectorError(f"scene {index} asset ID must be a string")
        if visual not in ("typography", "shape", "card", "asset", "counter", "bar_chart", "line_chart") or motion not in ("none", "fade", "zoom", "slide", "rise", "whip_left", "whip_right"):
            raise DirectorError(f"scene {index} visual or motion is unsupported")
        if visual == "asset" and asset_id not in asset_ids:
            raise DirectorError(f"scene {index} requests unavailable asset {asset_id!r}; generate or import it first")
        if visual != "asset" and asset_id != "":
            raise DirectorError(f"scene {index} has an asset ID without an asset visual")
        if motion == "zoom" and visual != "asset":
            raise DirectorError(f"scene {index} zoom needs an image or moving plate")
        counter_value = scene.get("counterValue")
        if visual == "counter":
            start_value = scene.get("counterStartValue", 0)
            decimals = scene.get("counterDecimals", 0)
            prefix, suffix = scene.get("counterPrefix", ""), scene.get("counterSuffix", "")
            if (not isinstance(counter_value, (int, float)) or isinstance(counter_value, bool) or not math.isfinite(counter_value)
                    or not isinstance(start_value, (int, float)) or isinstance(start_value, bool) or not math.isfinite(start_value)
                    or not isinstance(decimals, int) or isinstance(decimals, bool) or not 0 <= decimals <= 6
                    or not isinstance(prefix, str) or not isinstance(suffix, str)
                    or len(prefix) > 32 or len(suffix) > 32):
                raise DirectorError(f"scene {index} counter values or formatting are invalid")
        elif any(field in scene for field in ("counterValue", "counterStartValue", "counterDecimals", "counterPrefix", "counterSuffix")):
            raise DirectorError(f"scene {index} counter fields require a counter visual")
        chart_fields = ("chartDatasetId", "chartValueField", "chartCategoryField", "chartMinimum", "chartMaximum", "chartUnit", "chartDecimals", "chartTickCount")
        chart_dataset = None
        chart_refs: list[dict[str, Any]] = []
        if visual in ("bar_chart", "line_chart"):
            dataset_id, value_field = scene.get("chartDatasetId"), scene.get("chartValueField")
            category_field = scene.get("chartCategoryField")
            chart_dataset = datasets.get(dataset_id)
            if chart_dataset is None:
                raise DirectorError(f"scene {index} requests unavailable dataset {dataset_id!r}")
            columns = {column["name"]: column for column in chart_dataset.get("columns", [])}
            if value_field not in columns or columns[value_field].get("type") not in ("integer", "number"):
                raise DirectorError(f"scene {index} chart value field must be numeric")
            if category_field not in columns:
                raise DirectorError(f"scene {index} chart category field is unavailable")
            values = [row.get(value_field) for row in chart_dataset.get("rows", [])]
            if not values or any(not isinstance(value, (int, float)) or isinstance(value, bool)
                                 or not math.isfinite(value) for value in values):
                raise DirectorError(f"scene {index} chart needs finite numeric rows")
            chart_minimum = scene.get("chartMinimum", min(0, *values))
            chart_maximum = scene.get("chartMaximum", max(values))
            if (not isinstance(chart_minimum, (int, float)) or isinstance(chart_minimum, bool)
                    or not isinstance(chart_maximum, (int, float)) or isinstance(chart_maximum, bool)
                    or not math.isfinite(chart_minimum) or not math.isfinite(chart_maximum)
                    or chart_maximum <= chart_minimum
                    or any(value < chart_minimum or value > chart_maximum for value in values)):
                raise DirectorError(f"scene {index} chart range is invalid or clips values")
            chart_unit = scene.get("chartUnit", columns[value_field].get("unit", ""))
            chart_decimals = scene.get("chartDecimals", 0)
            chart_tick_count = scene.get("chartTickCount", 5)
            if (not isinstance(chart_unit, str) or len(chart_unit) > 32
                    or not isinstance(chart_decimals, int) or isinstance(chart_decimals, bool)
                    or not 0 <= chart_decimals <= 6
                    or not isinstance(chart_tick_count, int) or isinstance(chart_tick_count, bool)
                    or not 2 <= chart_tick_count <= 10):
                raise DirectorError(f"scene {index} chart formatting is invalid")
            chart_refs = chart_dataset.get("sourceRefs", [])
        elif any(field in scene for field in chart_fields):
            raise DirectorError(f"scene {index} chart fields require a chart visual")
        start, end = cursor, cursor + duration
        scene_id = f"scene_{index}"
        background_params = {"shape": "rect", "color": scene["background"]}
        if background_secondary:
            background_params.update({"gradientEnd": background_secondary,
                                      "gradientDirection": background_gradient})
        elements = [{"id": f"background_{index}", "kind": "shape", "startFrame": start,
                     "endFrameExclusive": end,
                     "bounds": {"x": 0, "y": 0, "width": width, "height": height},
                     "params": background_params, "zIndex": -1}]
        animations = []
        if visual == "asset":
            asset = asset_ids[asset_id]
            element_id = f"visual_{index}"
            elements.append({"id": element_id, "kind": "image" if asset["kind"] == "image" else "video",
                             "startFrame": start, "endFrameExclusive": end,
                             "bounds": {"x": 0, "y": 0, "width": width, "height": height},
                             "assetId": asset_id, "params": {"fit": "cover"}, "zIndex": 0,
                             "sourceRefs": asset.get("sourceRefs", [])})
            if motion == "zoom":
                animations.append({"targetId": element_id, "property": "scale", "keyframes": [
                    {"frame": start, "value": 1}, {"frame": end - 1, "value": 1.15, "easing": "ease_in_out"}]})
            if motion in ("whip_left", "whip_right"):
                direction = -1 if motion == "whip_left" else 1
                overshoot = -direction * round(width * 0.06)
                animations.append({"targetId": element_id, "property": "x", "keyframes": [
                    {"frame": start, "value": direction * width},
                    {"frame": start + max(2, round(entry_frames * 0.65)),
                     "value": overshoot, "easing": "ease_out"},
                    {"frame": start + entry_frames, "value": 0, "easing": "ease_in_out"}]})
            elements.append({"id": f"lower_third_{index}", "kind": "shape", "startFrame": start,
                             "endFrameExclusive": end,
                             "bounds": {"x": 0, "y": round(height * 0.62),
                                        "width": width, "height": height - round(height * 0.62)},
                             "params": {"shape": "rect", "color": scene["background"]}, "zIndex": 1})
        if visual == "shape":
            elements.append({"id": f"accent_{index}", "kind": "shape", "startFrame": start,
                             "endFrameExclusive": end,
                             "bounds": {"x": inset, "y": round(height * 0.59),
                                        "width": width - 2 * inset, "height": max(12, round(height * 0.06))},
                             "params": {"shape": "rect", "color": scene["accent"]}, "zIndex": 0})
        if visual == "card":
            elements.append({"id": f"card_{index}", "kind": "shape", "startFrame": start,
                             "endFrameExclusive": end,
                             "bounds": {"x": inset, "y": inset,
                                        "width": width - 2 * inset, "height": height - 2 * inset},
                             "params": {"shape": "rect", "color": scene["accent"]}, "zIndex": 0})
        if visual == "counter":
            counter_id = f"counter_{index}"
            counter_y = round(height * 0.38)
            elements.append({"id": counter_id, "kind": "counter", "startFrame": start,
                             "endFrameExclusive": end,
                             "bounds": {"x": inset, "y": counter_y,
                                        "width": width - 2 * inset, "height": round(height * 0.25)},
                             "params": {"startValue": start_value, "endValue": counter_value,
                                        "decimals": decimals, "prefix": prefix, "suffix": suffix,
                                        "color": scene["accent"],
                                        "fontSize": max(24, round(min(width, height) * 0.12)),
                                        "fontFamily": font_family, "align": "center"},
                             "zIndex": 1, "sourceRefs": [ref, *claim_refs]})
            finish = start + entry_frames
            animations.append({"targetId": counter_id, "property": "value", "keyframes": [
                {"frame": start, "value": start_value},
                {"frame": finish, "value": counter_value, "easing": "ease_out"}]})
        if visual in ("bar_chart", "line_chart"):
            chart_id = f"chart_{index}"
            chart_start = start + max(1, entry_frames // 3)
            elements.append({"id": chart_id, "kind": "chart.bar" if visual == "bar_chart" else "chart.line",
                             "startFrame": chart_start, "endFrameExclusive": end,
                             "bounds": {"x": inset, "y": round(height * 0.25),
                                        "width": width - 2 * inset, "height": round(height * 0.52)},
                             "dataBinding": {"datasetId": chart_dataset["id"], "field": value_field,
                                             "format": {"unit": chart_unit, "decimals": chart_decimals}},
                             "params": {"categoryField": category_field, "minimum": chart_minimum,
                                        "maximum": chart_maximum, "color": scene["accent"],
                                        "baselineColor": "#718096", "labelFontFamily": font_family,
                                        "tickCount": chart_tick_count, "showValues": True},
                             "zIndex": 1, "sourceRefs": chart_refs})
            animations.append({"targetId": chart_id, "property": "reveal", "keyframes": [
                {"frame": chart_start, "value": 0},
                {"frame": start + entry_frames,
                 "value": 1, "easing": "ease_out"}]})
        for role, value in (("title", scene["title"]), ("subtitle", scene["subtitle"])):
            if not value.strip():
                continue
            element_id = f"{role}_{index}"
            title = role == "title"
            if visual == "asset":
                y = round(height * (0.62 if title else 0.80))
                box_h = round(height * (0.18 if title else 0.16))
            elif visual == "card":
                card_h = height - 2 * inset
                y = inset + round(card_h * (0.18 if title else 0.62))
                box_h = round(card_h * (0.36 if title else 0.22))
            elif visual == "counter":
                y = round(height * (0.14 if title else 0.70))
                box_h = round(height * (0.20 if title else 0.15))
            elif visual in ("bar_chart", "line_chart"):
                y = round(height * (0.06 if title else 0.82))
                box_h = round(height * (0.16 if title else 0.16))
            else:
                y = round(height * (0.22 if title else 0.68))
                box_h = round(height * (0.35 if title else 0.18))
            text_x = 2 * inset if visual == "card" else inset
            text_width = width - 4 * inset if visual == "card" else width - 2 * inset
            elements.append({"id": element_id, "kind": "text", "startFrame": start,
                             "endFrameExclusive": end,
                             "bounds": {"x": text_x, "y": y, "width": text_width, "height": box_h},
                             "text": {"value": value, "locale": proposal["locale"],
                                      "direction": proposal["direction"], "fontFamily": font_family,
                                      "fontWeight": 700 if title else 400, "align": "center"},
                             "params": {"color": _card_text_color(scene["accent"]) if visual == "card" else "#FFFFFF",
                                        "fontSize": max(20, round(min(width, height) * (0.055 if title else 0.038))), "wrap": True},
                             "zIndex": 2, "sourceRefs": [ref, *claim_refs]})
            if motion == "fade":
                animations.append({"targetId": element_id, "property": "opacity", "keyframes": [
                    {"frame": start, "value": 0}, {"frame": start + entry_frames, "value": 1, "easing": "ease_out"}]})
            if motion == "slide":
                begin = start + (0 if title else max(1, entry_frames // 4))
                finish = start + entry_frames
                enter_x = -round(width - 2 * inset) if proposal["direction"] == "ltr" else width
                animations.append({"targetId": element_id, "property": "x", "keyframes": [
                    {"frame": begin, "value": enter_x},
                    {"frame": finish, "value": text_x, "easing": "ease_out"}]})
            if motion in ("whip_left", "whip_right"):
                begin = start + (0 if title else max(1, entry_frames // 4))
                direction = -1 if motion == "whip_left" else 1
                overshoot = text_x - direction * round(width * 0.05)
                overshoot_frame = begin + max(1, round((start + entry_frames - begin) * 0.65))
                animations.append({"targetId": element_id, "property": "x", "keyframes": [
                    {"frame": begin, "value": direction * width},
                    {"frame": overshoot_frame, "value": overshoot, "easing": "ease_out"},
                    {"frame": start + entry_frames, "value": text_x, "easing": "ease_in_out"}]})
                animations.append({"targetId": element_id, "property": "opacity", "keyframes": [
                    {"frame": begin, "value": 0},
                    {"frame": min(begin + max(2, entry_frames // 3), start + entry_frames),
                     "value": 1, "easing": "ease_out"}]})
            if motion == "rise":
                begin = start + (0 if title else max(1, entry_frames // 4))
                finish = start + entry_frames
                enter_y = min(height, y + max(24, round(height * 0.12)))
                animations.append({"targetId": element_id, "property": "y", "keyframes": [
                    {"frame": begin, "value": enter_y},
                    {"frame": finish, "value": y, "easing": "ease_out"}]})
                animations.append({"targetId": element_id, "property": "opacity", "keyframes": [
                    {"frame": begin, "value": 0},
                    {"frame": finish, "value": 1, "easing": "ease_out"}]})
        if exit_frames:
            fade_start = end - exit_frames
            for element in elements:
                if (element["kind"] not in {"text", "shape", "image", "video", "counter"}
                        or element["id"] == f"background_{index}"):
                    continue
                opacity = next((animation for animation in animations
                                if animation["targetId"] == element["id"]
                                and animation["property"] == "opacity"), None)
                exit_keys = [{"frame": fade_start, "value": 1},
                             {"frame": end - 1, "value": 0, "easing": "ease_in"}]
                if opacity is None:
                    animations.append({"targetId": element["id"], "property": "opacity",
                                       "keyframes": exit_keys})
                else:
                    opacity["keyframes"].extend(exit_keys)
        if audio_asset_id:
            elements.append({"id": f"narration_{index}", "kind": "audio", "startFrame": start,
                             "endFrameExclusive": end, "assetId": audio_asset_id,
                             "params": {"gainDb": 0, "role": "narration"}, "zIndex": 3})
        for cue_index, cue in enumerate(sound_effects, 1):
            cue_start = start + cue["startFrameOffset"]
            elements.append({"id": f"sfx_{index}_{cue_index}", "kind": "audio",
                             "startFrame": cue_start,
                             "endFrameExclusive": cue_start + cue["durationFrames"],
                             "assetId": cue["assetId"],
                             "params": {"gainDb": cue["gainDb"], "role": "sound_effect"},
                             "zIndex": 3})
        if soundtrack is not None:
            music_gain = max(-60, soundtrack["gainDb"]
                             + (soundtrack["duckUnderNarrationDb"] if audio_asset_id else 0))
            elements.append({"id": f"music_{index}", "kind": "audio", "startFrame": start,
                             "endFrameExclusive": end, "assetId": soundtrack["assetId"],
                             "params": {"gainDb": music_gain, "role": "music",
                                        "sourceStartFrame": start,
                                        "fadeInFrames": soundtrack["fadeInFrames"] if index == 1 else 0,
                                        "fadeOutFrames": (soundtrack["fadeOutFrames"]
                                                          if index == len(proposal["scenes"]) else 0)},
                             "zIndex": 3})
        timeline.append({"id": scene_id, "startFrame": start, "endFrameExclusive": end,
                         "transitionIn": "start" if index == 1 else transition,
                         **({"transitionFrames": transition_frames} if transition == "fade" else {}),
                         "elements": elements,
                         "beats": [{"id": f"beat_{index}", "startFrame": start, "endFrameExclusive": end,
                                    "elementIds": [element["id"] for element in elements],
                                    **({"notes": (f"Editorial timing: {entry_frames} frame entry, "
                                                    f"{timing['holdFrames']} frame hold, "
                                                    f"{exit_frames} frame exit. "
                                                    f"Purpose: {purpose}. Energy: {energy}/5.")}
                                       if timing is not None else {}),
                                    **({"voice": {"value": voice, "locale": proposal["locale"]}} if voice.strip() else {}),
                                    "onScreen": ([{"value": value, "locale": proposal["locale"]}
                                                  for value in (scene["title"], scene["subtitle"]) if value.strip()]
                                                 + ([{"value": prefix + f"{counter_value:.{decimals}f}" + suffix,
                                                       "locale": proposal["locale"]}]
                                                    if visual == "counter" else [])),
                                    "sourceRefs": [ref, *claim_refs, *chart_refs]}],
                         "animations": animations, "sourceRefs": [ref, *claim_refs, *chart_refs]
                         + ([{**plan_ref, "location": f"/scenes/{index - 1}"}] if plan_ref else [])})
        cursor = end
    if cursor > 10_000:
        raise DirectorError("first draft exceeds the 10,000-frame preview limit")
    spec = {"schemaVersion": "1.0.0",
            "project": {"id": project_id, "title": proposal["title"], "locale": proposal["locale"],
                        "direction": proposal["direction"],
                        "description": "Desktop-agent-directed first draft; review visuals, exact text, and source meaning."},
            "canvas": {"width": width, "height": height, "frameRate": {"numerator": fps, "denominator": 1},
                       "durationFrames": cursor, "colorSpace": "Rec.709", "background": "#101820",
                       "safeArea": {"top": inset, "right": inset, "bottom": inset, "left": inset}},
            "sources": [{"id": "user_prompt", "uri": prompt_uri, "mediaType": "text/plain",
                         "sha256": file_sha256(prompt), "authority": ["creative brief"]}]
                       + ([plan_source] if plan_source else [])
                       + ([claim_source] if claim_source else []) + research_sources + list(data_sources.values()),
            "assets": asset_list, "datasets": list(datasets.values()), "timeline": timeline,
            "deliverables": [{"id": "preview", "target": "video/mp4", "profile": "preview",
                              "required": True, "editable": False}],
            "policies": {"qa": (([{"id": "claim_review", "rule": "claim.semantic_review", "severity": "warning"}]
                                    if claim_source else [])
                                   + ([{"id": "chart_values", "rule": "chart.data_exact", "severity": "error"}]
                                      if any(scene["visual"] in ("bar_chart", "line_chart") for scene in proposal["scenes"]) else [])),
                         "disclosures": [], "approvals": ["first draft visual review"],
                         "unsupportedFeature": "error"}}
    errors = validate(spec)
    if errors:
        raise DirectorError("compiled MotionSpec is invalid: " + "; ".join(errors))
    capability = plan(spec)["capabilities"][0]
    if not capability["buildable"]:
        raise DirectorError("first draft needs unsupported feature: " + str(capability["unsupportedFeatures"]))
    return spec
