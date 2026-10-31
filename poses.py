"""Batdown poses, derived from the characters' own still sprites.

No new art of Archie or Holly: each still is split into a body and its two
arms (cut out of the painted sprite), and the arms are rotated about the
shoulder in code. That gives the bat swing, the throw (overarm and the lob's
underarm), the stoop to pick the ball up and the arms-up catch. The robot is
treated the same way.

Angles: 0 is an arm hanging straight down; positive swings it forwards (towards
the way the character faces on screen), 180 is straight up.
"""
import math

import numpy as np
import pygame

# How to find each arm in a full-size still: rows (top, bottom) of the arm and
# a way of telling arm pixels from the body.
#   strip: the outermost W px of each row (sleeves the same colour as the body)
#   skin:  skin-coloured pixels on that side (Holly's bare arms on her dress)
#   cols:  everything beyond a column (the robot's arms stand clear of it)
ARMS = {
    "archie": {"se": ("strip", 62, 125, 9), "ne": ("strip", 60, 127, 9)},
    "holly": {"se": ("skin", 58, 123, None), "ne": ("skin", 60, 124, None)},
    "robot": {"se": ("cols", (57, 126, 18), (55, 124, 55)), "ne": ("cols", (57, 112, 17), (64, 138, 53))},
}
FORWARD = {"se": 1, "sw": -1, "nw": -1, "ne": 1}     # which way is "forwards" on screen
BACK_VIEW = {"se": False, "sw": False, "nw": True, "ne": True}


def _masks(arr, kind, key):
    """(left arm mask, right arm mask) for a full-size RGBA array."""
    h, w = arr.shape[:2]
    a = arr[:, :, 3] > 60
    src_key = key if key in ARMS[kind] else {"sw": "se", "nw": "ne"}[key]
    mirror = src_key != key
    cfg = ARMS[kind][src_key]
    L = np.zeros_like(a)
    R = np.zeros_like(a)
    if cfg[0] == "strip":
        _, y0, y1, W = cfg
        for y in range(y0, y1 + 1):
            xs = np.nonzero(a[y])[0]
            if len(xs) == 0:
                continue
            L[y, xs[0]:xs[0] + W] = a[y, xs[0]:xs[0] + W]
            R[y, max(0, xs[-1] - W + 1):xs[-1] + 1] = a[y, max(0, xs[-1] - W + 1):xs[-1] + 1]
        # not the trousers: denim is much bluer than the grey sleeves and the hands
        r, g, b = (arr[:, :, i].astype(int) for i in range(3))
        denim = (b - r > 22) & (b > g)
        L &= ~denim
        R &= ~denim
    elif cfg[0] == "skin":
        _, y0, y1, _ = cfg
        r, g, b = (arr[:, :, i].astype(int) for i in range(3))
        skin = a & (r > 120) & (r - b > 38) & (r >= g) & (g - b > 8)
        band = np.zeros_like(a)
        band[y0:y1 + 1] = True
        cx = w / 2
        xs = np.arange(w)[None, :]
        L = skin & band & (xs < cx - 6)
        R = skin & band & (xs > cx + 6)
        # Holly's arms: keep the biggest connected blob only, and grow it by a pixel for the outline
        L, R = _grow(_biggest(L), a), _grow(_biggest(R), a)
    else:
        _, (ly0, ly1, lx), (ry0, ry1, rx) = cfg
        if mirror:
            lx, rx = w - 1 - lx, w - 1 - rx
            (ly0, ly1, lx), (ry0, ry1, rx) = (ry0, ry1, rx), (ly0, ly1, lx)
        xs = np.arange(w)[None, :]
        ys = np.arange(h)[:, None]
        L = a & (xs <= lx) & (ys >= ly0) & (ys <= ly1)
        R = a & (xs >= rx) & (ys >= ry0) & (ys <= ry1)
        return L, R
    return L, R


