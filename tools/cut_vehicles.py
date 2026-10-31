"""Cut the painted London traffic for the city street out of its magenta backgrounds.

    python tools/cut_vehicles.py

Reads assets/art_src/{bus,cab}_{front,rear}_raw.jpg (painted on flat #FF00FF)
and writes assets/art/{bus,cab}_{front,rear}.png, keyed and despilled the same
way as tools/cut_cars.py (red AND blue well above green is background, so the
red bus keeps its paint; the soft edges are un-mixed from the magenta and any
pink left in the glass goes neutral).

The bus paintings have the bus's length running lower-left to upper-right (the
city's y direction); the cabs run upper-left to lower-right (the x direction).
"""
import os
import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "art_src")
OUT = os.path.join(ROOT, "assets", "art")

NAMES = ["bus_front", "bus_rear", "cab_front", "cab_rear"]


def cut(name):
    im = np.asarray(Image.open(os.path.join(SRC, f"{name}_raw.jpg")).convert("RGB")).astype(np.float32)
    border = np.concatenate([im[:8].reshape(-1, 3), im[-8:].reshape(-1, 3),
                             im[:, :8].reshape(-1, 3), im[:, -8:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    k = np.minimum(r, b) - g                       # magenta-ness
    kb = min(bg[0], bg[2]) - bg[1]
    lo, hi = 0.30 * kb, 0.70 * kb
    a = np.clip((hi - k) / (hi - lo), 0, 1)
    aa = np.maximum(a, 1e-3)[..., None]
    fg = np.clip((im - (1 - aa) * bg) / aa, 0, 255)
    fr, fgg, fb = fg[..., 0], fg[..., 1], fg[..., 2]
    spill = np.maximum(0, np.minimum(fr, fb) - fgg - 6)
    fg[..., 0] = fr - spill
    fg[..., 2] = fb - spill
    am = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3))
    a = np.asarray(am).astype(np.float32) / 255
    a[a < 0.08] = 0
    # keep only the biggest blob (drop stray specks of noise in the backdrop)
    import cv2
    n, lab, stats, _ = cv2.connectedComponentsWithStats((a > 0.5).astype(np.uint8))
    if n > 2:
        keep = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        grow = cv2.dilate((lab == keep).astype(np.uint8), np.ones((5, 5), np.uint8))
        a = a * grow
    rgba = np.dstack([fg, a * 255]).astype(np.uint8)
    out = Image.fromarray(rgba, "RGBA")
    out = out.crop(out.getbbox())
    os.makedirs(OUT, exist_ok=True)
    out.save(os.path.join(OUT, f"{name}.png"))
    print(name, out.size)


if __name__ == "__main__":
    for n in NAMES:
        cut(n)
