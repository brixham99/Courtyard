"""The city: a street basketball court in an inner-city neighbourhood.

Behind the tall chain-link fence: a red-brick tenement with balconies and a
fire escape down the left, a terrace of yellow-brick flats with a corner shop
along the right, and cheerful murals painted by the local kids. Wheelie bins,
a bus shelter, street lamps and a hazy skyline of tower blocks.

The play area is the same N x N square as the other settings; here it is
tarmac with a painted full-length court (a hoop at each end, see
basketball.py). The hoops themselves are drawn by basketball_view, as they
are depth-sorted with the players.
"""
import math
import random
import pygame
import aa

from iso import WIN_W, WIN_H, HW, HH, N, P, shade, mix, poly, quad_x, quad_y, quad_z, box, SHADOW_K
from scene import (bricks_x, bricks_y, window_x, window_y, text_on_x_plane, text_on_y_plane, _cyl, _disc,
                   Obstacle)

RED_BRICK = (138, 62, 48)
STOCK = (196, 168, 112)          # London yellow stock brick
PAVING = (168, 168, 164)
ROAD = (70, 72, 78)
TARMAC = (74, 78, 86)
COURT = (178, 88, 66)            # terracotta acrylic
KEY = (58, 104, 168)
LINE = (240, 240, 236)
IRON = (34, 36, 40)
GALV = (176, 182, 188)

HOOP_X = (1.65, 12.35)           # rim centres along y = 7 (matches basketball.make_hoops)
ARC_R = 4.2


# ------------------------------------------------------------------ small helpers
def _shadow(s, pts, a=70):
    sh = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    aa.polygon(sh, (20, 20, 26, a), [(round(x), round(y)) for x, y in pts])
    s.blit(sh, (0, 0))


def _sheared(s, img, cx, cy, slope):
    """Blit a flat picture onto a wall: slope -0.5 for a +x wall, +0.5 for a +y wall."""
    w, h = img.get_size()
    for u in range(w):
        dy = slope * (u - w / 2)
        s.blit(img, (round(cx - w / 2 + u), round(cy - h / 2 + dy)), (u, 0, 1, h))


def star(surf, col, cx, cy, r, rot=0.0):
    pts = []
    for k in range(10):
        rr = r if k % 2 == 0 else r * 0.45
        a = rot - math.pi / 2 + k * math.pi / 5
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    aa.polygon(surf, col, pts)


def heart(surf, col, cx, cy, r):
    aa.circle(surf, col, (round(cx - r * 0.5), round(cy - r * 0.2)), round(r * 0.58))
    aa.circle(surf, col, (round(cx + r * 0.5), round(cy - r * 0.2)), round(r * 0.58))
    aa.polygon(surf, col, [(cx - r * 1.05, cy), (cx + r * 1.05, cy), (cx, cy + r * 1.1)])


def ball_icon(surf, cx, cy, r):
    aa.circle(surf, (236, 120, 40), (cx, cy), r)
    aa.circle(surf, (40, 24, 16), (cx, cy), r, 2)
    aa.line(surf, (40, 24, 16), (cx - r, cy), (cx + r, cy), 2)
    aa.line(surf, (40, 24, 16), (cx, cy - r), (cx, cy + r), 2)
    aa.arc(surf, (40, 24, 16), (cx - r * 1.6, cy - r, r * 1.4, r * 2), -1.2, 1.2, 2)
    aa.arc(surf, (40, 24, 16), (cx + r * 0.2, cy - r, r * 1.4, r * 2), math.pi - 1.2, math.pi + 1.2, 2)


def bubble_text(surf, txt, cx, cy, size, fills):
    """Chunky graffiti-style letters: each a different colour, with a thick outline."""
    f = pygame.font.SysFont("dejavusans", size, bold=True)
    ims = [f.render(ch, True, fills[i % len(fills)]) for i, ch in enumerate(txt)]
    outs = [f.render(ch, True, (30, 26, 40)) for ch in txt]
    tw = sum(im.get_width() for im in ims) - 2 * (len(ims) - 1)
    x = cx - tw / 2
    for i, (im, ol) in enumerate(zip(ims, outs)):
        y = cy - im.get_height() / 2 + (3 if i % 2 else -3)
        for ox, oy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2), (-2, 2), (2, -2), (4, 4)):
            surf.blit(ol, (x + ox, y + oy))
        surf.blit(im, (x, y))
        aa.line(surf, (255, 255, 255), (x + 5, y + im.get_height() * 0.3), (x + 9, y + im.get_height() * 0.24), 2)
        x += im.get_width() - 2


INK = (22, 20, 30)
TEAL = (20, 196, 190)
HOT = (255, 112, 40)
SUN = (255, 214, 50)
MAG = (236, 50, 150)


def splat(surf, col, cx, cy, r, seed):
    """A paint splat: a blob, a ring of lobes and a few flung droplets, inked."""
    rng = random.Random(seed)
    lobes = [(cx + math.cos(a) * r * 0.75, cy + math.sin(a) * r * 0.75, r * rng.uniform(0.3, 0.5))
             for a in [k * math.pi / 4 + rng.uniform(-0.3, 0.3) for k in range(8)]]
    drops = [(cx + math.cos(a) * r * d, cy + math.sin(a) * r * d, r * rng.uniform(0.1, 0.18))
             for a, d in [(rng.uniform(0, 6.28), rng.uniform(1.4, 1.9)) for _ in range(5)]]
    for c, grow in ((INK, 2), (col, 0)):
        aa.circle(surf, c, (round(cx), round(cy)), round(r * 0.8) + grow)
        for (x, y, rr) in lobes + drops:
            aa.circle(surf, c, (round(x), round(y)), round(rr) + grow)