def _biggest(m):
    from collections import deque
    h, w = m.shape
    seen = np.zeros_like(m)
    best = []
    for y, x in zip(*np.nonzero(m)):
        if seen[y, x]:
            continue
        q = deque([(y, x)])
        seen[y, x] = True
        comp = []
        while q:
            cy, cx = q.popleft()
            comp.append((cy, cx))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < h and 0 <= nx < w and m[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    q.append((ny, nx))
        if len(comp) > len(best):
            best = comp
    out = np.zeros_like(m)
    for y, x in best:
        out[y, x] = True
    return out


def _grow(m, a):
    g = m.copy()
    g[1:] |= m[:-1]; g[:-1] |= m[1:]; g[:, 1:] |= m[:, :-1]; g[:, :-1] |= m[:, 1:]
    return g & a


def _surf(arr):
    h, w = arr.shape[:2]
    return pygame.image.frombuffer(np.ascontiguousarray(arr).tobytes(), (w, h), "RGBA").copy()


class Arm:
    def __init__(self, img, pivot, hand):
        self.img = img            # the arm, cut out
        self.pivot = pivot        # shoulder, in the arm image's own coordinates
        self.hand = hand          # hand, ditto
        self.cache = {}

    def blit(self, s, shoulder, deg):
        """Draw the arm with its shoulder at the screen point; returns the hand's screen point."""
        d = int(round(deg / 3.0)) * 3
        if d not in self.cache:
            r = pygame.transform.rotate(self.img, d)
            # where the pivot lands in the rotated image
            w, h = self.img.get_size()
            c = pygame.math.Vector2(w / 2, h / 2)
            v = pygame.math.Vector2(self.pivot) - c
            v = v.rotate(-d)
            rc = pygame.math.Vector2(r.get_width() / 2, r.get_height() / 2)
            self.cache[d] = (r, rc + v)
        r, pv = self.cache[d]
        s.blit(r, (round(shoulder[0] - pv.x), round(shoulder[1] - pv.y)))
        return self.hand_at(shoulder, deg)

    def hand_at(self, shoulder, deg):
        v = pygame.math.Vector2(self.hand) - pygame.math.Vector2(self.pivot)
        v = v.rotate(-deg)
        return (shoulder[0] + v.x, shoulder[1] + v.y)


class Poser:
    """Body without arms + the two arms, for each facing, at in-game scale."""

    def __init__(self, kind, path_fmt, scale, anchors):
        self.kind = kind
        self.body, self.arms, self.shoulders, self.crouch = {}, {}, {}, {}
        for key in ("se", "sw", "nw", "ne"):
            im = pygame.image.load(path_fmt.format(kind=kind, key=key)).convert_alpha()
            arr = np.ascontiguousarray(pygame.surfarray.pixels3d(im).swapaxes(0, 1)).copy()
            alpha = np.array(pygame.surfarray.pixels_alpha(im)).swapaxes(0, 1).copy()
            rgba = np.dstack([arr, alpha]).astype(np.uint8)
            Lm, Rm = _masks(rgba, kind, key)
            body = rgba.copy()
            body[Lm | Rm, 3] = 0
            arms = []
            for m, side in ((Lm, -1), (Rm, 1)):
                ys, xs = np.nonzero(m)
                y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
                crop = np.zeros((y1 - y0 + 1, x1 - x0 + 1, 4), np.uint8)
                sub = rgba[y0:y1 + 1, x0:x1 + 1]
                crop[m[y0:y1 + 1, x0:x1 + 1]] = sub[m[y0:y1 + 1, x0:x1 + 1]]
                top = xs[ys < y0 + 5]
                bot = xs[ys > y1 - 5]
                piv = ((top.mean() - x0) * scale, 4 * scale)
                hand = ((bot.mean() - x0) * scale, (y1 - y0 - 3) * scale)
                img = _surf(crop)
                img = pygame.transform.smoothscale(img, (max(1, round(img.get_width() * scale)), max(1, round(img.get_height() * scale))))
                arms.append(Arm(img, piv, hand))
                # shoulder relative to the sprite's feet anchor
                ax, ay = anchors[key]
                self.shoulders.setdefault(key, []).append((x0 * scale + piv[0] - ax, y0 * scale + piv[1] - ay))
            bimg = _surf(body)
            bimg = pygame.transform.smoothscale(bimg, (round(bimg.get_width() * scale), round(bimg.get_height() * scale)))
            self.body[key] = bimg
            self.arms[key] = arms
            self.crouch[key] = self._crouch(bimg, anchors[key], FORWARD[key])

    @staticmethod
    def _crouch(img, anchor, fwd):
        """Knees bent and leaning in: the legs squashed and the top half sheared forwards."""
        w, h = img.get_size()
        ax, ay = anchor
        hip = int(ay * 0.62)
        drop = int(ay * 0.13)
        out = pygame.Surface((w + 16, h), pygame.SRCALPHA)
        legs = img.subsurface((0, hip, w, h - hip))
        lh = (h - hip) - drop
        legs = pygame.transform.smoothscale(legs, (w, max(1, lh)))
        out.blit(legs, (8, hip + drop))
        top = img.subsurface((0, 0, w, hip))
        for y in range(hip):
            sh = round((hip - y) / hip * 7 * fwd)
            out.blit(top, (8 + sh, y + drop), (0, y, w, 1))
        return out, drop

    def draw(self, s, key, feet, pose, a_left=0.0, a_right=0.0, crouch=False):
        """Draw at the feet point; arms at the given angles (degrees, forwards
        positive). Returns the two hand points (left, right) on screen."""
        fwd = FORWARD[key]
        back = BACK_VIEW[key]
        gx, gy = feet
        if crouch:
            img, drop = self.crouch[key]
            ox = -8
        else:
            img, drop, ox = self.body[key], 0, 0
        bx = round(gx - pose[0] + ox)
        by = round(gy - pose[1])
        hands = [None, None]
        order = []
        for i, a in enumerate((a_left, a_right)):
            behind = (a < -8) != back if abs(a) > 8 else False
            if back and abs(a) <= 8:
                behind = False
            order.append((behind, i, a))
        for behind, i, a in order:
            if behind:
                hands[i] = self._arm(s, key, i, gx, gy, a, drop, crouch, fwd)
        s.blit(img, (bx, by))
        for behind, i, a in order:
            if not behind:
                hands[i] = self._arm(s, key, i, gx, gy, a, drop, crouch, fwd)
        return hands

    def _arm(self, s, key, i, gx, gy, a, drop, crouch, fwd):
        sx, sy = self.shoulders[key][i]
        sh = (gx + sx + (7 * fwd if crouch else 0), gy + sy + drop)
        return self.arms[key][i].blit(s, sh, a * fwd)
