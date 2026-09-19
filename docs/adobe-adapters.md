# Adobe adapters

Adobe projects are optional delivery targets selected by MotionSpec. The core and public examples must run without Adobe installed. Each native adapter lives on a licensed Windows or macOS worker and reports capabilities before work starts.

| Target | Planned route | Must verify |
|---|---|---|
| After Effects | ExtendScript/JSX assembly of reusable shape, text, chart, and comp primitives; `aerender` for render | AEP opens, named layers and markers exist, text is editable, missing assets/fonts reported |
| Illustrator | JavaScript/ExtendScript for editable vectors, icons, diagrams | AI opens, layers/artboards/links correct |
| Photoshop | UXP scripting for layered still assets and treatments | PSD opens, layers retained, correct dimensions/profile |
| Premiere Pro | UXP project/sequence APIs, with a documented interchange fallback if the installed version lacks a needed operation | PRPROJ opens, tracks/cuts/markers/media online |

Do a small compatibility spike against installed versions before large adapter work: create, save, close, reopen, and inspect one project in each selected app. Pin OS, application version, fonts, codec profiles, and plugin set. Reopening in the owning app is the proof of native editability. Proxies or rendered plates do not substitute for editable text, charts, or shapes requested in the spec.

## Experimental After Effects text and rectangle exporter

`motion-engine make-ae-script SPEC --output-script build.jsx --output-aep result.aep --report result.txt` creates a local ExtendScript job. In After Effects, choose **File > Scripts > Run Script File** and select `build.jsx`. The job requires an empty project, saves a new AEP, closes and reopens it, checks master/scene dimensions and timing, text content and font family, editable rectangle geometry, and beat-marker timing, then writes a `PASS` or `FAIL` report. It leaves After Effects on an empty project after the check. Use three fresh, distinct output paths. The script refuses to overwrite an existing AEP.

The initial subset supports text layers, solid editable rectangle shape layers, scene cuts, composition markers for beat windows, and linear opacity keyframes. It resolves font family and Regular/Bold style through After Effects' installed font list and fails if the match is missing or ambiguous. It rejects other element types, assets, disclosure policies, voice, RTL text, unsupported text/shape parameters, nonzero `zIndex`, and other easing modes before creating a script. Exact text layout and visual parity still require review. The CLI capability registry continues to mark the complete `adobe.after_effects` target as planned because most MotionSpec primitives remain unsupported and execution currently requires an open licensed app.

After Effects 2024 version 24.5x52 on Windows passed save/reopen with `examples/ae-card.motion.json` (one landscape scene, two editable text layers), `examples/ae-vertical.motion.json` (two vertical scenes), and `examples/ae-shapes.motion.json` (an editable rectangle behind text). This is a compatibility result for that version and feature subset only. Exact installed font objects produced no font substitution prompt. The generated AEPs and logs were scratch files, not committed.

Sources: [Adobe After Effects scripting](https://helpx.adobe.com/after-effects/desktop/automate-in-after-effects/automate-animation/scripts.html), [aerender](https://helpx.adobe.com/after-effects/desktop/render-and-export/automate-rendering/automated-rendering-network-rendering.html), [Illustrator scripting](https://helpx.adobe.com/illustrator/desktop/automate-visualize-data/automate-actions/install-and-run-scripts.html), [Photoshop UXP scripting](https://developer.adobe.com/photoshop/uxp/scripting/), and [Premiere UXP project API](https://developer.adobe.com/premiere-pro/uxp/ppro-reference/classes/project).
