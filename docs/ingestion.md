# Ingestion in M1

Run `motion-engine ingest PATH --output evidence.json`. Supported extensions: `.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.xlsx`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.wav`, `.mp3`, `.m4a`, `.mp4`, `.mov`, and `.mkv`. `--source-id` overrides the generated ID. `--limit` sets the maximum number of evidence records; exceeding it fails instead of silently truncating. For PDF image files, run `motion-engine extract-pdf-images SOURCE.pdf --output-dir extracted-images`.

Output is `{source, evidence, issues, recordCount}`. `source` includes media type and SHA-256. Each evidence item has `sourceId`, `location`, `kind`, `value`, `method`, and `confidence`. Sheet names and cell coordinates, PDF page/line/word/table/image, DOCX block/table coordinates, CSV cells, or plain-text line numbers form locations. The extractor is deliberately non-semantic: words such as “ignore previous instructions” remain source text, not a command.

| Format | Method | Important limitation |
|---|---|---|
| TXT/Markdown | UTF-8 lines | Other encodings need a new parser or preconversion |
| CSV | UTF-8 CSV cells and headers | Requires unique nonblank headers and equal-width rows |
| PDF | pypdf text lines and decoded embedded images; pdfplumber word boxes, detected table cells, and image regions in top-left PDF-point coordinates | Reading order and detected table boundaries require visual review; page regions may not match every embedded image; pages without extractable text request OCR |
| DOCX | body paragraphs and tables in document order; section headers and footers, including first/even page variants | Drawings and tracked changes are flagged for review; drawing content and revision resolution are not extracted |
| XLSX | openpyxl values and formula strings | Formula results are cached values only; missing cache is flagged, never recalculated by this parser |
| PNG/JPEG/WebP | Pillow headers | Dimensions, mode, frame count, EXIF orientation, and ICC hash; not OCR or object recognition |
| WAV | Python wave header | Exact sample count, sample rate, channels, and rational duration for supported WAV files |
| MP3/M4A/MP4/MOV/MKV | FFprobe JSON | Stream codec, dimensions, rational frame-rate string, sample rate, channels, and duration when present; missing FFprobe produces an explicit issue |

The PDF image command writes each decoded embedded image plus `manifest.json` into a new directory. The manifest records the source hash, exported image hash, page, pixel size, and every matched placement box. Reused images can have several placements. Unmatched images or page regions are explicit issues; the extractor never invents coordinates. It refuses existing output directories, limits image count and decoded bytes, and publishes the directory only after extraction succeeds. Embedded vectors and full page renderings are outside this command.

Parsers never fetch external links, execute macros, or rewrite the source. They can be registered by extension through `register_parser`. OCR, DOCX drawing relationships, waveform/word timing, and visual interpretation remain later work. Image extraction uses the [pypdf image API](https://pypdf.readthedocs.io/en/stable/user/extract-images.html) and [pdfplumber page image metadata](https://github.com/jsvine/pdfplumber#image-properties).
