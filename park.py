"""The park: Batdown's setting.

The play area is the same N x N tiles as the school courtyard, laid as a
mown cricket-style lawn with stripes, a worn batting strip and painted
distance rings. A low privet hedge closes the two back edges and green iron
park railings run along the front. Round about: a bandstand, the duck pond,
old oaks, lamp-posts, benches, a litter bin, flowerbeds and the town's
rooftops in the distance. The sun is in the east, so shadows fall west
(screen left), as everywhere else in Courtyard. No moon.

Drawing order (see scene.build_background): backdrop (sky, hills, the lawn
outside, and everything beyond the back hedge) -> pitch -> back hedge ->
flat things on the front verges. The front layer (railings, then the lamps,
benches and bin that stand in front of them) is drawn over the players.
"""
import math
import random

import pygame

from iso import WIN_W, WIN_H, HW, HH, N, P, shade, mix, poly, quad_x, quad_y, quad_z, box, SHADOW_K

BAT_SPOT = (2.6, 2.6)          # where the batter stands (by the back hedge)
BOWL_MARK = (5.2, 8.4)         # the first throw of each turn comes from here (6.4 tiles out)
RINGS = (3.0, 6.0)             # distance rings from the batter: under 3 = 1 pt, 3-6 = 2, over 6 = 3

LAWN = (112, 168, 78)          # the park's grass, outside the pitch
STRIPE_A = (118, 178, 80)
STRIPE_B = (98, 154, 66)
HEDGE = (52, 104, 50)
IRON = (30, 66, 46)            # park railings: council green
GRAVEL = (204, 190, 156)
OAK_TRUNK = (98, 74, 52)
CREAM = (240, 234, 214)
VERDIGRIS = (86, 150, 128)

OAK = dict(x=10.3, y=4.4)      # the oak in the field of play (trunk; canopy above)
BENCH = dict(x0=8.0, y0=10.3, x1=9.5, y1=10.75)


# ------------------------------------------------------------------ obstacles inside
def park_obstacles():
    from scene import Obstacle
    return [
        # r is the trunk and its root flare (for the players); the ball also meets the canopy
        Obstacle("tree", x=OAK["x"], y=OAK["y"], r=0.36, trunk=0.24, trunk_h=2.5, canopy=(3.5, 1.55), style="oak"),
        Obstacle("bench", **BENCH, h_ball=0.8),
    ]


class OakArt:
    def __init__(self):
        self.canopy = oak_canopy(91, 86)


def oak_canopy(seed, r):
    """A broad, lumpy oak crown, lit from the east (screen right)."""
    rng = random.Random(seed)
    w = int(r * 2.3) + 20
    h = int(r * 1.75) + 20
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx, cy = w / 2, h / 2 + 4
    base = (58, 108, 46)
    # a few big lobes, then leafy clumps over them
    lobes = [(cx + rng.uniform(-r * 0.75, r * 0.75), cy + rng.uniform(-r * 0.45, r * 0.3), rng.uniform(r * 0.38, r * 0.55)) for _ in range(7)]
    lobes.append((cx, cy, r * 0.62))
    for (lx, ly, lr) in lobes:
        pygame.draw.circle(surf, shade(base, 0.8), (round(lx), round(ly)), round(lr))
    for i in range(170):
        lx, ly, lr = rng.choice(lobes)
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(0, 1) ** 0.7 * lr
        px, py = lx + math.cos(a) * d, ly + math.sin(a) * d * 0.9
        rr = rng.uniform(r * 0.1, r * 0.2)
        light = 0.72 + 0.5 * ((px - cx) / (r * 1.1) + 1) / 2 - 0.28 * ((py - cy) / r)
        pygame.draw.circle(surf, shade(base, light * rng.uniform(0.9, 1.06)), (round(px), round(py)), round(rr))
    for i in range(60):   # sunlit leaves on the east (right) and top
        a = rng.uniform(-1.4, 0.5)
        d = rng.uniform(0.45, 0.95) * r
        px, py = cx + math.cos(a) * d * 1.05, cy + math.sin(a) * d * 0.72
        pygame.draw.circle(surf, (132, 180, 80), (round(px), round(py)), rng.randint(3, 6))
    for i in range(40):   # dark gaps underneath
        px, py = cx + rng.uniform(-r, r) * 0.9, cy + rng.uniform(0.2, 0.6) * r
        pygame.draw.circle(surf, shade(base, 0.55), (round(px), round(py)), rng.randint(2, 5))
    # clip to the drawn shape (keeps the edge lumpy, no square corners)
    return surf


