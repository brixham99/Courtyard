"""London traffic on the city roads beyond the basketball court: now and then a
black cab or a red double-decker drives past, in the correct lane (we drive on
the left), and the bus pulls in at the stop by the court for a few seconds. Only one vehicle
is ever in view at a time, so they never clash.

The traffic is a pure function of the clock (app.t), so it needs no state, and
the title screen, the game and the recordings all see the same street.

Road 1 runs along y beyond the right-hand pavement (x from N+1.6 to N+6.8);
road 2 runs along x beyond the left-hand pavement. The painted vehicles
(tools/cut_vehicles.py) sit on their 2:1 footprints like the football Teslas.
"""
import functools
import math
import os
import random

import pygame

from iso import WIN_W, WIN_H, HW, N, P, SHADOW_K

ART_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "art")
TILES_PER_M = 0.62
# kind: (length m, width m, height m, speed tiles/s)
KINDS = {"bus": (11.0, 2.55, 4.4, 2.9), "cab": (4.6, 1.8, 1.75, 3.6)}

NEAR, FAR = N + 3.1, N + 5.3          # lane centres (the centre line is at N + 4.2)
C0, C1 = -14.0, 26.0                  # along-road range, off screen at both ends
# the four lanes: (road axis, lane centre, heading +1/-1)
#   on road 1 (along y) a car heading -y keeps left on the court side, +y on the far side;
#   on road 2 (along x) heading +x keeps left on the court side, -x on the far side
LANES = {"r1_up": ("y", NEAR, -1), "r1_down": ("y", FAR, +1),
         "r2_down": ("x", NEAR, +1), "r2_up": ("x", FAR, -1)}
# the bus stop: a bus heading up road 1 pulls in with its front by the shelter's far end
BUS_STOP_FRONT = 3.0
BRAKE_D, DWELL = 2.2, 3.0
KERB_PULL = 0.5                       # tiles the bus pulls in towards the kerb at the stop

_art = {}


def _sprite(kind, lane, width):
    """The painted sprite for a vehicle on a lane, scaled to a screen width."""
    axis, _, d = LANES[lane]
    if kind == "bus":
        name, flip = ("bus_front" if d > 0 else "bus_rear"), False      # painted along y
    else:
        name = "cab_front" if d > 0 else "cab_rear"                    # painted along x
        flip = axis == "y"
    key = (name, flip, width)
    if key not in _art:
        raw = _art.get(name)
        if raw is None:
            raw = _art[name] = pygame.image.load(os.path.join(ART_DIR, f"{name}.png"))
            try:
                raw = _art[name] = raw.convert_alpha()
            except pygame.error:
                pass
        if flip:
            raw = pygame.transform.flip(raw, True, False)
        w, h = raw.get_size()
        _art[key] = pygame.transform.smoothscale(raw, (width, max(1, round(h * width / w))))
    return _art[key]


class Trip:
    def __init__(self, kind, lane, t0):
        self.kind, self.lane, self.t0 = kind, lane, t0
        L, W, H, v = KINDS[kind]
        self.L, self.W, self.H, self.v = L * TILES_PER_M, W * TILES_PER_M, H * TILES_PER_M * 40, v
        self.stops = kind == "bus" and lane == "r1_up"

    def u_free(self, t):
        """Distance travelled (tiles) along the lane from its start, ignoring traffic."""
        tau = t - self.t0
        if not self.stops:
            return self.v * tau
        v = self.v
        S = (C1 - BUS_STOP_FRONT) - self.L / 2        # where the centre is when it stops
        tb = 2 * BRAKE_D / v                         # braking (and pulling away) time
        t1 = (S - BRAKE_D) / v                       # start braking
        if tau < t1:
            return v * tau
        if tau < t1 + tb:
            k = tau - t1
            return S - BRAKE_D + v * k - v / tb * k * k / 2
        if tau < t1 + tb + DWELL:
            return S
        if tau < t1 + 2 * tb + DWELL:
            k = tau - t1 - tb - DWELL
            return S + v / tb * k * k / 2
        return S + BRAKE_D + v * (tau - t1 - 2 * tb - DWELL)

    def pull_in(self, t):
        """How far (tiles) a stopping bus has pulled in towards the kerb at time t."""
        if not self.stops:
            return 0.0
        v = self.v
        S = (C1 - BUS_STOP_FRONT) - self.L / 2
        tb = 2 * BRAKE_D / v
        t1 = (S - BRAKE_D) / v
        tau = t - self.t0
        if tau < t1 or tau > t1 + 2 * tb + DWELL:
            return 0.0
        if tau < t1 + tb:
            k = (tau - t1) / tb
        elif tau < t1 + tb + DWELL:
            k = 1.0
        else:
            k = 1 - (tau - t1 - tb - DWELL) / tb
        return KERB_PULL * (3 * k * k - 2 * k ** 3)

    def centre(self, u, t=None):
        axis, lane_c, d = LANES[self.lane]
        c = C0 + u if d > 0 else C1 - u
        if t is not None:
            lane_c -= self.pull_in(t)
        return (lane_c, c) if axis == "y" else (c, lane_c)

    def footprint(self, x, y):
        axis = LANES[self.lane][0]
        a, b = (self.W / 2, self.L / 2) if axis == "y" else (self.L / 2, self.W / 2)
        return x - a, y - b, x + a, y + b


