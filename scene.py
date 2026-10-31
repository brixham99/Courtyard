"""The courtyard and its surroundings, drawn once into layers.

The play area (an N x N paved courtyard with a low brick wall at the back and
iron railings at the front) stays the same in every setting so the games play
the same; the surroundings come from a setting builder. There is one setting
so far, the village school; more are meant to be added to SETTINGS.

Layers:
  background  sky, buildings, the ground outside, the courtyard floor and its
              back walls (always behind the players)
  obstacles   things inside the courtyard that are depth-sorted with players
  front       the front railings (always in front of the players)
"""
import math
import random
import pygame

from iso import (WIN_W, WIN_H, HW, HH, N, P, shade, mix, poly, quad_x, quad_y, quad_z, box, SHADOW_K)

BRICK = (156, 68, 50)
MORTAR = (196, 170, 150)
STONE = (206, 198, 178)
SLATE = (84, 92, 104)
GRASS = (98, 150, 72)
PAVE = (176, 172, 164)


# ------------------------------------------------------------------ helpers
def text_on_x_plane(s, font, txt, col, x, ymid, z):
    """Lettering on a wall facing +x (reads left to right along the wall)."""
    im = font.render(txt, True, col)
    w, h = im.get_size()
    cx, cy = P(x, ymid, z)
    for u in range(w):
        dy = -(u - w / 2) * 0.5
        s.blit(im, (round(cx - w / 2 + u), round(cy - h / 2 + dy)), (u, 0, 1, h))


def text_on_y_plane(s, font, txt, col, xmid, y, z):
    """Lettering on a wall facing +y (reads left to right along the wall)."""
    im = font.render(txt, True, col)
    w, h = im.get_size()
    cx, cy = P(xmid, y, z)
    for u in range(w):
        dy = (u - w / 2) * 0.5
        s.blit(im, (round(cx - w / 2 + u), round(cy - h / 2 + dy)), (u, 0, 1, h))


def window_x(s, x, ya, yb, za, zb, frame=(240, 238, 228), glass=(70, 96, 120)):
    """A sash window on a +x wall."""
    poly(s, shade(frame, 0.8), quad_x(x, ya - 0.06, yb + 0.06, za - 5, zb + 4))   # stone surround
    poly(s, glass, quad_x(x, ya, yb, za, zb))
    ym = (ya + yb) / 2
    zm = (za + zb) / 2
    pygame.draw.line(s, frame, P(x, ya, zm), P(x, yb, zm), 2)
    pygame.draw.line(s, frame, P(x, ym, za), P(x, ym, zb), 1)
    poly(s, frame, quad_x(x, ya, yb, za, zb), 2)
    # sky reflected in the top corner
    poly(s, (150, 190, 215), [P(x, ya + 0.05, zb - 3), P(x, ya + (yb - ya) * 0.4, zb - 3), P(x, ya + 0.05, zb - 14)])


def window_y(s, y, xa, xb, za, zb, frame=(240, 238, 228), glass=(56, 78, 100)):
    poly(s, shade(frame, 0.75), quad_y(y, xa - 0.06, xb + 0.06, za - 5, zb + 4))
    poly(s, glass, quad_y(y, xa, xb, za, zb))
    xm = (xa + xb) / 2
    zm = (za + zb) / 2
    pygame.draw.line(s, frame, P(xa, y, zm), P(xb, y, zm), 2)
    pygame.draw.line(s, frame, P(xm, y, za), P(xm, y, zb), 1)
    poly(s, frame, quad_y(y, xa, xb, za, zb), 2)
    poly(s, (130, 168, 196), [P(xa + 0.05, y, zb - 3), P(xa + (xb - xa) * 0.4, y, zb - 3), P(xa + 0.05, y, zb - 14)])


def bricks_x(s, x, y0, y1, z0, z1, col, rng):
    """Brick courses on a +x wall: mortar lines and a little colour variation."""
    poly(s, col, quad_x(x, y0, y1, z0, z1))
    course = 6
    z = z0
    row = 0
    while z < z1:
        zt = min(z1, z + course)
        yy = y0 + (0.12 if row % 2 else 0)
        while yy < y1:
            yb = min(y1, yy + 0.25)
            k = rng.uniform(0.9, 1.08)
            poly(s, shade(col, k), quad_x(x, yy, yb, z, zt - 1))
            yy = yb
        pygame.draw.line(s, shade(MORTAR, 0.9), P(x, y0, zt - 0.5), P(x, y1, zt - 0.5), 1)
        z = zt
        row += 1


def bricks_y(s, y, x0, x1, z0, z1, col, rng):
    poly(s, col, quad_y(y, x0, x1, z0, z1))
    course = 6
    z = z0
    row = 0
    while z < z1:
        zt = min(z1, z + course)
        xx = x0 + (0.12 if row % 2 else 0)
        while xx < x1:
            xb = min(x1, xx + 0.25)
            k = rng.uniform(0.9, 1.08)
            poly(s, shade(col, k), quad_y(y, xx, xb, z, zt - 1))
            xx = xb
        pygame.draw.line(s, shade(MORTAR, 0.66), P(x0, y, zt - 0.5), P(x1, y, zt - 0.5), 1)
        z = zt
        row += 1


