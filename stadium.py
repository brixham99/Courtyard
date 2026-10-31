"""The stadium: a small-sided football pitch in a mini community stadium.

Along the back (y < 0) a little covered stand with four tiers of empty seats
in the club's colours, a green back wall and a roof with the scoreboard on
it; floodlight pylons at the corners. Behind the far goal (x < 0) the club car
park, a row of trees and farmland hills. Along the other side (y > N) the
Saturday farmers market: striped awnings over crates of veg, fruit, flowers,
cheese and bread, bunting and chalkboards (no people about). At the near end (x > N)
a hedge, a pavement and a country lane.

The pitch is the same N x N square as the other settings: bright striped
artificial grass, walled by low boards carrying the sponsors' hoardings (with
a cage net above the far boards). The goals themselves are drawn by
football_view, as the ball goes in and out of them.
"""
import math
import os
import random
import pygame
import aa

from iso import WIN_W, WIN_H, HW, HH, N, P, shade, mix, poly, quad_x, quad_y, quad_z, box, SHADOW_K
from scene import ART_DIR
from scene import text_on_x_plane, text_on_y_plane, _cyl, _disc, draw_tree, _prop_art, _soft_shadow

GRASS_A = (82, 166, 74)
GRASS_B = (72, 152, 66)
LINE = (246, 248, 240)
APRON = (92, 104, 98)
PAVING = (184, 180, 170)
ROAD = (82, 84, 88)
VERGE = (118, 164, 84)
BOARD = (246, 246, 240)
STAND = (34, 104, 70)            # club green
SEAT = (40, 90, 170)
ROOF = (70, 78, 92)
STEEL = (196, 202, 208)
GOAL_Y0, GOAL_Y1 = 4.8, 9.2      # the goal mouths (matches football.py)
BOARD_H = 26
CAGE_H = 140
BAR_PX = 128

# the stand
ST_X0, ST_X1 = 0.6, 13.4
ST_FRONT = -0.8                  # the front of the lowest tier
TIER_D, TIER_H, TIERS = 0.82, 22, 3
ST_BACK = ST_FRONT - TIER_D * TIERS - 0.1
ROOF_Z0, ROOF_Z1 = 120, 132      # roof height at the front and the back
# the scoreboard, on the roof's front edge (football_view draws the live score)
SB_X0, SB_X1, SB_Y, SB_Z0, SB_Z1 = 5.5, 8.5, ST_FRONT - 0.05, ROOF_Z0 + 2, ROOF_Z0 + 44

ADS_BACK = (("MILL BAKERY", (250, 236, 200), (150, 70, 30)),
            ("SUNNY ICES", (255, 214, 60), (200, 60, 90)),
            ("HART BIKES", (40, 60, 140), (255, 255, 255)),
            ("PIP'S PIES", (200, 50, 50), (255, 240, 210)),
            ("FARM FRESH", (60, 140, 70), (255, 255, 255)))
ADS_END = (("OAK & ASH", (110, 70, 40), (250, 232, 190)),
           ("BEE HAPPY", (250, 200, 40), (60, 40, 20)),
           ("KIT CORNER", (230, 110, 40), (255, 255, 255)),
           ("DAISY DAIRY", (240, 244, 255), (60, 110, 200)))
ADS_NEAR = (("RIVERSIDE", (60, 120, 190), (255, 255, 255)),
            ("TOP TILES", (250, 250, 246), (60, 60, 70)),
            ("VEG BOX CO", (70, 150, 70), (255, 250, 220)),
            ("BIG SCOOP", (255, 140, 170), (255, 255, 255)),
            ("PENNY'S PETS", (150, 90, 190), (255, 255, 255)))
ADS_NEAR_END = (("CRUMBS CAFE", (120, 70, 40), (255, 230, 170)),
                ("ZOOM TAXIS", (250, 220, 40), (30, 30, 30)))


def _font(size, bold=True):
    return pygame.font.SysFont("dejavusans", size, bold=bold)


def _shadow(s, pts, a=70):
    sh = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    aa.polygon(sh, (20, 22, 26, a), [(round(x), round(y)) for x, y in pts])
    s.blit(sh, (0, 0))


def horizon_y(x):
    """Where the far fields meet the sky (screen y)."""
    return 150 + 18 * math.sin(x / 260 + 0.4)


# ------------------------------------------------------------------ bits and pieces
# the car park's Teslas, painted (tools/cut_cars.py): (sprite, length m, width m)
TESLAS = (("tesla_model3_red", 4.72, 1.85), ("tesla_modely_white", 4.75, 1.92),
          ("tesla_models_grey", 4.97, 1.96), ("tesla_modelx_blue", 5.04, 2.00),
          ("tesla_cybertruck", 5.68, 2.03))
CAR_TILES_PER_M = 0.51          # (0.85 x 0.6: Nathan had them 40% smaller)
PARK_X0, PARK_X1 = -6.9, -1.3   # the car park, behind the far goal
BAY_NOSE = -1.75                # every car parks nose-in up to this line
BAY_W, BAY_LEN = 1.55, 3.4      # bay width (along y) and depth (along x)
# two runs of bays either side of the far goal, so no car hides behind it: (first bay's y, bays)
BAY_RUNS = ((-2.2, 2), (9.0, 3))


