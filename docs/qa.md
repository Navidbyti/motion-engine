# Initial QA gate

Run `motion-engine qa SPEC --output qa.json` for source and policy checks. Add `--render-dir DIR` to verify an existing preview's revision, frame sequence, MP4 hash, frame count, and renderer warnings. The command returns a report with `passed`, `needs_review`, or `failed` status. Only `passed` exits successfully.

Implemented checks include source and available-asset hashes, referenced asset availability, dataset source references, text-element bounds against the declared safe area, and full-duration disclosure timing when requested by policy. A rendered preview is checked against the current MotionSpec and source revision. Font substitution appears as a review issue.

Policy rules that need a human (`text.visual_review`) or have not been implemented (`chart.data_exact` and other unknown rules) remain visible and block a clean pass. This gate does not yet compare chart values directly with CSV/XLSX evidence, inspect native Adobe files, detect every visual flaw, or test audio. A `spec_only` pass applies only to static checks; final delivery needs a `spec_and_render` pass and later native/audio gates.