def clock_face(s, plane, a, b, z, r_tiles, r_z):
    """A round clock on a wall (plane 'x' at x=a centred y=b, or 'y' at y=a centred x=b)."""
    pts = []
    for i in range(40):
        t = 2 * math.pi * i / 40
        u, v = math.cos(t) * r_tiles, math.sin(t) * r_z
        pts.append(P(a, b + u, z + v) if plane == "x" else P(b + u, a, z + v))
    poly(s, (246, 242, 226), pts)
    poly(s, (40, 36, 30), pts, 2)
    for i in range(12):
        t = 2 * math.pi * i / 12
        u, v = math.cos(t) * r_tiles * 0.82, math.sin(t) * r_z * 0.82
        p = P(a, b + u, z + v) if plane == "x" else P(b + u, a, z + v)
        pygame.draw.circle(s, (40, 36, 30), (round(p[0]), round(p[1])), 1)
    c = P(a, b, z) if plane == "x" else P(b, a, z)
    # ten past ten, the classic shop-window time
    for ang, ln in ((math.radians(-60), 0.5), (math.radians(150 - 180), 0.75)):
        u, v = math.cos(ang) * r_tiles * ln, math.sin(ang) * r_z * ln
        p = P(a, b + u, z + v) if plane == "x" else P(b + u, a, z + v)
        pygame.draw.line(s, (30, 26, 22), c, p, 2)


def tree_surface(seed, r=58):
    """A rounded painted tree canopy, lit from the right (east)."""
    rng = random.Random(seed)
    w = r * 2 + 20
    surf = pygame.Surface((w, int(r * 1.9) + 20), pygame.SRCALPHA)
    cx, cy = w / 2, surf.get_height() / 2
    base = (64, 118, 52)
    for i in range(90):
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(0, 1) ** 0.6 * r * 0.78
        px, py = cx + math.cos(a) * d, cy + math.sin(a) * d * 0.85
        rr = rng.uniform(r * 0.18, r * 0.32)
        light = 0.75 + 0.45 * ((px - cx) / r + 1) / 2 - 0.25 * ((py - cy) / r)
        pygame.draw.circle(surf, shade(base, light * rng.uniform(0.9, 1.05)), (round(px), round(py)), round(rr))
    for i in range(40):
        a = rng.uniform(-1.2, 0.6)
        d = rng.uniform(0.3, 0.8) * r
        px, py = cx + math.cos(a) * d * 0.9, cy + math.sin(a) * d * 0.7
        pygame.draw.circle(surf, (128, 178, 84), (round(px), round(py)), rng.randint(3, 7))
    return surf


def draw_tree(s, x, y, seed, r=58, trunk_h=70):
    """A free-standing tree outside the courtyard: shadow, trunk, canopy."""
    gx, gy = P(x, y)
    sh = pygame.Surface((int(r * 3), int(r * 1.2)), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (20, 40, 10, 80), sh.get_rect())
    s.blit(sh, (gx - sh.get_width() + 30 - trunk_h * SHADOW_K * 0.6, gy - sh.get_height() / 2))
    pygame.draw.rect(s, (92, 66, 44), (gx - 5, gy - trunk_h, 10, trunk_h))
    pygame.draw.rect(s, (120, 90, 60), (gx + 1, gy - trunk_h, 4, trunk_h))
    c = tree_surface(seed, r)
    s.blit(c, (gx - c.get_width() / 2, gy - trunk_h - c.get_height() * 0.75))


# ------------------------------------------------------------------ the courtyard itself
def draw_floor(s, rng):
    """York stone flags, with painted playground markings."""
    for i in range(N):
        for j in range(N):
            k = rng.uniform(0.92, 1.05)
            c = shade((196, 188, 170), k)
            poly(s, c, quad_z(i, j, i + 1, j + 1, 0))
            poly(s, shade(c, 0.86), quad_z(i, j, i + 1, j + 1, 0), 1)
    # hopscotch (yellow) near the left-hand wall
    Y = (232, 196, 60)
    for (x0, y0, x1, y1) in [(1.0, 4.0, 2.0, 5.0), (1.0, 5.0, 2.0, 6.0), (0.5, 6.0, 1.5, 7.0), (1.5, 6.0, 2.5, 7.0),
                             (1.0, 7.0, 2.0, 8.0), (0.5, 8.0, 1.5, 9.0), (1.5, 8.0, 2.5, 9.0), (1.0, 9.0, 2.0, 10.0)]:
        poly(s, Y, quad_z(x0 + 0.04, y0 + 0.04, x1 - 0.04, y1 - 0.04, 0), 2)
    # four square (white) near the far wall
    W = (240, 240, 236)
    poly(s, W, quad_z(5.0, 0.8, 9.0, 2.8, 0), 2)
    pygame.draw.line(s, W, P(7.0, 0.8), P(7.0, 2.8), 2)
    pygame.draw.line(s, W, P(5.0, 1.8), P(9.0, 1.8), 2)
    # a big white circle round the tree, and a wiggly blue snake
    pts = [P(7 + 2.6 * math.cos(t), 7 + 2.6 * math.sin(t)) for t in [i * 2 * math.pi / 64 for i in range(64)]]
    pygame.draw.lines(s, W, True, pts, 2)