def car(s, name, length_m, width_m, y_mid):
    """A painted Tesla parked nose-in (towards the pitch), its length along x."""
    L, W = length_m * CAR_TILES_PER_M, width_m * CAR_TILES_PER_M
    x1 = BAY_NOSE
    x0 = x1 - L
    y0, y1 = y_mid - W / 2, y_mid + W / 2
    # soft shadow, falling west (screen left), plus a darker patch under the body
    d = 0.35
    _soft_shadow(s, [P(x0 - d, y0 + d), P(x1 - d, y0 + d), P(x1 - d, y1 + d), P(x0 - d, y1 + d)], alpha=70, blur=5)
    _soft_shadow(s, [P(x0 + 0.2, y0 + 0.1), P(x1 - 0.2, y0 + 0.1), P(x1 - 0.2, y1 - 0.05), P(x0 + 0.2, y1 - 0.05)], alpha=90, blur=3)
    left, right = P(x0, y1)[0], P(x1, y0)[0]
    raw = pygame.image.load(os.path.join(ART_DIR, f"{name}.png"))
    rw, rh = raw.get_size()
    w = round(right - left)
    img = _prop_art(name, max(1, round(rh * w / rw)))
    iw, ih = img.get_size()
    bottom = P(x1, y1)[1] + 3
    s.blit(img, (round((left + right) / 2 - iw / 2), round(bottom - ih)))


def floodlight(s, x, y, H=236):
    """A lattice floodlight pylon with a bank of lamps on top, facing the pitch."""
    gx, gy = P(x, y)
    d = H * SHADOW_K / HW / 2
    _shadow(s, [P(x + 0.15, y - 0.15), P(x - d + 0.1, y + d - 0.1), P(x - d - 0.1, y + d + 0.1), P(x - 0.15, y + 0.15)], 45)
    G = (150, 156, 164)
    base_w, top_w = 10, 3
    for side in (-1, 1):
        aa.line(s, shade(G, 0.8 if side < 0 else 1.1), (gx + side * base_w, gy), (gx + side * top_w, gy - H), 3)
    k = 0
    for z in range(0, H - 10, 18):
        w0 = base_w + (top_w - base_w) * z / H
        w1 = base_w + (top_w - base_w) * (z + 18) / H
        a = (gx - w0, gy - z) if k % 2 == 0 else (gx + w0, gy - z)
        b = (gx + w1, gy - z - 18) if k % 2 == 0 else (gx - w1, gy - z - 18)
        aa.line(s, shade(G, 0.9), a, b, 1)
        aa.line(s, shade(G, 0.9), (gx - w0, gy - z), (gx + w0, gy - z), 1)
        k += 1
    # the lamp bank: a grid of lamps in a frame
    hw, hh = 26, 20
    top = gy - H - hh + 4
    pygame.draw.rect(s, (60, 64, 72), (gx - hw - 3, top - 3, 2 * hw + 6, hh + 6), border_radius=3)
    for i in range(4):
        for j in range(3):
            cx = gx - hw + 7 + i * 13
            cy = top + 4 + j * 7
            pygame.draw.rect(s, (255, 252, 226), (cx - 5, cy - 2, 10, 5), border_radius=2)
    aa.line(s, (60, 64, 72), (gx, gy - H), (gx, top + hh), 3)


def crate(s, x, y, w, d, col=(186, 140, 86), z0=0, h=8):
    box(s, x, y, x + w, y + d, h, col, z0=z0)
    aa.line(s, shade(col, 0.6), P(x + w, y, z0 + h / 2), P(x + w, y + d, z0 + h / 2), 1)
    aa.line(s, shade(col, 0.5), P(x, y + d, z0 + h / 2), P(x + w, y + d, z0 + h / 2), 1)


def heap(s, x, y, w, d, z, kind, rng):
    """A crate topped with produce: little round shapes in the produce's colours."""
    crate(s, x, y, w, d, z0=z, h=7)
    top = z + 7
    cols = {"apples": [(200, 40, 40), (220, 70, 50), (170, 200, 60)],
            "oranges": [(250, 150, 30), (240, 130, 20)],
            "lemons": [(250, 226, 60), (240, 214, 50)],
            "carrots": [(240, 120, 30)],
            "cabbage": [(110, 170, 80), (130, 190, 90)],
            "tomatoes": [(220, 40, 30), (200, 30, 30)],
            "potatoes": [(196, 160, 110), (180, 146, 98)],
            "plums": [(110, 50, 110), (130, 60, 120)],
            "pears": [(190, 200, 80), (170, 190, 70)]}[kind]
    n = 9 if kind != "cabbage" else 4
    for i in range(n):
        u, v = rng.uniform(0.12, 0.88), rng.uniform(0.15, 0.85)
        gx, gy = P(x + u * w, y + v * d, top + 2)
        c = rng.choice(cols)
        if kind == "carrots":
            aa.line(s, c, (gx - 4, gy + 1), (gx + 4, gy - 1), 3)
            aa.line(s, (80, 160, 60), (gx + 4, gy - 1), (gx + 7, gy - 4), 2)
        elif kind == "cabbage":
            aa.circle(s, shade(c, 0.8), (round(gx), round(gy) - 1), 6)
            aa.circle(s, c, (round(gx) - 1, round(gy) - 2), 4)
        else:
            r = 3 if kind != "potatoes" else 3
            aa.circle(s, c, (round(gx), round(gy)), r)
            aa.circle(s, shade(c, 1.3), (round(gx) - 1, round(gy) - 1), 1)


def flowers(s, x, y, z, rng):
    """Buckets of flowers: a bucket and a bunch of colourful heads on stems."""
    for i in range(3):
        bx, by = x + i * 0.42, y
        gx, gy = P(bx + 0.15, by + 0.15, z)
        aa.polygon(s, (90, 100, 120), [(gx - 6, gy - 12), (gx + 6, gy - 12), (gx + 5, gy), (gx - 5, gy)])
        aa.ellipse(s, (130, 140, 160), (gx - 6, gy - 14, 12, 5))
        cols = rng.choice([[(240, 80, 120), (250, 160, 190)], [(250, 220, 60), (250, 180, 40)],
                           [(160, 90, 220), (200, 150, 240)], [(250, 250, 250), (250, 120, 60)]])
        for k in range(7):
            fx, fy = gx + rng.uniform(-8, 8), gy - 16 - rng.uniform(0, 12)
            aa.line(s, (60, 130, 60), (gx, gy - 12), (fx, fy), 1)
            aa.circle(s, rng.choice(cols), (round(fx), round(fy)), 3)


