# Implementation milestones

| Milestone | Result | Exit gate |
|---|---|---|
| M0, repository (done) | General schema, CLI, synthetic fixtures, docs, license | Public clone installs; both fixtures validate; no private files |
| M1, ingestion and planning (done) | PDF/DOCX/text/CSV/XLSX extractors, evidence map, frame plan, capability registry | Synthetic source files retain locations; two unrelated fixtures produce valid plans; built-in targets honestly report planned |
| M2, deterministic rendering | Text, shapes, charts, transitions, data binding, FFmpeg preview | Public fixtures render at exact frame counts; values match sources |
| M3, native Adobe | AE, Illustrator, Photoshop, Premiere adapters | Every requested file opens, saves, reopens, and stays editable |
| M4, voice and optional assets | Whisper alignment, audio mix, provider manifest | Timed voice and approved assets reproduce from hashes |
| M5, QA and package | Automated reports, visual review, portable archive | Data, language, timing, media, and native reopen gates pass |
| M6, private acceptance | Owner-supplied reel and workbook kept outside Git | 19 beats, 2,355 frames, seven exact series, locale-specific text/disclosures, four native projects and final render |

Build M1 before promising arbitrary documents. The extension contracts make the architecture general; actual format and visual coverage grows through tested implementations. The private fixture tests the harder end of the range but must never become a special-case code path.