def draw_back_walls(s, rng):
    h = 22
    t = 0.28
    # along the x = 0 edge (wall faces +x into the courtyard)
    bricks_y(s, 0.0, -t, 0.0, 0, h, BRICK, rng)
    bricks_x(s, 0.0, -t, N, 0, h, BRICK, rng)
    poly(s, STONE, quad_z(-t - 0.05, -t - 0.05, 0.05, N, h))
    poly(s, shade(STONE, 0.8), quad_x(0.05, -t, N, h - 3, h))
    # along the y = 0 edge (faces +y)
    bricks_y(s, 0.0, 0.0, N, 0, h, shade(BRICK, 0.85), rng)
    poly(s, STONE, quad_z(0.0, -t - 0.05, N, 0.05, h))
    poly(s, shade(STONE, 0.7), quad_y(0.05, 0.0, N, h - 3, h))
    # the end of the y-wall at x = N
    poly(s, shade(BRICK, 1.0), quad_x(N, -t, 0.0, 0, h))
    poly(s, shade(STONE, 0.9), quad_x(N + 0.05, -t - 0.05, 0.05, h - 3, h))
    # the end of the x-wall at y = N
    poly(s, shade(BRICK, 0.72), quad_y(N, -t, 0.0, 0, h))


def build_front():
    """Black iron railings along the two front edges, on a stone plinth."""
    s = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    plinth = 6
    H = 30
    IRON = (28, 30, 34)
    # stone plinth
    poly(s, shade(STONE, 0.72), quad_y(N + 0.18, 0.0, N + 0.18, 0, plinth))
    poly(s, shade(STONE, 1.0), quad_x(N + 0.18, 0.0, N + 0.18, 0, plinth))
    poly(s, STONE, quad_z(N, N, N + 0.18, N + 0.18, plinth))
    poly(s, STONE, [P(0, N, plinth), P(N, N, plinth), P(N, N + 0.18, plinth), P(0, N + 0.18, plinth)])
    poly(s, STONE, [P(N, 0, plinth), P(N + 0.18, 0, plinth), P(N + 0.18, N, plinth), P(N, N, plinth)])
    poly(s, shade(STONE, 0.72), quad_x(0.0, N, N + 0.18, 0, plinth))
    poly(s, shade(STONE, 0.72), quad_y(0.0, N, N + 0.18, 0, plinth))
    # railings
    for k in range(0, N * 4 + 1):
        u = k / 4
        for p0, p1 in ((P(N + 0.09, u, plinth), P(N + 0.09, u, H)), (P(u, N + 0.09, plinth), P(u, N + 0.09, H))):
            pygame.draw.line(s, IRON, p0, p1, 2)
            pygame.draw.polygon(s, IRON, [(p1[0] - 2, p1[1] + 1), (p1[0] + 2, p1[1] + 1), (p1[0], p1[1] - 4)])
    for z in (plinth + 4, H - 4):
        pygame.draw.line(s, IRON, P(N + 0.09, 0, z), P(N + 0.09, N + 0.09, z), 2)
        pygame.draw.line(s, IRON, P(0, N + 0.09, z), P(N + 0.09, N + 0.09, z), 2)
    # stone gate piers at the corners
    for (x, y) in ((N - 0.05, -0.05), (N - 0.05, N - 0.05), (-0.05, N - 0.05)):
        box(s, x, y, x + 0.32, y + 0.32, H + 10, STONE)
        box(s, x - 0.04, y - 0.04, x + 0.36, y + 0.36, 4, shade(STONE, 1.05), z0=H + 10)
    return s


# ------------------------------------------------------------------ obstacles inside
class Obstacle:
    def __init__(self, kind, **kw):
        self.kind = kind
        self.__dict__.update(kw)


def courtyard_obstacles():
    return [
        Obstacle("tree", x=7.0, y=7.0, r=0.85),                      # the old oak in a round brick planter
        Obstacle("planter", x0=3.0, y0=10.2, x1=5.0, y1=11.2),
        Obstacle("planter", x0=10.2, y0=3.0, x1=11.2, y1=5.0),
        Obstacle("bench", x0=10.4, y0=10.6, x1=11.8, y1=11.1),
    ]


def draw_planter(s, o, rng=None):
    rng = rng or random.Random(int(o.x0 * 10 + o.y0))
    h = 16
    bricks_y(s, o.y1, o.x0, o.x1, 0, h, shade(BRICK, 0.9), rng)
    bricks_x(s, o.x1, o.y0, o.y1, 0, h, BRICK, rng)
    poly(s, STONE, quad_z(o.x0 - 0.04, o.y0 - 0.04, o.x1 + 0.04, o.y1 + 0.04, h))
    poly(s, (86, 60, 40), quad_z(o.x0 + 0.12, o.y0 + 0.12, o.x1 - 0.12, o.y1 - 0.12, h))
    cols = [(220, 60, 70), (250, 210, 70), (240, 240, 250), (170, 90, 200), (250, 140, 60)]
    fr = random.Random(int(o.x0 * 7 + o.y1 * 3))
    for i in range(int((o.x1 - o.x0) * (o.y1 - o.y0) * 22)):
        px = fr.uniform(o.x0 + 0.2, o.x1 - 0.2)
        py = fr.uniform(o.y0 + 0.2, o.y1 - 0.2)
        gx, gy = P(px, py, h + 2)
        pygame.draw.circle(s, (60, 120, 50), (round(gx), round(gy - 2)), 4)
        pygame.draw.circle(s, fr.choice(cols), (round(gx + fr.randint(-2, 2)), round(gy - 5)), 2)


