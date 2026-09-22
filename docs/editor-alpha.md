# Editor alpha test

This alpha is for motion designers who have Windows, a desktop coding agent such as Codex, Claude Code, or Antigravity, and optionally After Effects or Premiere Pro. Python and FFmpeg are the only core runtime requirements. Adobe applications are needed only for native handoff testing.

## Start with one message

Open a new coding-agent task, attach the script and any approved brand or media files, and send:

> Clone https://github.com/Navidbyti/motion-engine.git into a fresh folder. Read AGENTS.md and START_HERE.md, install the documented environment, and run `motion-engine doctor`. Create a private project workspace for my attached script and production request. Research any current or factual claims, build the complete first draft, inspect its MP4 and QA, and give me the review page and editor delivery. Handle repository commands and files yourself. Ask me only for an essential creative choice, rights-cleared asset, account access, or manual Adobe step.

The agent should run the workflow. The editor should not have to write JSON or manage output folders.

## What the editor receives

- A playable complete MP4.
- A local review page with every scene, timing, copy, and a copyable scene revision prompt.
- A verified source package containing MotionSpec, inputs, revision hashes, and QA.
- Prepared Adobe JSX or Premiere XML where the project uses the currently supported subset.
- `OPEN_ME.md`, which explains the exact handoff available for that production.

## Test sequence

1. Watch the complete cut and judge the story, pacing, content density, visual quality, and sound.
2. Review each scene in the local review page.
3. Copy two scene prompts into the same agent task: one copy or timing edit and one visual or asset edit.
4. Confirm the agent uses `revise-production`, creates a new version, rerenders the named scene, and records the reused unrelated scenes in the revision summary.
5. Open the prepared After Effects JSX or Premiere XML when available. Save the generated native project, change text and transforms manually, close it, reopen it, and confirm the edits persist.
6. Send the diagnostic report, failed command output, project request, and the affected scene ID with any bug report. Do not send private source files unless the tester is authorized to share them.

## Pass criteria

The test passes when the editor starts from a script and one message, receives a coherent full first draft, can revise two scenes by prompt, and can make a supported manual Adobe edit without learning the repository layout. QA must identify unsupported or unverifiable work instead of silently claiming completion.

## Known alpha limits

- The desktop agent writes the creative plan; the repository does not call an LLM API.
- Current research checks source linkage and exact excerpts. A human still reviews meaning before factual release.
- Generated 3D or photographic motion inside a video plate remains baked and must be regenerated for internal camera or subject changes.
- Manual Adobe edits are not yet synchronized back into MotionSpec. Finish prompt revisions first, then do final manual polishing.
- Adobe exporters support documented subsets and may mark an adapter unsupported for a particular project. The deterministic MP4 and review workflow still work.
