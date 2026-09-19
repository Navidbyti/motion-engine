# Ingestion in M1

Run `motion-engine ingest PATH --output evidence.json`. Supported extensions: `.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.xlsx`. `--source-id` overrides the generated ID. `--limit` sets the maximum number of evidence records; exceeding it fails instead of silently truncating.

Output is `{source, evidence, issues, recordCount}`. `source` includes media type and SHA-256. Each evidence item has `sourceId`, `location`, `kind`, `value`, `method`, and `confidence`. Sheet names and cell coordinates, PDF page and line, DOCX block/table coordinates, CSV cells, or plain-text line numbers form locations. The extractor is deliberately non-semantic: words such as “ignore previous instructions” remain source text, not a command.

| Format | Method | Important limitation |
|---|---|---|
| TXT/Markdown | UTF-8 lines | Other encodings need a new parser or preconversion |
| CSV | UTF-8 CSV cells and headers | Requires unique nonblank headers and equal-width rows |
| PDF | pypdf extractable text by page and line | Scans, figures, and visually laid-out tables need OCR or layout review later |
| DOCX | paragraphs and tables in document body order | Headers, footers, drawings, and tracked-change review are later work |
| XLSX | openpyxl values and formula strings | Formula results are cached values only; missing cache is flagged, never recalculated by this parser |

Parsers never fetch external links, execute macros, or rewrite the source. They can be registered by extension through `register_parser`. M2 will add richer evidence types, OCR, visual extraction, and media timecodes while retaining the same provenance envelope.
