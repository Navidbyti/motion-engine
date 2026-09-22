# Local review interface

The review interface is a portable static dashboard generated from a target MotionSpec, compatible scene-module manifests, and an optional verified assembled preview. It has no server, account, model API, or external web dependency.

```powershell
motion-engine make-review-site project/second.motion.json `
  --modules project/first-scene-modules `
  --modules project/second-revised-modules `
  --render-dir project/second-assembled `
  --output-dir project/second-review-site
```

Open `project/second-review-site/index.html` in a browser. The page contains the complete assembled preview when supplied, one independently playable clip and poster per scene, stable scene IDs, exact time ranges, visible copy, primitive kinds, source-reference counts, and a prompt box for each scene. **Copy prompt** copies an instruction such as `Revise scene scene_7: ...` for the current Codex or Claude conversation.

The generator verifies scene input hashes and media integrity before copying anything. A stale, missing, tampered, or conflicting module stops the build and leaves no partial site. The supplied assembled render must match the target MotionSpec and frozen input revision.

The generated page is a review surface. It does not edit MotionSpec, invoke a model, rerender media, or submit a prompt directly to a coding-agent task. Those operations remain in the desktop agent so the user retains one creative conversation and the repository remains free of an LLM API requirement.