def draw_bench(s, o):
    WOOD = (150, 104, 62)
    IRON = (40, 40, 44)
    for yy in (o.y0 + 0.08, o.y1 - 0.08):
        for xx in (o.x0 + 0.1, o.x1 - 0.1):
            pygame.draw.line(s, IRON, P(xx, yy, 0), P(xx, yy, 12), 3)
    box(s, o.x0, o.y0, o.x1, o.y1, 3, WOOD, z0=12)
    # backrest along the far (y0) side
    for z in (20, 27):
        box(s, o.x0, o.y0, o.x1, o.y0 + 0.08, 4, shade(WOOD, 0.95), z0=z)
    for xx in (o.x0 + 0.1, o.x1 - 0.1):
        pygame.draw.line(s, IRON, P(xx, o.y0 + 0.04, 12), P(xx, o.y0 + 0.04, 31), 3)


class TreeArt:
    def __init__(self):
        self.canopy = tree_surface(42, 74)


def draw_tree_base(s, o):
    """The round brick planter and trunk of the courtyard tree."""
    h = 14
    pts_top = [P(o.x + o.r * math.cos(t), o.y + o.r * math.sin(t), h) for t in [i * 2 * math.pi / 40 for i in range(40)]]
    # side wall: front half of the cylinder
    for i in range(40):
        t0 = i * 2 * math.pi / 40
        t1 = (i + 1) * 2 * math.pi / 40
        nx = math.cos((t0 + t1) / 2)
        ny = math.sin((t0 + t1) / 2)
        if nx + ny < -0.05:
            continue
        light = 0.75 + 0.3 * nx - 0.05 * ny
        q = [P(o.x + o.r * math.cos(t0), o.y + o.r * math.sin(t0), 0), P(o.x + o.r * math.cos(t1), o.y + o.r * math.sin(t1), 0),
             P(o.x + o.r * math.cos(t1), o.y + o.r * math.sin(t1), h), P(o.x + o.r * math.cos(t0), o.y + o.r * math.sin(t0), h)]
        poly(s, shade(BRICK, light), q)
    poly(s, STONE, pts_top)
    inner = [P(o.x + (o.r - 0.14) * math.cos(t), o.y + (o.r - 0.14) * math.sin(t), h) for t in [i * 2 * math.pi / 40 for i in range(40)]]
    poly(s, (84, 62, 40), inner)
    gx, gy = P(o.x, o.y, h)
    pygame.draw.rect(s, (88, 62, 42), (gx - 7, gy - 96, 14, 98))
    pygame.draw.rect(s, (122, 92, 62), (gx + 1, gy - 96, 5, 98))
    pygame.draw.line(s, (88, 62, 42), (gx, gy - 70), (gx - 22, gy - 96), 5)
    pygame.draw.line(s, (88, 62, 42), (gx + 2, gy - 80), (gx + 20, gy - 104), 4)


def tree_canopy_rect(o, art):
    gx, gy = P(o.x, o.y, 14)
    c = art.canopy
    return pygame.Rect(round(gx - c.get_width() / 2), round(gy - 96 - c.get_height() * 0.7), c.get_width(), c.get_height())


def draw_obstacle_shadows(s, obstacles):
    """Shadows fall west (screen left)."""
    sh = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    for o in obstacles:
        if o.kind == "tree":
            gx, gy = P(o.x, o.y)
            L = 110 * SHADOW_K * 1.6
            pygame.draw.ellipse(sh, (30, 26, 20, 70), (gx - L - 60, gy - 26, 130, 52))
            pygame.draw.ellipse(sh, (30, 26, 20, 60), (gx - 26, gy - 13, 52, 26))
        elif o.kind == "planter":
            d = 16 * SHADOW_K / HW / 2   # in tiles along (-x, +y) = screen left
            poly(sh, (30, 26, 20, 70), [P(o.x0, o.y0), P(o.x0 - d, o.y0 + d), P(o.x0 - d, o.y1 + d), P(o.x1 - d, o.y1 + d), P(o.x1, o.y1), P(o.x0, o.y1)])
        elif o.kind == "bench":
            d = 0.25
            poly(sh, (30, 26, 20, 55), [P(o.x0 - d, o.y0 + d), P(o.x1 - d, o.y0 + d), P(o.x1 - d, o.y1 + d), P(o.x0 - d, o.y1 + d)])
    s.blit(sh, (0, 0))