def draw_oak_base(s, o):
    """Trunk with a root flare straight out of the grass."""
    gx, gy = P(o.x, o.y)
    th = round(o.trunk_h * 40)
    # root flare
    pygame.draw.ellipse(s, shade(OAK_TRUNK, 0.8), (gx - 16, gy - 7, 32, 12))
    pts = [(gx - 15, gy), (gx - 9, gy - 14), (gx - 8, gy - th), (gx + 8, gy - th), (gx + 9, gy - 14), (gx + 15, gy)]
    pygame.draw.polygon(s, OAK_TRUNK, pts)
    pygame.draw.polygon(s, shade(OAK_TRUNK, 1.3), [(gx + 2, gy - 1), (gx + 3, gy - th), (gx + 8, gy - th), (gx + 9, gy - 14), (gx + 14, gy)])
    for k in range(7):     # bark furrows
        yy = gy - 10 - k * (th - 14) / 7
        pygame.draw.line(s, shade(OAK_TRUNK, 0.7), (gx - 4, yy), (gx - 2, yy - 9), 1)
        pygame.draw.line(s, shade(OAK_TRUNK, 0.75), (gx + 4, yy - 4), (gx + 5, yy - 11), 1)
    # boughs into the crown
    pygame.draw.line(s, OAK_TRUNK, (gx - 2, gy - th + 26), (gx - 30, gy - th - 6), 6)
    pygame.draw.line(s, OAK_TRUNK, (gx + 3, gy - th + 18), (gx + 28, gy - th - 10), 5)
    pygame.draw.line(s, OAK_TRUNK, (gx, gy - th + 4), (gx + 2, gy - th - 22), 6)


def oak_canopy_rect(o, art):
    gx, gy = P(o.x, o.y)
    c = art.canopy
    th = o.trunk_h * 40
    return pygame.Rect(round(gx - c.get_width() / 2), round(gy - th - c.get_height() * 0.62), c.get_width(), c.get_height())


