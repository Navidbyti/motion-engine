# Verified revisions

Run `motion-engine freeze SPEC --output revision.json` after validation. The command reads each local source and each `available` asset, verifies any declared SHA-256, and emits a revision manifest with the canonical MotionSpec hash, verified input hashes, and a revision hash. It does not change source files or the MotionSpec, and it refuses to overwrite an existing revision file. Running it again with unchanged inputs produces the same hashes.

Local `uri` values are relative to the MotionSpec file and use `/` separators. Absolute paths, parent traversal, remote URLs, missing files, and hash mismatches stop the command. Pending and optional assets remain listed as unverified. Remote source storage will need a separate fetch-and-verify adapter before it can be frozen.

The canonical spec bytes are UTF-8 JSON with sorted object keys, no extra whitespace, and non-ASCII characters preserved. The hash is stable across property order and formatting changes. Numeric spelling such as `1` versus `1.0` remains distinct. The revision hash binds the canonical spec hash plus sorted source and asset records. A changed source changes the revision even when the spec text is unchanged.

The CLI preview command freezes inputs before rendering and writes `revisionSha256` to `render-manifest.json`. Code using the lower-level `render_preview()` function directly must verify inputs and supply the revision hash itself.

## Scoped scene edits

`motion-engine revise-scene base.motion.json edit.json --output next.motion.json` applies a typed edit to one scene. All three files must be in the same directory so relative source and asset links stay portable. The output must be new. The request must include the exact `baseSpecSha256`; a stale request fails instead of overwriting a newer change. The request JSON is itself hashed and recorded as a source in the new MotionSpec. Run `freeze` and `render` on the new spec to produce version-bound outputs.

```json
{
  "baseSpecSha256": "64 lowercase hexadecimal characters from freeze or Python spec_sha256",
  "sceneId": "scene_1",
  "operations": [
    {"op": "set_text", "elementId": "text_1", "value": "Exact replacement text"},
    {"op": "set_color", "elementId": "text_1", "value": "#F4C542"}
  ]
}
```

`set_text` accepts a text element, replaces matching beat copy, and binds the new words to the revision request instead of retaining stale exact-text citations. `set_color` accepts text, rectangle, and bar/line chart elements. `set_visual_zoom` accepts an image or video element and a list of absolute frame keyframes with finite scale values from 1 to 3; the visual remains clipped to its bounds. The earlier `set_image_zoom` operation remains supported for still images. These are deterministic edit operations for an agent to call after interpreting a prompt. Natural-language editing, scene insertions, and research verification are separate open tasks.