# ------------------------------------------------------------------ settings
def village_school(s, fonts):
    """An English village: a Victorian red-brick school down the left, a row of
    pastel cottages (Brixham-style) along the right, ending in a clock tower."""
    rng = random.Random(7)
    # sky
    for y in range(WIN_H):
        t = min(1, y / 330)
        pygame.draw.line(s, mix((96, 160, 226), (204, 226, 242), t), (0, y), (WIN_W, y))
    for cx, cy, sc in ((170, 70, 1.0), (520, 40, 0.7), (980, 80, 1.1), (1180, 30, 0.6), (760, 110, 0.5)):
        for i in range(9):
            r = int(rng.uniform(16, 30) * sc)
            pygame.draw.circle(s, (250, 252, 255), (cx + int(rng.uniform(-50, 50) * sc), cy + int(rng.uniform(-8, 8) * sc)), r)
        pygame.draw.ellipse(s, (232, 238, 246), (cx - 60 * sc, cy + 4 * sc, 120 * sc, 22 * sc))
    # distant hills
    pts = [(0, 330)] + [(x, 300 - 28 * math.sin(x / 210) - 16 * math.sin(x / 77 + 1)) for x in range(0, WIN_W + 20, 20)] + [(WIN_W, 330)]
    pygame.draw.polygon(s, (116, 160, 104), pts + [(WIN_W, WIN_H), (0, WIN_H)])
    # the ground: grass, then a pavement round the courtyard
    poly(s, GRASS, quad_z(-4.8, -4.8, 40, 40, 0))
    # a hedgerow of trees where the ground meets the hills, beyond the buildings
    for k in range(8):
        draw_tree(s, -5.0, 16.4 + k * 1.3, 20 + k, 40, 30)
        draw_tree(s, 16.4 + k * 1.3, -5.0, 40 + k, 40, 30)
    for i in range(500):
        gx, gy = rng.uniform(0, WIN_W), rng.uniform(300, WIN_H)
        pygame.draw.line(s, shade(GRASS, rng.uniform(0.82, 1.15)), (gx, gy), (gx + rng.uniform(-2, 2), gy - 3), 1)
    poly(s, PAVE, quad_z(-1.6, -1.6, N + 1.4, N + 1.4, 0))
    for i in range(-2, N + 2):
        pygame.draw.line(s, shade(PAVE, 0.85), P(i, -1.6), P(i, N + 1.4), 1)
        pygame.draw.line(s, shade(PAVE, 0.85), P(-1.6, i), P(N + 1.4, i), 1)
    poly(s, shade(PAVE, 0.8), quad_z(-1.6, -1.6, N + 1.4, N + 1.4, 0), 2)

    # --- the school, down the x < 0 side
    x0, x1, y0, y1, h = -4.4, -1.6, -1.6, 15.8, 148
    bricks_x(s, x1, y0, y1, 0, h, BRICK, rng)
    # stone bands
    for z in (70, h - 6):
        poly(s, STONE, quad_x(x1 + 0.02, y0, y1, z, z + 6))
    for i, ym in enumerate([0.6 + k * 1.75 for k in range(9)]):
        if 7.2 < ym < 9.0:
            continue
        window_x(s, x1 + 0.01, ym, ym + 0.75, 14, 58)
        window_x(s, x1 + 0.01, ym, ym + 0.75, 86, 132)
    # the door with a stone porch and the school's name
    ym = 8.1
    poly(s, STONE, quad_x(x1 + 0.01, ym - 0.75, ym + 0.75, 0, 64))
    poly(s, (40, 70, 110), quad_x(x1 + 0.02, ym - 0.45, ym + 0.45, 0, 50))
    pygame.draw.line(s, (220, 190, 90), P(x1 + 0.03, ym - 0.1, 26), P(x1 + 0.03, ym - 0.1, 26), 3)
    poly(s, (40, 46, 56), quad_x(x1 + 0.01, ym - 2.1, ym + 2.1, 72, 94))
    text_on_x_plane(s, fonts["sign"], "VILLAGE SCHOOL", (240, 226, 160), x1 + 0.02, ym, 83)
    # gable end (faces +y)
    gab = [P(x0, y1, 0), P(x1, y1, 0), P(x1, y1, h), P((x0 + x1) / 2, y1, h + 62), P(x0, y1, h)]
    poly(s, shade(BRICK, 0.7), gab)
    window_y(s, y1, -3.6, -2.4, 20, 64)
    window_y(s, y1, -3.6, -2.4, 90, 136)
    # roof
    xr = (x0 + x1) / 2
    poly(s, SLATE, [P(x1 + 0.25, y0 - 0.2, h - 4), P(x1 + 0.25, y1 + 0.2, h - 4), P(xr, y1 + 0.2, h + 62), P(xr, y0 - 0.2, h + 62)])
    for k in range(1, 9):
        t = k / 9
        xa = x1 + 0.25 + (xr - x1 - 0.25) * t
        za = h - 4 + 66 * t
        pygame.draw.line(s, shade(SLATE, 0.8), P(xa, y0 - 0.2, za), P(xa, y1 + 0.2, za), 1)
    pygame.draw.line(s, shade(SLATE, 0.6), P(xr, y0 - 0.2, h + 62), P(xr, y1 + 0.2, h + 62), 3)
    poly(s, shade(SLATE, 0.75), [P(x1 + 0.25, y1 + 0.2, h - 4), P(xr, y1 + 0.2, h + 62), P(xr, y1 + 0.2, h + 58), P(x1 + 0.1, y1 + 0.2, h - 4)])
    # bell cupola and chimneys
    box(s, xr - 0.4, 7.7, xr + 0.4, 8.5, 34, (236, 232, 220), z0=h + 50)
    poly(s, (60, 64, 72), [P(xr - 0.5, 7.6, h + 84), P(xr + 0.5, 7.6, h + 84), P(xr + 0.5, 8.6, h + 84), P(xr, 8.1, h + 112)])
    poly(s, (70, 76, 86), [P(xr + 0.5, 7.6, h + 84), P(xr + 0.5, 8.6, h + 84), P(xr, 8.1, h + 112)])
    poly(s, (50, 54, 62), [P(xr - 0.5, 8.6, h + 84), P(xr + 0.5, 8.6, h + 84), P(xr, 8.1, h + 112)])
    pygame.draw.circle(s, (200, 160, 60), P(xr + 0.4, 8.1, h + 66), 5)
    for yc in (2.5, 13.5):
        box(s, xr - 0.3, yc, xr + 0.3, yc + 0.6, 40, shade(BRICK, 0.95), z0=h + 40)
        for k in range(2):
            pygame.draw.rect(s, (170, 90, 60), (*[round(v) for v in P(xr, yc + 0.15 + k * 0.3, h + 86)], 5, 8))

    # --- the cottages, along the y < 0 side
    X0, X1, Y0, Y1, H = -1.6, 12.4, -4.4, -1.6, 116
    colours = [(238, 226, 196), (172, 206, 222), (236, 184, 168), (190, 214, 176), (246, 222, 140)]
    doors = [(40, 70, 120), (170, 40, 40), (40, 100, 70), (30, 30, 34), (90, 60, 120)]
    cw = (X1 - X0) / 5
    for i in range(5):
        a, b = X0 + i * cw, X0 + (i + 1) * cw
        c = colours[i]
        poly(s, shade(c, 0.8), quad_y(Y1, a, b, 0, H))
        poly(s, shade(c, 0.7), quad_y(Y1 + 0.01, a, b, 0, 8))
        window_y(s, Y1 + 0.01, a + 0.3, a + 1.0, 16, 52)
        window_y(s, Y1 + 0.01, a + 0.3, a + 1.0, 70, 104)
        window_y(s, Y1 + 0.01, a + 1.6, a + 2.3, 70, 104)
        poly(s, shade(STONE, 0.8), quad_y(Y1 + 0.01, a + 1.55, a + 2.35, 0, 58))
        poly(s, doors[i], quad_y(Y1 + 0.02, a + 1.65, a + 2.25, 0, 52))
        pygame.draw.circle(s, (220, 190, 90), [round(v) for v in P(a + 2.1, Y1 + 0.02, 26)], 2)
        pygame.draw.line(s, shade(c, 0.6), P(b, Y1 + 0.01, 0), P(b, Y1 + 0.01, H), 1)
    # house numbers would go here; a hanging basket on the middle house
    hb = P(X0 + 2.5 * cw, Y1 + 0.2, 64)
    pygame.draw.circle(s, (60, 110, 50), (round(hb[0]), round(hb[1])), 9)
    for k in range(10):
        pygame.draw.circle(s, rng.choice([(230, 60, 90), (250, 220, 80), (250, 250, 250)]), (round(hb[0] + rng.uniform(-8, 8)), round(hb[1] + rng.uniform(-8, 6))), 2)
    # gable end at X1 (faces +x, lit)
    poly(s, colours[-1], [P(X1, Y0, 0), P(X1, Y1, 0), P(X1, Y1, H), P(X1, (Y0 + Y1) / 2, H + 56), P(X1, Y0, H)])
    window_x(s, X1 + 0.01, -3.6, -2.4, 70, 104)
    # roof
    yr = (Y0 + Y1) / 2
    ROOF = (150, 82, 62)  # clay tiles
    poly(s, ROOF, [P(X0 - 0.2, Y1 + 0.25, H - 4), P(X1 + 0.2, Y1 + 0.25, H - 4), P(X1 + 0.2, yr, H + 56), P(X0 - 0.2, yr, H + 56)])
    for k in range(1, 8):
        t = k / 8
        ya = Y1 + 0.25 + (yr - Y1 - 0.25) * t
        pygame.draw.line(s, shade(ROOF, 0.82), P(X0 - 0.2, ya, H - 4 + 60 * t), P(X1 + 0.2, ya, H - 4 + 60 * t), 1)
    pygame.draw.line(s, shade(ROOF, 0.6), P(X0 - 0.2, yr, H + 56), P(X1 + 0.2, yr, H + 56), 3)
    poly(s, shade(ROOF, 1.15), [P(X1 + 0.2, Y1 + 0.25, H - 4), P(X1 + 0.2, yr, H + 56), P(X1 + 0.2, yr, H + 52), P(X1 + 0.05, Y1 + 0.25, H - 4)])
    for i in range(1, 5):
        xc = X0 + i * cw - 0.3
        box(s, xc, yr - 0.3, xc + 0.6, yr + 0.3, 36, (150, 120, 100), z0=H + 40)
        for k in range(2):
            p = P(xc + 0.15 + k * 0.3, yr, H + 82)
            pygame.draw.rect(s, (180, 96, 64), (round(p[0]) - 2, round(p[1]), 5, 8))

    # --- the clock tower at the right-hand end of the cottage row (clear of the
    #     courtyard tree and below the HUD bar)
    tx0, ty0, tx1, ty1, th = 12.5, -4.4, 15.1, -1.8, 206
    bricks_x(s, tx1, ty0, ty1, 0, th, shade(BRICK, 1.05), rng)
    bricks_y(s, ty1, tx0, tx1, 0, th, shade(BRICK, 0.8), rng)
    for z in (0, 96):
        poly(s, STONE, quad_x(tx1 + 0.01, ty0, ty1, z, z + 6))
        poly(s, shade(STONE, 0.75), quad_y(ty1 + 0.01, tx0, tx1, z, z + 6))
    poly(s, STONE, quad_x(tx1 + 0.01, ty0, ty1, th - 12, th))
    poly(s, shade(STONE, 0.75), quad_y(ty1 + 0.01, tx0, tx1, th - 12, th))
    clock_face(s, "x", tx1 + 0.02, (ty0 + ty1) / 2, 160, 0.8, 26)
    clock_face(s, "y", ty1 + 0.02, (tx0 + tx1) / 2, 160, 0.8, 26)
    tm, tn = (ty0 + ty1) / 2, (tx0 + tx1) / 2
    window_x(s, tx1 + 0.01, tm - 0.35, tm + 0.35, 106, 140)
    window_y(s, ty1 + 0.01, tn - 0.35, tn + 0.35, 106, 140)
    # arched doorway on the front
    poly(s, shade(STONE, 0.8), quad_y(ty1 + 0.01, tn - 0.55, tn + 0.55, 0, 66))
    poly(s, (60, 40, 30), quad_y(ty1 + 0.02, tn - 0.42, tn + 0.42, 0, 58))
    window_x(s, tx1 + 0.01, tm - 0.3, tm + 0.3, 30, 76)
    apex = P(tn, tm, th + 84)
    poly(s, (62, 70, 80), [P(tx0 - 0.15, ty1 + 0.15, th), P(tx1 + 0.15, ty1 + 0.15, th), apex])
    poly(s, (86, 96, 108), [P(tx1 + 0.15, ty1 + 0.15, th), P(tx1 + 0.15, ty0 - 0.15, th), apex])
    pygame.draw.line(s, (200, 160, 60), apex, (apex[0], apex[1] - 20), 2)
    pygame.draw.polygon(s, (200, 160, 60), [(apex[0], apex[1] - 20), (apex[0] + 11, apex[1] - 16), (apex[0], apex[1] - 12)])