def _sprite_h(kind, lane, width):
    """The height (px) the sprite has at a screen width, without needing a display."""
    axis, _, d = LANES[lane]
    name = ("bus_front" if d > 0 else "bus_rear") if kind == "bus" else ("cab_front" if d > 0 else "cab_rear")
    if name not in _sizes:
        _sizes[name] = pygame.image.load(os.path.join(ART_DIR, f"{name}.png")).get_size()
    w, h = _sizes[name]
    return max(1, round(h * width / w))


_sizes = {}


def screen_rect(tr, x, y):
    """The screen rectangle a vehicle covers at (x, y): its sprite and its shadow."""
    fp = tr.footprint(x, y)
    x0, y0, x1, y1 = fp
    left, right = P(x0, y1)[0], P(x1, y0)[0]
    width = max(1, round(right - left))
    ih = _sprite_h(tr.kind, tr.lane, width)
    bottom = P(x1, y1)[1] + 2
    r = pygame.Rect(round((left + right) / 2 - width / 2), round(bottom - ih), width, ih)
    sh = _shadow_poly(fp, tr.H * 0.8)
    xs = [p[0] for p in sh]; ys = [p[1] for p in sh]
    return r.union(pygame.Rect(int(min(xs)) - 8, int(min(ys)) - 8,
                               int(max(xs) - min(xs)) + 16, int(max(ys) - min(ys)) + 16))


SCREEN = pygame.Rect(0, 0, WIN_W, WIN_H)


@functools.lru_cache(maxsize=None)
def on_screen(kind, lane):
    """(first, last) seconds after a trip starts that any of it is on screen."""
    tr = Trip(kind, lane, 0.0)
    first = last = None
    tau = 0.0
    while True:
        u = tr.u_free(tau)
        if u > (C1 - C0) + 2:
            break
        x, y = tr.centre(u, tau)
        if screen_rect(tr, x, y).colliderect(SCREEN):
            first = tau if first is None else first
            last = tau
        tau += 0.02
    return first, last


# One vehicle on screen at a time, so nothing can ever clash: each trip is timed to
# come into view only after the one before has gone, with a breather in between.
# The timetable is worked out once and repeats every PERIOD seconds.
BREATHER = (1.0, 4.0)                # seconds of empty road between vehicles
QUIET = (0.2, 4.0, 9.0)              # now and then a longer quiet spell (chance, min, max)
TRIPS_PER_CYCLE = 48


@functools.lru_cache(maxsize=1)
def timetable():
    """([(trip, shown_from, shown_to)], PERIOD): every trip's start and on-screen spell."""
    rng = random.Random(2026)
    out = []
    t_free = 1.0                     # the road is clear from here on
    for i in range(TRIPS_PER_CYCLE):
        if i == 0:
            kind, lane = "bus", "r1_up"        # first along: a bus pulling in at the stop
        elif i == 1:
            kind, lane = "cab", rng.choice(("r2_down", "r2_up"))
        else:
            kind = "bus" if rng.random() < 0.35 else "cab"
            lane = rng.choice(("r1_up", "r1_down") if kind == "bus" else tuple(LANES))
        a, b = on_screen(kind, lane)
        tr = Trip(kind, lane, t_free - a)
        out.append((tr, t_free, tr.t0 + b))
        gap = rng.uniform(*BREATHER)
        if rng.random() < QUIET[0]:
            gap += rng.uniform(QUIET[1], QUIET[2])
        t_free = tr.t0 + b + gap
    period = t_free                  # so the next cycle's first trip comes into view at period + 1
    return out, period


