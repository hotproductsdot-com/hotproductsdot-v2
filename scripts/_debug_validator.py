"""Investigation: print exact validator measurements for today's 4 slugs
to confirm the source-image check fires the way we expect on the runner."""
import os
import sys

sys.path.insert(0, "/mnt/e/GITHUB/hotproductsdot-v2")
os.chdir("/mnt/e/GITHUB/hotproductsdot-v2")

import numpy as np
from PIL import Image

from instagram import banner_compose

SLUGS = [
    "husqvarna-automower-450x-robotic-lawn-mower",
    "apple-mac-mini-m4-2024",
    "sony-a7r-v-camera",
    "horow-black-smart-toilet-with-pump-and-bidet-built-in",
]

for slug in SLUGS:
    path = f"site/public/products/{slug}.jpg"
    img = Image.open(path).convert("RGB")
    w, h = img.size
    corner = max(40, min(w, h) // 20)
    print(f"\n{slug}")
    print(f"  size={w}x{h} aspect={w/h:.3f} corner={corner}")

    samples = [
        ("TL", img.crop((0, 0, corner, corner))),
        ("TR", img.crop((w - corner, 0, w, corner))),
        ("BL", img.crop((0, h - corner, corner, h))),
        ("BR", img.crop((w - corner, h - corner, w, h))),
    ]
    for label, c in samples:
        b = float(np.asarray(c, dtype=np.float32).mean())
        cls = "light" if b > 215 else "dark" if b < 35 else "scene"
        print(f"  {label}: brightness={b:6.1f}  class={cls}")

    ok, reason = banner_compose._validate_source_image(img)
    print(f"  validator: ok={ok} reason={reason!r}")
