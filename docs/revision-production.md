# One-command scene revision production

`revise-production` turns one hash-bound typed scene edit into a complete new review version. The desktop agent interprets the user's natural-language instruction, identifies the stable scene and element IDs, and writes the typed request. Motion Engine checks the base MotionSpec hash before changing anything.

```bash
motion-engine revise-production project/v1.motion.json project/v2-request.json \
  --modules project/v1-scenes --name v2 --scale 0.5
```

The command:

1. Applies the typed operations to one scene and writes `v2.motion.json`.
2. Renders only the changed scene into `v2-scenes/`.
3. Verifies and reuses compatible unchanged scenes from every supplied `--modules` directory.
4. Assembles `v2-preview/preview.mp4` with exact global frame and audio semantics.
5. Rebuilds QA and `v2-review/index.html`.
6. Creates `v2-editor-delivery/` with the verified source package and supported Adobe handoffs.
7. Writes `v2-revision-summary.json`, listing the changed scene, rerendered scene, reused scenes, hashes, QA, and delivery paths.

Use a new `--name` for every accepted attempt. The command never overwrites an existing version. A stale request fails when its `baseSpecSha256` differs from the supplied MotionSpec. Missing, changed, ambiguous, or incompatible cached scenes also fail before assembly.

The current typed operations cover supported text, color, bounds, opacity, position, image zoom, 2D plate rotation, audio gain, approved shot replacement, and claim ID mapping. If the user's instruction cannot be represented honestly, the agent must extend the engine or compile a new director plan instead of claiming the edit succeeded.
