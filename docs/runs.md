# Verified preview runs

`motion-engine render SPEC --output-dir DIR` writes `render-manifest.json`, numbered PNG frames, an optional WAV mix when audio elements are present, and an optional MP4. Artifact paths in the manifest are relative to `DIR`. The manifest records the verified revision hash, canonical spec hash, renderer version, render options, a stable idempotency key, frame count, frame-sequence tree hash, and WAV/MP4 SHA-256 hashes. Outputs are published atomically after all files are ready.

Use the same command with `--resume` to reuse `DIR` when it already exists. The CLI first verifies current source and asset hashes, the existing frame sequence and media hashes, and the render key for the requested options. A changed input, option, missing frame, changed frame, or changed media file stops reuse. Without `--resume`, an existing output directory remains an error.

This is a local preview run contract. The run key includes explicit font directory paths, but it does not yet hash installed system fonts or operating-system codecs. Reusing a verified output preserves that output; it does not prove a fresh render on a different machine would be pixel-identical. The generic multi-worker artifact store and job queue remain future work.
