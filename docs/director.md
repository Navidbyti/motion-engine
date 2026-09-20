# Whole-video first draft

The director turns a natural-language creative brief into an ordered plan for **every scene**, then compiles the plan to MotionSpec and renders a complete preview. The plan has a deliberately small, declared vocabulary: typography, a rectangle composition, or a supplied image/moving plate; cuts; fades; and bounded visual zoom. The model chooses the content and visual approach within those capabilities. The compiler checks actual asset IDs, frame limits, schema, and renderer support before the draft is accepted.

## One command with a configured model

Set `OPENAI_API_KEY` in your environment and select a Responses API model that supports structured outputs. The optional planner uses the [official OpenAI structured-output format](https://developers.openai.com/api/docs/guides/structured-outputs) to propose a director plan. The core MotionSpec compiler and renderer have no OpenAI dependency. An API call can incur provider charges; this repository does not ship an API key.

Place a UTF-8 prompt in a project directory and choose new output paths in that directory:

```powershell
motion-engine first-draft project/prompt.txt --model YOUR_MODEL_ID --project-id sample --output-plan project/plan.json --output-spec project/first.motion.json --output-dir project/preview --width 1080 --height 1920 --fps 30 --scale 0.5
```

The command saves the model proposal first, compiles a source-bound MotionSpec, freezes input hashes, then renders PNG frames and an MP4. Each output path must be new. If compilation or rendering fails, the saved plan and, when compilation succeeded, the spec remain available for correction; no partial render directory is published. Use `motion-engine qa project/first.motion.json --render-dir project/preview` after a successful draft.

The available asset catalog is an optional JSON array of MotionSpec asset records passed with `--assets project/assets.json`. Paths in it are relative to the MotionSpec directory. Assets must exist and carry matching SHA-256 hashes. A plan that asks for an unlisted asset fails with its ID so the asset can be generated or imported. Moving footage can enter through [the video-plate importer](rendering.md). The model receives asset IDs and kinds, not raw file contents.

## Use another model or edit the plan yourself

Run `motion-engine director-schema` to obtain the plan JSON Schema, or inspect the [public abstract plan](../examples/director-abstract.plan.json) and [moving-plate plan](../examples/director-plate.plan.json). Ask any LLM to create a complete plan matching that schema, save it as JSON, then compile it:

```powershell
motion-engine compile-director project/prompt.txt project/plan.json --output project/first.motion.json --project-id sample --width 1080 --height 1920 --fps 30 --assets project/assets.json
motion-engine render project/first.motion.json --output-dir project/preview
```

The plan and original prompt are both hashed sources in MotionSpec. A factual prompt, such as an explainer about causes or chronology, must be marked `researchRequired: true`; this director compiler holds it until an evidence-bound research stage is available. It will not turn an unsupported factual assertion into confident narration. The model may misclassify a prompt, so producer review and the future claim gate remain required. For creative prompts, this is a first cut for review; longer scripts, provider-generated assets, voice, transitions, and polished design direction remain open roadmap work.

## How scene revision connects

The generated MotionSpec gives every scene and element a stable ID. Use `motion-engine revise-scene` with a hash-bound typed request to change text, color, or the zoom of an image/video plate without replacing the other scenes. With a configured model, `prompt-revise` proposes that typed request from a scene-level instruction, writes it for review, creates a new spec, and renders a new preview:

```powershell
motion-engine prompt-revise project/first.motion.json --scene-id scene_2 --instruction "Make this title coral" --model YOUR_MODEL_ID --output-request project/edit-2.json --output-spec project/second.motion.json --output-dir project/second-preview
```

Supported prompt edits currently map to text replacement, color, and image/video zoom only. Requests for new objects, 3D changes, sound, transitions, or factual research return an explicit unsupported explanation. Both the first-draft and prompt-revision model calls use the [Responses API structured-output contract](https://developers.openai.com/api/docs/guides/structured-outputs); model results must still pass local checks. Model calls have been tested with simulated responses, not a live account. See [revisions](revisions.md).