# ------------------------------------------------------------------ the pitch
def park_floor(s, rng):
    # mowing stripes, a tile wide, running along x
    for j in range(N):
        for i in range(N):
            c = STRIPE_A if j % 2 == 0 else STRIPE_B
            c = shade(c, rng.uniform(0.97, 1.03))
            poly(s, c, quad_z(i, j, i + 1, j + 1, 0))
    # the worn strip from the batter's spot towards the bowling mark
    bx, by = BAT_SPOT
    mx, my = BOWL_MARK
    L = math.hypot(mx - bx, my - by)
    ux, uy = (mx - bx) / L, (my - by) / L
    vx, vy = -uy, ux
    worn = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    for k in range(5):
        w = 0.75 - k * 0.12
        a0, a1 = -0.6, L * (0.85 - k * 0.12)
        pts = [(bx + ux * a0 + vx * w, by + uy * a0 + vy * w), (bx + ux * a1 + vx * w * 0.8, by + uy * a1 + vy * w * 0.8),
               (bx + ux * a1 - vx * w * 0.8, by + uy * a1 - vy * w * 0.8), (bx + ux * a0 - vx * w, by + uy * a0 - vy * w)]
        poly(worn, (176, 160, 104, 46), [P(x, y) for x, y in pts])
    # bare earth where the batter stands and the fielder runs up
    for (cx, cy, r, a) in ((bx, by, 0.8, 120), (bx + ux * 0.5, by + uy * 0.5, 0.55, 90), (mx, my, 0.5, 70)):
        poly(worn, (166, 140, 92, a), [P(cx + r * math.cos(t), cy + r * math.sin(t) * 0.8) for t in [i * math.pi / 14 for i in range(28)]])
    s.blit(worn, (0, 0))
    # grass texture
    for i in range(1600):
        x, y = rng.uniform(0.1, N - 0.1), rng.uniform(0.1, N - 0.1)
        gx, gy = P(x, y)
        c = shade(STRIPE_A if int(y) % 2 == 0 else STRIPE_B, rng.uniform(0.84, 1.16))
        pygame.draw.line(s, c, (gx, gy), (gx + rng.uniform(-1.5, 1.5), gy - rng.uniform(2, 4)), 1)
    # the painted rings: dashed white arcs round the batter's spot
    W = (244, 246, 238)
    for r in RINGS:
        n = int(r * 14)
        for k in range(n):
            if k % 2:
                continue
            t0, t1 = k * 2 * math.pi / n, (k + 0.62) * 2 * math.pi / n
            a = (bx + r * math.cos(t0), by + r * math.sin(t0))
            b = (bx + r * math.cos(t1), by + r * math.sin(t1))
            if all(0.12 < v < N - 0.12 for v in (*a, *b)):
                pygame.draw.line(s, W, P(*a), P(*b), 2)
    # ring numbers painted on the grass, squashed flat onto the ground
    f = pygame.font.SysFont("dejavusans", 22, bold=True)
    for txt, r, ang in (("1", 1.9, 0.33), ("2", 4.5, 0.38), ("3", 8.0, 0.40), ("1", 1.9, 1.24), ("2", 4.5, 1.19), ("3", 8.0, 1.17)):
        im = f.render(txt, True, W)
        im = pygame.transform.smoothscale(im, (im.get_width(), max(1, im.get_height() // 2)))
        im.set_alpha(200)
        p = P(bx + r * math.cos(ang), by + r * math.sin(ang))
        s.blit(im, im.get_rect(center=p))
    # the batter's spot (a painted circle) and the bowling mark (a short line)
    poly(s, W, [P(bx + 0.34 * math.cos(t), by + 0.34 * math.sin(t)) for t in [i * math.pi / 12 for i in range(24)]], 2)
    pygame.draw.line(s, W, P(mx - vx * 0.45, my - vy * 0.45), P(mx + vx * 0.45, my + vy * 0.45), 3)


def park_back(s, rng):
    """The low privet hedge along the two back edges."""
    h = 24
    t = 0.4
    # along y = 0 (faces +y, in shade) and x = 0 (faces +x, lit)
    poly(s, shade(HEDGE, 0.72), quad_y(0.0, 0.0, N, 0, h))
    poly(s, shade(HEDGE, 1.0), quad_x(0.0, 0.0, N, 0, h))
    poly(s, shade(HEDGE, 1.0), quad_x(N, -t, 0.0, 0, h))        # the ends
    poly(s, shade(HEDGE, 0.72), quad_y(N, -t, 0.0, 0, h))
    poly(s, shade(HEDGE, 1.18), quad_z(-t, -t, N, 0.0, h))
    poly(s, shade(HEDGE, 1.18), quad_z(-t, 0.0, 0.0, N, h))
    # leafy texture: little clumps, lighter on top and on the lit faces
    for k in range(900):
        side = rng.random()
        if side < 0.25:
            x, y, z = rng.uniform(0, N), 0.0, rng.uniform(2, h - 2)
            c = shade(HEDGE, rng.uniform(0.6, 0.85))
        elif side < 0.5:
            x, y, z = 0.0, rng.uniform(0, N), rng.uniform(2, h - 2)
            c = shade(HEDGE, rng.uniform(0.85, 1.2))
        elif side < 0.75:
            x, y, z = rng.uniform(-t, N), rng.uniform(-t, 0), h
            c = shade(HEDGE, rng.uniform(1.05, 1.45))
        else:
            x, y, z = rng.uniform(-t, 0), rng.uniform(0, N), h
            c = shade(HEDGE, rng.uniform(1.05, 1.45))
        gx, gy = P(x, y, z)
        pygame.draw.circle(s, c, (round(gx), round(gy)), rng.choice((1, 2, 2, 3)))
    # a bumpy top edge
    for k in range(int(N * 6)):
        for (x, y) in ((k / 6, -t / 2), (-t / 2, k / 6)):
            gx, gy = P(x, y, h)
            pygame.draw.circle(s, shade(HEDGE, rng.uniform(1.0, 1.3)), (round(gx), round(gy - 1)), 3)


# ------------------------------------------------------------------ outside
def _ground_shadow(s, pts, a=70):
    sh = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    pygame.draw.polygon(sh, (24, 40, 16, a), pts)
    pygame.draw.polygon(sh, (0, 0, 0, 0), quad_z(-0.45, -0.45, N + 0.25, N + 0.25, 0))
    s.blit(sh, (0, 0))


def horizon_y(x):
    """Where the lawn meets the hills (screen y): highest behind the middle."""
    return 184 + ((x - WIN_W / 2) / (WIN_W / 2)) ** 2 * 74


def _tree_ok(x, y, r, th):
    gx, gy = P(x, y)
    # on the lawn (not floating over the hills), and the crown clear of the HUD bar
    return gy > horizon_y(gx) + 6 and gy - th - r * 1.35 > 84


def draw_far_tree(s, x, y, seed, r, th):
    from scene import draw_tree
    if _tree_ok(x, y, r, th):
        draw_tree(s, x, y, seed, r, th)


def draw_bandstand(s, cx, cy):
    """A Victorian bandstand: brick plinth, cream iron posts, a green roof."""
    R = 1.45
    sides = 8
    base_h, post_h, eave = 12, 70, 84
    ang = [math.pi / 8 + i * 2 * math.pi / sides for i in range(sides)]
    ring = lambda r, z: [P(cx + r * math.cos(a), cy + r * math.sin(a), z) for a in ang]
    d = (eave + 30) * SHADOW_K / HW / 2
    _ground_shadow(s, [P(cx + R * math.cos(a) - d * 1.4, cy + R * math.sin(a) + d * 1.4) for a in ang])
    # plinth: visible faces are those facing the viewer (+x+y)
    for i in range(sides):
        a0, a1 = ang[i], ang[(i + 1) % sides]
        nx, ny = math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2)
        if nx + ny < -0.1:
            continue
        light = 0.72 + 0.32 * nx - 0.04 * ny
        q = [P(cx + R * math.cos(a0), cy + R * math.sin(a0), 0), P(cx + R * math.cos(a1), cy + R * math.sin(a1), 0),
             P(cx + R * math.cos(a1), cy + R * math.sin(a1), base_h), P(cx + R * math.cos(a0), cy + R * math.sin(a0), base_h)]
        poly(s, shade((168, 82, 60), light), q)
    poly(s, (214, 204, 186), ring(R, base_h))
    poly(s, (182, 150, 112), ring(R - 0.12, base_h))
    # posts and a balustrade: back half first
    def posts(front):
        for a in ang:
            nx, ny = math.cos(a), math.sin(a)
            if (nx + ny > 0) != front:
                continue
            p0 = P(cx + (R - 0.08) * nx, cy + (R - 0.08) * ny, base_h)
            p1 = P(cx + (R - 0.08) * nx, cy + (R - 0.08) * ny, base_h + post_h)
            pygame.draw.line(s, shade(CREAM, 0.85 + 0.15 * nx), p0, p1, 4)
            pygame.draw.circle(s, CREAM, (round(p1[0]), round(p1[1]) + 2), 3)

    def rail(front):
        for i in range(sides):
            a0, a1 = ang[i], ang[(i + 1) % sides]
            nx, ny = math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2)
            if (nx + ny > 0) != front:
                continue
            for z in (base_h + 6, base_h + 20):
                pygame.draw.line(s, CREAM, P(cx + (R - 0.08) * math.cos(a0), cy + (R - 0.08) * math.sin(a0), z),
                                 P(cx + (R - 0.08) * math.cos(a1), cy + (R - 0.08) * math.sin(a1), z), 2)
            for k in range(1, 5):
                t = k / 5
                ax = cx + (R - 0.08) * (math.cos(a0) * (1 - t) + math.cos(a1) * t)
                ay = cy + (R - 0.08) * (math.sin(a0) * (1 - t) + math.sin(a1) * t)
                pygame.draw.line(s, shade(CREAM, 0.9), P(ax, ay, base_h + 6), P(ax, ay, base_h + 20), 1)
    posts(False)
    rail(False)
    # the band's music stands, a hint of life
    for k, (ox, oy) in enumerate(((-0.4, -0.2), (0.1, -0.5), (0.4, 0.2))):
        p = P(cx + ox, cy + oy, base_h)
        pygame.draw.line(s, (40, 40, 44), p, (p[0], p[1] - 14), 1)
        pygame.draw.line(s, (40, 40, 44), (p[0] - 4, p[1] - 15), (p[0] + 4, p[1] - 13), 2)
    posts(True)
    rail(True)
    # roof: eaves ring, then an ogee-ish pyramid in two tiers, then a finial
    zt = base_h + post_h
    poly(s, shade(CREAM, 0.95), ring(R + 0.12, zt))
    for i in range(sides):
        a0, a1 = ang[i], ang[(i + 1) % sides]
        nx, ny = math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2)
        if nx + ny < -0.3:
            continue
        light = 0.75 + 0.35 * nx - 0.05 * ny
        poly(s, shade(VERDIGRIS, light), [P(cx + (R + 0.12) * math.cos(a0), cy + (R + 0.12) * math.sin(a0), zt),
                                         P(cx + (R + 0.12) * math.cos(a1), cy + (R + 0.12) * math.sin(a1), zt),
                                         P(cx + 0.5 * math.cos(a1), cy + 0.5 * math.sin(a1), zt + 26),
                                         P(cx + 0.5 * math.cos(a0), cy + 0.5 * math.sin(a0), zt + 26)])
        # a scalloped valance under the eaves
        for k in range(3):
            t = (k + 0.5) / 3
            ax = cx + (R + 0.12) * (math.cos(a0) * (1 - t) + math.cos(a1) * t)
            ay = cy + (R + 0.12) * (math.sin(a0) * (1 - t) + math.sin(a1) * t)
            p = P(ax, ay, zt)
            pygame.draw.circle(s, CREAM, (round(p[0]), round(p[1]) + 1), 3)
    for i in range(sides):
        a0, a1 = ang[i], ang[(i + 1) % sides]
        nx, ny = math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2)
        if nx + ny < -0.3:
            continue
        light = 0.8 + 0.35 * nx - 0.05 * ny
        poly(s, shade(VERDIGRIS, light), [P(cx + 0.5 * math.cos(a0), cy + 0.5 * math.sin(a0), zt + 26),
                                         P(cx + 0.5 * math.cos(a1), cy + 0.5 * math.sin(a1), zt + 26),
                                         P(cx, cy, zt + 46)])
    top = P(cx, cy, zt + 46)
    pygame.draw.line(s, (200, 170, 70), top, (top[0], top[1] - 12), 2)
    pygame.draw.circle(s, (220, 190, 80), (round(top[0]), round(top[1]) - 13), 3)


