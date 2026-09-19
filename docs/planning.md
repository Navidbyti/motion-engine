# Planning in M1

Run `motion-engine plan SPEC --output plan.json`. Planning first validates MotionSpec, then emits a frame-indexed scene graph with beats, elements, animations, data bindings, asset IDs, and source references. A capability report lists requested element kinds for every deliverable.

The built-in `video/mp4` preview adapter is available for text, rectangles, raster images, bar/line charts, and hashed WAV audio elements. Adobe output adapters remain `planned`. `plan` succeeds when it can describe the work and there is no unsupported required feature. The report says `buildable: false` when an output needs a missing adapter or feature. Add `--require-buildable` to fail until every required target is available. This makes the CLI useful for agent planning without claiming native rendering exists.

A future installed adapter may supply `--capabilities manifest.json`:

```json
{
  "targets": [
    {
      "target": "org.example.renderer",
      "status": "available",
      "supportedKinds": ["text", "shape"],
      "editableKinds": ["text", "shape"],
      "version": "1.0.0"
    }
  ]
}
```

This is an adapter declaration, not a renderer implementation. A later build command must resolve the installed adapter and verify the produced artifact. Unknown targets and unsupported required kinds are explicit issues. An editable deliverable also requires the adapter to declare the relevant kinds editable; a raster video cannot satisfy an editable-project requirement.
