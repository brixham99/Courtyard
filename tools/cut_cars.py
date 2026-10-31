"""Cut the painted Teslas for the football car park out of their magenta backgrounds.

    python tools/cut_cars.py

Reads assets/art_src/tesla_*_raw.jpg (painted on flat #FF00FF), keys out the
background by its magenta-ness (red AND blue well above green, so a red or a
blue car keeps its paint), un-mixes the magenta from the soft edge pixels,
takes the pink cast out of the glass, paints out the nose badges, stretches the image a touch vertically so
the car's axes sit on the scene's 2:1 grid, crops to the car and writes
assets/art/tesla_*.png.
"""
import os
import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "art_src")
OUT = os.path.join(ROOT, "assets", "art")

CARS = ["tesla_model3_red", "tesla_modely_white", "tesla_models_grey",
        "tesla_modelx_blue", "tesla_cybertruck"]
# the little T badges the painter put on the noses (raw px, radius): painted out, no logos
BADGES = {"tesla_model3_red": (876, 469, 11), "tesla_models_grey": (898, 501, 10),
          "tesla_modelx_blue": (894, 492, 10)}
Y_STRETCH = 1.15   # the paintings sit a little flatter than true 2:1


def cut(name):
    im = np.asarray(Image.open(os.path.join(SRC, f"{name}_raw.jpg")).convert("RGB"))
    if name in BADGES:
        import cv2
        bx, by, br = BADGES[name]
        mask = np.zeros(im.shape[:2], np.uint8)
        cv2.circle(mask, (bx, by), br, 255, -1)
        im = cv2.inpaint(np.ascontiguousarray(im), mask, 6, cv2.INPAINT_TELEA)
    im = im.astype(np.float32)
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
    # despill: anything still pink/purple (glass reflecting the backdrop) goes neutral
    fr, fgg, fb = fg[..., 0], fg[..., 1], fg[..., 2]
    spill = np.maximum(0, np.minimum(fr, fb) - fgg - 6)
    fg[..., 0] = fr - spill
    fg[..., 2] = fb - spill
    am = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3))
    a = np.asarray(am).astype(np.float32) / 255
    a[a < 0.08] = 0
    rgba = np.dstack([fg, a * 255]).astype(np.uint8)
    out = Image.fromarray(rgba, "RGBA")
    out = out.crop(out.getbbox())
    w, h = out.size
    out = out.resize((w, round(h * Y_STRETCH)), Image.LANCZOS)
    os.makedirs(OUT, exist_ok=True)
    out.save(os.path.join(OUT, f"{name}.png"))
    print(name, out.size)


if __name__ == "__main__":
    for n in CARS:
        cut(n)
