# End-to-end user test

This test exercises the intended first-time user experience: start with only the public repository link, create a first draft from a prompt, revise it with another prompt, and finish supported layers manually in After Effects.

## Recommended test: editable Bitcoin poster reel

Attach one rights-cleared Bitcoin PNG or JPG to the coding-agent task. A transparent PNG is ideal. This test uses a linked still image so Scale, Position, and 2D Rotation remain editable in the generated After Effects project. It tests flat rotation around the image plane; a coin turning in 3D requires a generated or rendered video plate and its internal 3D motion remains baked.

### 1. Start like a new user

Start a new coding-agent task in an empty or projectless workspace. This new task is intentional because the goal is to test discovery with no prior Motion Engine conversation or clone. Attach the Bitcoin image and send:

> Clone https://github.com/Navidbyti/motion-engine.git into a fresh local directory and open it. Follow the repository's own instructions without relying on prior chat context. Set up its documented local environment, report `motion-engine version`, and run its tests. Then create a fresh ignored project at `runs/bitcoin-editability-test/`. Do not ask me to create folders, write JSON, or run repository commands.

Expected result:

- The agent clones the repository itself and discovers `AGENTS.md` and `START_HERE.md`.
- The agent reports build `0.63.1` or newer.
- It creates the ignored `runs/bitcoin-editability-test/` directory itself.
- It does not ask for knowledge from this development conversation.

### 2. Prompt the first draft

Send this as the production request with the image attached:

> Create a polished 10-second 1080×1920 motion graphic using my attached Bitcoin image. Start on a near-black background. Bring the coin in sharply from the left with a short overshoot, then hold it large in the center while it slowly scales up and rotates 12 degrees clockwise. Animate the exact text “BITCOIN IS AWESOME” as a separate editable text layer beneath it. Finish with the coin expanding into a full orange screen. Use strong spacing and readable pacing. Create and inspect the MP4 first draft, contact sheet, QA report, and the supported editable After Effects project. Keep the linked image and text editable. Do not substitute a fake 3D turn for the requested flat rotation.

Inspect these results:

- The first draft has a clear entrance, readable hold, and orange finish.
- The exact text is correct and remains separate from the image.
- The image moves, scales, and rotates without leaving unwanted pixels outside its designed bounds.
- The QA report and native export report pass.
- The agent gives concrete paths for the MP4, MotionSpec, review sheet, and AEP.

### 3. Edit it with a prompt

Send this follow-up in the same conversation:

> Revise only the Bitcoin scene. Make the coin 15% larger, reduce the final clockwise rotation from 12 degrees to 7 degrees, slow the zoom so most of it happens during the hold, move the coin 40 pixels to the right, and change the text to the exact words “BITCOIN, BUILT TO MOVE”. Preserve every other scene and export a new version. Show me the changed scene and the new QA result.

Expected result:

- The agent writes a hash-bound typed revision instead of rebuilding unrelated scenes.
- It uses supported bounds, position, scale, rotation, and text operations.
- It produces new paths such as `v2.motion.json` and `v2-preview/`; it does not overwrite version 1.
- A repeated request against the old base hash fails safely instead of silently editing the wrong version.

### 4. Edit it manually in After Effects

Open the version 2 AEP supplied by the agent. In the scene composition:

1. Select the linked Bitcoin image layer.
2. Press **P** for Position, **S** for Scale, and **R** for Rotation.
3. Change the final Scale value, drag a Rotation key later, and move the image slightly right.
4. Select the text layer, edit the Source Text, and change its wording or font size.
5. Save as a new file such as `bitcoin-editability-manual-v3.aep`.
6. Preview or render a short proof and confirm the manual changes persist after closing and reopening the project.

The test passes when the image is linked footage, the title is real text, the named transform properties contain editable keys, and the saved changes survive reopen.

Stay in this same coding-agent task for steps 2 and 3 so the agent retains the project paths, accepted creative choices, and current MotionSpec hash. Starting another task between the first draft and prompt revision would weaken the continuity test. Manual editing happens in After Effects after the agent supplies version 2.

## Separate existing-user update test

Update behavior is a different acceptance case. After the fresh-user test is complete, reopen the same clone in a later coding session and ask the agent to follow `docs/update-policy.md`. It should fetch once, preserve the existing `runs/` project, use a fast-forward-only pull when an update exists, and continue in the same conversation unless it identifies a documented restart condition.

## Ambitious production test

After the editability test passes, try a fuller reel with a generated 3D Bitcoin plate, sound effects, and music:

> Create a 15-second vertical Bitcoin brand reel. Use a real generated or rendered plate of a coin turning in 3D, a sharp left entrance, a slow camera push, a full-screen orange transition, separate exact title text, synchronized whoosh and impact effects, and a restrained music bed with fades. Inspect the visuals, pacing, and audio mix before showing me the draft. Then revise only the second scene from a follow-up prompt.

This second test exercises generation, moving plates, pacing, audio, and scoped revisions. Premiere can retime, position, scale, and grade the rendered scene clips. After Effects can edit the supported deterministic layers it receives. The direction and camera angle inside a generated 3D plate remain baked and require regeneration when changed.

## Additional real test ideas

- **Spreadsheet reel:** attach a CSV or XLSX and request a 20-second comparison with exact labeled bars, a counter, sources, and two prompt revisions to values and pacing.
- **Factual explainer:** request a current event explainer that challenges the premise, researches claims, creates a claim ledger, and flags uncertainty before rendering.
- **Brand product reel:** attach product photography and a brand guide, request a three-scene reel, then revise one headline, one crop, one color, and one timing window.
- **RTL reel:** attach Persian copy and data, request localized digits and right-to-left layout, then manually inspect glyph shaping and font availability in Adobe.
