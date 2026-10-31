"""2:1 isometric projection and drawing helpers shared by the scene and game.

World: x runs down-right on screen, y runs down-left, z is up (in screen px).
One tile is TILE_W x TILE_H = 64 x 32 px (strict 2:1). The sun is in the east
(screen right), so lit faces are the right-hand (+x) faces and shadows fall to
the screen left, as in Moon Sweeper.
"""
import pygame
import aa

WIN_W, WIN_H = 1280, 720
TILE_W, TILE_H = 64, 32
HW, HH = TILE_W // 2, TILE_H // 2
N = 14                       # the courtyard is N x N tiles
OX, OY = WIN_W // 2, 232     # screen position of the courtyard's back corner (0, 0)
SHADOW_K = 0.55              # shadow length per px of height (low-ish morning sun)


def P(x, y, z=0.0):
    return (OX + (x - y) * HW, OY + (x + y) * HH - z)


def shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c[:3])


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def poly(s, col, pts, width=0):
    aa.polygon(s, col, [(round(px), round(py)) for px, py in pts], width)


def quad_x(x, y0, y1, z0, z1):
    """A rectangle on the plane x = const (faces +x, screen bottom-right)."""
    return [P(x, y0, z0), P(x, y1, z0), P(x, y1, z1), P(x, y0, z1)]


def quad_y(y, x0, x1, z0, z1):
    """A rectangle on the plane y = const (faces +y, screen bottom-left)."""
    return [P(x0, y, z0), P(x1, y, z0), P(x1, y, z1), P(x0, y, z1)]


def quad_z(x0, y0, x1, y1, z):
    return [P(x0, y0, z), P(x1, y0, z), P(x1, y1, z), P(x0, y1, z)]


def box(s, x0, y0, x1, y1, h, col, z0=0.0, top=None, outline=None):
    """An iso box: the two visible sides (+x lit, +y in shade) and the top."""
    poly(s, shade(col, 0.72), quad_y(y1, x0, x1, z0, z0 + h))
    poly(s, shade(col, 1.0), quad_x(x1, y0, y1, z0, z0 + h))
    poly(s, top or shade(col, 1.12), quad_z(x0, y0, x1, y1, z0 + h))
    if outline:
        for q in (quad_y(y1, x0, x1, z0, z0 + h), quad_x(x1, y0, y1, z0, z0 + h), quad_z(x0, y0, x1, y1, z0 + h)):
            poly(s, outline, q, 1)
