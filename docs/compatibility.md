# Tested compatibility

The public core is tested on GitHub-hosted Windows, Linux, and macOS runners with Python 3.11 and 3.12. The pinned Python development dependency snapshot is `requirements-dev.lock`; the build backend is pinned in `pyproject.toml`. [Six-job verification](https://github.com/Navidbyti/motion-engine/actions/runs/35434480164) installed, ran all tests, and built a wheel on each combination.

| Component | Current support |
|---|---|
| MotionSpec validation, ingestion, planning | Tested on all six runner combinations |
| Raster/MP4 preview | Tested on all six runner combinations with the synthetic fixtures |
| Right-to-left preview | Requires a Pillow build with libraqm; the renderer stops clearly if unavailable |
| After Effects text, rectangle, linked image, linear position keys, and `zIndex` layer order | Experimental JSX exporter; save/reopen passed on Windows with After Effects 2024 24.5x52 for four original public fixtures, two position probes, and two layer-order probes |
| Illustrator static text and rectangle artboards | Experimental JSX exporter; save/reopen passed on Windows with Illustrator 2024 28.6.0 for two public synthetic fixtures |
| Photoshop layered PSD subset | Save/close/reopen passed on Windows with Photoshop 2024 25.9.1 for two MotionSpec fixtures: 1920×1080, five layers; 1080×1920, three layers. Editable single-line text and raster rectangles only. |
| Premiere Pro 2024 24.5.0.57 | Empty project create/save/close/reopen passed on Windows on 2026-09-19. The reopened application showed the same saved `.prproj` path; the file remained 5,971 bytes with SHA-256 `3fb926b5239fa7b6a68b13d4871f19a59b4d7dac3824af3db3c1c862d990edc4`. UXP is unavailable on this version, so a 24.x adapter needs a tested CEP/ExtendScript or interchange route. No sequence/export compatibility claim yet. |
| Premiere Pro 2026 26.5.1 | The plugin-free Final Cut Pro 7 XML subset passed native import on Windows on 2026-09-20. Premiere created a 4-second, 30 fps, 270×480 sequence with two contiguous clips and two named beat markers. The linked H.264 media was online. The `.prproj` reopened with both clips and markers intact; both scenes were visible in the Program Monitor. A native H.264 export contained 120 frames; sampled frames at 0, 30, 60, 90, and 119 matched the source within re-encoding differences. This proves the silent, cut-only fixture, not audio, graphic editability in Premiere, or other sequence profiles. UXP remains optional and untested. |
| FFmpeg | System executable or the pinned `imageio-ffmpeg` development package for preview MP4 |
| Fonts | Project fonts must be supplied or installed; substitution is reported in the render manifest |

The dependency snapshot fixes Python package versions. It does not freeze operating-system images, font files, native codecs, or Adobe applications. Pixel-identical output across operating systems requires those inputs to be fixed and compared separately. Update pinned versions deliberately, run the full matrix, and record visual differences before changing supported combinations.
