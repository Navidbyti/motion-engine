# Whole-video first draft

Codex or Claude running on the desktop is the director. It reads the user's prompt and source material, plans the entire video, prepares assets, and writes a director-plan JSON file. The local Motion Engine CLI validates, compiles, freezes, and renders that plan. There is no LLM API key or model service in this workflow. See [desktop-agent workflow](desktop-agent-workflow.md).

The currently supported plan vocabulary is small: typography, rectangle compositions, supplied still images or moving plates, cuts, fades, and bounded zoom. An agent should use `motion-engine director-schema` and the [abstract](../examples/director-abstract.plan.json) and [moving-plate](../examples/director-plate.plan.json) examples to write the plan. It should never imply a requested visual exists when it has only been described.

Put `prompt.txt`, `plan.json`, and any assets in one project directory. For an available asset, list its relative path and SHA-256 in an asset catalog. For a video plate, first use `motion-engine import-video` to make an exact-frame ZIP. Then run:

```powershell
motion-engine first-draft project/prompt.txt project/plan.json --project-id sample --output-spec project/first.motion.json --output-dir project/preview --assets project/assets.json --width 1080 --height 1920 --fps 30 --scale 0.5
motion-engine qa project/first.motion.json --render-dir project/preview
```

Omit `--assets` when the plan uses no external media. The command requires new spec and render paths. It writes an MP4 and PNG frames. Prompt and plan are hashed as MotionSpec sources. If compilation or rendering fails, the agent corrects the plan or assets and tries a new output path.

`assetRequests` records missing shots explicitly. Compilation stops while requests remain unresolved; a requested rotating 3D object cannot silently become a title card. `researchRequired: true` also stops compilation until evidence-bound research is implemented. An agent may research and draft independently, but the current compiler cannot certify factual claims; do not present a factual explainer as verified output from this path.

For a smaller step, use `motion-engine compile-director PROMPT PLAN --output SPEC --project-id ID`, followed by `freeze` and `render`. The compiler checks scene frame limits, IDs, available assets, and the resulting MotionSpec. The desktop agent must inspect the actual video and revise weak scenes. See [revisions](revisions.md) for typed scene edits.
