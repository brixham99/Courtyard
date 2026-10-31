"""Cut a painted sprite out of its flat magenta background.

Keys on distance from the background colour sampled at the corners (the
painter's magenta is rarely pure #FF00FF), then despills the edges.
Usage: python tools/cutout.py src.jpg dst.png height
"""
import sys
import numpy as np
from PIL import Image, ImageFilter


def cut(src, dst, height):
    im = np.asarray(Image.open(src).convert("RGB")).astype(np.float32)
    h, w, _ = im.shape
    k = 12
    corners = np.concatenate([im[:k, :k].reshape(-1, 3), im[:k, -k:].reshape(-1, 3),
                              im[-k:, :k].reshape(-1, 3), im[-k:, -k:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)
    d = np.sqrt(((im - bg) ** 2).sum(axis=2))
    # magenta-ness relative to the background (catches the pink fringe too)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    mag = np.minimum(r, b) - g
    bgmag = min(bg[0], bg[2]) - bg[1]
    a = np.clip((d - 40) / 70, 0, 1)
    a = np.where(mag > bgmag * 0.55, np.minimum(a, np.clip(1 - (mag - bgmag * 0.55) / (bgmag * 0.3), 0, 1)), a)
    a = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3))).astype(np.float32) / 255
    # despill: pull the magenta cast out of semi-transparent and edge pixels
    spill = np.clip(np.minimum(r, b) - g - 20, 0, None)
    im[..., 0] -= spill * 0.8
    im[..., 2] -= spill * 0.8
    rgba = np.dstack([np.clip(im, 0, 255), a * 255]).astype(np.uint8)
    img = Image.fromarray(rgba, "RGBA")
    img = img.crop(img.getbbox())
    nw = round(img.width * height / img.height)
    img = img.resize((nw, height), Image.LANCZOS)
    img.save(dst)
    print(dst, nw, height, "bg", bg)


if __name__ == "__main__":
    cut(sys.argv[1], sys.argv[2], int(sys.argv[3]))
