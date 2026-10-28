"""Builds the README's demo GIF from the stills recorded by frontend/e2e-video/demo.spec.ts.

    python scripts/demo_gif.py ../frontend/test-results/demo-frames ../docs/demo/pathtopro-demo.gif

Each still is held for its time in timeline.json, with a short cross-fade between scenes.
GitHub plays an animated GIF inline in a README (a video file in the repository it does not).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

WIDTH = 960  # the README column is narrower than 1280; smaller frames keep the file light
FADE_STEPS = 3
FADE_MS = 70


def main(frames_dir: str, out: str) -> None:
    folder = Path(frames_dir)
    timeline = json.loads((folder / "timeline.json").read_text())
    stills = []
    for item in timeline:
        img = Image.open(folder / item["file"]).convert("RGB")
        img = img.resize((WIDTH, round(img.height * WIDTH / img.width)), Image.LANCZOS)
        stills.append((img, item["hold"]))

    frames, durations = [], []
    for i, (img, hold) in enumerate(stills):
        frames.append(img)
        durations.append(hold)
        if i + 1 < len(stills):
            nxt = stills[i + 1][0]
            for k in range(1, FADE_STEPS + 1):
                frames.append(Image.blend(img, nxt, k / (FADE_STEPS + 1)))
                durations.append(FADE_MS)

    # One shared palette keeps colours steady from frame to frame
    palette_src = Image.new("RGB", (WIDTH, stills[0][0].height * len(stills)))
    for i, (img, _) in enumerate(stills):
        palette_src.paste(img, (0, i * img.height))
    palette = palette_src.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    quantized = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    quantized[0].save(out, save_all=True, append_images=quantized[1:], duration=durations, loop=0, optimize=True, disposal=1)
    total = sum(durations) / 1000
    print(f"{out}: {len(frames)} frames, {total:.0f} s, {Path(out).stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python scripts/demo_gif.py <frames dir> <out.gif>")
    main(sys.argv[1], sys.argv[2])