def cheeses(s, x, y, z):
    """Wheels and wedges of cheese on a board."""
    poly(s, (170, 120, 70), quad_z(x, y, x + 1.6, y + 0.55, z + 2))
    for i, (u, c, r) in enumerate(((0.3, (246, 206, 90), 0.2), (0.8, (236, 180, 60), 0.18), (1.3, (250, 230, 160), 0.16))):
        _cyl(s, x + u, y + 0.28, r, z + 2, z + 10, c, segs=16)
        _disc(s, x + u, y + 0.28, r, z + 10, shade(c, 1.08))
    # a wedge with holes
    gx, gy = P(x + 1.0, y + 0.45, z + 3)
    aa.polygon(s, (250, 220, 90), [(gx - 9, gy), (gx + 9, gy - 2), (gx - 9, gy - 8)])
    aa.circle(s, (220, 180, 60), (round(gx - 4), round(gy - 3)), 1)


def breads(s, x, y, z, rng):
    """Loaves, baguettes and buns in wicker baskets."""
    for i in range(3):
        bx = x + i * 0.55
        gx, gy = P(bx + 0.2, y + 0.25, z)
        aa.ellipse(s, (170, 120, 60), (gx - 12, gy - 6, 24, 10))
        aa.ellipse(s, (140, 96, 46), (gx - 12, gy - 6, 24, 10), 1)
        if i == 0:
            for k in range(3):
                aa.ellipse(s, (206, 150, 80), (gx - 10 + k * 6, gy - 12, 8, 7))
        elif i == 1:
            for k in range(2):
                aa.line(s, (214, 160, 90), (gx - 9, gy - 6 - k * 3), (gx + 9, gy - 12 - k * 3), 5)
        else:
            aa.ellipse(s, (196, 136, 70), (gx - 10, gy - 14, 20, 12))
            for k in range(3):
                aa.line(s, (236, 200, 140), (gx - 5 + k * 5, gy - 13), (gx - 7 + k * 5, gy - 6), 1)


