"""Build the robot's walk sheets from its two painted views.

Painted views (cut out of magenta with tools/cutout.py):
  assets/characters/robot_se.png  front three-quarter, facing screen bottom-right
  assets/characters/robot_ne.png  back three-quarter, facing screen top-right
The left-hand facings (sw, nw) are mirror images.

The head is enlarged (Nathan wanted a big cartoon head), then 8 walk frames are
made by splitting the legs apart at the hips and shearing each one forwards
and back along the facing (2:1 isometric: 2 px across for 1 px down), lifting
the swinging foot, with a small body bob. Writes robot_<k>.png,
robot_<k>_walk.png (8 frames side by side) and robot_walk.json (anchors).
"""
import json
import math
import os
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CH = os.path.join(HERE, "assets", "characters")
FRAMES = 8
HEAD_SCALE = 1.3
# per painted view: neck row, hip split row, leg-gap column, iso forward (dx, dy)
VIEWS = {"se": dict(neck=39, hip=114, gap=38, fwd=(2, 1)),
         "ne": dict(neck=41, hip=118, gap=31, fwd=(2, -1))}
STRIDE = 7.0       # px the foot moves forward/back at full stride
LIFT = 4.0         # px the swinging foot lifts
BOB = 2.0          # px the body rises as the legs pass


def big_head(img, neck):
    w, h = img.size
    head = img.crop((0, 0, w, neck + 2))
    a = np.asarray(head)[..., 3] > 40
    xs = np.where(a.any(axis=0))[0]
    cx = (xs.min() + xs.max()) / 2
    nh = round(head.height * HEAD_SCALE)
    nw = round(w * HEAD_SCALE)
    head = head.resize((nw, nh), Image.LANCZOS)
    grow = nh - head.height if False else nh - (neck + 2)
    pad = 12
    out = Image.new("RGBA", (w + 2 * pad, h + grow), (0, 0, 0, 0))
    out.alpha_composite(img, (pad, grow))
    hx = round(pad + cx - cx * HEAD_SCALE)
    out.alpha_composite(head, (hx, 0))
    return out, grow, pad


def frame(img, hip, gap, fwd, t):
    """One walk frame: the legs below `hip` split at column `gap` and sheared."""
    w, h = img.size
    arr = np.asarray(img).astype(np.float32)
    out = np.zeros((h + 8, w + 16, 4), np.float32)
    s = math.sin(2 * math.pi * t)
    c = math.cos(2 * math.pi * t)
    body_dy = -round(BOB * (1 - abs(s)))   # highest as the legs pass each other
    fx, fy = fwd
    n = math.hypot(fx, fy)
    fx, fy = fx / n, fy / n
    oy, ox = 4, 8
    # upper body (everything above the hips)
    out[oy + body_dy: oy + body_dy + hip, ox: ox + w] = arr[:hip]
    legs = [(0, gap, s, max(0.0, c)), (gap, w, -s, max(0.0, -c))]
    L = max(1, h - hip)
    for x0, x1, sw, lift in legs:
        A = sw * STRIDE * fy - LIFT * lift          # foot's vertical move
        Bx = sw * STRIDE * fx                       # foot's horizontal move
        g = 1 + (A - body_dy) / L                   # rows stretch/squash
        t0 = oy + body_dy + hip
        t1 = int(math.ceil(t0 + (h - 1 - hip) * g))
        for ty in range(int(math.floor(t0)), t1 + 1):
            y = hip + (ty - t0) / g                  # inverse map to the source row
            if y < hip or y > h - 1 or not (0 <= ty < out.shape[0]):
                continue
            yi = min(h - 1, int(round(y)))
            k = (y - hip) / L
            dx = Bx * k
            row = arr[yi, x0:x1]
            ix = int(math.floor(dx)); f = dx - ix
            seg = np.zeros((x1 - x0 + 1, 4), np.float32)
            seg[:-1] += row * (1 - f)
            seg[1:] += row * f
            tx = ox + x0 + ix
            dst = out[ty, tx: tx + seg.shape[0]]
            a = seg[:, 3:4] / 255
            pa = dst[:, 3:4] / 255
            col = seg[:, :3] * a + dst[:, :3] * pa * (1 - a)
            na = a + pa * (1 - a)
            dst[:, :3] = np.where(na > 0, col / np.maximum(na, 1e-6), 0)
            dst[:, 3:4] = na * 255
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA"), (ox, oy)


def main():
    meta = {"frames": FRAMES, "facings": {}}
    for k, v in VIEWS.items():
        src = Image.open(os.path.join(CH, f"robot_{k}_paint.png")).convert("RGBA")
        img, grow, pad = big_head(src, v["neck"])
        hip = v["hip"] + grow
        gap = v["gap"] + pad
        frames = []
        for i in range(FRAMES):
            fr, (ox, oy) = frame(img, hip, gap, v["fwd"], i / FRAMES)
            frames.append(fr)
        still, _ = frame(img, hip, gap, v["fwd"], 0.0)
        # sheet: crop all frames to a common box
        box = None
        for fr in frames + [still]:
            b = fr.getbbox()
            box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
        box = (box[0] - 1, box[1] - 1, box[2] + 1, box[3] + 1)
        frames = [f.crop(box) for f in frames]
        still = still.crop(box)
        fw, fh = still.size
        # feet anchor: middle of the boots, a few px above the sole
        a = np.asarray(still)[..., 3] > 100
        rows = np.where(a.any(axis=1))[0]
        foot = a[rows.max() - 22: rows.max() + 1]
        xs = np.where(foot.any(axis=0))[0]
        anchor = [float((xs.min() + xs.max()) / 2), float(rows.max() - 7)]
        for kk, mirror in ((k, False), ({"se": "sw", "ne": "nw"}[k], True)):
            sheet = Image.new("RGBA", (fw * FRAMES, fh))
            for i, f in enumerate(frames):
                sheet.alpha_composite(f.transpose(Image.FLIP_LEFT_RIGHT) if mirror else f, (i * fw, 0))
            st = still.transpose(Image.FLIP_LEFT_RIGHT) if mirror else still
            sheet.save(os.path.join(CH, f"robot_{kk}_walk.png"))
            st.save(os.path.join(CH, f"robot_{kk}.png"))
            ax = fw - anchor[0] if mirror else anchor[0]
            meta["facings"][kk] = {"anchor": [ax, anchor[1]]}
        meta["size"] = [fw, fh]
        print(k, fw, fh, anchor)
    meta["cycle_tiles"] = 1.15
    with open(os.path.join(CH, "robot_walk.json"), "w") as f:
        json.dump(meta, f, indent=1)


if __name__ == "__main__":
    main()
