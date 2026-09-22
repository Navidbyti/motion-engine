# Start here

Motion Engine is designed to be operated by a desktop coding agent such as Codex, Claude Code, or Antigravity. You describe the video; the agent handles repository setup, research, planning files, command line tools, rendering, inspection, and revisions.

**Current build: v0.68.0.** Existing clones should follow [the update policy](docs/update-policy.md). A normal fast-forward update does not require a new chat.

## Give this to your coding agent

Copy and paste this prompt into a new coding-agent task:

> Clone https://github.com/Navidbyti/motion-engine.git into a fresh local directory and open it. Read AGENTS.md and docs/desktop-agent-workflow.md. Report `motion-engine version`, install the documented local dependencies, and run the tests. Then act as the motion director for this request: **[describe the video here]**. Create a new private workspace under `runs/<project-name>/`; do not assume an output or project folder already exists. Inspect any files I attach, research factual claims when needed, write the complete director plan, prepare or request required assets, render the first MP4 draft, inspect the actual video and QA report, and improve weak scenes before showing me the result. Keep exact text and data in deterministic layers. Do not ask me to create folders, write JSON, copy files, or run repository commands. Ask me only when you genuinely need an external choice, licensed asset, account access, or manual Adobe action.

The agent should begin with `motion-engine doctor`, create the private folder with `motion-engine init-project`, and use `motion-engine produce` once its researched director plan and approved assets are ready. The output includes a complete preview, scene review interface, QA, verified source package, and supported Adobe handoffs.

Attach your script, PDF, spreadsheet, images, audio, brand files, or reference video to that task. Replace the bold placeholder with your request.

Editors joining the alpha can follow [the editor alpha test](docs/editor-alpha.md). The complete creative loop is documented in [full-script production](docs/full-script-production.md).

If the repository is already cloned, tell the agent to open that clone and follow `docs/update-policy.md` instead of cloning another copy. This is an existing-user maintenance path, separate from the fresh-user workflow above.

Examples:

> Make a 20-second vertical motion graphic explaining compound interest. Use a clean dark style, research the claims, and show the first draft.

> Use the attached spreadsheet to create a 30-second animated comparison with labeled charts. Render a first draft and show me the MP4.

> Create a slow zoom toward a rotating Bitcoin plate with the text “Bitcoin is awesome.” Generate or source the moving plate through an available tool, then render and inspect the draft.

## What happens next

The coding agent should:

1. Clone and set up the repository.
2. Create `runs/<project-name>/` for your private inputs and generated project. The repository intentionally ships without this folder and Git ignores it.
3. Turn your request into a complete scene plan.
4. Research and cite factual material when needed.
5. Generate, import, or explicitly request missing visual and audio assets.
6. Render an MP4, contact sheets, and a QA report.
7. Inspect the actual result and revise weak scenes.
8. Give you the video and explain any remaining limitations.
9. Apply later prompts with `motion-engine revise-production`; rerender only the requested scene, reuse verified unchanged scenes, and produce a complete new review and editor delivery.

The local Motion Engine performs deterministic compilation, rendering, provenance, and QA. The desktop coding agent supplies creative judgment. No model API key is required by the repository.

For manual finishing, read [what remains editable](docs/editability.md). The After Effects subset preserves supported text, shapes, linked still images, and their opacity, position, still-image scale, and still-image 2D rotation keys. Premiere receives rendered scene clips and markers, so graphics inside those clips are flat.

To test the complete update, prompt, prompt-edit, and manual-edit loop, use the step-by-step [end-to-end user test](docs/end-to-end-user-test.md).

For a full social reel, tell the agent the desired length and ask it to use the `reel` pacing profile, purposeful scene progression, script-led entry/hold/exit timing, sound effects, an optional ducked music bed, and an inspected final audio mix. The agent should choose scene count and reading time from the content. Use the `shot` profile for one compact visual idea.

## Current boundary

The current release can create useful first drafts from supported typography, cards, images, video plates, narration WAVs, counters, and source-backed bar or line charts. Complex 3D work and complete editable coverage across every Adobe application still require additional tools or adapter work. The agent must state those limitations accurately instead of silently replacing a requested effect.