def draw_pond(s, cx, cy, rx, ry, rng):
    pts = [(cx + rx * math.cos(t) * (1 + 0.06 * math.sin(3 * t)), cy + ry * math.sin(t) * (1 + 0.05 * math.cos(2 * t)))
           for t in [i * 2 * math.pi / 60 for i in range(60)]]
    poly(s, (122, 112, 80), [P(x, y) for x, y in [(cx + (px - cx) * 1.09, cy + (py - cy) * 1.14) for px, py in pts]])   # muddy bank
    poly(s, (72, 120, 150), [P(x, y) for x, y in pts])
    inner = [(cx + (px - cx) * 0.78, cy + (py - cy) * 0.72) for px, py in pts]
    poly(s, (96, 150, 184), [P(x, y) for x, y in inner])
    for k in range(14):    # sky glints
        x, y = cx + rng.uniform(-0.7, 0.7) * rx, cy + rng.uniform(-0.6, 0.6) * ry
        gx, gy = P(x, y)
        pygame.draw.line(s, (190, 220, 240), (gx - 6, gy), (gx + 6, gy), 1)
    for k in range(6):     # lily pads
        x, y = cx + rng.uniform(-0.75, 0.75) * rx, cy + rng.uniform(-0.6, 0.6) * ry
        gx, gy = P(x, y)
        pygame.draw.ellipse(s, (70, 130, 60), (gx - 5, gy - 2, 10, 5))
        if k % 2 == 0:
            pygame.draw.circle(s, (246, 200, 220), (round(gx), round(gy - 1)), 2)
    # reeds at the two ends
    for (ex, ey) in ((cx - rx * 0.9, cy + ry * 0.2), (cx + rx * 0.92, cy - ry * 0.25)):
        for k in range(16):
            x, y = ex + rng.uniform(-0.3, 0.3), ey + rng.uniform(-0.35, 0.35)
            gx, gy = P(x, y)
            hgt = rng.uniform(10, 20)
            pygame.draw.line(s, (88, 120, 50), (gx, gy), (gx + rng.uniform(-3, 3), gy - hgt), 2)
            if k % 4 == 0:
                pygame.draw.ellipse(s, (110, 76, 46), (gx - 2, gy - hgt - 2, 4, 8))
    # ducks: a drake, a duck and a duckling or two
    for (x, y, kind) in ((cx - 0.6, cy - 0.1, "drake"), (cx + 0.2, cy + 0.35, "duck"), (cx + 0.55, cy + 0.55, "ling"),
                         (cx + 0.75, cy + 0.45, "ling")):
        gx, gy = P(x, y)
        sc = 0.55 if kind == "ling" else 1.0
        body = (232, 226, 210) if kind == "drake" else ((150, 112, 72) if kind == "duck" else (210, 190, 90))
        pygame.draw.ellipse(s, (60, 100, 130), (gx - 10 * sc, gy - 1, 20 * sc, 4))           # ripple
        pygame.draw.ellipse(s, body, (gx - 8 * sc, gy - 6 * sc, 16 * sc, 8 * sc))
        hx = gx + 6 * sc
        head = (40, 110, 70) if kind == "drake" else body
        pygame.draw.circle(s, head, (round(hx), round(gy - 8 * sc)), max(2, round(3.5 * sc)))
        pygame.draw.polygon(s, (240, 170, 40), [(hx + 3 * sc, gy - 9 * sc), (hx + 7 * sc, gy - 8 * sc), (hx + 3 * sc, gy - 7 * sc)])
        pygame.draw.line(s, shade(body, 0.7), (gx - 8 * sc, gy - 4 * sc), (gx - 11 * sc, gy - 7 * sc), 2)