def chalkboard(s, x, y, words, font, seed):
    """An A-frame chalkboard on the pavement, with a chalk word and little drawings (shapes, no symbols)."""
    rng = random.Random(seed)
    gx, gy = P(x, y)
    gx, gy = round(gx), round(gy)
    w, h = 34, 38
    aa.polygon(s, (110, 76, 46), [(gx - w // 2 - 3, gy), (gx - w // 2 + 2, gy - h - 4), (gx + w // 2 - 2, gy - h - 4), (gx + w // 2 + 3, gy)])
    r = pygame.Rect(gx - w // 2 + 2, gy - h, w - 4, h - 6)
    pygame.draw.rect(s, (40, 46, 44), r)
    im = font.render(words, True, (240, 240, 230))
    if im.get_width() > r.w - 2:
        im = pygame.transform.smoothscale(im, (r.w - 2, im.get_height()))
    s.blit(im, im.get_rect(midtop=(r.centerx, r.y + 3)))
    # chalk drawings: a little apple or carrot and a wavy underline
    c = rng.choice([(250, 140, 120), (250, 200, 110), (160, 230, 140)])
    aa.circle(s, c, (r.centerx - 6, r.bottom - 10), 4, 1)
    aa.line(s, (160, 230, 140), (r.centerx - 6, r.bottom - 14), (r.centerx - 4, r.bottom - 17), 1)
    aa.lines(s, (240, 240, 230), False, [(r.centerx + 1 + i * 3, r.bottom - 9 + (i % 2) * 2) for i in range(4)], 1)


def stall(s, x0, x1, y0, y1, stripe, kind, label, font, rng):
    """A market stall facing the viewer (+y): counter, goods, posts and a striped awning."""
    wood = (150, 108, 66)
    cloth = stripe
    # the counter: a trestle table with a cloth over it
    box(s, x0 + 0.1, y0 + 0.35, x1 - 0.1, y1, 18, (236, 230, 216))
    poly(s, cloth, quad_y(y1, x0 + 0.1, x1 - 0.1, 6, 18))
    aa.lines(s, shade(cloth, 0.7), False, [P(x0 + 0.1 + i * 0.25, y1, 6 - (i % 2) * 2) for i in range(int((x1 - x0 - 0.2) / 0.25) + 1)], 1)
    # crates on the ground in front, and the goods on top
    z = 18
    w = x1 - x0
    if kind == "veg":
        heap(s, x0 + 0.2, y0 + 0.45, 0.6, 0.45, z, "carrots", rng)
        heap(s, x0 + 0.85, y0 + 0.45, 0.6, 0.45, z, "cabbage", rng)
        heap(s, x0 + 1.5, y0 + 0.45, 0.55, 0.45, z, "tomatoes", rng)
        heap(s, x1 + 0.05, y1 - 0.3, 0.5, 0.5, 0, "potatoes", rng)
    elif kind == "fruit":
        heap(s, x0 + 0.2, y0 + 0.45, 0.6, 0.45, z, "apples", rng)
        heap(s, x0 + 0.85, y0 + 0.45, 0.6, 0.45, z, "oranges", rng)
        heap(s, x0 + 1.5, y0 + 0.45, 0.55, 0.45, z, "pears", rng)
        heap(s, x1 + 0.05, y1 - 0.3, 0.5, 0.5, 0, "lemons", rng)
    elif kind == "flowers":
        flowers(s, x0 + 0.25, y0 + 0.4, z, rng)
        flowers(s, x1 + 0.0, y1 - 0.25, 0, rng)
    elif kind == "cheese":
        cheeses(s, x0 + 0.3, y0 + 0.4, z)
    elif kind == "bread":
        breads(s, x0 + 0.25, y0 + 0.45, z, rng)
    # posts
    TOP_B, TOP_F = 60, 50
    for (px, py, top) in ((x0, y0 + 0.1, TOP_B), (x1, y0 + 0.1, TOP_B), (x0, y1 + 0.2, TOP_F), (x1, y1 + 0.2, TOP_F)):
        aa.line(s, wood, P(px, py), P(px, py, top), 3)
    # the awning: stripes running down the slope
    n = max(4, int(w / 0.3))
    for i in range(n):
        a, b = x0 + w * i / n, x0 + w * (i + 1) / n
        col = stripe if i % 2 == 0 else (250, 250, 246)
        poly(s, col, [P(a, y0, TOP_B + 2), P(b, y0, TOP_B + 2), P(b, y1 + 0.3, TOP_F), P(a, y1 + 0.3, TOP_F)])
    # the scalloped valance along the front, and a name board on it
    for i in range(n):
        a = x0 + w * (i + 0.5) / n
        col = stripe if i % 2 == 0 else (250, 250, 246)
        cx, cy = P(a, y1 + 0.3, TOP_F)
        aa.circle(s, col, (round(cx), round(cy)), 6, draw_top_left=False, draw_top_right=False,
                           draw_bottom_left=True, draw_bottom_right=True)
        aa.polygon(s, col, [P(x0 + w * i / n, y1 + 0.3, TOP_F), P(x0 + w * (i + 1) / n, y1 + 0.3, TOP_F),
                                     P(x0 + w * (i + 1) / n, y1 + 0.3, TOP_F - 2), P(x0 + w * i / n, y1 + 0.3, TOP_F - 2)])
    aa.line(s, shade(stripe, 0.7), P(x0, y1 + 0.3, TOP_F), P(x1, y1 + 0.3, TOP_F), 1)
    tw = font.size(label)[0] / HW + 0.3
    xm = (x0 + x1) / 2
    poly(s, (250, 246, 232), quad_y(y1 + 0.32, xm - tw / 2, xm + tw / 2, TOP_F + 1, TOP_F + 14))
    poly(s, shade(stripe, 0.6), quad_y(y1 + 0.32, xm - tw / 2, xm + tw / 2, TOP_F + 1, TOP_F + 14), 1)
    text_on_y_plane(s, font, label, shade(stripe, 0.55), xm, y1 + 0.33, TOP_F + 7.5)


def bunting(s, pts, rng, z_low=58, sag=8):
    """Strings of little flags between points (world xy, z px), sagging between them."""
    cols = [(220, 50, 50), (250, 200, 40), (60, 140, 220), (80, 180, 90), (250, 250, 250), (240, 120, 180)]
    k = 0
    for (xa, ya, za), (xb, yb, zb) in zip(pts, pts[1:]):
        n = 10
        line = []
        for i in range(n + 1):
            t = i / n
            dz = sag * math.sin(math.pi * t)
            line.append(P(xa + (xb - xa) * t, ya + (yb - ya) * t, za + (zb - za) * t - dz))
        aa.lines(s, (90, 90, 90), False, line, 1)
        for i in range(n):
            (ax, ay), (bx, by) = line[i], line[i + 1]
            mx, my = (ax + bx) / 2, (ay + by) / 2
            aa.polygon(s, cols[k % len(cols)], [(ax + (bx - ax) * 0.15, ay + (by - ay) * 0.15),
                                                         (ax + (bx - ax) * 0.85, ay + (by - ay) * 0.85), (mx, my + 9)])
            k += 1


# ------------------------------------------------------------------ the backdrop
def stadium(s, fonts):
    rng = random.Random(41)
    # a warm afternoon sky, peachy at the horizon
    for y in range(WIN_H):
        t = min(1, y / 230)
        aa.line(s, mix((92, 152, 220), (242, 222, 196), t ** 1.4), (0, y), (WIN_W, y))
    for cx, cy, sc in ((120, 92, 0.7), (380, 52, 0.55), (1180, 70, 0.6)):
        for i in range(7):
            r = int(rng.uniform(14, 24) * sc)
            aa.circle(s, (255, 250, 244), (cx + int(rng.uniform(-40, 40) * sc), cy + int(rng.uniform(-6, 6) * sc)), r)
        aa.ellipse(s, (244, 236, 230), (cx - 48 * sc, cy + 4 * sc, 96 * sc, 16 * sc))
    # far farmland: two rows of rolling hills patched with fields and hedgerows
    hy = horizon_y
    for layer, (col, lift, amp) in enumerate((((150, 176, 150), 40, 14), ((128, 170, 110), 18, 9))):
        pts = [(x, hy(x) - lift - amp * math.sin(x / (120 + 50 * layer) + layer)) for x in range(0, WIN_W + 20, 20)]
        aa.polygon(s, col, pts + [(WIN_W, WIN_H), (0, WIN_H)])
        if layer == 1:
            # field boundaries: hedgerow lines down the slopes, and a few crop-coloured fields
            for fx in range(30, WIN_W, 90):
                top = hy(fx) - lift - amp * math.sin(fx / 170 + 1)
                fc = rng.choice([(196, 186, 100), (150, 186, 100), (176, 196, 120), (120, 160, 92)])
                aa.polygon(s, fc, [(fx, top + 3), (fx + 80, top + 1 - 4 * math.sin(fx)), (fx + 84, hy(fx + 84)), (fx - 4, hy(fx))])
                aa.line(s, (90, 120, 70), (fx - 4, top + 2), (fx - 6, hy(fx)), 2)
    # a little church and some farm buildings on the hills
    def house(x, base, w, h, col, roof):
        pygame.draw.rect(s, col, (x, base - h, w, h))
        aa.polygon(s, roof, [(x - 3, base - h), (x + w + 3, base - h), (x + w // 2, base - h - w // 2)])
    b = hy(150) - 12
    house(130, b, 22, 14, (230, 222, 206), (150, 80, 60))
    pygame.draw.rect(s, (200, 194, 180), (160, b - 30, 9, 30))
    aa.polygon(s, (110, 110, 120), [(158, b - 30), (171, b - 30), (164.5, b - 52)])
    house(176, b, 30, 12, (214, 206, 190), (120, 70, 60))
    house(1210, hy(1210) - 14, 26, 13, (200, 60, 50), (90, 90, 96))
    house(1240, hy(1240) - 12, 18, 10, (230, 222, 206), (140, 80, 60))
    # the ground beyond: a verge of grass up to the horizon
    aa.polygon(s, VERGE, [(x, hy(x)) for x in range(0, WIN_W + 20, 20)] + [(WIN_W, WIN_H), (0, WIN_H)])
    for i in range(500):
        gx = rng.uniform(0, WIN_W)
        gy = rng.uniform(hy(gx) + 3, WIN_H)
        aa.line(s, shade(VERGE, rng.uniform(0.85, 1.15)), (gx, gy), (gx + rng.uniform(-2, 2), gy - 3), 1)

    # behind the far goal: the club car park, with a row of trees behind it
    poly(s, ROAD, quad_z(PARK_X0, -5.0, PARK_X1, N + 0.6, 0))
    for k in range(400):
        x, y = rng.uniform(PARK_X0, PARK_X1), rng.uniform(-5, N + 0.6)
        gx, gy = P(x, y)
        s.set_at((round(gx), round(gy)), shade(ROAD, rng.uniform(0.8, 1.2)))
    # trees along the back of the car park (only where they stand on the ground)
    for k in range(9):
        x, y = -7.6, -1.6 + k * 1.9
        gx, gy = P(x, y)
        if gy > hy(gx) + 6 and gx > -30:
            draw_tree(s, x, y, 70 + k, 36, 30)
    # the marked bays, nose-in towards the pitch, and the five Teslas in them
    LINE = (232, 232, 226)
    bx0, bx1 = BAY_NOSE + 0.25 - BAY_LEN, BAY_NOSE + 0.25
    bays = []
    for y0, n in BAY_RUNS:
        for i in range(n + 1):
            y = y0 + i * BAY_W
            aa.line(s, LINE, P(bx0, y), P(bx1, y), 2)
        aa.line(s, LINE, P(bx1, y0), P(bx1, y0 + n * BAY_W), 2)
        bays += [y0 + (i + 0.5) * BAY_W for i in range(n)]
    aa.line(s, (240, 210, 60), P(PARK_X1 - 0.12, -3.0), P(PARK_X1 - 0.12, N + 0.6), 2)
    for i, (name, lm, wm) in enumerate(TESLAS):
        car(s, name, lm, wm, bays[i])

    # the near end: a hedge, a pavement and a country lane beyond
    poly(s, PAVING, quad_z(15.2, -6, 16.4, N + 6, 0))
    for i in range(-6, N + 6):
        aa.line(s, shade(PAVING, 0.86), P(15.2, i), P(16.4, i), 1)
    poly(s, (214, 212, 204), quad_z(16.3, -6, 16.45, N + 6, 0))
    poly(s, ROAD, quad_z(16.45, -6, 19.4, N + 6, 0))
    for k in range(260):
        x, y = rng.uniform(16.45, 19.4), rng.uniform(-6, N + 6)
        gx, gy = P(x, y)
        s.set_at((round(gx), round(gy)), shade(ROAD, rng.uniform(0.8, 1.2)))
    for k in range(-6, N + 6, 2):
        aa.line(s, (236, 236, 230), P(17.92, k), P(17.92, k + 1.1), 3)
    poly(s, VERGE, quad_z(19.4, -6, 24, N + 6, 0))
    for k, y in enumerate((-2.6, 1.6, 6.0)):
        draw_tree(s, 20.2, y, 90 + k, 40, 44)


def stadium_floor(s, rng):
    """The apron round the pitch, the striped artificial grass and its lines."""
    poly(s, APRON, quad_z(-1.3, ST_FRONT, 15.2, N + 0.9, 0))
    for k in range(900):
        x, y = rng.uniform(-1.3, 15.2), rng.uniform(ST_FRONT, N + 0.9)
        gx, gy = P(x, y)
        s.set_at((round(gx), round(gy)), shade(APRON, rng.uniform(0.85, 1.15)))
    # mown-look stripes across the pitch
    for i in range(N):
        poly(s, GRASS_A if i % 2 == 0 else GRASS_B, quad_z(i, 0, i + 1, N, 0))
    for k in range(3000):
        x, y = rng.uniform(0, N), rng.uniform(0, N)
        gx, gy = P(x, y)
        base = GRASS_A if int(x) % 2 == 0 else GRASS_B
        s.set_at((round(gx), round(gy)), shade(base, rng.uniform(0.86, 1.14)))
    m = 0.18
    aa.lines(s, LINE, True, quad_z(m, m, N - m, N - m, 0), 3)
    aa.line(s, LINE, P(7, m), P(7, N - m), 3)
    ring = lambda cx, cy, r, a0=0.0, a1=2 * math.pi, n=64: [P(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
    aa.lines(s, LINE, True, ring(7, 7, 1.7)[:-1], 2)
    poly(s, LINE, ring(7, 7, 0.09)[:-1])
    for side, gx in ((1, m), (-1, N - m)):
        # the penalty area, the goal area, the spot and the arc
        fx = gx + side * 2.6
        aa.lines(s, LINE, False, [P(gx, 3.2), P(fx, 3.2), P(fx, 10.8), P(gx, 10.8)], 2)
        ex = gx + side * 1.0
        aa.lines(s, LINE, False, [P(gx, 4.3), P(ex, 4.3), P(ex, 9.7), P(gx, 9.7)], 2)
        poly(s, LINE, ring(gx + side * 1.9, 7, 0.07)[:-1])
        a = math.acos(0.7 / 1.25)
        aa.lines(s, LINE, False, [P(gx + side * 1.9 + side * 1.25 * math.cos(t), 7 + 1.25 * math.sin(t))
                                           for t in [-a + 2 * a * i / 20 for i in range(21)]], 2)
        # corner arcs
        for cy, sg in ((m, 1), (N - m, -1)):
            aa.lines(s, LINE, False, ring(gx, cy, 0.4, 0 if (side > 0) == (sg > 0) else math.pi,
                                                   (0 if (side > 0) == (sg > 0) else math.pi) + (math.pi / 2 if side * sg > 0 else -math.pi / 2), 8), 2)
    # the stand's shadow over the near touchline strip (the sun is in the east, shadows fall west)
    d = ROOF_Z0 * SHADOW_K / HW / 2
    _shadow(s, [P(ST_X0, ST_FRONT), P(ST_X1, ST_FRONT), P(ST_X1 - d, ST_FRONT + d * 0.7), P(ST_X0 - d, ST_FRONT + d * 0.7)], 50)
    # the goals' shadows
    for gxl, sd in ((0.0, 1), (float(N), -1)):
        dz = BAR_PX * SHADOW_K / HW / 2
        w = 0.05
        _shadow(s, [P(gxl - w, GOAL_Y0), P(gxl - w - dz, GOAL_Y0 + dz), P(gxl - w - dz, GOAL_Y1 + dz), P(gxl - w, GOAL_Y1),
                    P(gxl + w, GOAL_Y1), P(gxl + w - dz + 0.1, GOAL_Y1 + dz - 0.1), P(gxl + w - dz + 0.1, GOAL_Y0 + dz + 0.1), P(gxl + w, GOAL_Y0)], 40)


def _fit(font, name, px):
    """The font itself if the name fits in px, else a smaller one that does."""
    if font.size(name)[0] <= px:
        return font
    for size in (11, 10, 9, 8):
        f = _font(size)
        if f.size(name)[0] <= px:
            return f
    return _font(8)


def _ad_y(s, x0, x1, y, z0, z1, ad, font):
    name, bg, fg = ad
    font = _fit(font, name, (x1 - x0) * HW - 8)
    poly(s, bg, quad_y(y, x0, x1, z0, z1))
    text_on_y_plane(s, font, name, fg, (x0 + x1) / 2, y + 0.005, (z0 + z1) / 2)
    aa.line(s, shade(bg, 0.7), P(x0, y, z0), P(x0, y, z1), 1)


def _ad_x(s, x, y0, y1, z0, z1, ad, font):
    name, bg, fg = ad
    font = _fit(font, name, (y1 - y0) * HW - 8)
    poly(s, bg, quad_x(x, y0, y1, z0, z1))
    text_on_x_plane(s, font, name, fg, x + 0.005, (y0 + y1) / 2, (z0 + z1) / 2)
    aa.line(s, shade(bg, 0.7), P(x, y0, z0), P(x, y0, z1), 1)


def _mesh(s, plane, length, z0, z1, spacing=0.34, alpha=70):
    """A square cage net on a plane: plane(u, z) gives the screen point."""
    m = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    col = (230, 236, 240, alpha)
    u = 0.0
    while u <= length + 1e-6:
        pygame.draw.aaline(m, col, plane(u, z0), plane(u, z1))
        u += spacing
    z = z0
    while z <= z1 + 1e-6:
        pygame.draw.aaline(m, col, plane(0, z), plane(length, z))
        z += spacing * 40
    s.blit(m, (0, 0))


def stadium_back(s, rng):
    """The stand behind the far touchline, then the far boards (with hoardings) and the cage net above them."""
    draw_stand(s, rng)
    floodlight(s, 15.3, -1.4)
    f = _font(12)
    # boards along the back (y = 0) and the far end (x = 0, either side of the goal)
    poly(s, shade(BOARD, 0.7), quad_z(-0.12, -0.12, N, 0, BOARD_H))
    n = len(ADS_BACK)
    for i, ad in enumerate(ADS_BACK):
        _ad_y(s, i * N / n, (i + 1) * N / n, 0.0, 2, BOARD_H, ad, f)
    poly(s, BOARD, quad_z(-0.12, -0.12, N, 0.0, BOARD_H))
    for k, (ya, yb) in enumerate(((0.0, GOAL_Y0), (GOAL_Y1, float(N)))):
        poly(s, BOARD, quad_z(-0.12, ya, 0.0, yb, BOARD_H))
        yb2 = min(yb, N - 0.3)          # the near boards hide the last bit at the corner
        h = (yb2 - ya) / 2
        for j in range(2):
            _ad_x(s, 0.0, ya + j * h, ya + (j + 1) * h, 2, BOARD_H, ADS_END[k * 2 + j], f)
    # the cage net above the far boards (and over the far goal)
    _mesh(s, lambda u, z: P(u, -0.02, z), N, BOARD_H, CAGE_H)
    _mesh(s, lambda u, z: P(-0.02, u, z), GOAL_Y0, BOARD_H, CAGE_H)
    _mesh(s, lambda u, z: P(-0.02, GOAL_Y1 + u, z), N - GOAL_Y1, BOARD_H, CAGE_H)
    _mesh(s, lambda u, z: P(-0.02, GOAL_Y0 + u, z), GOAL_Y1 - GOAL_Y0, BAR_PX + 6, CAGE_H)
    G = (60, 66, 74)
    for k in range(0, N + 1, 2):
        aa.line(s, G, P(k, -0.02, BOARD_H), P(k, -0.02, CAGE_H + 4), 3)
        if not (GOAL_Y0 - 0.3 < k < GOAL_Y1 + 0.3):
            aa.line(s, G, P(-0.02, k, BOARD_H), P(-0.02, k, CAGE_H + 4), 3)
    aa.line(s, G, P(0, -0.02, CAGE_H), P(N, -0.02, CAGE_H), 2)
    aa.line(s, G, P(-0.02, 0, CAGE_H), P(-0.02, N, CAGE_H), 2)


SEAT_PITCH = 0.62                # seat spacing along a row (tiles)


def seat(s, x, y, h, col):
    """One tip-up seat facing the pitch (+y): a pan and a back, 0.46 tiles wide."""
    a, b = x - 0.23, x + 0.23
    back = y - 0.05
    # the back: its face towards the pitch, and its lit +x edge
    poly(s, shade(col, 0.8), quad_y(back, a, b, h + 9, h + 26))
    poly(s, shade(col, 0.62), quad_x(b, back - 0.06, back, h + 9, h + 26))
    poly(s, shade(col, 1.08), quad_z(a, back - 0.06, b, back, h + 26))
    # the pan, on its stalk
    aa.line(s, (90, 92, 96), P(x, y + 0.14, h), P(x, y + 0.14, h + 7), 2)
    poly(s, col, quad_z(a, back, b, y + 0.3, h + 10))
    poly(s, shade(col, 0.7), quad_y(y + 0.3, a, b, h + 7, h + 10))
    poly(s, shade(col, 0.6), quad_x(b, back, y + 0.3, h + 7, h + 10))


def draw_stand(s, rng):
    """The covered stand: back wall, three tiers of empty seats, the roof and the scoreboard."""
    # the back wall, in club green, with the club's name in white along it
    poly(s, STAND, quad_y(ST_BACK, ST_X0, ST_X1, 0, ROOF_Z1))
    for k in range(int(ST_X0 * 4), int(ST_X1 * 4)):
        x = k / 4
        aa.line(s, shade(STAND, 0.85), P(x, ST_BACK, 0), P(x, ST_BACK, ROOF_Z1), 1)
    # the seats, empty today: club green and yellow in blocks, with white in the middle block's front row
    palette = [(34, 120, 76), (240, 200, 40)]
    for k in range(TIERS - 1, -1, -1):
        yf = ST_FRONT - k * TIER_D
        yb = yf - TIER_D
        h = 10 + TIER_H * k
        box(s, ST_X0, yb if k < TIERS - 1 else ST_BACK, ST_X1, yf, h, (176, 176, 170))
        x = ST_X0 + 0.35
        while x < ST_X1 - 0.3:
            if 6.55 < x < 7.45:                          # leave the steps clear
                x += SEAT_PITCH
                continue
            blk = int((x - ST_X0) / ((ST_X1 - ST_X0) / 4))      # four blocks along the stand
            col = palette[(blk + k) % 2]
            if k == 0 and blk in (1, 2):
                col = (238, 238, 232)
            seat(s, x, yb + 0.3, h, col)
            x += SEAT_PITCH
        # the riser's front edge: a painted line
        aa.line(s, (240, 240, 236), P(ST_X0, yf, h), P(ST_X1, yf, h), 1)
    # steps up the middle
    for k in range(TIERS):
        yf = ST_FRONT - k * TIER_D
        poly(s, (200, 200, 194), quad_y(yf, 6.75, 7.25, 10 + TIER_H * k - 8, 10 + TIER_H * k))
    # the glazed end screen (faces +x, the end we can see) with its frame
    gl = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    prof = [P(ST_X1, ST_FRONT, 0), P(ST_X1, ST_BACK, 0), P(ST_X1, ST_BACK, ROOF_Z1), P(ST_X1, ST_FRONT, ROOF_Z0)]
    aa.polygon(gl, (200, 230, 240, 70), prof)
    s.blit(gl, (0, 0))
    aa.lines(s, STEEL, True, prof, 2)
    # roof posts at the ends and in the middle
    for x in (ST_X0 + 0.05, 7.0, ST_X1 - 0.05):
        aa.line(s, shade(STEEL, 0.75), P(x, ST_FRONT + 0.05, 10), P(x, ST_FRONT + 0.05, ROOF_Z0), 4)
        aa.line(s, shade(STEEL, 1.05), P(x, ST_FRONT + 0.05, 10), P(x, ST_FRONT + 0.05, ROOF_Z0), 1)
    # the roof: a sloped sheet, its fascia in club green
    poly(s, ROOF, [P(ST_X0 - 0.2, ST_FRONT, ROOF_Z0), P(ST_X1 + 0.2, ST_FRONT, ROOF_Z0), P(ST_X1 + 0.2, ST_BACK - 0.2, ROOF_Z1),
                   P(ST_X0 - 0.2, ST_BACK - 0.2, ROOF_Z1)])
    for k in range(int(ST_X0), int(ST_X1) + 1):
        aa.line(s, shade(ROOF, 1.2), P(k, ST_FRONT, ROOF_Z0), P(k, ST_BACK - 0.2, ROOF_Z1), 1)
    poly(s, STAND, quad_y(ST_FRONT, ST_X0 - 0.2, ST_X1 + 0.2, ROOF_Z0 - 10, ROOF_Z0))
    poly(s, shade(STAND, 1.2), quad_x(ST_X1 + 0.2, ST_BACK - 0.2, ST_FRONT, ROOF_Z0 - 10, ROOF_Z0))
    f = _font(11)
    text_on_y_plane(s, f, "COURTYARD ROVERS", (250, 250, 246), 3.2, ST_FRONT + 0.01, ROOF_Z0 - 5)
    text_on_y_plane(s, f, "EST. 1923", (250, 250, 246), 11.0, ST_FRONT + 0.01, ROOF_Z0 - 5)
    # the scoreboard frame on top of the fascia (the live score is drawn by football_view)
    for x in (SB_X0 + 0.3, SB_X1 - 0.3):
        aa.line(s, (50, 54, 60), P(x, SB_Y, ROOF_Z0), P(x, SB_Y, SB_Z0 + 4), 3)
    poly(s, (24, 26, 32), quad_y(SB_Y, SB_X0, SB_X1, SB_Z0, SB_Z1))
    poly(s, (60, 64, 72), quad_x(SB_X1, SB_Y - 0.12, SB_Y, SB_Z0, SB_Z1))
    poly(s, (70, 74, 82), quad_z(SB_X0, SB_Y - 0.12, SB_X1, SB_Y, SB_Z1))
    poly(s, (200, 200, 196), quad_y(SB_Y, SB_X0, SB_X1, SB_Z0, SB_Z1), 2)


def stadium_props(s):
    """The farmers market along the other side, the hedge at the near end, the second floodlight."""
    rng = random.Random(43)
    # the market square's paving
    poly(s, PAVING, quad_z(-7, N + 0.9, 15.2, N + 8, 0))
    for i in range(-7, 16):
        aa.line(s, shade(PAVING, 0.88), P(i, N + 0.9), P(i, N + 8), 1)
    for j in range(0, 8):
        aa.line(s, shade(PAVING, 0.88), P(-7, N + 0.9 + j), P(15.2, N + 0.9 + j), 1)
    poly(s, (210, 208, 200), quad_z(-7, N + 0.9, 15.2, N + 1.05, 0))
    # the hedge at the near end, behind the pitch apron
    hedge = (60, 120, 56)
    box(s, 15.0, -6, 15.35, N + 0.9, 20, hedge)
    for k in range(80):
        y = -6 + k * (N + 6.9) / 80
        gx, gy = P(15.35, y, 20)
        aa.circle(s, shade(hedge, rng.uniform(0.9, 1.25)), (round(gx - 2), round(gy)), 4)
    floodlight(s, -1.5, N + 1.6)
    # the stalls: veg, fruit, flowers and bread, 1.35x the old size (the cheese stall made way)
    f = _font(10)
    fc = _font(9)
    stalls = ((-2.2, (40, 140, 70), "veg", "VEG"), (1.25, (220, 70, 60), "fruit", "FRUIT"),
              (4.7, (230, 110, 170), "flowers", "FLOWERS"), (8.15, (60, 120, 200), "bread", "BREAD"))
    for x0, col, kind, label in stalls:
        big_stall(s, x0, MK_Y1, col, kind, label, f, rng)
    # bunting along the fronts of the awnings
    zf = 50 * MK_S
    bunting(s, [(x, MK_Y1 + 0.3 * MK_S, zf) for x in [st[0] for st in stalls] + [stalls[-1][0] + 2.1 * MK_S]], rng,
            sag=11)
    # chalkboards in the aisle (the market is quiet: no shoppers)
    for x, words, seed in ((1.0, "FRESH", 1), (7.95, "LOCAL", 2), (11.3, "TODAY", 3)):
        chalkboard(s, x, MK_Y1 + 0.8, words, fc, seed)


MK_S = 1.35                      # the market stalls are drawn at this scale
MK_Y1 = N + 3.3                  # the front of the counters (their backs are at MK_Y1 - 1.35)


def big_stall(s, x0, y1, stripe, kind, label, font, rng):
    """A stall scaled up by MK_S about its front-left foot at world (x0, y1).

    It is drawn at the normal size on a clear layer and smooth-scaled; a uniform
    scale of the picture is a uniform scale of the world, so it stays 2:1 isometric."""
    lay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    lay.fill((*PAVING, 0))
    ox, oy0, oy1 = 3.0, N + 2.0, N + 3.0         # a spot with room all round on the layer
    stall(lay, ox, ox + 2.1, oy0, oy1, stripe, kind, label, font, rng)
    r = lay.get_bounding_rect()
    ax, ay = P(ox, oy1)
    big = pygame.transform.smoothscale(lay.subsurface(r), (round(r.w * MK_S), round(r.h * MK_S)))
    bx, by = P(x0, y1)
    s.blit(big, (round(bx + (r.x - ax) * MK_S), round(by + (r.y - ay) * MK_S)))


def build_stadium_front():
    """The near boards (in front of the players), a touch see-through, with their hoardings."""
    s = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    f = _font(12)
    n = len(ADS_NEAR)
    for i, ad in enumerate(ADS_NEAR):
        _ad_y(s, i * N / n, (i + 1) * N / n, float(N), 2, BOARD_H, ad, f)
    poly(s, shade(BOARD, 0.85), quad_y(float(N), 0, N, 0, 2))
    poly(s, BOARD, quad_z(0, N - 0.1, N + 0.1, N, BOARD_H))
    for k, (ya, yb) in enumerate(((0.0, GOAL_Y0), (GOAL_Y1, float(N)))):
        _ad_x(s, float(N), ya, yb, 2, BOARD_H, ADS_NEAR_END[k], f)
        poly(s, shade(BOARD, 0.85), quad_x(float(N), ya, yb, 0, 2))
        poly(s, BOARD, quad_z(N, ya, N + 0.1, yb, BOARD_H))
    # a touch see-through, so feet behind them aren't lost entirely
    arr = pygame.surfarray.pixels_alpha(s)
    arr[arr > 0] = 225
    del arr
    return s


def stadium_obstacles():
    return []
