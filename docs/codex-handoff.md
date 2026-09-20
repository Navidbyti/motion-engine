# Codex continuation

This is the current technical handoff for a coding agent cloning this public repository. Read `AGENTS.md`, `README.md`, `MotionSpec.schema.json`, and `docs/product-roadmap.md` before changing code. The roadmap is the source of truth for completion; checked items describe only the tested subset named there.

## Current implementation

The Python CLI covers ingestion with source hashes/evidence, MotionSpec validation and planning, revisions and resumable preview runs, deterministic supported PNG/MP4 previews, data checks, structured source reviews, initial QA, and preview bundles. Public examples and negative tests are under `examples/` and `tests/`. Narrow After Effects, Illustrator, and Photoshop exporters have passed save/reopen tests on the installed 2024 apps; their unsupported features fail explicitly. Premiere 2024 passed an empty-project check. A narrow MotionSpec-to-Final Cut Pro 7 XML exporter passed native Premiere Pro 2026 (26.5.1) import, save/reopen, and H.264 export for a silent two-scene fixture. `adapters/premiere-uxp-probe/` is optional and has not run in Premiere. See `docs/compatibility.md` and `docs/adobe-adapters.md` for exact version and feature claims.

## Next engineering steps

1. Build the source-to-MotionSpec drafting workflow with citations for exact text, numbers, and claims. Use public fixtures unrelated to the private acceptance case, require review of uncertainty, and fail explicitly when source evidence is missing. This is the largest gap in the promised arbitrary-input workflow.
2. Premiere development currently uses Final Cut Pro 7 XML interchange, which requires no plugin installation. The silent two-scene fixture passed native import, save/reopen, and export in Premiere 2026; extend the XML path only where broader fixture import fidelity passes. The UXP probe is optional and remains unverified.
3. Extend the After Effects, Illustrator, and Photoshop adapters by primitive and verify native editability in the owning app after reopening.
4. Keep proprietary acceptance inputs and outputs outside the public repo. The private case is a conformance test, never the architecture's default.

Run `python -m pip install -e ".[dev]" -c requirements-dev.lock` and `python -m pytest` in a fresh clone. CI runs the supported OS/Python matrix. Check the most recent GitHub Action after pushing. Preserve exact source values and report uncertainty instead of filling gaps with generated data.
