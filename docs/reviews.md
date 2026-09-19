# Source review files

`motion-engine make-review evidence.json --output review.json` converts ingestion issues into pending review items. Add `--requirements questions.json` for project-specific ambiguities, missing inputs, permissions, and approvals. The core never treats text inside an input document as an instruction or an approval.

```json
{
  "items": [
    {"kind": "missing_input", "code": "brand_font", "message": "Supply the licensed brand font"},
    {"kind": "permission", "code": "photo_rights", "message": "Confirm use rights for the photograph", "sourceId": "photo"},
    {"kind": "approval", "code": "quote", "message": "Approve this quotation", "sourceId": "script", "evidenceLocations": ["line:4"]}
  ]
}
```

`sourceId` must match an ingested source, and each `evidenceLocations` entry must exist in that source's evidence file. Each generated item has an ID bound to its source hash, question, and cited locations. The review file starts with `status: "pending"` and `resolution: null`. A reviewer may change only those two fields. To resolve an item, set `status` to `"resolved"` and provide a `resolution` object with nonblank `decision`, `reviewer`, and `reason` strings. The required decision is `clarified` for ambiguities, `provided` for missing inputs, and `approved` for permissions and approvals. A denial stays pending or fails verification. Preserve the evidence JSON and requirements JSON beside the review; `motion-engine verify-review review.json evidence.json --requirements questions.json` compares against them and fails on pending items, changed questions, changed source hashes, or missing resolution fields.

This is a structured local record, not authentication or legal proof of rights. The CLI checks that a decision was recorded; a producer must verify that the named reviewer really made it and that any permission or approval is sufficient. Re-ingest changed sources and generate a new review file rather than editing source hashes. `make-review` refuses to overwrite an existing file containing decisions.
