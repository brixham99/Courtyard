"""Cut the painted phone box and pillar box out of their magenta backgrounds.

    python tools/cut_props.py

Reads assets/art_src/{phonebox,pillarbox}_raw.jpg (painted on flat magenta),
keys out the background by its blue-over-green excess (the reds have none),
un-mixes the magenta from the soft edge pixels so no pink fringe is left,
shades the west (left) side a little as the sun is in the east,
crops to the object and writes assets/art/{phonebox,pillarbox}.png.
"""
import os
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "art_src")
OUT = os.path.join(ROOT, "assets", "art")


def cut(name, left_shade=None, cyl_shade=False):
    im = np.asarray(Image.open(os.path.join(SRC, f"{name}_raw.jpg")).convert("RGB")).astype(np.float32)
    h, w, _ = im.shape
    border = np.concatenate([im[:8].reshape(-1, 3), im[-8:].reshape(-1, 3), im[:, :8].reshape(-1, 3), im[:, -8:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    # magenta-ness: blue well above green, and red high
    k = (b - g) - 0.15 * np.maximum(0, 200 - r)
    kb = (bg[2] - bg[1])
    lo, hi = 0.35 * kb, 0.75 * kb
    a = np.clip((hi - k) / (hi - lo), 0, 1)
    # un-mix the background from partial pixels: C = a F + (1 - a) BG
    aa = np.maximum(a, 1e-3)[..., None]
    fg = (im - (1 - aa) * bg) / aa
    fg = np.clip(fg, 0, 255)
    # despill: nothing in these objects is bluer than it is green by much, except glass (high green)
    spill = (fg[..., 2] > fg[..., 1] + 25) & (fg[..., 1] < 120)
    fg[..., 2] = np.where(spill, fg[..., 1] + 25, fg[..., 2])
    # shrink the matte a touch (removes the last fringe) and drop specks
    from PIL import ImageFilter
    am = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3))
    a = np.asarray(am).astype(np.float32) / 255
    a[a < 0.06] = 0
    if left_shade:
        # darker west face (left of the near vertical corner edge)
        cx, k_dark = left_shade
        xs = np.arange(w)[None, :]
        t = np.clip((cx * w - xs) / 3.0, 0, 1)        # 0 right of edge, 1 left of it
        fac = 1 - (1 - k_dark) * t
        fg = fg * fac[..., None]
    if cyl_shade:
        # a round body: shade the west (left) side, keep the lit east side
        xs = np.arange(w)[None, :] / w
        bb = np.nonzero(a.max(axis=0) > 0.5)[0]
        u = (xs - bb[0] / w) / max(1e-3, (bb[-1] - bb[0]) / w)
        fac = np.clip(0.80 + 0.36 * u, 0.80, 1.0)
        fg = fg * fac[..., None]
    rgba = np.dstack([fg, a * 255]).astype(np.uint8)
    out = Image.fromarray(rgba, "RGBA")
    out = out.crop(out.getbbox())
    os.makedirs(OUT, exist_ok=True)
    out.save(os.path.join(OUT, f"{name}.png"))
    print(name, out.size)


if __name__ == "__main__":
    cut("phonebox", left_shade=(0.5, 0.84))
    cut("pillarbox", cyl_shade=True)
