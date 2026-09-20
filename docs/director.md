# Whole-video first draft

Codex or Claude running on the desktop is the director. It reads the user's prompt and source material, plans the entire video, prepares assets, and writes a director-plan JSON file. The local Motion Engine CLI validates, compiles, freezes, and renders that plan. There is no LLM API key or model service in this workflow. See [desktop-agent workflow](desktop-agent-workflow.md).

The currently supported plan vocabulary is small: typography, rectangle compositions, contrast-aware cards, supplied still images or moving plates, cuts, fades, bounded zoom, text slide entrances, and staggered rises. A `visual: "card"` scene uses the accent color as a rectangular panel and selects black or white text for at least 4.5:1 color contrast. For `motion: "slide"`, text enters from the left in LTR projects or the right in RTL projects. For `motion: "rise"`, the title and subtitle move upward and fade in on staggered frame tracks. An agent should use `motion-engine director-schema` and the [abstract](../examples/director-abstract.plan.json), [horizontal card](../examples/card-horizontal.plan.json), [vertical card](../examples/card-vertical.plan.json), and [moving-plate](../examples/director-plate.plan.json) examples to write the plan. It should never imply a requested visual exists when it has only been described.

Put `prompt.txt`, `plan.json`, and any assets in one project directory. For an available asset, list its relative path and SHA-256 in an asset catalog. For a video plate, first use `motion-engine import-video` to make an exact-frame ZIP. Then run:

```powershell
motion-engine first-draft project/prompt.txt project/plan.json --project-id sample --output-spec project/first.motion.json --output-dir project/preview --review-dir project/review --assets project/assets.json --width 1080 --height 1920 --fps 30 --scale 0.5
```

Omit `--assets` when the plan uses no external media. The command requires new spec and render paths. It writes an MP4, PNG frames, `preview/qa.json`, and, with `--review-dir`, scene contact sheets. Prompt and plan are hashed as MotionSpec sources. If compilation or rendering fails, the agent corrects the plan or assets and tries a new output path.

`assetRequests` records missing shots explicitly. Compilation stops while requests remain unresolved; a requested rotating 3D object cannot silently become a title card. Once the desktop agent has made and inspected the media, use `motion-engine resolve-assets project/plan.json --assets project/assets.json --output project/ready-plan.json --fps 30`. The resolver checks request IDs, approved and licensed files, hashes, media type, frame rate, and plate duration, then writes a new plan with cleared requests. A 3D request additionally needs `generation.technique: "3d"` on a frame-plate asset; that metadata does not prove visible depth, so the agent must inspect the shot. Use `ready-plan.json` for `first-draft`.

For a factual prompt, set `researchRequired: true`, provide `claimIds` for every scene, and pass a [source-linked claim ledger](research.md) with `--claims`. The preview is reviewable, but QA requires a person to assess claim meaning, source quality, and uncertainty before factual release. The compiler does not certify truth.

For a smaller step, use `motion-engine compile-director PROMPT PLAN --output SPEC --project-id ID`, followed by `freeze` and `render`. The compiler checks scene frame limits, IDs, available assets, and the resulting MotionSpec. The desktop agent must inspect the actual video and revise weak scenes. See [revisions](revisions.md) for typed scene edits.