def drip(surf, col, x, y, length, w=5):
    """A run of paint with a fat drop on the end, inked."""
    for c, g in ((INK, 2), (col, 0)):
        pygame.draw.rect(surf, c, (x - w // 2 - g, y, w + 2 * g, length + g))
        aa.circle(surf, c, (x, y + length), w // 2 + 2 + g)


def sparkle(surf, col, cx, cy, r):
    pts = []
    for k in range(8):
        rr = r if k % 2 == 0 else r * 0.28
        a = k * math.pi / 4
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    aa.polygon(surf, INK, [(cx + (x - cx) * 1.25, cy + (y - cy) * 1.25) for x, y in pts])
    aa.polygon(surf, col, pts)


def wild_letters(surf, txt, cx, cy, size, top, bot, extrude=TEAL, seed=7):
    """Bubbly, tilted graffiti letters: a gradient fill, a fat ink outline, a 3D
    extrusion and drips running off them."""
    rng = random.Random(seed)
    f = pygame.font.SysFont("dejavusans", size, bold=True)
    pieces = []
    for i, ch in enumerate(txt):
        g = f.render(ch, True, (255, 255, 255))
        g = pygame.transform.rotozoom(g, rng.uniform(-11, 11), 1.0)
        pieces.append(g)
    tw = sum(p.get_width() for p in pieces) - 9 * (len(pieces) - 1)
    x = cx - tw / 2
    placed = []
    for i, g in enumerate(pieces):
        y = cy - g.get_height() / 2 + (-4 if i % 2 == 0 else 4)
        placed.append((g, x, y))
        x += g.get_width() - 9

    def tinted(g, col):
        im = g.copy()
        im.fill((*col, 255), special_flags=pygame.BLEND_RGBA_MULT)
        return im
    # the extrusion, then a fat outline round letters and extrusion together
    for g, x, y in placed:
        ink = tinted(g, INK)
        for k in range(1, 8):
            for a in range(0, 360, 45):
                surf.blit(ink, (x + k + 3.5 * math.cos(math.radians(a)), y + k + 3.5 * math.sin(math.radians(a))))
        for a in range(0, 360, 30):
            surf.blit(ink, (x + 3.5 * math.cos(math.radians(a)), y + 3.5 * math.sin(math.radians(a))))
    for g, x, y in placed:
        ex = tinted(g, extrude)
        for k in range(1, 7):
            surf.blit(ex, (x + k, y + k))
    for i, (g, x, y) in enumerate(placed):
        w, h = g.get_size()
        grad = pygame.Surface((w, h), pygame.SRCALPHA)
        for yy in range(h):
            grad.fill((*mix(top, bot, yy / h), 255), (0, yy, w, 1))
        grad.blit(g, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(grad, (x, y))
        # a shine on each letter
        aa.ellipse(surf, (255, 255, 255), (x + w * 0.22, y + h * 0.2, w * 0.18, h * 0.08))
        if i % 2 == 0:            # paint running off alternate letters
            drip(surf, bot, round(x + w * (0.35 + 0.2 * (i % 3) / 2)), round(y + h * 0.8), 10 + 4 * i, 5)


def friendly_robot(surf, cx, cy, s=1.0):
    """A cartoon robot waving, holding a basketball: shapes only, inked."""
    def rr(col, rect, rad, w=0):
        x, y, ww, hh = rect
        pygame.draw.rect(surf, col, (round(cx + x * s), round(cy + y * s), round(ww * s), round(hh * s)), w, round(rad * s))

    def blob(rect, col, rad):
        x, y, ww, hh = rect
        rr(INK, (x - 2.5, y - 2.5, ww + 5, hh + 5), rad + 2)
        rr(col, rect, rad)
    # antenna
    aa.line(surf, INK, (cx, cy - 34 * s), (cx, cy - 46 * s), 3)
    aa.circle(surf, INK, (round(cx), round(cy - 48 * s)), round(6 * s))
    aa.circle(surf, MAG, (round(cx), round(cy - 48 * s)), round(4 * s))
    # waving arm (left) and the arm with the ball (right)
    aa.line(surf, INK, (cx - 18 * s, cy + 2 * s), (cx - 34 * s, cy - 20 * s), round(9 * s))
    aa.line(surf, (200, 210, 220), (cx - 18 * s, cy + 2 * s), (cx - 34 * s, cy - 20 * s), round(5 * s))
    aa.circle(surf, INK, (round(cx - 35 * s), round(cy - 23 * s)), round(7 * s))
    aa.circle(surf, SUN, (round(cx - 35 * s), round(cy - 23 * s)), round(5 * s))
    aa.line(surf, INK, (cx + 18 * s, cy + 4 * s), (cx + 30 * s, cy + 14 * s), round(9 * s))
    aa.line(surf, (200, 210, 220), (cx + 18 * s, cy + 4 * s), (cx + 30 * s, cy + 14 * s), round(5 * s))
    # legs
    for lx in (-11, 5):
        blob((lx, 26, 7, 14), (200, 210, 220), 2)
        blob((lx - 3, 38, 13, 6), HOT, 3)
    # body and head
    blob((-20, -4, 40, 32), TEAL, 9)
    rr((255, 255, 255), (-12, 4, 24, 14), 4)
    aa.circle(surf, MAG, (round(cx - 4 * s), round(cy + 11 * s)), round(3 * s))
    aa.circle(surf, SUN, (round(cx + 5 * s), round(cy + 11 * s)), round(3 * s))
    blob((-22, -36, 44, 30), (230, 236, 242), 12)
    rr(INK, (-16, -30, 32, 18), 8)
    for ex in (-7, 7):
        aa.circle(surf, (110, 240, 255), (round(cx + ex * s), round(cy - 22 * s)), round(4 * s))
        aa.circle(surf, (255, 255, 255), (round(cx + ex * s + 1), round(cy - 23 * s)), max(1, round(1.3 * s)))
    aa.arc(surf, (110, 240, 255), (cx - 5 * s, cy - 19 * s, 10 * s, 6 * s), math.pi + 0.3, 2 * math.pi - 0.3, 2)
    for ex in (-24, 20):      # cheeks / ear bolts
        rr(INK, (ex - 1, -26, 6, 12), 3)
        rr(HOT, (ex, -25, 4, 10), 2)
    ball_icon(surf, round(cx + 34 * s), round(cy + 20 * s), round(10 * s))


def mural_left(w, h):
    """The big one on the tenement: modern street art. "PLAY" in bubbly wildstyle
    letters, a friendly robot waving, splats, drips and sparkles."""
    m = pygame.Surface((w, h))
    m.fill((40, 42, 58))
    # big soft colour fields behind everything
    aa.circle(m, (30, 120, 130), (int(w * 0.62), int(h * 0.5)), int(h * 0.62))
    aa.circle(m, (120, 40, 110), (int(w * 0.98), int(h * 0.15)), int(h * 0.45))
    aa.circle(m, (70, 50, 120), (int(w * 0.12), int(h * 0.95)), int(h * 0.5))
    # sprayed stripes, like a quick fade
    for k, c in enumerate((MAG, HOT, SUN)):
        aa.line(m, c, (int(w * 0.28), h - 12 - k * 7), (w - 6, h - 30 - k * 7), 4)
    splat(m, MAG, w * 0.9, h * 0.22, 13, 3)
    splat(m, SUN, w * 0.42, h * 0.12, 7, 5)
    splat(m, HOT, w * 0.96, h * 0.84, 7, 9)
    wild_letters(m, "PLAY", int(w * 0.63), int(h * 0.45), 52, SUN, HOT, TEAL)
    friendly_robot(m, int(w * 0.16), int(h * 0.56), 1.05)
    for (fx, fy, r, c) in ((0.31, 0.12, 7, (255, 255, 255)), (0.95, 0.62, 6, SUN), (0.42, 0.66, 5, TEAL),
                           (0.06, 0.2, 5, (255, 255, 255))):
        sparkle(m, c, fx * w, fy * h, r)
    for (fx, c, ln) in ((0.04, TEAL, 16), (0.98, MAG, 12)):     # drips from the top edge
        drip(m, c, int(fx * w), 0, ln, 6)
    return m


def mural_right(w, h):
    """On the flats: bubble letters, stars, and a big smiling sun."""
    m = pygame.Surface((w, h))
    for x in range(w):
        m.fill(mix((250, 130, 170), (130, 110, 230), x / w), (x, 0, 1, h))
    for k in range(9):
        aa.circle(m, (255, 255, 255), (int(w * (0.05 + k * 0.115)), int(h * 0.88)), 14)
    cx, cy = int(w * 0.1), int(h * 0.36)
    for k in range(12):
        a = k * math.pi / 6
        aa.line(m, (255, 210, 60), (cx, cy), (cx + 26 * math.cos(a), cy + 26 * math.sin(a)), 4)
    aa.circle(m, (255, 210, 60), (cx, cy), 16)
    aa.circle(m, (30, 26, 40), (cx, cy), 16, 2)
    aa.circle(m, (30, 26, 40), (cx - 5, cy - 3), 2)
    aa.circle(m, (30, 26, 40), (cx + 5, cy - 3), 2)
    aa.arc(m, (30, 26, 40), (cx - 8, cy - 6, 16, 14), math.pi + 0.4, 2 * math.pi - 0.4, 2)
    bubble_text(m, "HOOPS", int(w * 0.56), int(h * 0.42), 34,
                [(255, 236, 90), (120, 230, 140), (110, 210, 255), (255, 150, 90), (255, 255, 255)])
    for (fx, fy, r) in ((0.25, 0.14, 7), (0.9, 0.18, 9), (0.95, 0.66, 6), (0.22, 0.7, 6)):
        star(m, (255, 255, 255), fx * w, fy * h, r)
    heart(m, (255, 90, 120), w * 0.92, h * 0.42, 8)
    return m


def fire_escape(s, x, ya, yb, floors):
    """Black iron landings at each floor with zig-zag stairs, on a +x wall."""
    d = 0.55
    for i, z in enumerate(floors):
        # landing: a grid platform with a railing
        poly(s, shade(IRON, 1.3), quad_z(x, ya, x + d, yb, z))
        poly(s, IRON, quad_x(x + d, ya, yb, z - 3, z))
        for yy in [ya + k * (yb - ya) / 8 for k in range(9)]:
            aa.line(s, IRON, P(x + d, yy, z), P(x + d, yy, z + 22), 1)
        aa.line(s, IRON, P(x + d, ya, z + 22), P(x + d, yb, z + 22), 2)
        aa.line(s, IRON, P(x, ya, z + 22), P(x + d, ya, z + 22), 2)
        aa.line(s, IRON, P(x, yb, z + 22), P(x + d, yb, z + 22), 2)
        # stairs down to the one below, alternately left and right
        if i > 0:
            zb = floors[i - 1]
            if i % 2:
                p0, p1 = (ya + 0.1, z), (yb - 0.1, zb)
            else:
                p0, p1 = (yb - 0.1, z), (ya + 0.1, zb)
            for off in (0.08, d - 0.08):
                aa.line(s, IRON, P(x + off, p0[0], p0[1]), P(x + off, p1[0], p1[1]), 2)
            for k in range(1, 9):
                t = k / 9
                yy = p0[0] + (p1[0] - p0[0]) * t
                zz = p0[1] + (p1[1] - p0[1]) * t
                aa.line(s, IRON, P(x + 0.08, yy, zz), P(x + d - 0.08, yy, zz), 1)
    # the drop ladder from the lowest landing
    z = floors[0]
    for yy in (yb - 0.32, yb - 0.08):
        aa.line(s, IRON, P(x + d - 0.05, yy, z), P(x + d - 0.05, yy, 18), 2)
    for zz in range(22, int(z), 9):
        aa.line(s, IRON, P(x + d - 0.05, yb - 0.32, zz), P(x + d - 0.05, yb - 0.08, zz), 1)


def balcony_x(s, x, ya, yb, z, col=(60, 66, 80)):
    d = 0.42
    box(s, x, ya, x + d, yb, 4, (150, 146, 140), z0=z)
    for yy in [ya + k * (yb - ya) / 7 for k in range(8)]:
        aa.line(s, col, P(x + d, yy, z + 4), P(x + d, yy, z + 24), 2)
    aa.line(s, col, P(x + d, ya, z + 24), P(x + d, yb, z + 24), 3)
    aa.line(s, col, P(x, yb, z + 24), P(x + d, yb, z + 24), 3)


def balcony_y(s, y, xa, xb, z, col=(60, 66, 80)):
    d = 0.42
    box(s, xa, y, xb, y + d, 4, (150, 146, 140), z0=z)
    for xx in [xa + k * (xb - xa) / 7 for k in range(8)]:
        aa.line(s, col, P(xx, y + d, z + 4), P(xx, y + d, z + 24), 2)
    aa.line(s, col, P(xa, y + d, z + 24), P(xb, y + d, z + 24), 3)
    aa.line(s, col, P(xb, y, z + 24), P(xb, y + d, z + 24), 3)


def wheelie_bin(s, x, y, col, part="all"):
    """A wheelie bin; part='shadow' or 'body' draws just that (for the far pavements,
    whose bins stand in front of the passing traffic)."""
    w, d, H = 0.42, 0.5, 40
    sd = H * SHADOW_K / HW / 2
    if part != "body":
        _shadow(s, [P(x + w, y), P(x + w - sd, y + sd), P(x - sd, y + d + sd), P(x, y + d)], 60)
    if part == "shadow":
        return
    box(s, x, y, x + w, y + d, H, col)
    box(s, x - 0.03, y - 0.03, x + w + 0.03, y + d + 0.03, 4, shade(col, 0.8), z0=H)
    for yy in (y + 0.1, y + d - 0.1):
        aa.circle(s, (20, 20, 22), [round(v) for v in P(x + w, yy, 4)], 4)


def _hull(pts):
    pts = sorted(set((round(x, 2), round(y, 2)) for x, y in pts))
    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2 and ((out[-1][0] - out[-2][0]) * (p[1] - out[-2][1])
                                     - (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0])) <= 0:
                out.pop()
            out.append(p)
        return out
    lo, hi = half(pts), half(pts[::-1])
    return lo[:-1] + hi[:-1]


ROUNDEL_RED = (220, 36, 31)          # #DC241F


def roundel(w, h):
    """The bus stop sign: a red panel, a thick white ring, and a white bar right
    across the panel through the ring's centre. Shapes only."""
    S = 4                                               # draw big, then smooth down
    im = pygame.Surface((w * S, h * S))
    im.fill(ROUNDEL_RED)
    cx, cy = w * S / 2, h * S / 2
    ro = min(w, h) * S * 0.40
    th = ro * 0.30
    aa.circle(im, (255, 255, 255), (round(cx), round(cy)), round(ro))
    aa.circle(im, ROUNDEL_RED, (round(cx), round(cy)), round(ro - th))
    im.fill((255, 255, 255), (0, round(cy - th / 2), w * S, round(th)))
    im = pygame.transform.smoothscale(im, (w, h))
    pygame.draw.rect(im, (70, 74, 82), (0, 0, w, h), 1)
    return im


def bus_shelter(s, x0, y0, x1, y1):
    """A glass bus shelter on the pavement, its long side along the kerb (the y
    direction), its back panel on the x0 side and its open front facing the road."""
    H = 96
    GL = (190, 220, 235)
    FR = (60, 64, 72)
    sd = H * SHADOW_K / HW / 2
    foot = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    _shadow(s, _hull([P(x, y) for x, y in foot] + [P(x - sd, y + sd) for x, y in foot]), 55)
    glass = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    poly(glass, (*GL, 120), quad_x(x0, y0, y1, 6, H - 8))       # the back panel
    poly(glass, (*GL, 95), quad_y(y0, x0, x1, 6, H - 8))        # the far end panel
    s.blit(glass, (0, 0))
    # an advert in the back panel: a poster for the courts
    ya, yb = y0 + 0.25, y0 + 0.95
    poly(s, (250, 236, 120), quad_x(x0 + 0.01, ya, yb, 20, 72))
    poly(s, (40, 24, 16), quad_x(x0 + 0.01, ya, yb, 20, 72), 1)
    pa = P(x0 + 0.01, (ya + yb) / 2, 50)
    ball_icon(s, round(pa[0]), round(pa[1]), 10)
    for (x, y) in ((x0, y0), (x1, y0), (x0, y1)):
        aa.line(s, FR, P(x, y, 0), P(x, y, H), 3)
    aa.line(s, FR, P(x0, y0, 6), P(x0, y1, 6), 2)
    aa.line(s, FR, P(x0, y0, H - 8), P(x0, y1, H - 8), 2)
    # a bench along the back panel
    for yy in (y0 + 0.45, y1 - 0.45):
        aa.line(s, FR, P(x0 + 0.2, yy, 0), P(x0 + 0.2, yy, 24), 3)
    box(s, x0 + 0.06, y0 + 0.3, x0 + 0.34, y1 - 0.3, 4, (180, 60, 60), z0=22)
    # the near end panel, the front post, and the roof
    glass = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    poly(glass, (*GL, 95), quad_y(y1, x0, x1, 6, H - 8))
    s.blit(glass, (0, 0))
    aa.line(s, FR, P(x0, y1, 6), P(x1, y1, 6), 2)
    aa.line(s, FR, P(x1, y1, 0), P(x1, y1, H), 3)
    rx0, ry0, rx1, ry1 = x0 - 0.05, y0 - 0.08, x1 + 0.12, y1 + 0.08
    poly(s, FR, quad_z(rx0, ry0, rx1, ry1, H))
    poly(s, (90, 96, 108), quad_y(ry1, rx0, rx1, H - 6, H))
    poly(s, (110, 116, 128), quad_x(rx1, ry0, ry1, H - 6, H))
    # the bus stop flag on its own pole at the kerb end, the sign square to the road
    fx, fy = x1 + 0.12, y1 + 0.45
    sh = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    d = 150 * SHADOW_K / HW / 2
    aa.line(sh, (20, 20, 26, 55), P(fx, fy), P(fx - d, fy + d), 4)
    s.blit(sh, (0, 0))
    aa.line(s, FR, P(fx, fy, 0), P(fx, fy, 152), 4)
    aa.line(s, (120, 126, 136), P(fx, fy, 0), P(fx, fy, 152), 1)
    img = roundel(34, 28)
    _sheared(s, img, *P(fx - 0.56, fy, 134), 0.5)
    aa.circle(s, FR, [round(v) for v in P(fx, fy, 154)], 3)


FAR = N + 6.8      # the far kerbs of the two front roads


def far_street(s, part):
    """The bins and lamps on the far pavements, beyond the traffic."""
    wheelie_bin(s, FAR + 0.6, 7.2, (60, 62, 66), part)
    wheelie_bin(s, 7.6, FAR + 0.6, (60, 120, 70), part)
    street_lamp(s, FAR + 0.5, 3.4, arm=(-1, 0), part=part)
    street_lamp(s, 3.4, FAR + 0.5, arm=(0, -1), part=part)


def build_city_street():
    """The far pavements' bins and lamps, drawn over the passing traffic."""
    s = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    far_street(s, "body")
    return s


def street_lamp(s, x, y, arm=(-1, 0), part="all"):
    """A modern grey street lamp, its arm over the court (part: 'all', 'shadow' or 'body')."""
    H = 220
    gx, gy = P(x, y)
    d = H * SHADOW_K / HW / 2
    if part != "body":
        sh = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        w = 0.06
        aa.polygon(sh, (20, 20, 26, 60), [P(x + w, y - w), P(x + w - d, y - w + d), P(x - w - d, y + w + d), P(x - w, y + w)])
        s.blit(sh, (0, 0))
    if part == "shadow":
        return
    G = (96, 102, 112)
    pygame.draw.rect(s, shade(G, 0.8), (gx - 5, gy - 14, 10, 14))
    aa.line(s, G, (gx, gy - 10), (gx, gy - H), 5)
    aa.line(s, shade(G, 1.4), (gx + 1, gy - 10), (gx + 1, gy - H), 1)
    ex, ey = P(x + arm[0] * 0.8, y + arm[1] * 0.8, H + 6)
    aa.lines(s, G, False, [(gx, gy - H), ((gx + ex) / 2, (gy - H + ey) / 2 - 6), (ex, ey)], 4)
    aa.ellipse(s, shade(G, 0.7), (ex - 14, ey - 4, 28, 10))
    aa.ellipse(s, (255, 248, 210), (ex - 10, ey + 1, 20, 6))


# ------------------------------------------------------------------ the backdrop
def city(s, fonts):
    rng = random.Random(31)
    # a bright, slightly hazy city sky
    for y in range(WIN_H):
        t = min(1, y / 300)
        aa.line(s, mix((78, 146, 214), (206, 222, 236), t ** 1.3), (0, y), (WIN_W, y))
    for cx, cy, sc in ((140, 60, 0.8), (470, 34, 0.6), (930, 50, 0.9), (1200, 96, 0.7)):
        for i in range(8):
            r = int(rng.uniform(14, 26) * sc)
            aa.circle(s, (250, 252, 255), (cx + int(rng.uniform(-44, 44) * sc), cy + int(rng.uniform(-6, 6) * sc)), r)
        aa.ellipse(s, (232, 238, 246), (cx - 52 * sc, cy + 4 * sc, 104 * sc, 18 * sc))
    # the skyline: hazy tower blocks and a crane
    for layer, (col, base, hmin, hmax) in enumerate((((168, 182, 200), 300, 60, 170), ((140, 154, 176), 320, 40, 120))):
        x = -20
        while x < WIN_W:
            w = rng.randint(34, 80)
            h = rng.randint(hmin, hmax)
            pygame.draw.rect(s, col, (x, base - h, w, h + 40))
            if layer == 1:
                for wy in range(base - h + 8, base, 12):
                    for wx in range(x + 5, x + w - 6, 10):
                        if rng.random() < 0.7:
                            pygame.draw.rect(s, shade(col, 1.12), (wx, wy, 5, 6))
            x += w + rng.randint(4, 30)
    cr = (230, 180, 60)
    aa.line(s, cr, (1000, 300), (1000, 120), 4)
    aa.line(s, cr, (940, 126), (1110, 126), 4)
    aa.line(s, (90, 90, 96), (1080, 126), (1080, 176), 1)

    # the ground: pavement round the court, a road beyond the front pavements
    poly(s, ROAD, quad_z(-12, -12, 40, 40, 0))
    poly(s, PAVING, quad_z(-5.0, -5.0, N + 1.6, N + 1.6, 0))
    for i in range(-5, N + 2):
        aa.line(s, shade(PAVING, 0.86), P(i, -5.0), P(i, N + 1.6), 1)
        aa.line(s, shade(PAVING, 0.86), P(-5.0, i), P(N + 1.6, i), 1)
    for k in range(260):
        x, y = rng.uniform(-5, N + 1.6), rng.uniform(-5, N + 1.6)
        gx, gy = P(x, y)
        aa.circle(s, shade(PAVING, rng.uniform(0.82, 0.95)), (round(gx), round(gy)), 1)
    # pavements on the far side of the two front roads, with their kerbs
    FAR = N + 6.8
    for q in (quad_z(FAR, -12, 40, N + 1.6, 0), quad_z(-12, FAR, N + 1.6, 40, 0)):
        poly(s, PAVING, q)
    for i in range(-12, 40):
        if i > FAR:
            aa.line(s, shade(PAVING, 0.86), P(i, -12), P(i, N + 1.6), 1)
            aa.line(s, shade(PAVING, 0.86), P(-12, i), P(N + 1.6, i), 1)
        aa.line(s, shade(PAVING, 0.86), P(FAR, i), P(40, i), 1) if i < N + 1.6 else None
        aa.line(s, shade(PAVING, 0.86), P(i, FAR), P(i, 40), 1) if i < N + 1.6 else None
    for k in range(160):
        a, b = rng.uniform(FAR, FAR + 6), rng.uniform(-6, N + 1.6)
        for (x, y) in ((a, b), (b, a)):
            gx, gy = P(x, y)
            aa.circle(s, shade(PAVING, rng.uniform(0.82, 0.95)), (round(gx), round(gy)), 1)
    poly(s, (214, 214, 208), quad_z(FAR, -12, FAR + 0.22, N + 1.6, 0))      # kerb stones
    poly(s, (214, 214, 208), quad_z(-12, FAR, N + 1.6, FAR + 0.22, 0))
    aa.line(s, (150, 150, 146), P(FAR, -12), P(FAR, N + 1.6), 2)
    aa.line(s, (150, 150, 146), P(-12, FAR), P(N + 1.6, FAR), 2)
    for (a, b) in ((FAR - 0.25, None), (FAR - 0.35, None)):
        aa.line(s, (236, 200, 50), P(a, -12), P(a, N + 1.6), 2)
        aa.line(s, (236, 200, 50), P(-12, a), P(N + 1.6, a), 2)
    # a bin and a lamp or two over there: just their shadows here, as the traffic
    # passes behind them (build_city_street draws them, over the traffic)
    far_street(s, "shadow")
    # kerbs and road markings on the front roads
    poly(s, (196, 196, 190), quad_y(N + 1.6, -5.0, N + 1.6, -4, 0))
    poly(s, (210, 210, 204), quad_x(N + 1.6, -5.0, N + 1.6, -4, 0))
    for (a, b) in ((N + 1.85, None), (N + 1.95, None)):
        aa.line(s, (236, 200, 50), P(a, -5.0), P(a, N + 1.75), 2)
        aa.line(s, (236, 200, 50), P(-5.0, a), P(N + 1.75, a), 2)
    for k in range(-4, N + 6, 2):
        aa.line(s, (236, 236, 230), P(N + 4.2, k), P(N + 4.2, k + 1), 3)
        aa.line(s, (236, 236, 230), P(k, N + 4.2), P(k + 1, N + 4.2), 3)
    # a drain cover or two
    for (x, y) in ((N + 1.3, 6.0), (5.0, N + 1.3)):
        poly(s, (90, 92, 96), quad_z(x - 0.18, y - 0.18, x + 0.18, y + 0.18, 0))

    tenement(s, fonts, rng)
    terrace(s, fonts, rng)
    # wheelie bins against the tenement, beside the left-hand corner
    for k, c in enumerate(((60, 120, 70), (50, 70, 130), (60, 62, 66), (150, 110, 50))):
        wheelie_bin(s, -1.3, 11.3 + k * 0.62, c)


def tenement(s, fonts, rng):
    """Four storeys of red brick down the left (x < 0), facing the court."""
    x0, x1, y0, y1, h = -5.0, -1.8, -2.6, 16.6, 206
    bricks_x(s, x1, y0, y1, 0, h, RED_BRICK, rng)
    poly(s, shade((200, 190, 170), 1.0), quad_x(x1 + 0.01, y0, y1, h - 10, h))      # parapet coping
    poly(s, shade(RED_BRICK, 0.55), quad_y(y1, x0, x1, 0, h))                       # the end wall in shade
    poly(s, (200, 190, 170), quad_z(x0, y0, x1 + 0.04, y1, h))
    poly(s, (110, 106, 100), quad_z(x0 + 0.2, y0 + 0.2, x1 - 0.2, y1 - 0.2, h))     # flat roof
    for yc in (1.0, 6.0, 12.6):
        box(s, x1 - 1.4, yc, x1 - 0.9, yc + 0.8, 26, shade(RED_BRICK, 0.9), z0=h)
    # the mural, on a windowless stretch of the ground and first floors
    m = mural_left(260, 112)
    poly(s, (240, 236, 226), quad_x(x1 + 0.01, 3.55, 11.45, 14, 132))
    _sheared(s, m, *P(x1 + 0.01, 7.5, 73), -0.5)
    floors = (10, 58, 106, 154)
    for k in range(10):
        ym = -1.9 + k * 1.85
        for i, z in enumerate(floors):
            if 3.0 < ym + 0.4 < 12.0 and i < 3:
                continue
            window_x(s, x1 + 0.01, ym, ym + 0.75, z + 8, z + 38, frame=(232, 228, 216), glass=(70, 90, 112))
            if i >= 1 and k % 3 == 1:
                balcony_x(s, x1, ym - 0.25, ym + 1.0, z)
                # a pot plant or two on the balcony
                pc = P(x1 + 0.2, ym + 0.1, z + 4)
                pygame.draw.rect(s, (180, 90, 60), (round(pc[0]) - 3, round(pc[1]) - 7, 7, 7))
                aa.circle(s, (70, 150, 70), (round(pc[0]), round(pc[1]) - 10), 6)
    # the front door with a canopy
    ym = 13.4
    poly(s, (40, 50, 70), quad_x(x1 + 0.02, ym - 0.4, ym + 0.4, 0, 44))
    box(s, x1, ym - 0.6, x1 + 0.5, ym + 0.6, 4, (200, 196, 186), z0=48)
    # fire escape down the stretch beyond the mural
    fire_escape(s, x1, -1.6, 0.8, (58, 106, 154))
    poly(s, (40, 46, 56), quad_x(x1 + 0.02, 12.2, 14.6, 52, 64))
    text_on_x_plane(s, fonts["sign"], "VICTORIA BUILDINGS", (240, 226, 160), x1 + 0.03, 13.4, 58)


def terrace(s, fonts, rng):
    """Three storeys of yellow-brick flats along the right (y < 0), with a corner shop."""
    X0, X1, Y0, Y1, H = -1.8, 13.2, -5.0, -2.6, 156
    bricks_y(s, Y1, X0, X1, 0, H, STOCK, rng)
    poly(s, (226, 220, 206), quad_y(Y1 + 0.01, X0, X1, H - 8, H))
    poly(s, (226, 220, 206), quad_y(Y1 + 0.01, X0, X1, 48, 53))           # string course
    # slate roof (front pitch) with chimney stacks
    poly(s, (78, 84, 96), [P(X0, Y1 + 0.2, H - 2), P(X1 + 0.2, Y1 + 0.2, H - 2), P(X1 + 0.2, (Y0 + Y1) / 2, H + 48), P(X0, (Y0 + Y1) / 2, H + 48)])
    for k in range(1, 6):
        t = k / 6
        yy = Y1 + 0.2 + ((Y0 + Y1) / 2 - Y1 - 0.2) * t
        aa.line(s, (66, 70, 82), P(X0, yy, H - 2 + 50 * t), P(X1 + 0.2, yy, H - 2 + 50 * t), 1)
    for xc in (1.5, 5.5, 9.5):
        box(s, xc, -4.2, xc + 0.7, -3.6, 34, shade(STOCK, 0.85), z0=H + 30)
        for k in range(3):
            c = P(xc + 0.15 + k * 0.2, -3.9, H + 66)
            pygame.draw.rect(s, (180, 96, 64), (round(c[0]) - 2, round(c[1]) - 7, 5, 8))
    # windows on the upper floors (some with little balconies), doors below
    for k in range(7):
        xm = -1.0 + k * 2.0
        for z in (62, 110):
            window_y(s, Y1 + 0.01, xm, xm + 0.8, z + 6, z + 36, frame=(246, 244, 236), glass=(60, 82, 104))
            if z == 110 and k % 2 == 0:
                balcony_y(s, Y1, xm - 0.2, xm + 1.0, z)
    # the right-hand mural over the ground floor of the middle flats
    m = mural_right(250, 80)
    poly(s, (240, 236, 226), quad_y(Y1 + 0.01, 0.85, 8.95, 6, 46))
    _sheared(s, m, *P(4.9, Y1 + 0.01, 26), 0.5)
    for xm in (-1.2, 9.6):
        poly(s, (120, 40, 60), quad_y(Y1 + 0.01, xm, xm + 0.6, 0, 40))
        aa.circle(s, (220, 190, 90), [round(v) for v in P(xm + 0.45, Y1 + 0.02, 20)], 2)
    # the corner shop, at the end of the terrace (and round the corner)
    sx0 = 10.3
    poly(s, (40, 90, 70), quad_y(Y1 + 0.01, sx0, X1, 0, 48))
    poly(s, (40, 90, 70), quad_x(X1, Y0, Y1, 0, 48))
    poly(s, (150, 190, 210), quad_y(Y1 + 0.02, sx0 + 0.25, sx0 + 1.6, 6, 38))     # shop window
    poly(s, (150, 190, 210), quad_y(Y1 + 0.02, sx0 + 2.4, X1 - 0.2, 6, 38))
    poly(s, (60, 54, 50), quad_y(Y1 + 0.02, sx0 + 1.75, sx0 + 2.25, 0, 40))       # door
    # things in the window: jars of sweets
    for k in range(6):
        c = P(sx0 + 2.6 + k * 0.05 * 6, Y1 + 0.02, 14)
        pygame.draw.rect(s, (255, 255, 255), (round(c[0]) - 3, round(c[1]) - 10, 7, 10))
        pygame.draw.rect(s, [(240, 80, 120), (250, 200, 60), (90, 200, 120)][k % 3], (round(c[0]) - 2, round(c[1]) - 7, 5, 6))
    # the fascia sign
    poly(s, (30, 70, 56), quad_y(Y1 + 0.03, sx0, X1, 48, 64))
    text_on_y_plane(s, fonts["sign"], "CORNER SHOP", (250, 236, 170), (sx0 + X1) / 2, Y1 + 0.04, 56)
    # end wall of the terrace (lit)
    bricks_x(s, X1, Y0, Y1, 48, H, STOCK, rng)
    window_x(s, X1 + 0.01, -4.2, -3.5, 68, 98)
    window_x(s, X1 + 0.01, -4.2, -3.5, 116, 146)
    poly(s, (226, 220, 206), quad_x(X1 + 0.01, Y0, Y1, H - 8, H))
    poly(s, (90, 96, 108), [P(X1 + 0.2, Y1 + 0.2, H - 2), P(X1 + 0.2, Y0 - 0.1, H - 2), P(X1 + 0.2, (Y0 + Y1) / 2, H + 48)])
    # the striped awning over the pavement
    stripes = 14
    for k in range(stripes):
        xa = sx0 + (X1 - sx0) * k / stripes
        xb = sx0 + (X1 - sx0) * (k + 1) / stripes
        col = (220, 60, 60) if k % 2 == 0 else (250, 246, 236)
        poly(s, col, [P(xa, Y1, 46), P(xb, Y1, 46), P(xb, Y1 + 0.8, 34), P(xa, Y1 + 0.8, 34)])
        poly(s, shade(col, 0.8), quad_y(Y1 + 0.8, xa, xb, 28, 34))
    # fruit and veg crates on the pavement under the awning
    for k, c in enumerate(((240, 140, 40), (90, 170, 60), (220, 50, 50), (250, 210, 60))):
        xa = sx0 + 0.2 + k * 0.62
        box(s, xa, Y1 + 0.1, xa + 0.5, Y1 + 0.55, 14, (150, 110, 70), z0=0)
        for j in range(5):
            p = P(xa + 0.1 + j * 0.08, Y1 + 0.3, 16)
            aa.circle(s, c, (round(p[0]), round(p[1])), 3)


# ------------------------------------------------------------------ the court
def city_floor(s, rng):
    """Tarmac, with a painted full-length court on it."""
    poly(s, TARMAC, quad_z(0, 0, N, N, 0))
    for k in range(2600):
        x, y = rng.uniform(0, N), rng.uniform(0, N)
        gx, gy = P(x, y)
        s.set_at((round(gx), round(gy)), shade(TARMAC, rng.uniform(0.8, 1.25)))
    m = 0.35
    poly(s, COURT, quad_z(m, m, N - m, N - m, 0))
    # the keys (blue) and the centre circle
    for hx, side in ((HOOP_X[0], 1), (HOOP_X[1], -1)):
        bx = m if side > 0 else N - m
        fx = bx + side * 3.9
        poly(s, KEY, quad_z(min(bx, fx), 5.6, max(bx, fx), 8.4, 0))
    ring = lambda cx, cy, r, a0=0, a1=2 * math.pi, n=64: [P(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
    poly(s, KEY, ring(7, 7, 1.2)[:-1])
    # lines
    aa.lines(s, LINE, True, quad_z(m, m, N - m, N - m, 0), 3)
    aa.line(s, LINE, P(7, m), P(7, N - m), 3)
    aa.lines(s, LINE, True, ring(7, 7, 1.2)[:-1], 2)
    for hx, side in ((HOOP_X[0], 1), (HOOP_X[1], -1)):
        bx = m if side > 0 else N - m
        fx = bx + side * 3.9
        aa.lines(s, LINE, True, quad_z(min(bx, fx), 5.6, max(bx, fx), 8.4, 0), 2)
        # free-throw circle: solid half towards half-way, dashed inside the key
        for i in range(24):
            a0 = -math.pi / 2 + i * math.pi / 24
            a1 = a0 + math.pi / 24
            pts = [P(fx + side * 1.0 * math.cos(a), 7 + 1.0 * math.sin(a)) for a in (a0, a1)]
            aa.line(s, LINE, pts[0], pts[1], 2)
        for i in range(0, 24, 2):
            a0 = math.pi / 2 + i * math.pi / 24
            a1 = a0 + math.pi / 24
            pts = [P(fx + side * 1.0 * math.cos(a), 7 + 1.0 * math.sin(a)) for a in (a0, a1)]
            aa.line(s, LINE, pts[0], pts[1], 2)
        # the three-point line: straight from the baseline, then an arc round the hoop
        yoff = 3.7                      # where the straight bits are
        ang = math.asin(yoff / ARC_R)
        xs = hx + side * ARC_R * math.cos(ang)
        for sgn in (-1, 1):
            aa.line(s, LINE, P(bx, 7 + sgn * yoff), P(xs, 7 + sgn * yoff), 2)
        pts = [P(hx + side * ARC_R * math.cos(a), 7 + ARC_R * math.sin(a)) for a in [-ang + 2 * ang * i / 48 for i in range(49)]]
        aa.lines(s, LINE, False, pts, 2)
        # a little painted target square under the hoop (the "no charge" arc)
        pts = [P(hx + side * 0.9 * math.cos(a), 7 + 0.9 * math.sin(a)) for a in [-math.pi / 2 + math.pi * i / 20 for i in range(21)]]
        aa.lines(s, LINE, False, pts, 1)
    # a few cracks and patches in the tarmac margin
    for k in range(6):
        x = rng.uniform(1, 13)
        y = rng.choice([0.15, N - 0.15])
        pts = [P(x + i * 0.12, y + rng.uniform(-0.08, 0.08)) for i in range(6)]
        aa.lines(s, shade(TARMAC, 0.7), False, pts, 1)


FENCE_H = 128


def _mesh_lines(plane, length, H, spacing=0.3):
    """Diamond mesh on a fence plane: lines at +/- 45 degrees (in world units)."""
    rise = H / 40.0                   # tiles of height (40 px a tile, like the game)
    segs = []
    c = -rise
    while c < length + rise:
        for sgn in (1, -1):
            a, b = c, c + sgn * rise          # along-the-fence position at z=0 and z=H
            # clip to 0..length
            t0, t1 = 0.0, 1.0
            for lim in (0.0, length):
                if (a - lim) * (b - lim) < 0:
                    t = (lim - a) / (b - a)
                    if (a < lim) == (lim == 0.0):
                        t0 = max(t0, t)
                    else:
                        t1 = min(t1, t)
            if (a < 0 and b < 0) or (a > length and b > length) or t0 >= t1:
                continue
            u0, u1 = a + (b - a) * t0, a + (b - a) * t1
            segs.append((plane(u0, H * t0), plane(u1, H * t1)))
        c += spacing
    return segs


def chain_link(s, H, front=False):
    """A tall galvanised chain-link fence along the two back edges (or, low, the front ones)."""
    mesh = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    if front:
        planes = (lambda u, z: P(N + 0.08, u, z), lambda u, z: P(u, N + 0.08, z))
    else:
        planes = (lambda u, z: P(-0.02, u, z), lambda u, z: P(u, -0.02, z))
    for pl in planes:
        for a, b in _mesh_lines(pl, N + (0.08 if front else 0), H, 0.22 if front else 0.3):
            pygame.draw.aaline(mesh, (210, 216, 222, 120), a, b)
    s.blit(mesh, (0, 0))
    # posts and rails
    for pl in planes:
        for k in range(0, N + 1, 2):
            p0, p1 = pl(k, 0), pl(k, H + 4)
            aa.line(s, shade(GALV, 0.7), p0, p1, 4)
            aa.line(s, shade(GALV, 1.15), (p0[0] + 1, p0[1]), (p1[0] + 1, p1[1]), 1)
        for z in (H, 2):
            aa.line(s, shade(GALV, 0.85), pl(0, z), pl(N, z), 3)
        if not front:
            aa.line(s, shade(GALV, 0.85), pl(0, H / 2), pl(N, H / 2), 2)


def city_back(s, rng):
    # a soft shadow of the fence on the court (falling west)
    chain_link(s, FENCE_H)
    # a painted sign on the fence
    f = pygame.font.SysFont("dejavusans", 12, bold=True)
    tw = f.size("COMMUNITY COURTS")[0] / HW / 2 * 2     # text width in tiles along x
    xm = min(11.55, 13.85 - tw / 2 - 0.3)
    xa, xb = xm - tw / 2 - 0.3, xm + tw / 2 + 0.3
    poly(s, (250, 250, 246), quad_y(0.0, xa, xb, 16, 44))
    poly(s, (40, 60, 140), quad_y(0.0, xa, xb, 16, 44), 2)
    text_on_y_plane(s, f, "COMMUNITY COURTS", (40, 60, 140), xm, 0.01, 30)


def city_props(s):
    pass


def build_city_front():
    """The low mesh fence along the two front edges, and the street lamps."""
    s = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    chain_link(s, 34, front=True)
    bus_shelter(s, N + 0.5, 3.2, N + 1.2, 5.4)
    street_lamp(s, N + 0.75, -0.5, arm=(-1, 0))
    street_lamp(s, -0.5, N + 0.75, arm=(0, -1))
    return s


def city_obstacles():
    from basketball import court_obstacles
    return court_obstacles()