def _cyl(s, cx, cy, r, z0, z1, col, segs=28):
    """The visible (front) half of an upright cylinder, lit from +x."""
    for i in range(segs):
        t0, t1 = i * 2 * math.pi / segs, (i + 1) * 2 * math.pi / segs
        nx, ny = math.cos((t0 + t1) / 2), math.sin((t0 + t1) / 2)
        if nx + ny < -0.05:
            continue
        light = 0.74 + 0.32 * nx - 0.04 * ny
        poly(s, shade(col, light), [P(cx + r * math.cos(t0), cy + r * math.sin(t0), z0), P(cx + r * math.cos(t1), cy + r * math.sin(t1), z0),
                                    P(cx + r * math.cos(t1), cy + r * math.sin(t1), z1), P(cx + r * math.cos(t0), cy + r * math.sin(t0), z1)])


def _disc(s, cx, cy, r, z, col):
    poly(s, col, [P(cx + r * math.cos(t), cy + r * math.sin(t), z) for t in [i * 2 * math.pi / 28 for i in range(28)]])


def _outside_shadow(s, pts):
    """A soft ground shadow (falling west), kept off the courtyard floor."""
    sh = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    pygame.draw.polygon(sh, (30, 26, 20, 75), pts)
    pygame.draw.polygon(sh, (0, 0, 0, 0), quad_z(-0.3, -0.3, N + 0.25, N + 0.25, 0))
    s.blit(sh, (0, 0))


