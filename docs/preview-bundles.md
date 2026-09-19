# Portable preview bundles

After rendering, run `motion-engine package-preview SPEC --render-dir DIR --output-dir BUNDLE`. The command validates the MotionSpec, verifies source and available-asset hashes, verifies the render manifest and every frame, runs QA, and creates a new directory atomically. It refuses to overwrite an existing bundle, package a failed QA result, or claim any required native deliverable is present. A required MP4 must exist in the render.

The bundle contains `project/` with the original MotionSpec and its relative source and asset paths, `render/` with the verified frame sequence and optional WAV mix and MP4, `revision.json`, `qa-report.json`, and `package-manifest.json`. Every non-manifest file has a SHA-256 in the package manifest. Run `motion-engine verify-package BUNDLE` after copying it to another machine to check file hashes, input revision, and render integrity. A `needs_review` QA status stays visible in the package; it is not final approval.

This command creates a preview review artifact. It does not create Adobe files, include licensed dependencies that are absent from the spec, or certify final delivery. The final package stage will require approved QA, native app reopen checks, audio checks, and all required deliverables.
