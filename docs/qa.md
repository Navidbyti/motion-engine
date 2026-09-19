# Initial QA gate

Run `motion-engine qa SPEC --output qa.json` for source and policy checks. Add `--render-dir DIR` to verify an existing preview's revision, frame sequence, MP4 hash, frame count, and renderer warnings. The command returns a report with `passed`, `needs_review`, or `failed` status. Only `passed` exits successfully.

Implemented checks include source and available-asset hashes, referenced asset availability, dataset source references, exact direct-copy chart values from CSV/XLSX, text-element bounds against the declared safe area, and full-duration disclosure timing when requested by policy. A rendered preview is checked against the current MotionSpec and source revision. Font substitution appears as a review issue.

For `chart.data_exact`, a direct-copy dataset declares `transform.columnSources` for every column. Each entry names a `sourceId` cited in `sourceRefs` and an exact one-column range such as `B2:B4` for CSV or `'Sheet'!B2:B4` for XLSX. Row count and each value must match the source cells. Formula cells require cached results. Derived or rebased values need a deterministic transform contract before they can pass this check.

Policy rules that need a human (`text.visual_review`) or have not been implemented remain visible and block a clean pass. This gate does not yet inspect native Adobe files, detect every visual flaw, or test audio. A `spec_only` pass applies only to static checks; final delivery needs a `spec_and_render` pass and later native/audio gates.
