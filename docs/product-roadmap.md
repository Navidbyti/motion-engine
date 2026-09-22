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

- [ ] Build the complete prompt-to-first-draft production loop in [creative-workflow.md](creative-workflow.md): understand, research, direct, execute, inspect, and revise by scene ID.
- [x] Add a first whole-video director slice: a desktop-agent-authored plan, capability-checked MotionSpec compilation, and one-command preview rendering for creative text/shape/supplied-asset briefs. Factual research remains unverified.
- [x] Make the director declare unmet visual asset requests and stop compilation until the required shot exists; do not silently substitute an unrelated primitive.
- [x] Resolve image, moving-video, and declared 3D shot requests against approved, licensed, hashed local assets before compilation; visual suitability still needs inspection.
- [x] Build portable image and frame-plate catalogs from agent-reviewed local manifests, with automatic hashes and media checks.
- [ ] Verify researched claims against stored evidence spans and dates, including checks that challenge a prompt's premise before narration is written.
- [x] Add a local claim ledger with source hashes, exact excerpt checks, event/publication/retrieval dates, scene-to-claim mapping, and an explicit semantic-review warning. Truth assessment and reviewed factual release remain open.
- [x] Invalidate stale claim mappings after factual text edits and support hash-checked scene claim remapping in a scoped revision.
- [x] Add hash-bound typed scene revisions for text, color, and image zoom; preserve unrelated scenes and cite the revision request.
- [x] Add a desktop-agent-authored typed-revision route for scene text, color, and visual zoom, followed by a version-bound render. Broader edit types remain open.
- [x] Add scoped image/video shot replacement with approved local assets, hash and frame checks, provenance, and a version-bound render. Scene insertion and asset generation remain open.
- [x] Add hash-bound bounds and opacity edits for visual elements, including same-scene multi-operation revisions and invalid geometry/keyframe rejection.
- [x] Add scoped audio gain edits with exact revision provenance and rendered sample comparison.
- [x] Add preview x/y position tracks, desktop-agent slide entrances, and scoped position-keyframe edits with frame and canvas bounds checks.
- [x] Add a reusable contrast-aware card layout to the desktop director, verified on horizontal and vertical public fixtures.
- [x] Add a staggered rise-and-fade text entrance on frame-based tracks, verified on two public aspect ratios.
- [x] Add explicit shot, reel, and explainer pacing profiles with editor-authored entry, hold, and exit windows; script needs determine scene count and duration.
- [x] Add directional whip entrances with overshoot and settle, plus deterministic horizontal and vertical two-color scene backgrounds.
- [x] Let desktop director plans attach exact narration text to approved scene-length WAV assets, resolve pending audio requests, and render the synchronized track into the first-draft MP4. Transcription and word alignment remain open.
- [x] Let a director plan select an explicit font family; two static card plans rendered complete previews and passed native After Effects save/reopen checks on horizontal and vertical fixtures. Font coverage remains open.
- [x] Preserve director `rise`, `slide`, and eased opacity motion in editable After Effects projects through exact integer-frame sampling; horizontal and vertical plans passed native save/reopen key checks. Font coverage remains open.

- [x] Extract embedded PDF images and detected tables with page coordinates where available; flag ambiguous reading order, unmatched image placements, and scans for OCR review.
- [x] Extract DOCX headers, footers, embedded image relationships, and tracked-change warnings. Drawing placement and appearance still require visual review.
- [x] Probe image, WAV, compressed-audio, and video headers with source hashes and stream locations; report missing FFprobe.
- [ ] Add full color-space and timecode interpretation, plus deep media validation beyond header metadata.
- [ ] Add OCR and language detection as optional providers with confidence and original-page evidence.
- [ ] Add a source-to-MotionSpec drafting workflow that requires citations for exact text, numbers, and claims.
- [x] Prove a literal text drafting subset: each UTF-8 line becomes a cited MotionSpec scene, validates, and renders to MP4 on two public language/aspect fixtures. This does not interpret briefs, tables, or creative intent.
- [x] Add a structured source review file for ambiguities, missing inputs, permissions, and approvals, with source-bound IDs and explicit resolutions. Human identity and rights remain producer checks.
- [x] Add deterministic CSV/XLSX-to-dataset mapping with source ranges, formula-cache checks, and conservative numeric types.
- [x] Connect imported CSV/XLSX fragments to source-checked bar and line scenes in the desktop director. Rich axes, labels, and unit formatting remain open.
- [ ] Add explicit unit interpretation and mappings for nonrectangular tables and decimal values beyond JSON number precision.

## 2. Generic scene composition and preview

- [x] Render stable scene IDs as independent, hash-bound review modules with exact global-frame semantics and selective scene requests.
- [x] Assemble a verified full timeline from compatible cached modules and newly rendered scene modules; reject stale, tampered, missing, or disagreeing candidates before publishing output.
- [x] Generate a portable local review interface with the assembled preview, independently playable scene modules, visible copy and timing, stable IDs, and copyable scene edit prompts.
- [ ] Add active agent-session integration so submitting a scene prompt from the review interface can route directly to the current desktop coding-agent task.
- [ ] Add a dependency-scoped cache index so unrelated asset and dataset changes do not conservatively invalidate every scene module.

- [x] Add frame-exact, bounded image scale keyframes for slow zooms, tested on two public project shapes; moving 3D subjects still require a video or 3D source.
- [x] Add frame-exact clockwise 2D rotation for image and video plates, typed prompt revisions, and editable linked-image Rotation tracks; 25 eased keys passed native save/reopen verification in After Effects 2024 24.5x52 on Windows on 2026-09-21.

