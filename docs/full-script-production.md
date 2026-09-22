# Full-script production workflow

The desktop coding agent is the writer, researcher, director, and operator. Motion Engine provides checked contracts, rendering, revision safety, QA, and handoff files. This keeps creative reasoning flexible while making exact text, data, timing, and deliverables reproducible.

## Direct

Read the complete request and every supplied source. Establish audience, target duration, canvas, language, tone, required copy, calls to action, brand constraints, and deliverables. For an existing script, preserve its meaning and identify sections that need visual treatment. For a topic prompt, draft the spoken and on-screen narrative before scene planning.

For factual work, research the premise, save local source snapshots, and build a claim ledger. Every factual scene receives claim IDs. Separate verified facts from visual metaphor and generated imagery.

## Plan

Write one complete director plan against `motion-engine director-schema`. The script determines scene count and duration. Every paced scene has a purpose, energy level, and entry, hold, and exit windows. Account for narration, exact screen copy, source references, asset requests, transitions, sound effects, and music before rendering.

Use deterministic primitives for copy, numbers, charts, logos, and disclosures. Use approved image or video plates when the requested visual cannot be built from the supported primitives. Resolve all asset requests before compiling; never hide a missing shot behind an unrelated placeholder.

## Execute

Run `motion-engine produce prompt.txt director-plan.json --project-id <id> --name v1` with any claim, asset, data, font, canvas, and frame-rate options required by the project. This creates scene modules, the full preview, QA, the review interface, a verified source package, and supported editor handoffs.

The agent watches the output and inspects representative scene frames and the audio mix. A command completing successfully is not visual approval.

## Polish

Use stable scene IDs from the review page. Turn each user instruction into a hash-bound typed revision, rerender affected scenes, assemble them with compatible cached scenes, and make a new review version. Recheck facts when wording changes meaning.

Once prompt revisions are accepted, run prepared Adobe scripts or import the Premiere XML for supported native editing. Save native projects under new names and verify them after reopening.

## Version behavior

Use `v1`, `v2`, and later names without overwriting old artifacts. `project.json` records the current first-draft version when the workspace was created by `init-project`. Repeated update checks do not create versions. A new coding-agent task is unnecessary during production; staying in the same task preserves paths, choices, and the current revision hash.