def draw_houses(s, x0, x1, hy, rng):
    """The town's rooftops beyond the park: little terraces on the hill."""
    x = x0
    cols = [(214, 196, 170), (196, 118, 96), (226, 218, 196), (176, 190, 200), (200, 150, 120)]
    while x < x1:
        w = rng.randint(26, 40)
        h = rng.randint(22, 34)
        c = rng.choice(cols)
        c = mix(c, (170, 196, 220), 0.35)                    # aerial haze
        y = hy(x + w / 2) - 10 + rng.randint(-3, 3)
        pygame.draw.rect(s, c, (x, y - h, w, h))
        pygame.draw.rect(s, shade(c, 1.12), (x + w - 6, y - h, 6, h))       # lit east end
        roof = mix((150, 86, 70) if rng.random() < 0.6 else (92, 100, 112), (170, 196, 220), 0.35)
        pygame.draw.polygon(s, roof, [(x - 2, y - h), (x + w + 2, y - h), (x + w - 6, y - h - 12), (x + 6, y - h - 12)])
        cx = x + rng.randint(6, w - 8)
        pygame.draw.rect(s, shade(roof, 0.85), (cx, y - h - 18, 5, 8))
        for k in range(2):
            pygame.draw.rect(s, mix((70, 90, 110), (170, 196, 220), 0.3), (x + 5 + k * (w // 2), y - h + 7, 6, 7))
        x += w + rng.randint(0, 4)


def park(s, fonts):
    rng = random.Random(21)
    # a clear blue summer sky, deepest at the top
    for y in range(WIN_H):
        t = min(1, y / 320)
        pygame.draw.line(s, mix((64, 136, 222), (196, 224, 246), t ** 1.2), (0, y), (WIN_W, y))
    for cx, cy, sc in ((150, 110, 0.8), (430, 70, 0.6), (900, 104, 0.9), (1160, 66, 0.7)):
        for i in range(8):
            r = int(rng.uniform(14, 26) * sc)
            pygame.draw.circle(s, (252, 253, 255), (cx + int(rng.uniform(-44, 44) * sc), cy + int(rng.uniform(-6, 6) * sc)), r)
        pygame.draw.ellipse(s, (234, 240, 248), (cx - 52 * sc, cy + 4 * sc, 104 * sc, 18 * sc))
    # the far edge of the park: a gentle horizon (lowest at the sides), hills
    # above it with the town's rooftops, and the lawn running up to it
    hy = horizon_y
    pts = [(0, hy(0))] + [(x, hy(x) - 34 - 16 * math.sin(x / 170 + 0.6) - 8 * math.sin(x / 61)) for x in range(0, WIN_W + 20, 20)] + [(WIN_W, hy(WIN_W))]
    pygame.draw.polygon(s, (156, 190, 146), pts + [(WIN_W, WIN_H), (0, WIN_H)])
    draw_houses(s, 0, 330, hy, rng)
    draw_houses(s, 950, WIN_W, hy, rng)
    pygame.draw.polygon(s, LAWN, [(x, hy(x)) for x in range(0, WIN_W + 20, 20)] + [(WIN_W, WIN_H), (0, WIN_H)])
    for i in range(900):
        gx = rng.uniform(0, WIN_W)
        gy = rng.uniform(hy(gx) + 4, WIN_H)
        pygame.draw.line(s, shade(LAWN, rng.uniform(0.82, 1.15)), (gx, gy), (gx + rng.uniform(-2, 2), gy - 3), 1)
    # clumps of trees at the far edge of the park (only where they stand on the lawn)
    for k in range(8):
        draw_far_tree(s, -6.6, 5.5 + k * 1.8, 60 + k, 36, 26)
        draw_far_tree(s, 5.5 + k * 1.8, -6.6, 80 + k, 36, 26)
    # gravel paths behind the hedges, and one up to the bandstand
    poly(s, GRAVEL, quad_z(-1.7, -1.7, -0.9, N + 1.3, 0))
    poly(s, GRAVEL, quad_z(-1.7, -1.7, N + 1.3, -0.9, 0))
    poly(s, GRAVEL, quad_z(-3.0, 4.6, -1.7, 5.4, 0))
    for k in range(400):
        x, y = rng.uniform(-1.7, -0.9), rng.uniform(-1.7, N + 1.3)
        if rng.random() < 0.5:
            x, y = y, x
        gx, gy = P(x, y)
        pygame.draw.circle(s, shade(GRAVEL, rng.uniform(0.8, 1.1)), (round(gx), round(gy)), 1)
    # beyond the left hedge: the bandstand; beyond the right hedge: the duck pond
    draw_bandstand(s, -4.6, 5.0)
    draw_pond(s, 6.6, -3.9, 2.5, 1.25, rng)
    # old oaks at the back corners, clear of the HUD and the pitch
    from scene import draw_tree
    draw_tree(s, -3.0, 11.8, 5, 64, 84)
    draw_tree(s, 12.4, -3.2, 6, 64, 84)
    # a bench and a bin by the pond path
    _bench_y_facing(s, 9.6, -1.55)


def _bench_y_facing(s, x0, y):
    """A park bench outside, along x, its back to the far side (y smaller)."""
    from scene import draw_bench, Obstacle
    draw_bench(s, Obstacle("bench", x0=x0, y0=y - 0.45, x1=x0 + 1.4, y1=y))


def park_props(s):
    """Flat things on the front verges, over the floor: the path and flowerbeds."""
    rng = random.Random(23)
    poly(s, GRAVEL, quad_z(N + 0.45, -1.7, N + 1.25, N + 1.25, 0))
    poly(s, GRAVEL, quad_z(-1.7, N + 0.45, N + 0.45, N + 1.25, 0))
    for k in range(500):
        if rng.random() < 0.5:
            x, y = rng.uniform(N + 0.45, N + 1.25), rng.uniform(-1.7, N + 1.25)
        else:
            x, y = rng.uniform(-1.7, N + 0.45), rng.uniform(N + 0.45, N + 1.25)
        gx, gy = P(x, y)
        pygame.draw.circle(s, shade(GRAVEL, rng.uniform(0.8, 1.1)), (round(gx), round(gy)), 1)
    cols = [(220, 60, 70), (250, 210, 70), (240, 240, 250), (170, 90, 200), (250, 140, 60)]
    for (a, b, L) in ((N + 1.6, 0.6, 3.0), (N + 1.6, 8.6, 3.4), (0.6, N + 1.6, 3.0), (8.6, N + 1.6, 3.4)):
        q = quad_z(a, b, a + 0.9, b + L, 0) if a > N else quad_z(a, b, a + L, b + 0.9, 0)
        poly(s, (100, 72, 48), q)
        poly(s, (78, 120, 60), q, 2)
        xs = [p[0] for p in q]; ys = [p[1] for p in q]
        from scene import _inside
        for k in range(40):
            px, py = rng.uniform(min(xs) + 4, max(xs) - 4), rng.uniform(min(ys) + 3, max(ys) - 3)
            if _inside(q, (px, py)):
                pygame.draw.circle(s, (60, 120, 50), (round(px), round(py)), 4)
                pygame.draw.circle(s, rng.choice(cols), (round(px), round(py) - 2), 2)


# ------------------------------------------------------------------ the front layer
def draw_lamp(s, x, y):
    """A Victorian park lamp-post, about 2 x a child's height."""
    gx, gy = P(x, y)
    H = 200
    d = H * SHADOW_K / HW / 2
    w = 0.09
    _ground_shadow(s, [P(x + w, y - w), P(x + w - d, y - w + d), P(x - w - d, y + w + d), P(x - w, y + w)], 60)
    ex, ey = P(x - d + 0.1, y + d - 0.1)       # the lantern's shadow at the tip
    sh = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (24, 40, 16, 60), (ex - 22, ey - 7, 26, 14))
    pygame.draw.polygon(sh, (0, 0, 0, 0), quad_z(-0.45, -0.45, N + 0.25, N + 0.25, 0))
    s.blit(sh, (0, 0))
    BL = (34, 40, 40)
    pygame.draw.rect(s, BL, (gx - 6, gy - 16, 12, 16))
    pygame.draw.rect(s, shade(BL, 1.6), (gx + 1, gy - 16, 4, 16))
    pygame.draw.rect(s, BL, (gx - 3, gy - H + 30, 6, H - 46))
    pygame.draw.line(s, shade(BL, 1.8), (gx + 1, gy - H + 30), (gx + 1, gy - 16), 1)
    pygame.draw.rect(s, BL, (gx - 8, gy - H + 28, 16, 4))       # ladder bar
    # lantern
    top = gy - H + 28
    pygame.draw.polygon(s, (250, 240, 200), [(gx - 9, top - 4), (gx + 9, top - 4), (gx + 12, top - 28), (gx - 12, top - 28)])
    pygame.draw.polygon(s, BL, [(gx - 9, top - 4), (gx + 9, top - 4), (gx + 12, top - 28), (gx - 12, top - 28)], 2)
    pygame.draw.line(s, BL, (gx, top - 4), (gx, top - 28), 1)
    pygame.draw.polygon(s, BL, [(gx - 15, top - 28), (gx + 15, top - 28), (gx, top - 40)])
    pygame.draw.circle(s, BL, (gx, top - 42), 3)


def park_bench(s, x0, y0, x1, y1, back):
    """A slatted park bench facing the pitch, its back on the far side
    (back="x": along x1, facing -x; back="y": along y1, facing -y)."""
    WOOD = (150, 104, 62)
    BL = (34, 40, 40)
    d = 0.3
    _ground_shadow(s, [P(x0 - d, y0 + d), P(x1 - d, y0 + d), P(x1 - d, y1 + d), P(x0 - d, y1 + d)], 50)
    for (xx, yy) in ((x0 + 0.08, y0 + 0.1), (x1 - 0.08, y0 + 0.1), (x0 + 0.08, y1 - 0.1), (x1 - 0.08, y1 - 0.1)):
        pygame.draw.line(s, BL, P(xx, yy, 0), P(xx, yy, 12), 3)
    box(s, x0, y0, x1, y1, 3, WOOD, z0=12)
    if back == "x":
        for z in (19, 26):
            box(s, x1 - 0.08, y0, x1, y1, 4, shade(WOOD, 0.95), z0=z)
        for yy in (y0 + 0.1, y1 - 0.1):
            pygame.draw.line(s, BL, P(x1 - 0.04, yy, 12), P(x1 - 0.04, yy, 31), 3)
    else:
        for z in (19, 26):
            box(s, x0, y1 - 0.08, x1, y1, 4, shade(WOOD, 0.95), z0=z)
        for xx in (x0 + 0.1, x1 - 0.1):
            pygame.draw.line(s, BL, P(xx, y1 - 0.04, 12), P(xx, y1 - 0.04, 31), 3)


def draw_bin(s, x, y):
    from scene import _cyl, _disc
    r = 0.24
    H = 36
    d = H * SHADOW_K / HW / 2
    _ground_shadow(s, [P(x + r * 0.7, y - r * 0.7), P(x + r * 0.7 - d, y - r * 0.7 + d), P(x - r * 0.7 - d, y + r * 0.7 + d), P(x - r * 0.7, y + r * 0.7)], 60)
    _cyl(s, x, y, r, 0, H, (40, 70, 52))
    for z in (8, H - 8):
        _cyl(s, x, y, r + 0.02, z, z + 3, (200, 170, 70))
    _cyl(s, x, y, r + 0.04, H, H + 5, (34, 60, 44))
    _disc(s, x, y, r + 0.04, H + 5, (50, 84, 62))
    _disc(s, x, y, r * 0.6, H + 5, (20, 26, 22))


def build_park_front():
    """Green iron park railings on the two front edges, then the things that
    stand in front of them: lamp-posts at the side corners, benches and a bin."""
    s = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    H = 26
    e = N + 0.08
    pygame.draw.line(s, IRON, P(e, 0, 3), P(e, e, 3), 3)
    pygame.draw.line(s, IRON, P(0, e, 3), P(e, e, 3), 3)
    for k in range(0, N * 5 + 1):
        u = k / 5
        for p0, p1 in ((P(e, u, 2), P(e, u, H)), (P(u, e, 2), P(u, e, H))):
            pygame.draw.line(s, IRON, p0, p1, 2)
    # hooped tops between the bars
    for k in range(0, N * 5):
        u = k / 5
        for a, b in ((P(e, u, H), P(e, u + 0.2, H)), (P(u, e, H), P(u + 0.2, e, H))):
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - 4
            pygame.draw.lines(s, IRON, False, [a, (mx, my), b], 2)
    pygame.draw.line(s, IRON, P(e, 0, H - 7), P(e, e, H - 7), 2)
    pygame.draw.line(s, IRON, P(0, e, H - 7), P(e, e, H - 7), 2)
    # posts with ball finials every 2 tiles and at the corners
    for k in range(0, N + 1, 2):
        for p in (P(e, k, 0), P(k, e, 0)):
            pygame.draw.rect(s, IRON, (round(p[0]) - 2, round(p[1]) - H - 6, 5, H + 6))
            pygame.draw.circle(s, shade(IRON, 1.5), (round(p[0]), round(p[1]) - H - 8), 4)
    # in front of the railings
    park_bench(s, N + 1.55, 4.6, N + 2.0, 6.0, "x")
    park_bench(s, 4.6, N + 1.55, 6.0, N + 2.0, "y")
    draw_bin(s, N + 1.0, 7.6)
    draw_lamp(s, N + 0.7, -0.9)
    draw_lamp(s, -0.9, N + 0.7)
    return s
