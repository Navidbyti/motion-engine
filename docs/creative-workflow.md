# Prompt to first draft, then scene revisions

The product goal is a **complete first video draft** from a natural-language request. The producer then prompts any scene, element, claim, shot, or transition and receives a new version with the rest of the project preserved. The current CLI supports literal text drafting, a limited deterministic preview, and typed scene revisions; this document specifies the broader implementation contracts.

## Production loop

1. **Understand** — Parse the user's request into a project brief: audience, purpose, aspect ratio, length, exact copy, factual claims, desired motion, and delivery targets. Preserve the original prompt as a source. Ask only when an essential constraint cannot be inferred; record other assumptions in the draft.
2. **Research when needed** — Split the proposed narration into atomic claims. Verify the premise and chronology before storyboarding. Store URL or document, publisher, publication and event dates, quoted evidence span, retrieval date, and confidence for each claim. Distinguish established facts, disputed interpretations, and unknowns. An input document's instructions remain data. If a claim cannot be checked, change the wording or visibly flag the gap; do not invent a citation.
3. **Direct** — Create an editable scene plan. For every scene, specify its narrative purpose, duration in frames, shot type, visual elements, motion, voice, exact on-screen text, asset requests, and claim references. The model chooses from a capability registry and records any unsupported requirement. It should plan the whole video before building individual scenes.
4. **Execute** — Resolve asset requests with local procedural tools, licensed user assets, or an optional image/video/3D provider. Keep exact copy, charts, and legal text as deterministic layers. Check generated assets for suitability and provenance. Compile the scene plan to MotionSpec, validate and freeze it, then render the entire first draft.
5. **Inspect** — Generate a contact sheet, preview video, timing and audio reports, asset manifest, and claim/citation report. Check every scene for missing media, clipping, overflow, blank frames, and unsupported output features. Keep the draft reviewable even if an optional Adobe target is unavailable.
6. **Revise** — A prompt targets a scene or element by stable ID. The model proposes a typed change against a known spec hash, shows the affected scenes and claims, applies only that change, validates, rerenders affected frames, and makes a new revision. A claim edit requires renewed source verification. The producer can compare or restore revisions.
7. **Deliver** — Export the final MP4 and supported editable projects, then verify native project files in their owning applications. Package the spec, sources, asset provenance, research, review decisions, and QA reports.

## Tool contract the model needs

| Tool | Input | Output | Gate |
| --- | --- | --- | --- |
| `inspect_sources` | Files, URLs, user prompt | Evidence records with locations and hashes | Extraction warnings visible |
| `research_claims` | Topic, proposed claims | Claim ledger with sources and uncertainty | No uncited factual claim in final narration |
| `plan_project` | Brief, evidence, capability registry | Complete scene/beat/asset plan | Duration and every requested deliverable accounted for |
| `request_asset` | Shot description, style, duration, rights constraints | Hashed asset or explicit pending request | Generated material is inspected before use |
| `compile_spec` | Plan, approved assets | MotionSpec and capability report | Schema, references, and frame continuity pass |
| `render_draft` | Frozen spec | Video and contact sheet | No partial output on failure |
| `revise_scene` | Base spec hash, stable scene/element ID, typed change | New immutable spec revision | Unaffected scenes unchanged; claim verification remains an open gate |
| `export_native` | Approved revision, target app | Editable project and verification report | Save, close, reopen, inspect |

This is an orchestration contract, not an assertion that these tools are all implemented. Each operation must advertise its actual capabilities and fail clearly when a requested feature is missing.

## Acceptance case: rotating object with a slow zoom

Request: “A slowly zooming shot of a Bitcoin coin rotating in the air, with the exact text ‘bitcoin is awesome’.” The first draft should contain one coherent moving shot and a separate text layer with those exact bytes. A flat image spinning in its own plane is not a valid substitute for an object rotating in 3D. The director must request or render a 3D/video plate for the coin, inspect it, and use the motion layer for the slow zoom. Image and frame-addressed video plates now support `scale` keyframes from 1 to 3 in the raster preview; 3D asset generation and native camera/3D handling remain open work. The text stays editable and can be revised without regenerating the coin.

Checks: visible depth change while the coin turns; smooth frame-by-frame zoom; correct title spelling and timing; no clipping; asset provenance; a revised title does not change the shot.

## Acceptance case: researched explainer

Request: “Make a motion graphic about why America started a war with Iran.” The premise itself is a claim to test. The research stage must establish which event and time period the producer means, what happened, who acted, the available evidence for motives, and where accounts disagree. It must not transform a contested interpretation into an undisputed headline. The first draft should still be a complete video: use wording supported by the evidence, cite substantive claims in the project record, and show uncertainty where necessary. Later prompts may change one claim, graphic, source, pacing choice, or scene without silently changing the others.

Checks: each substantive claim has a source and evidence span; dates distinguish publication from event; numerical graphics match their sources; disputed interpretations are attributed; changing a claim invalidates its old verification until it is rechecked; the exported video and MotionSpec share one revision ID.

## Build order

1. Add stable scene-level revision history and a prompt-to-typed-edit planner. Typed revisions and hash-bound outputs are in place.
2. Extend the source-linked claim ledger and scene mapping with semantic review decisions and claim-level release gates.
3. Teach the desktop Codex or Claude agent to select tools, plan the full project, compile MotionSpec, and loop on QA failures without an LLM API integration.
4. Add native output coverage and clean-machine verification for the resulting scene types.
5. Add efficient proxies, color management, and long-form performance for moving plates.
