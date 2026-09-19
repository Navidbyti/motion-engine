# Codex continuation

This is the current technical handoff for a coding agent cloning this public repository. Read `AGENTS.md`, `README.md`, `MotionSpec.schema.json`, and `docs/product-roadmap.md` before changing code. The roadmap is the source of truth for completion; checked items describe only the tested subset named there.

## Current implementation

The Python CLI covers ingestion with source hashes/evidence, MotionSpec validation and planning, revisions and resumable preview runs, deterministic supported PNG/MP4 previews, data checks, structured source reviews, initial QA, and preview bundles. Public examples and negative tests are under `examples/` and `tests/`. Narrow After Effects, Illustrator, and Photoshop exporters have passed save/reopen tests on the installed 2024 apps; their unsupported features fail explicitly. Premiere 2024 passed an empty-project check. Premiere Pro 2026 (26.5.1) is now installed, and `adapters/premiere-uxp-probe/` has a UXP command that creates and verifies a one-clip, one-marker scratch project. Its code and mocks pass locally, but UXP Developer Tool is not yet installed and the command has **not** run in Premiere. No Premiere MotionSpec adapter exists. See `docs/compatibility.md` and `docs/adobe-adapters.md` for exact version and feature claims.

## Next engineering steps

1. Build the next unfinished generic contract in `docs/product-roadmap.md` with public fixtures and explicit unsupported behavior.
2. Load `adapters/premiere-uxp-probe/` in Premiere 2026 via UXP Developer Tool and get a native `PASS` report, fixing any API mismatches discovered in the app. Then add explicit sequence profile, more than one media type, and MotionSpec input. Do not advertise a Premiere target as buildable before native tests pass.
3. Extend the After Effects, Illustrator, and Photoshop adapters by primitive and verify native editability in the owning app after reopening.
4. Keep proprietary acceptance inputs and outputs outside the public repo. The private case is a conformance test, never the architecture's default.

Run `python -m pip install -e ".[dev]" -c requirements-dev.lock` and `python -m pytest` in a fresh clone. CI runs the supported OS/Python matrix. Check the most recent GitHub Action after pushing. Preserve exact source values and report uncertainty instead of filling gaps with generated data.
