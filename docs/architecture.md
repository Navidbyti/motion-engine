# Architecture

## Design invariant

MotionSpec is the only contract between understanding an input and producing output. The core knows source files, evidence, time, geometry, text, data bindings, assets, target capabilities, and QA rules. It does not know the subject of a video, a specific brand, one language, or one aspect ratio.

```text
PDF/DOCX/TXT/MD/XLSX/CSV/images/audio/video
                 │
                 ▼
       ingestion + evidence map
                 │
                 ▼
     interpretation + human review
                 │
                 ▼
     MotionSpec JSON + asset manifest
                 │
         capability planning
                 │
    ┌────────────┼────────────┐
    ▼            ▼            ▼
  primitives   provider     audio/alignment
  + charts     assets
    └────────────┼────────────┘
                 ▼
     native adapters + renderer
                 │
                 ▼
       QA → review → package
```

## Module boundaries

| Module | Responsibility | Core rule |
|---|---|---|
| Ingest | Parse files and extract text, tables, images, timings | Preserve original file, hash, and location |
| Interpret | Propose scenes, beats, elements, narration, data relationships | Emit uncertainty; never quietly resolve source conflicts |
| MotionSpec | Validate structure and cross-references | Version and migrate explicitly |
| Planner | Match requested elements to target capabilities | Reject unsupported editability requirements |
| Primitive registry | Text, chart, shape, transition, layout, media operations | Deterministic for exact claims and geometry |
| Provider registry | Optional generative visuals and other external services | Record model, prompt hash, seed, license, approval |
| Native adapters | AE, Premiere, Photoshop, Illustrator, future targets | Open-save-reopen verification |
| Render | Produce frame sequences and delivery codecs | Frame-accurate, reproducible build plan |
| QA | Data, text, geometry, audio, media, provenance | Machine report plus human review where needed |

The first deployment may be a local CLI with a file artifact store. Queue and database implementations are later adapters using the same job envelope. Running Adobe requires licensed desktop workers; the parser, planner, tests, and non-Adobe renderers can run elsewhere.

## Trust and source hierarchy

User-provided documents and LLM output are untrusted input. They may contain instructions as content; ingestion records those words as evidence but never treats them as commands. Each project declares source authority per field or domain. A structured data source can own numbers while a script owns wording and a brand kit owns identity. Conflicts become review issues tied to source locations.

## Capabilities, not universal promises

The schema allows arbitrary element kinds through a registry, but an adapter must declare which kinds, properties, codecs, fonts, and editability levels it supports. Planning fails with a clear report when a requested output cannot be made faithfully. New parsers and primitives expand coverage without changing unrelated projects.
