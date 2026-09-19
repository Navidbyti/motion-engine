# Codex continuation

This is the current technical handoff for a coding agent cloning this public repository. Read `AGENTS.md`, `README.md`, `MotionSpec.schema.json`, and `docs/product-roadmap.md` before changing code. The roadmap is the source of truth for completion; checked items describe only the tested subset named there.

## Current implementation

The Python CLI covers ingestion with source hashes/evidence, MotionSpec validation and planning, revisions and resumable preview runs, deterministic supported PNG/MP4 previews, data checks, structured source reviews, initial QA, and preview bundles. Public examples and negative tests are under `examples/` and `tests/`. Narrow After Effects, Illustrator, and Photoshop exporters have passed save/reopen tests on the installed 2024 apps; their unsupported features fail explicitly. The Premiere 2024 empty project passed a manual create/save/close/reopen check, but no Premiere sequence adapter exists. See `docs/compatibility.md` and `docs/adobe-adapters.md` for exact version and feature claims.

## Next engineering steps

1. Build the next unfinished generic contract in `docs/product-roadmap.md` with public fixtures and explicit unsupported behavior.
2. For Premiere 25.6 or newer, prove UXP project creation, hashed media import, sequence creation, track insertion, beat marker timing, and save/close/reopen before advertising a Premiere target as buildable. Adobe introduced Premiere UXP after 24.x; keep the older CEP/ExtendScript or interchange route separate until tested.
3. Extend the After Effects, Illustrator, and Photoshop adapters by primitive and verify native editability in the owning app after reopening.
4. Keep proprietary acceptance inputs and outputs outside the public repo. The private case is a conformance test, never the architecture's default.

Run `python -m pip install -e ".[dev]" -c requirements-dev.lock` and `python -m pytest` in a fresh clone. CI runs the supported OS/Python matrix. Check the most recent GitHub Action after pushing. Preserve exact source values and report uncertainty instead of filling gaps with generated data.