PHONE_BOX = (15.6, -0.25, 1.1)       # x, y, size (tiles): beside the right-hand corner pier
PILLAR_BOX = (-0.35, 15.0, 0.32)     # x, y, radius: beside the left-hand corner pier
CHILD_PX = 113                       # Archie/Holly on screen (sprite 166 px x 0.68)


def draw_phone_box(s):
    """A K6 kiosk, about 2.5 m: ~1.55 x a child's height."""
    bx, by, w = PHONE_BOX
    H = round(CHILD_PX * 1.55)               # 175
    RED = (196, 28, 34)
    d = H * SHADOW_K / HW / 2
    _outside_shadow(s, [P(bx, by), P(bx, by + w), P(bx + w, by + w), P(bx + w - d, by + w + d), P(bx - d, by + w + d), P(bx - d, by + d)])
    box(s, bx - 0.06, by - 0.06, bx + w + 0.06, by + w + 0.06, 8, shade(RED, 0.9))       # plinth
    box(s, bx, by, bx + w, by + w, H - 30, RED, z0=8)
    # glazing: 3 columns x 8 rows on the two visible sides, in a door frame
    for side in ("x", "y"):
        for col in range(3):
            for row in range(8):
                za = 26 + row * 13
                a = 0.17 + col * 0.26
                if side == "x":
                    poly(s, (214, 232, 238), quad_x(bx + w + 0.005, by + a, by + a + 0.2, za, za + 10))
                else:
                    poly(s, (160, 186, 198), quad_y(by + w + 0.005, bx + a, bx + a + 0.2, za, za + 10))
    # TELEPHONE signs in the crown
    zc = H - 22
    box(s, bx - 0.03, by - 0.03, bx + w + 0.03, by + w + 0.03, 16, shade(RED, 1.04), z0=zc - 4)
    poly(s, (248, 246, 236), quad_x(bx + w + 0.035, by + 0.18, by + w - 0.18, zc, zc + 8))
    poly(s, (226, 224, 214), quad_y(by + w + 0.035, bx + 0.18, bx + w - 0.18, zc, zc + 8))
    for k in range(9):        # lettering hint
        u = 0.24 + k * (w - 0.48) / 8
        pygame.draw.line(s, (40, 40, 44), P(bx + w + 0.04, by + u, zc + 2), P(bx + w + 0.04, by + u, zc + 6), 1)
        pygame.draw.line(s, (40, 40, 44), P(bx + u, by + w + 0.04, zc + 2), P(bx + u, by + w + 0.04, zc + 6), 1)
    # the domed roof (stepped)
    z = zc + 12
    for k, inset in enumerate((0.0, 0.12, 0.26, 0.4)):
        box(s, bx + inset - 0.04, by + inset - 0.04, bx + w - inset + 0.04, by + w - inset + 0.04, 5 if k < 3 else 4, shade(RED, 1.08 - 0.04 * k), z0=z)
        z += 5
    # door handle
    pygame.draw.line(s, (60, 50, 40), P(bx + w + 0.01, by + 0.12, 70), P(bx + w + 0.01, by + 0.12, 90), 2)


