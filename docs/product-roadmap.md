# Product completion plan

This is the ordered work list for a usable, general motion-production engine. A checkbox is complete only when the named exit gate is automated where possible and documented where a human or licensed application is required. The Signal Investment materials are a private acceptance fixture, never a branch in core code.

## 0. Foundation and repeatability

- [x] Publish public repository, MIT license, agent instructions, MotionSpec v1, synthetic fixtures, and CLI.
- [x] Ingest PDF, DOCX, text, CSV, and XLSX with source locations, hashes, and uncertainty reports.
- [x] Validate MotionSpec structure and core references; compile a frame plan and target capability report.
- [x] Render a silent, deterministic PNG/MP4 preview for text, rectangles, and bar/line charts.
- [x] Publish preview outputs atomically so failed renders cannot leave a partial deliverable.
- [x] Validate typed dataset cells and reject chart ranges that hide source values.
- [x] Pin Python development and build dependencies; verify Windows, Linux, and macOS on Python 3.11/3.12. [Six-job run](https://github.com/Navidbyti/motion-engine/actions/runs/35434480164).
- [x] Add CI on Windows, Linux, and macOS for schema, unit, integration, packaging, and synthetic media tests.
- [ ] Pin OS images, fonts, and codecs for pixel-identical media builds where required.
- [x] Add canonical MotionSpec serialization, verified local input hashes, revision hashes, and public compatibility fixtures.
- [ ] Add MotionSpec migrations before the first incompatible schema change.
- [x] Add a content-verified preview run manifest and safe local `--resume` behavior.
- [ ] Add a generic immutable artifact store and retry-safe jobs for every stage.

## 1. Source understanding and authoring

- [x] Extract embedded PDF images and detected tables with page coordinates where available; flag ambiguous reading order, unmatched image placements, and scans for OCR review.
- [ ] Extract DOCX headers, footers, drawing relationships, and tracked-change warnings.
- [x] Probe image, WAV, compressed-audio, and video headers with source hashes and stream locations; report missing FFprobe.
- [ ] Add full color-space and timecode interpretation, plus deep media validation beyond header metadata.
- [ ] Add OCR and language detection as optional providers with confidence and original-page evidence.
- [ ] Add a source-to-MotionSpec drafting workflow that requires citations for exact text, numbers, and claims.
- [ ] Add a review interface or structured review file for ambiguities, missing inputs, permissions, and approvals.
- [x] Add deterministic CSV/XLSX-to-dataset mapping with source ranges, formula-cache checks, and conservative numeric types.
- [ ] Add explicit unit interpretation and mappings for nonrectangular tables and decimal values beyond JSON number precision.

## 2. Generic scene composition and preview

- [x] Add local raster image assets with hash checks, fit/crop rules, and no silent substitution.
- [ ] Add vector assets/SVG and licensed font manifests; verify availability and glyph coverage.
- [ ] Add video plates with trimming, proxies, color conversion, and deterministic frame mapping.
- [ ] Add tables, cards, counters, scatter charts, icons, masks, and reusable compositions as tested primitives.
- [ ] Add scene transitions and a complete animation property/easing contract, with exact frame semantics.
- [x] Add explicit multiline text, opt-in space wrapping, overflow rejection, and libraqm-backed RTL preview.
- [ ] Add word breaking for scripts without spaces, rich text, glyph coverage checks, and locale-aware formatting.
- [ ] Add chart axes, ticks, labels, units, baseline rules, and exact-data visual conformance checks.
- [x] Add frame-placed mono PCM WAV tracks with exact sample alignment, deterministic mixing, and clipping rejection.
- [ ] Add compressed/stereo audio, background music workflows, fades, ducking, loudness controls, and audio QA.
- [ ] Add a performance path for long videos and high-resolution frames without changing deterministic output.

## 3. Adobe-native outputs

- [ ] Run a create/save/close/reopen compatibility spike on the selected installed versions of each Adobe app. After Effects 2024 (24.5x52), Illustrator 2024 (28.6.0), and Photoshop 2024 (25.9.1) passed on Windows on 2026-09-19. Premiere Pro remains.
- [ ] Build an After Effects adapter for editable comps, text, shapes, charts, timing, markers, and linked media.
- [x] Prove an initial editable After Effects text and rectangle subset on three public fixtures with app-level save/reopen checks; other primitives and automated execution remain.
- [x] Add composition markers for beat windows and verify marker comments, starts, and durations after native reopen.
- [x] Import hashed local PNG/JPEG images as linked After Effects footage, with fit rules and missing-link reopen checks.
- [ ] Build an Illustrator adapter for editable artboards, vector assets, type, and charts.
- [x] Prove an initial static Illustrator artboard subset with editable text and rectangles on two public fixtures, with native save/reopen checks.
- [ ] Build a Photoshop adapter for layered still assets, text, treatments, and links.
- [x] Prove an initial static Photoshop PSD subset with editable text and separate rectangle layers on two public fixtures, with native save/close/reopen checks.
- [ ] Build a Premiere Pro adapter for sequence tracks, cuts, markers, audio, and linked assets.
- [ ] Implement per-adapter capability negotiation and explicit fallback records before building.
- [ ] Verify every native file in its owning application after save and reopen; inspect structure and missing links.
- [ ] Version and test adapter behavior against supported app releases; document unsupported releases.

## 4. Voice and optional generation

- [ ] Ingest and transcribe voice with Whisper or an equivalent provider; retain word-level timestamps and confidence.
- [ ] Align narration to beats and flag mismatches, pauses, overruns, and unspoken scripted text.
- [ ] Provide a manual timing correction path and compare corrected alignments to original audio.
- [ ] Integrate optional image/video providers behind asset requests, consent, license, and provenance records.
- [ ] Review generated plates before use; never use generated pixels as the authority for exact charts or copy.

## 5. Quality assurance and delivery

- [x] Add an initial QA gate for input hashes, missing source references/assets, safe areas, disclosure timing, font substitutions, and render integrity.
- [x] Compare direct-copy chart columns with exact CSV/XLSX source cells and reject mismatches or missing mappings.
- [x] Verify explicit decimal arithmetic and rounding for derived/rebased chart values.
- [ ] Add broader transformation operators and check every claim citation.
- [ ] Build rendered QA for frame drops, blank frames, clipping, text overflow, and chart geometry beyond hash and frame-count checks.
- [ ] Build audio QA for duration, sync, silence, clipping, and loudness.
- [ ] Create contact sheets, review notes, and a gate that blocks unapproved critical findings.
- [ ] Package original hashes, MotionSpec, approvals, licenses, editable projects, final renders, and QA reports with relative links.
- [ ] Reopen the package on a clean machine and run dependency/link checks.
- [ ] Add accessibility and localization checks for reading order, subtitles/sidecars where requested, and target locales.

## 6. Productization and release

- [ ] Offer a documented local CLI workflow from inputs through final package, with resumable runs.
- [ ] Add the REST/job service and worker queue only after local stages have stable contracts.
- [ ] Add credential isolation, project access control, audit history, quotas, and storage retention for multi-user use.
- [ ] Publish a compatibility matrix, example projects, troubleshooting guide, and contributor setup.
- [ ] Release versioned installers or containers where licensing permits, plus signed source releases.

## Acceptance sequence

1. Public synthetic projects in at least two languages, aspect ratios, content types, and styles pass every relevant stage.
2. Negative fixtures prove missing assets, unsupported features, incorrect values, timing gaps, and text overflow fail clearly.
3. Native adapters pass app-level save/reopen checks on licensed workers.
4. The owner's private Signal Investment brief and workbook pass the separate 2,355-frame, 19-beat, seven-series acceptance run, including the four requested editable Adobe files and final video.
5. A fresh clone and clean-machine package can reproduce the documented supported outputs.

No finite test suite proves perfection. Release gates aim to make errors visible, reproducible, and blocking where accuracy matters.
