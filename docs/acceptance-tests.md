# Acceptance tests

## Public core gates

1. `examples/hello.motion.json` (English, 16:9, text) and `examples/weather.motion.json` (Arabic, 1:1, data chart) validate against the same schema and semantic checker.
2. IDs and source, asset, dataset, element, beat, animation, and disclosure references resolve. Scene and beat ranges use integer frames, are contiguous when present, and stay within canvas duration.
3. Invalid examples fail with actionable errors for duplicate IDs, missing sources, wrong data bindings, unsupported element kinds, non-monotonic keyframes, and unfulfilled editability requirements.
4. A source parser preserves hashes and page, sheet, or line locators (timecode begins with audio/video ingestion). It reports uncertainty and never executes document text as instructions. PDF pages without text request OCR/visual review; spreadsheet formulas without cached results request recalculation rather than using blank as zero.
5. Exact text and chart data survive `source → MotionSpec → plan → output` without model-generated substitution. Localization policies are per project or text element.

## Adapter and media gates

6. A target capability plan lists supported and unsupported primitives/properties before build; unsupported required features stop or create an explicit reviewable fallback.
7. Rendered video frame count equals MotionSpec duration; audio is free of clipping; visual QA checks black frames, overflow, missing assets, and disclosures.
8. Each Adobe file is reopened in its owning application and inspected for named editable layers/tracks, correct timing, online assets, and saved version. Never accept file existence alone.
9. Package includes MotionSpec, original-source hashes, asset licenses/provenance, native files, render, QA report, and relative links.

## Private acceptance

See [private fixture instructions](private-fixtures.md). The owner's private test is a **separate** conformance run: 78.5 seconds at 30 fps; 19 beats on six slides; 11 annual points for seven nominal and USD-rebased series; two hard chart-format cuts; accurate year winners; locale-specific digits and full-duration disclosure; an editable AEP, PRPROJ, PSD, and AI; and a final render. Other public examples must continue to work without fixture-specific logic.
