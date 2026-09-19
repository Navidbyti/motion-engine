# Motion Engine

An open-source, implementation-ready design for turning scripts, documents, data, audio, and assets into editable motion projects and rendered videos. The architecture is **input-agnostic**: a complex private reel is one acceptance case, not the product model.

## Status

This repository is a **build specification and early implementation**, not a finished production engine. It contains a general MotionSpec schema, source extractors, validation and planning commands, a deterministic visual preview renderer, adapter contracts, synthetic examples, tests, and implementation milestones. Native Adobe project generation is a future milestone. Do not describe the repository as producing `.aep`, `.prproj`, `.psd`, or `.ai` until those adapters pass native-app reopen tests.

## What goes in and comes out

Inputs may include PDF, DOCX, Markdown, TXT, CSV, XLSX, images, SVG, audio, video, and brand assets. Ingestion extracts evidence with source locations; a human or LLM drafts MotionSpec; validators and reviewers approve it; provider adapters build assets; native adapters produce editable projects; render and QA workers produce final media. New input parsers, design primitives, renderers, and model providers are registered behind interfaces rather than added as special cases in core code.

```text
sources → evidence → MotionSpec → plan → assets + native projects → render → QA → package
```

The core makes no assumption about language, script direction, subject matter, aspect ratio, chart type, provider, or creative style. A target adapter may report that a requested feature is unsupported; it must not silently flatten or omit it.

## Prerequisites

### To read, validate, and develop the core

- Git.
- Python 3.11 or newer. Python 3.11 and 3.12 are verified in CI. Install the tested development set with `python -m pip install -e ".[dev]" -c requirements-dev.lock`.
- Node.js 20 or newer for the planned TypeScript/Adobe adapters.
- FFmpeg and FFprobe on `PATH` for media probing, proxies, audio, and exports.
- Poppler for PDF rendering/inspection (optional for the initial CLI, required for PDF visual QA).

### To build native Adobe outputs

- A licensed, supported installation of **After Effects**, **Premiere Pro**, **Photoshop**, and **Illustrator** on a Windows or macOS worker. Use only the applications needed for selected targets.
- `aerender` supplied with After Effects for automated AE renders.
- Fonts required by each project and rights to use any assets. Right-to-left projects need an appropriate installed font and native-app visual review.
- Native adapter versions must be pinned and verified against the installed Adobe versions; see [Adobe contract](docs/adobe-adapters.md).

### Optional integrations

- Whisper or a compatible speech aligner for voice timing.
- Higgsfield credentials for generated image/video plates. They are optional and never needed for exact data, text, charts, or logos.
- PostgreSQL and object storage for multi-worker operation. The first implementation can run locally with file artifacts.

Do not commit API keys, licensed fonts, model weights, customer inputs, or Adobe binaries. This repository does not distribute Adobe products or third-party services.

## Start here

```bash
git clone https://github.com/Navidbyti/motion-engine.git
cd motion-engine
python -m pip install -e ".[dev]" -c requirements-dev.lock
motion-engine validate examples/hello.motion.json
motion-engine inspect examples/hello.motion.json
motion-engine ingest examples/assets/hello-script.md --output evidence.json
motion-engine plan examples/hello.motion.json --output plan.json
motion-engine freeze examples/hello.motion.json --output revision.json
motion-engine render examples/hello.motion.json --output-dir hello-preview
motion-engine render examples/hello.motion.json --output-dir hello-preview --resume
motion-engine render examples/image-card.motion.json --output-dir image-card-preview
python -m pytest
```

The CLI validates and inspects MotionSpec, checks typed dataset cells and chart ranges, extracts evidence from PDF/DOCX/TXT/Markdown/CSV/XLSX, and produces a frame plan with target capability status. It can render silent MP4 previews for text, rectangles, local raster images, bar charts, and line charts. Other elements and voice audio fail explicitly. Adobe output adapters remain planned. See [ingestion](docs/ingestion.md), [planning](docs/planning.md), [preview rendering](docs/rendering.md), and [milestones](docs/milestones.md).

## Give this repository to a coding agent

Open the repository in your coding agent and use this prompt:

> Read AGENTS.md, MotionSpec.schema.json, and docs/milestones.md. Implement M2 in small commits. Keep the core independent of the example subject, language, aspect ratio, and provider. Run the tests and add conformance tests for each new adapter. Do not claim native outputs until they open and remain editable in the owning application.

`AGENTS.md` is the persistent engineering contract. [Architecture](docs/architecture.md), [service contracts](docs/contracts.md), [verified revisions](docs/revisions.md), [preview runs](docs/runs.md), [extension API](docs/extensions.md), [compatibility](docs/compatibility.md), and [acceptance tests](docs/acceptance-tests.md) give agents the rest of the build instructions.

The [product completion plan](docs/product-roadmap.md) lists every remaining workstream and the release gates in build order.

## Examples and private acceptance test

`examples/hello.motion.json`, `examples/weather.motion.json`, and `examples/image-card.motion.json` are synthetic and public. A separate owner-supplied brief, workbook, and derived spec remain outside the public repository as a **private acceptance fixture** for a 78.5-second right-to-left video with 19 beats, exact charts, and editable Adobe outputs. See [private fixture instructions](docs/private-fixtures.md). The core must pass public fixtures in other formats and languages too.

## License

MIT for original code and documentation in this repository. Input media and assets retain their owners' licenses. See [LICENSE](LICENSE).
