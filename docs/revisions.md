# Verified revisions

Run `motion-engine freeze SPEC --output revision.json` after validation. The command reads each local source and each `available` asset, verifies any declared SHA-256, and emits a revision manifest with the canonical MotionSpec hash, verified input hashes, and a revision hash. It does not change source files or the MotionSpec, and it refuses to overwrite an existing revision file. Running it again with unchanged inputs produces the same hashes.

Local `uri` values are relative to the MotionSpec file and use `/` separators. Absolute paths, parent traversal, remote URLs, missing files, and hash mismatches stop the command. Pending and optional assets remain listed as unverified. Remote source storage will need a separate fetch-and-verify adapter before it can be frozen.

The canonical spec bytes are UTF-8 JSON with sorted object keys, no extra whitespace, and non-ASCII characters preserved. The hash is stable across property order and formatting changes. Numeric spelling such as `1` versus `1.0` remains distinct. The revision hash binds the canonical spec hash plus sorted source and asset records. A changed source changes the revision even when the spec text is unchanged.

The CLI preview command freezes inputs before rendering and writes `revisionSha256` to `render-manifest.json`. Code using the lower-level `render_preview()` function directly must verify inputs and supply the revision hash itself.
