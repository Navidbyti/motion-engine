# What remains editable

Motion Engine keeps the production plan in MotionSpec and can build several delivery forms. Their editability differs.

| Output | Manual editing today |
|---|---|
| MotionSpec JSON | Change supported text, colors, bounds, opacity, x/y position, image or video scale, linked visual assets, and audio gain through typed revisions. Recompile and render after a change. |
| After Effects AEP | Supported text remains real text; rectangles remain separate shape layers; still images remain linked footage layers; opacity, position, and still-image scale tracks remain editable keyframes. |
| Premiere XML / PRPROJ | Scenes are rendered video clips with cut timing and markers. Premiere can trim, retime, scale, position, and grade those clips, but text and graphics inside each rendered scene are pixels. |
| Preview MP4 | Flat review media. It has no editable layers. |
| Illustrator AI | Supported static text and rectangles remain separate editable objects. |
| Photoshop PSD | Supported static text and rectangles remain separate layers. |

For example, a linked still image of a Bitcoin can be made larger or moved directly in After Effects, and its Scale or Position keys can be retimed. A generated clip of a rotating Bitcoin is a rendered plate: an editor can resize, reposition, trim, or slow the whole plate, but changing the internal 3D rotation direction or camera angle requires regenerating it or replacing it with a true 3D scene or model. Motion Engine does not yet build editable 3D geometry.

The preview engine is deterministic Python rendering with Pillow for frames, a frame-addressed asset layer, and FFmpeg for encoded video and audio. Codex or Claude supplies direction and research. MotionSpec is the portable contract between that agent, the renderer, revision tools, and Adobe adapters.

Native editability is claimed only for adapter features that have passed save, close, reopen, and structural inspection in the owning Adobe application. See [Adobe adapters](adobe-adapters.md) for the tested versions and current boundaries.