- [x] Add local raster image assets with hash checks, fit/crop rules, and no silent substitution.
- [ ] Add vector assets/SVG and licensed font manifests; verify availability and glyph coverage.
- [ ] Add video plates with trimming, proxies, color conversion, and deterministic frame mapping.
- [x] Add a hashed PNG-frame video proxy with exact frame mapping, explicit source trim, FFmpeg import, and two public aspect-ratio fixtures. Native media import, broad color management, and performance remain open.
- [ ] Add tables, cards, counters, scatter charts, icons, masks, and reusable compositions as tested primitives.
- [x] Add a structured animated counter with finite numeric tracks, deterministic precision and affixes, safe-area QA, and horizontal/vertical director tests. Broader locale and source binding remain open.
- [ ] Add scene transitions and a complete animation property/easing contract, with exact frame semantics.
- [x] Add a deterministic nonoverlapping scene fade through the project background, verified on horizontal and vertical plans. Overlapping transitions and audio fades remain open.
- [x] Add explicit multiline text, opt-in space wrapping, overflow rejection, and libraqm-backed RTL preview.
- [ ] Add word breaking for scripts without spaces, rich text, glyph coverage checks, and locale-aware formatting.
- [ ] Add chart axes, ticks, labels, units, baseline rules, and exact-data visual conformance checks.
- [x] Render chart category labels, bounded value ticks, explicit units, final values, and positive/negative zero baselines. Automated pixel-level geometry conformance remains open.
- [x] Add frame-placed mono PCM WAV tracks with exact sample alignment, deterministic mixing, and clipping rejection.
- [x] Let director plans place multiple approved sound-effect WAV cues at exact scene-relative frames with independent gain.
- [x] Add project-length background music with exact source offsets, first/last fades, audio roles, and scene-level ducking under narration.
- [ ] Add compressed/stereo audio, speech-activity ducking, loudness controls, and broader audio QA.
- [ ] Add a performance path for long videos and high-resolution frames without changing deterministic output.

## 3. Adobe-native outputs

- [x] Run a create/save/close/reopen compatibility spike on the selected installed versions of each Adobe app. After Effects 2024 (24.5x52), Illustrator 2024 (28.6.0), Photoshop 2024 (25.9.1), and Premiere Pro 2024 (24.5.0.57) passed basic project checks on Windows on 2026-09-19. Adapter feature checks remain separate.
- [ ] Build an After Effects adapter for editable comps, text, shapes, charts, timing, markers, and linked media.
- [x] Prove an initial editable After Effects text and rectangle subset on three public fixtures with app-level save/reopen checks; other primitives and automated execution remain.
- [x] Add composition markers for beat windows and verify marker comments, starts, and durations after native reopen.
- [x] Import hashed local PNG/JPEG images as linked After Effects footage, with fit rules and missing-link reopen checks.
- [x] Preserve linear x/y position keyframes as editable After Effects Position tracks; save/reopen passed on landscape and two-scene vertical public fixtures in After Effects 2024 24.5x52.
- [x] Generate editable After Effects Scale tracks for linked still images with contain/stretch base-scale preservation and reopen assertions; a 25-key eased Scale track passed native save/reopen verification in After Effects 2024 24.5x52 on Windows on 2026-09-21.
- [x] Preserve stable MotionSpec `zIndex` stacking in After Effects; reordered landscape and vertical public fixtures passed native save/reopen checks.
- [x] Create editable After Effects paragraph text boxes for `wrap: true`; landscape and vertical fixtures passed native save/reopen geometry checks. Visual text flow review remains open.
- [ ] Build an Illustrator adapter for editable artboards, vector assets, type, and charts.
- [x] Prove an initial static Illustrator artboard subset with editable text and rectangles on two public fixtures, with native save/reopen checks.
- [ ] Build a Photoshop adapter for layered still assets, text, treatments, and links.
- [x] Prove an initial static Photoshop PSD subset with editable text and separate rectangle layers on two public fixtures, with native save/close/reopen checks.
- [ ] Build a Premiere Pro adapter for sequence tracks, cuts, markers, audio, and linked assets.
- [x] Add a first Final Cut Pro 7 XML interchange exporter from a verified preview run, with contiguous scene cuts, beat markers, and explicit unsupported-audio errors. The public two-scene fixture passed native Premiere Pro 2026 import, save/reopen, post-reopen timeline and visual inspection, and 120-frame H.264 export on 2026-09-20; broader fixture coverage remains.
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
- [x] Add paginated, revision-bound scene contact sheets with first/middle/final frames for agent and producer review.
- [ ] Build audio QA for duration, sync, silence, clipping, and loudness.
- [x] Check rendered mono WAV mix format and frame-derived duration; flag silence and near-clipping. Loudness and narration sync remain open.
- [ ] Create contact sheets, review notes, and a gate that blocks unapproved critical findings.
- [ ] Package original hashes, MotionSpec, approvals, licenses, editable projects, final renders, and QA reports with relative links.
- [ ] Reopen the package on a clean machine and run dependency/link checks.
- [ ] Add accessibility and localization checks for reading order, subtitles/sidecars where requested, and target locales.

## 6. Productization and release

- [x] Add a repository-owned desktop-agent production skill that routes Codex or Claude through research, complete planning, asset approval, first-draft rendering, scoped revisions, QA, and supported native exports without an LLM API key.
- [x] Add one-command first-draft and revision review bundles containing verified inputs, preview media, QA, and revision-bound contact sheets.
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
