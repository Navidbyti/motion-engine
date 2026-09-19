# Adobe adapters

Adobe projects are optional delivery targets selected by MotionSpec. The core and public examples must run without Adobe installed. Each native adapter lives on a licensed Windows or macOS worker and reports capabilities before work starts.

| Target | Planned route | Must verify |
|---|---|---|
| After Effects | ExtendScript/JSX assembly of reusable shape, text, chart, and comp primitives; `aerender` for render | AEP opens, named layers and markers exist, text is editable, missing assets/fonts reported |
| Illustrator | JavaScript/ExtendScript for editable vectors, icons, diagrams | AI opens, layers/artboards/links correct |
| Photoshop | UXP scripting for layered still assets and treatments | PSD opens, layers retained, correct dimensions/profile |
| Premiere Pro | UXP project/sequence APIs, with a documented interchange fallback if the installed version lacks a needed operation | PRPROJ opens, tracks/cuts/markers/media online |

Do a small compatibility spike against installed versions before large adapter work: create, save, close, reopen, and inspect one project in each selected app. Pin OS, application version, fonts, codec profiles, and plugin set. Reopening in the owning app is the proof of native editability. Proxies or rendered plates do not substitute for editable text, charts, or shapes requested in the spec.

Sources: [Adobe After Effects scripting](https://helpx.adobe.com/after-effects/desktop/automate-in-after-effects/automate-animation/scripts.html), [aerender](https://helpx.adobe.com/after-effects/desktop/render-and-export/automate-rendering/automated-rendering-network-rendering.html), [Illustrator scripting](https://helpx.adobe.com/illustrator/desktop/automate-visualize-data/automate-actions/install-and-run-scripts.html), [Photoshop UXP scripting](https://developer.adobe.com/photoshop/uxp/scripting/), and [Premiere UXP project API](https://developer.adobe.com/premiere-pro/uxp/ppro-reference/classes/project).