def draw_pillar_box(s):
    """A Royal Mail pillar box, about 1.6 m: a bit taller than the children."""
    cx, cy, r = PILLAR_BOX
    H = round(CHILD_PX * 1.12)               # 127
    RED = (196, 28, 34)
    d = H * SHADOW_K / HW / 2
    gx, gy = P(cx, cy)
    _outside_shadow(s, [P(cx + r * 0.7, cy - r * 0.7), P(cx + r * 0.7 - d, cy - r * 0.7 + d), P(cx - r * 0.7 - d, cy + r * 0.7 + d), P(cx - r * 0.7, cy + r * 0.7)])
    _cyl(s, cx, cy, r + 0.03, 0, 10, (34, 34, 38))                   # black base
    _cyl(s, cx, cy, r, 10, H - 18, RED)
    _cyl(s, cx, cy, r + 0.05, H - 18, H - 12, shade(RED, 1.05))        # the cap rim
    for k, (rr, zz) in enumerate(((r + 0.05, H - 12), (r * 0.85, H - 6), (r * 0.6, H - 2), (r * 0.3, H))):
        _cyl(s, cx, cy, rr, zz - (4 if k else 0), zz, shade(RED, 1.05))
        _disc(s, cx, cy, rr, zz, shade(RED, 1.12 - 0.02 * k))
    # posting slot and the collection plate, on the side facing the viewer (+x+y)
    fx, fy = cx + r * 0.72, cy + r * 0.72
    sx, sy = P(fx, fy, H - 30)
    pygame.draw.rect(s, (24, 20, 20), (round(sx) - 9, round(sy), 18, 4))
    px, py = P(fx, fy, H - 58)
    pygame.draw.rect(s, (238, 236, 226), (round(px) - 7, round(py), 14, 10))
    pygame.draw.rect(s, (200, 160, 60), (round(px) - 4, round(py) + 18, 8, 7))      # cipher


def village_props(s):
    """Things outside the railings, drawn after the floor so nothing covers them;
    placed beside the corner piers so the front railings never cross them."""
    rng = random.Random(9)
    draw_tree(s, 17.6, -0.6, 3, 62, 86)
    draw_tree(s, -0.8, 17.6, 4, 62, 86)
    draw_phone_box(s)
    draw_pillar_box(s)
    # flowerbeds along the front verges
    cols = [(220, 60, 70), (250, 210, 70), (240, 240, 250), (170, 90, 200)]
    for (a, b) in ((N + 1.6, 7.0), (N + 1.6, 10.5), (7.0, N + 1.6), (10.5, N + 1.6)):
        if a > N:
            q = quad_z(a, b, a + 0.8, b + 2.6, 0)
        else:
            q = quad_z(a, b, a + 2.6, b + 0.8, 0)
        poly(s, (96, 70, 46), q)
        xs = [p[0] for p in q]; ys = [p[1] for p in q]
        for k in range(26):
            px, py = rng.uniform(min(xs) + 6, max(xs) - 6), rng.uniform(min(ys) + 4, max(ys) - 4)
            if _inside(q, (px, py)):
                pygame.draw.circle(s, (60, 120, 50), (round(px), round(py)), 4)
                pygame.draw.circle(s, rng.choice(cols), (round(px), round(py) - 2), 2)


def _inside(q, p):
    x, y = p
    inside = False
    n = len(q)
    for i in range(n):
        x1, y1 = q[i]
        x2, y2 = q[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


SETTINGS = {"village_school": ("Village School", village_school, village_props)}


def _register_park():
    import park
    # name, backdrop, props (after the floor), floor, back edge, front layer, obstacles
    SETTINGS["park"] = ("The Park", park.park, park.park_props, park.park_floor, park.park_back,
                        park.build_park_front, park.park_obstacles)


_register_park()


def _register_city():
    import city
    SETTINGS["city"] = ("The City", city.city, city.city_props, city.city_floor, city.city_back,
                        city.build_city_front, city.city_obstacles)


_register_city()


def build_background(setting, fonts):
    # explicit 24-bit, no alpha: on macOS the display format carries an alpha
    # channel, so a default Surface came out fully transparent there
    s = pygame.Surface((WIN_W, WIN_H), 0, 24)
    st = SETTINGS[setting]
    st[1](s, fonts)
    rng = random.Random(11)
    (st[3] if len(st) > 3 else draw_floor)(s, rng)
    (st[4] if len(st) > 4 else draw_back_walls)(s, rng)
    if len(st) > 2:
        st[2](s)      # props outside the railings, over the floor
    return s


def build_front_for(setting):
    st = SETTINGS[setting]
    return st[5]() if len(st) > 5 else build_front()


def obstacles_for(setting):
    st = SETTINGS[setting]
    return st[6]() if len(st) > 6 else courtyard_obstacles()
