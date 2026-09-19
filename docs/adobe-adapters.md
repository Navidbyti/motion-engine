# Adobe adapters

Adobe projects are optional delivery targets selected by MotionSpec. The core and public examples must run without Adobe installed. Each native adapter lives on a licensed Windows or macOS worker and reports capabilities before work starts.

| Target | Planned route | Must verify |
|---|---|---|
| After Effects | ExtendScript/JSX assembly of reusable shape, text, chart, and comp primitives; `aerender` for render | AEP opens, named layers and markers exist, text is editable, missing assets/fonts reported |
| Illustrator | JavaScript/ExtendScript for editable vectors, icons, diagrams | AI opens, layers/artboards/links correct |
| Photoshop | UXP scripting for layered still assets and treatments | PSD opens, layers retained, correct dimensions/profile |
| Premiere Pro | UXP project/sequence APIs, with a documented interchange fallback if the installed version lacks a needed operation | PRPROJ opens, tracks/cuts/markers/media online |

Do a small compatibility spike against installed versions before large adapter work: create, save, close, reopen, and inspect one project in each selected app. Pin OS, application version, fonts, codec profiles, and plugin set. Reopening in the owning app is the proof of native editability. Proxies or rendered plates do not substitute for editable text, charts, or shapes requested in the spec.

## Experimental After Effects text, rectangle, and image exporter

`motion-engine make-ae-script SPEC --output-script build.jsx --output-aep result.aep --report result.txt` creates a local ExtendScript job. In After Effects, choose **File > Scripts > Run Script File** and select `build.jsx`. The job requires an empty project, saves a new AEP, closes and reopens it, checks master/scene dimensions and timing, text content and font family, editable rectangle geometry, linked image footage, and beat-marker timing, then writes a `PASS` or `FAIL` report. It leaves After Effects on an empty project after the check. Use three fresh, distinct output paths. The script refuses to overwrite an existing AEP.

The initial subset supports text layers, solid editable rectangle shape layers, local PNG/JPEG image footage with `contain` or `stretch` fit, scene cuts, composition markers for beat windows, and linear opacity keyframes. Image files must be inside the MotionSpec directory tree and match their declared SHA-256 before import. It resolves font family and Regular/Bold style through After Effects' installed font list and fails if the match is missing or ambiguous. It rejects other element types and image formats, disclosure policies, voice, RTL text, unsupported parameters, nonzero `zIndex`, and other easing modes before creating a script. Exact text layout and visual parity still require review. Image files remain linked to their local paths; portable packaging of those links is a later milestone. The CLI capability registry continues to mark the complete `adobe.after_effects` target as planned because most MotionSpec primitives remain unsupported and execution currently requires an open licensed app.

After Effects 2024 version 24.5x52 on Windows passed save/reopen with `examples/ae-card.motion.json` (one landscape scene, two editable text layers), `examples/ae-vertical.motion.json` (two vertical scenes), `examples/ae-shapes.motion.json` (an editable rectangle behind text), and `examples/ae-image.motion.json` (a linked local PNG). This is a compatibility result for that version and feature subset only. Exact installed font objects produced no font substitution prompt. The generated AEPs and logs were scratch files, not committed.

## Experimental Illustrator static artboards

`motion-engine make-ai-script SPEC --output-script build.jsx --output-ai result.ai --report ai-report.txt` writes an Illustrator ExtendScript job. In Illustrator, choose **File > Scripts > Other Script** and select `build.jsx`. It requires no document to be open. It creates one named artboard and layer per scene, with editable text, rectangles, and a background shape. It saves the AI file, closes and reopens it, checks artboard count and dimensions, named layers, editable objects, text values, and font families, then writes a `PASS` or `FAIL` report. It closes its own document and refuses to overwrite any output.

This is a static artwork subset. Elements must cover their whole scene. The exporter rejects animation, partial-scene elements, linked assets, charts, datasets, disclosures, RTL text, multiline text, non-left alignment, and unsupported styles rather than dropping those features. The artboards are editable design material, not an animated video or a complete Illustrator adapter. Text uses a simple point-text baseline placement and needs visual review for exact layout. A requested font family must resolve uniquely to Regular or Bold. The complete `adobe.illustrator` target remains planned in the capability registry.

Illustrator 2024 version 28.6.0 on Windows passed save/reopen with `examples/ai-card.motion.json` (landscape text and rectangle) and `examples/ai-vertical.motion.json` (two vertical artboards). The saved files are local demo artifacts, not repository fixtures.

## Photoshop compatibility probe

Photoshop 2024 version 25.9.1 on Windows passed a manual scratch create/save/close/reopen probe for a 640×360 layered PSD with editable text. The script temporarily set ruler units to pixels for dimension checks and restored the prior setting afterward. This proves the basic native path only.

## Experimental Photoshop still exporter

`motion-engine make-ps-script SPEC --output-script build.jsx --output-psd result.psd --report ps-report.txt` generates a JSX job for one static scene. In Photoshop, choose **File > Scripts > Browse** and select `build.jsx`. The job requires no document to be open. It builds one layered PSD with editable single-line text and separate raster rectangle layers, embeds the MotionSpec source references in the document caption, saves, closes, reopens, and checks dimensions, layers, text, font, and provenance. It refuses to overwrite outputs and restores the user's ruler units.

The first subset rejects animation, multiple scenes, partial-scene elements, external assets, datasets, disclosures, RTL or auto-direction text, non-left alignment, multiline text, and unknown styles. Rectangles are raster pixel layers in this subset; exact text placement and color-managed appearance need visual review. Both public fixtures passed the native Photoshop 2024 version 25.9.1 save/close/reopen check on Windows on 2026-09-19: the 1920×1080 card reopened with five layers and the 1080×1920 still with three. This verifies only the stated subset. The complete `adobe.photoshop` target remains planned in the capability registry.

Sources: [Adobe After Effects scripting](https://helpx.adobe.com/after-effects/desktop/automate-in-after-effects/automate-animation/scripts.html), [aerender](https://helpx.adobe.com/after-effects/desktop/render-and-export/automate-rendering/automated-rendering-network-rendering.html), [Illustrator scripting](https://helpx.adobe.com/illustrator/desktop/automate-visualize-data/automate-actions/install-and-run-scripts.html), [Photoshop UXP scripting](https://developer.adobe.com/photoshop/uxp/scripting/), and [Premiere UXP project API](https://developer.adobe.com/premiere-pro/uxp/ppro-reference/classes/project).
