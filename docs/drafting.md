# Literal text drafting

`motion-engine draft-text` is the first prompt-to-video path. Put one line of visible copy per shot in a UTF-8 `.txt` file. The command creates a MotionSpec with one scene and beat per nonblank line, exact source citations, a simple opacity entrance, and a required MP4 preview. It copies no private input into the repository automatically.

```bash
motion-engine draft-text examples/assets/prompt-en.txt \
  --output examples/my-draft.motion.json \
  --project-id my_draft --locale en-US \
  --width 1080 --height 1920 --fps 30 --frames-per-line 60
motion-engine validate examples/my-draft.motion.json
motion-engine render examples/my-draft.motion.json --output-dir my-draft-preview
```

The source must be inside the MotionSpec output directory so its relative URI stays portable. The output file must be new. Set `--direction rtl` and a licensed `--font-family` for right-to-left text; visual review and a renderer with libraqm are required. Long lines can fail the renderer's overflow check. Choose a larger canvas or shorten the authored copy rather than silently shrinking or clipping it.

This command preserves line text and hashes the source. It does not infer pacing, summarize a brief, extract claims from a PDF, design charts, choose images, or make an Adobe project. The generated timing and visual design require review. The next interpretation stage will accept richer source evidence and an LLM-produced draft only after it can verify citations and report unsupported or uncertain decisions.
