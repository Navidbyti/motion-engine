# Tested compatibility

The public core is tested on GitHub-hosted Windows, Linux, and macOS runners with Python 3.11 and 3.12. The pinned Python development dependency snapshot is `requirements-dev.lock`; the build backend is pinned in `pyproject.toml`. [Six-job verification](https://github.com/Navidbyti/motion-engine/actions/runs/35434480164) installed, ran all tests, and built a wheel on each combination.

| Component | Current support |
|---|---|
| MotionSpec validation, ingestion, planning | Tested on all six runner combinations |
| Raster/MP4 preview | Tested on all six runner combinations with the synthetic fixtures |
| Right-to-left preview | Requires a Pillow build with libraqm; the renderer stops clearly if unavailable |
| After Effects text and rectangle project | Experimental JSX exporter; save/reopen passed on Windows with After Effects 2024 24.5x52 for three public synthetic fixtures |
| Other native Adobe targets | Planned; no app-version compatibility claim yet |
| FFmpeg | System executable or the pinned `imageio-ffmpeg` development package for preview MP4 |
| Fonts | Project fonts must be supplied or installed; substitution is reported in the render manifest |

The dependency snapshot fixes Python package versions. It does not freeze operating-system images, font files, native codecs, or Adobe applications. Pixel-identical output across operating systems requires those inputs to be fixed and compared separately. Update pinned versions deliberately, run the full matrix, and record visual differences before changing supported combinations.
