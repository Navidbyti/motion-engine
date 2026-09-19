# Ingestion in M1

Run `motion-engine ingest PATH --output evidence.json`. Supported extensions: `.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.xlsx`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.wav`, `.mp3`, `.m4a`, `.mp4`, `.mov`, and `.mkv`. `--source-id` overrides the generated ID. `--limit` sets the maximum number of evidence records; exceeding it fails instead of silently truncating.

Output is `{source, evidence, issues, recordCount}`. `source` includes media type and SHA-256. Each evidence item has `sourceId`, `location`, `kind`, `value`, `method`, and `confidence`. Sheet names and cell coordinates, PDF page/line/word/table/image, DOCX block/table coordinates, CSV cells, or plain-text line numbers form locations. The extractor is deliberately non-semantic: words such as “ignore previous instructions” remain source text, not a command.

| Format | Method | Important limitation |
|---|---|---|
| TXT/Markdown | UTF-8 lines | Other encodings need a new parser or preconversion |
| CSV | UTF-8 CSV cells and headers | Requires unique nonblank headers and equal-width rows |
| PDF | pypdf text lines; pdfplumber word boxes, detected table cells, and image regions in top-left PDF-point coordinates | Reading order and detected table boundaries require visual review; image regions are located but their contents are not interpreted; pages without extractable text request OCR |
| DOCX | paragraphs and tables in document body order | Headers, footers, drawings, and tracked-change review are later work |
| XLSX | openpyxl values and formula strings | Formula results are cached values only; missing cache is flagged, never recalculated by this parser |
| PNG/JPEG/WebP | Pillow headers | Dimensions, mode, frame count, EXIF orientation, and ICC hash; not OCR or object recognition |
| WAV | Python wave header | Exact sample count, sample rate, channels, and rational duration for supported WAV files |
| MP3/M4A/MP4/MOV/MKV | FFprobe JSON | Stream codec, dimensions, rational frame-rate string, sample rate, channels, and duration when present; missing FFprobe produces an explicit issue |

Parsers never fetch external links, execute macros, or rewrite the source. They can be registered by extension through `register_parser`. OCR, embedded image export, waveform/word timing, and visual interpretation remain later work.