def positions(t):
    """[(trip, x, y)] for the vehicle on screen at time t (at most one)."""
    trips, period = timetable()
    tt = t % period
    res = []
    for tr, a, b in trips:
        if a - 0.05 <= tt <= b + 0.05:
            u = tr.u_free(tt)
            x, y = tr.centre(u, tt)
            res.append((tr, x, y))
    return res


def check_no_clash(seconds=600.0, step=1 / 60):
    """Sample the street and make sure no two vehicles ever share screen space.

    Returns (number of vehicles seen, the kinds seen, longest empty spell in seconds)."""
    period = timetable()[1]
    seen, kinds = set(), set()
    longest = empty = 0.0
    t = 0.0
    while t < seconds:
        vs = positions(t)
        rects = [screen_rect(tr, x, y).clip(SCREEN) for tr, x, y in vs]
        rects = [r for r in rects if r.w > 0 and r.h > 0]
        assert len(rects) <= 1, f"two vehicles in view at t={t:.2f}"
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                assert not rects[i].colliderect(rects[j]), f"traffic clash at t={t:.2f}"
        for tr, _, _ in vs:
            seen.add((int(t // period), id(tr)))
            kinds.add(tr.kind)
        empty = 0.0 if rects else empty + step
        longest = max(longest, empty)
        t += step
    return len(seen), kinds, longest


def _in_front(a, b):
    ta, xa, ya = a
    tb, xb, yb = b
    a0x, a0y, a1x, a1y = ta.footprint(xa, ya)
    b0x, b0y, b1x, b1y = tb.footprint(xb, yb)
    if a0x >= b1x - 1e-6:
        return 1
    if b0x >= a1x - 1e-6:
        return -1
    if a0y >= b1y - 1e-6:
        return 1
    if b0y >= a1y - 1e-6:
        return -1
    return 1 if xa + ya > xb + yb else -1


def _shadow_poly(fp, H):
    x0, y0, x1, y1 = fp
    d = H * SHADOW_K / HW / 2
    pts = [P(x0, y0), P(x1, y0), P(x1, y1), P(x1 - d, y1 + d), P(x0 - d, y1 + d), P(x0 - d, y0 + d)]
    return pts


def draw_shadows(s, t):
    """Soft shadows of the traffic on the road (falling west); drawn under everything else."""
    vs = positions(t)
    if not vs:
        return
    for tr, x, y in vs:
        fp = tr.footprint(x, y)
        pts = _shadow_poly(fp, tr.H * 0.8)
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        pad = 8
        ox, oy = int(min(xs)) - pad, int(min(ys)) - pad
        w, h = int(max(xs)) - ox + pad, int(max(ys)) - oy + pad
        if ox > WIN_W or oy > WIN_H or ox + w < 0 or oy + h < 0:
            continue
        sh = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.polygon(sh, (20, 20, 26, 70), [(px - ox, py - oy) for px, py in pts])
        x0, y0, x1, y1 = fp
        pygame.draw.polygon(sh, (12, 12, 16, 60), [(px - ox, py - oy) for px, py in
                                                    (P(x0 + 0.1, y0 + 0.1), P(x1 - 0.1, y0 + 0.1), P(x1 - 0.1, y1 - 0.1), P(x0 + 0.1, y1 - 0.1))])
        small = pygame.transform.smoothscale(sh, (max(1, w // 4), max(1, h // 4)))
        s.blit(pygame.transform.smoothscale(small, (w, h)), (ox, oy))


def draw(s, t):
    """The vehicles themselves, back to front (call after the court's front layer)."""
    vs = positions(t)
    vs.sort(key=functools.cmp_to_key(_in_front))
    for tr, x, y in vs:
        x0, y0, x1, y1 = tr.footprint(x, y)
        left, right = P(x0, y1)[0], P(x1, y0)[0]
        img = _sprite(tr.kind, tr.lane, max(1, round(right - left)))
        iw, ih = img.get_size()
        bottom = P(x1, y1)[1] + 2
        s.blit(img, (round((left + right) / 2 - iw / 2), round(bottom - ih)))

