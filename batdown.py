"""Batdown: the rules, the ball and the computer player. No drawing here, so
it can be run headless for tests (like tag.py).

Rules (Nathan's backyard-cricket variant)
- One batter, one fielder. The batter stands still on the batting spot with
  the bat down in front of them and turns to face the fielder.
- The fielder throws the ball at the bat. The batter swings to hit it away.
- The fielder goes to where the ball first landed (marked with a chalk X),
  picks the ball up and throws from that spot, never from closer than
  MIN_THROW tiles. The first throw of each turn is from the bowling mark.
- If a throw hits the bat, or a hit is caught on the full, they swap.
- Only the batter scores, by where a hit first lands: inside the 3-tile ring
  1, 3-6 tiles 2, beyond 6 tiles 3. On the full into the hedge or the
  railings: 5. Every 3 throws survived in a row: +1 (the streak).
- The fielder has 6 s from picking the ball up to throw, or the batter gets
  +1 and the clock starts again.
- First to 30, or the most points once both have had 3 turns at bat.

Units: x, y in tiles; z (height) in tiles too, drawn at ZPX px per tile.
"""
import math
import random

from iso import N
from park import BAT_SPOT, BOWL_MARK, RINGS
from tag import Runner, World, FACINGS, RADIUS, SPEED, BACK_SPEED, TURN_S, ROBOT_SPEED, CELL

ZPX = 40.0              # screen px per tile of height (a child is ~2.8 tiles = 113 px)
GRAV = 14.0             # tiles/s^2 (a tennis ball, a little floaty for play)
BALL_R = 0.09
E_GROUND = 0.5          # bounce on grass
E_WALL = 0.42
FRICTION = 0.72         # speed kept along the ground at each bounce
ROLL_DECEL = 3.4        # tiles/s^2 rolling on grass
HAND_Z = 1.9            # release height, overarm
LOB_Z = 1.0             # release height, underarm
BAT_OFF = 0.55          # the bat stands this far in front of the batter
BAT_HALF = 0.32         # half the blade's width (tiles)
BAT_H = 0.72            # the blade's height
BAT_THICK = 0.14
HIT_OFF = 0.85          # where the swing meets the ball (just in front of the bat)
REACH = 0.9            # ... and how far from there it can reach
REACH_Z = 1.75
SWING_HIT_T = 0.14      # the bat comes through this long after pressing Space
SWING_LEN = 0.42
SWING_RECOVER = 0.55    # before you can swing again
BAT_UP = (0.04, 0.30)   # while swinging the blade is off the ground and can't be knocked down
AIMS = (-38.0, 0.0, 38.0)      # off side, straight, leg side (degrees from the line to the fielder)
AIM_NAMES = ("off side", "straight", "leg side")
CATCH_R = 0.62
CATCH_Z = (0.3, 2.6)
PICK_R = 0.48
ON_X = 0.36
MIN_THROW = 2.2
THROW_TIME = 6.0
TARGET = 30
TURNS = 3
THROW_TYPES = ("flat", "lob", "bouncer")
MAX_RANGE = 13.0        # the human's throw: power 1 = this far
CHARGE_S = 2.4          # seconds to charge from 0 to full power
AIM_TURN = math.radians(75)    # aiming speed, per second


def unit(dx, dy):
    d = math.hypot(dx, dy)
    return (dx / d, dy / d) if d > 1e-9 else (1.0, 0.0)


def facing_for(dx, dy):
    """The nearest of the four facings to a direction."""
    best, bd = 0, -9
    for k, (fx, fy) in enumerate(FACINGS):
        d = fx * dx + fy * dy
        if d > bd:
            best, bd = k, d
    return best


class Geom:
    """What the ball can hit: tree trunks, leafy crowns and boxes (benches)."""

    def __init__(self, obstacles):
        self.trunks, self.crowns, self.boxes = [], [], []
        for o in obstacles:
            if o.kind == "tree":
                self.trunks.append((o.x, o.y, getattr(o, "trunk", o.r * 0.5), getattr(o, "trunk_h", 2.4)))
                if hasattr(o, "canopy"):
                    zc, rr = o.canopy
                    self.crowns.append((o.x, o.y, zc, rr))
            elif o.kind in ("bench", "planter"):
                self.boxes.append((o.x0, o.y0, o.x1, o.y1, getattr(o, "h_ball", 0.4)))

    def floor(self, x, y):
        for x0, y0, x1, y1, h in self.boxes:
            if x0 <= x <= x1 and y0 <= y <= y1:
                return h
        return 0.0


class Ball:
    def __init__(self):
        self.x, self.y, self.z = BOWL_MARK[0], BOWL_MARK[1], HAND_Z
        self.vx = self.vy = self.vz = 0.0
        self.rolling = False
        self.resting = True
        self.in_leaves = False
        self.age = 0.0

    def copy(self):
        b = Ball.__new__(Ball)
        b.__dict__.update(self.__dict__)
        return b

    def launch(self, x, y, z, vx, vy, vz):
        self.x, self.y, self.z = x, y, z
        self.vx, self.vy, self.vz = vx, vy, vz
        self.rolling = self.resting = self.in_leaves = False
        self.age = 0.0

    @property
    def speed(self):
        return math.sqrt(self.vx ** 2 + self.vy ** 2 + self.vz ** 2)

    def step(self, dt, geom, n=4):
        """Advance; returns events [(kind, data)]: ground, wall, tree, leaves, bench, rest."""
        ev = []
        if self.resting:
            return ev
        self.age += dt
        h = dt / n
        for _ in range(n):
            pz = self.z
            if self.rolling:
                v = math.hypot(self.vx, self.vy)
                nv = max(0.0, v - ROLL_DECEL * h)
                if nv <= 0.04:
                    self.vx = self.vy = 0.0
                    self.resting = True
                    ev.append(("rest", (self.x, self.y)))
                    return ev
                self.vx *= nv / v
                self.vy *= nv / v
            else:
                self.vz -= GRAV * h
            self.x += self.vx * h
            self.y += self.vy * h
            self.z += self.vz * h
            # the hedge and the railings (an invisible net above them keeps the ball in play)
            for axis in ("x", "y"):
                p = getattr(self, axis)
                v = getattr(self, "v" + axis)
                if p < BALL_R and v < 0:
                    setattr(self, axis, BALL_R)
                    setattr(self, "v" + axis, -v * E_WALL)
                    ev.append(("wall", "back"))
                elif p > N - BALL_R and v > 0:
                    setattr(self, axis, N - BALL_R)
                    setattr(self, "v" + axis, -v * E_WALL)
                    ev.append(("wall", "front"))
            # tree trunks
            for cx, cy, r, th in geom.trunks:
                if self.z < th:
                    dx, dy = self.x - cx, self.y - cy
                    d = math.hypot(dx, dy)
                    if d < r + BALL_R:
                        nx, ny = (dx / d, dy / d) if d > 1e-6 else (1.0, 0.0)
                        self.x, self.y = cx + nx * (r + BALL_R), cy + ny * (r + BALL_R)
                        vn = self.vx * nx + self.vy * ny
                        if vn < 0:
                            self.vx -= (1 + E_WALL) * vn * nx
                            self.vy -= (1 + E_WALL) * vn * ny
                            ev.append(("tree", None))
            # leafy crowns slow it and drop it
            for cx, cy, cz, rr in geom.crowns:
                d = math.sqrt((self.x - cx) ** 2 + (self.y - cy) ** 2 + ((self.z - cz) * 1.2) ** 2)
                if d < rr and not self.in_leaves:
                    self.in_leaves = True
                    self.vx *= 0.3
                    self.vy *= 0.3
                    self.vz = min(self.vz, 0.0) * 0.3
                    ev.append(("leaves", None))
                elif d > rr + 0.1:
                    self.in_leaves = False
            # benches: off the top or off the sides
            for x0, y0, x1, y1, bh in geom.boxes:
                if x0 - BALL_R < self.x < x1 + BALL_R and y0 - BALL_R < self.y < y1 + BALL_R and self.z < bh:
                    if pz >= bh - 0.02:
                        self.z = bh
                        if self.vz < 0:
                            self.vz = -self.vz * E_GROUND
                            self.vx *= FRICTION
                            self.vy *= FRICTION
                            ev.append(("bench", None))
                    else:
                        opts = ((self.x - (x0 - BALL_R), 0, -1), ((x1 + BALL_R) - self.x, 0, 1),
                                (self.y - (y0 - BALL_R), 1, -1), ((y1 + BALL_R) - self.y, 1, 1))
                        _, ax, sg = min(opts)
                        if ax == 0:
                            self.x = x0 - BALL_R if sg < 0 else x1 + BALL_R
                            if self.vx * sg < 0:
                                self.vx = -self.vx * E_WALL
                        else:
                            self.y = y0 - BALL_R if sg < 0 else y1 + BALL_R
                            if self.vy * sg < 0:
                                self.vy = -self.vy * E_WALL
                        ev.append(("bench", None))
            fl = geom.floor(self.x, self.y)
            if self.rolling and fl == 0.0 and self.z > 0.01:
                self.rolling = False          # rolled off the bench
            if self.z <= fl and not self.rolling:
                self.z = fl
                if self.vz < 0:
                    ev.append(("ground", (self.x, self.y, -self.vz)))
                    self.vz = -self.vz * E_GROUND
                    self.vx *= FRICTION
                    self.vy *= FRICTION
                    if self.vz < 1.1:
                        self.vz = 0.0
                        self.rolling = True
        return ev


def solve_throw(rx, ry, rz, tx, ty, tz, kind):
    """Launch velocity from the release point to land on a target point."""
    dx, dy = tx - rx, ty - ry
    d = max(0.3, math.hypot(dx, dy))
    ux, uy = dx / d, dy / d
    if kind == "flat":
        vh = min(11.0, max(6.5, 5.5 + 0.55 * d))
        T = d / vh
    elif kind == "lob":
        T = 0.85 + 0.065 * d
        vh = d / T
    else:   # bouncer: pitch it short, on the ground
        db = max(0.6, d - min(1.5, 0.28 * d))
        vh = min(10.0, max(6.5, 6.0 + 0.4 * d))
        T = db / vh
        tz = 0.0
    vz = (tz - rz + 0.5 * GRAV * T * T) / T
    return ux * vh, uy * vh, vz


class FieldBrain:
    """The robot as fielder (and the AI standing in for a player)."""

    def __init__(self, me, rng, skill=1.0):
        self.me = me
        self.rng = rng
        self.skill = skill
        self.think = 0.0
        self.wait = None          # time to wait before throwing
        self.react = 0.0
        self.target = None
        self.fcache = {}

    def reset(self):
        self.wait = None
        self.target = None
        self.react = 0.22 / self.skill

    def steer(self, world, tx, ty, other):
        """(turn, move) for tank controls towards a point, round obstacles."""
        me = self.me
        dx, dy = tx - me.x, ty - me.y
        dist = math.hypot(dx, dy)
        if dist < 0.12:
            return 0, 0
        # straight there if nothing is in the way, else follow the path field
        if self.clear(world, me.x, me.y, tx, ty):
            cands = []
            for k, (fx, fy) in enumerate(FACINGS):
                along = fx * dx + fy * dy
                if along > 0.06:
                    cands.append((-(along + (0.25 if k == me.facing else 0.0)), k))
            want = min(cands)[1] if cands else me.facing
        else:
            key = world.cell_of(tx, ty)
            if key not in self.fcache:
                self.fcache[key] = world.field(tx, ty)
            f = self.fcache[key]
            want, best = me.facing, None
            for k, (fx, fy) in enumerate(FACINGS):
                px, py = me.x + fx * CELL, me.y + fy * CELL
                if world.blocked(px, py):
                    continue
                i, j = world.cell_of(px, py)
                sc = f[i][j] - (0.3 if k == me.facing else 0.0)
                if best is None or sc < best:
                    want, best = k, sc
        turn = 0
        if want != me.facing:
            diff = (want - me.facing) % 4
            turn = 1 if diff == 1 else (-1 if diff == 3 else 1)
            # don't walk on while facing the wrong way (except a small correction)
            fx, fy = FACINGS[me.facing]
            return turn, (1 if fx * dx + fy * dy > 0.3 else 0)
        return 0, 1

    @staticmethod
    def clear(world, x0, y0, x1, y1):
        d = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(d / 0.25))
        for i in range(1, n + 1):
            t = i / n
            if world.blocked(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, RADIUS * 0.9):
                return False
        return True


class BatBrain:
    """The robot as batter: reads the throw, swings with a timing error."""

    def __init__(self, me, rng, skill=1.0):
        self.me = me
        self.rng = rng
        self.skill = skill
        self.plan = None          # time (since the throw) to press Space
        self.loft = False
        self.aim = 1

    def read(self, game):
        """Called once as the ball is thrown."""
        b = game.ball.copy()
        hx, hy = game.hit_point()
        ux, uy = game.bat_u
        t = 0.0
        best = None
        while t < 3.0:
            b.step(1 / 120, game.geom, 1)
            t += 1 / 120
            along = (b.x - hx) * ux + (b.y - hy) * uy
            if along <= 0.0:
                best = (t, math.hypot(b.x - hx, b.y - hy), b.z)
                break
            if b.resting:
                break
        self.plan = None
        if best is None:
            return
        tc, d, z = best
        on_target = d < 0.6 and z < 1.4
        if d > REACH * 0.9 or z > REACH_Z:
            return                          # can't reach it: leave it
        if not on_target and self.rng.random() < 0.5:
            return                          # going wide: leave it
        speed = game.ball.speed
        sigma = (0.05 + 0.004 * speed) / self.skill
        self.plan = tc - SWING_HIT_T + self.rng.gauss(0, sigma)
        # aim away from the fielder, mostly; sometimes go straight; loft now and then
        self.aim = self.rng.choice((0, 2, 0, 2, 1))
        self.loft = self.rng.random() < 0.3


class BatdownGame:
    def __init__(self, player_kind, player_name, opponent=("robot", "Robot"), player_ai=False, seed=None,
                 obstacles=None, target=TARGET, turns=TURNS):
        from park import park_obstacles
        self.rng = random.Random(seed)
        obstacles = obstacles if obstacles is not None else park_obstacles()
        self.world = World(obstacles)
        self.geom = Geom(obstacles)
        self.target = target
        self.turns = turns
        self.p1 = Runner(player_kind, player_name, 3.0, 6.0, 0, ai=player_ai, speed_k=ROBOT_SPEED if player_ai else 1.0)
        self.p2 = Runner(opponent[0], opponent[1], 6.0, 3.0, 1, ai=True, speed_k=ROBOT_SPEED)
        for r in self.runners:
            r.score = 0
            r.turns = 0
            r.anim, r.anim_t = "idle", 0.0
            r.holding = False
            if r.ai:
                r.field_brain = FieldBrain(r, self.rng)
                r.bat_brain = BatBrain(r, self.rng)
        self.ball = Ball()
        self.events = []
        self.callouts = []            # [text, colour, age]
        self.dust = []                # [x, y, age]
        self.state = "toss"           # toss -> play <-> swap -> match_over
        self.state_t = 2.6
        self.phase = None             # aim | flight | hit | fetch
        self.batter = self.rng.choice(self.runners)
        self.fielder = self.other(self.batter)
        self.toss_winner = self.batter
        self.x_mark = None
        self.throw_clock = THROW_TIME
        self.clock_running = False
        self.aim_i = 1
        self.loft = False
        self.throw_type = 0
        self.aim_ang = 0.0
        self.charging = False
        self.charge_t = 0.0
        self.power = 0.0
        self.swing_t = None
        self.swing_cool = 0.0
        self.swing_checked = False
        self.streak = 0
        self.passed = False
        self.on_full = False
        self.bat_u = (1.0, 0.0)
        self.last_throw = None
        self.swap_reason = None
        self.flight_t = 0.0
        self.stats = {"throws": 0, "hits": 0, "bat_down": 0, "caught": 0, "boundary": 0, "too_slow": 0, "missed": 0}
        self.winner = None
        self.fallen = None
        self.place_for_turn(snap=True)
        self.events.append(("toss", self.batter))

    # ---------------------------------------------------------------- helpers
    @property
    def runners(self):
        return (self.p1, self.p2)

    def other(self, r):
        return self.p2 if r is self.p1 else self.p1

    def say(self, text, col=(255, 255, 255)):
        self.callouts.append([text, col, 0.0])

    def bat_point(self):
        bx, by = self.batter.x, self.batter.y
        ux, uy = self.bat_u
        return bx + ux * BAT_OFF, by + uy * BAT_OFF

    def hit_point(self):
        bx, by = self.batter.x, self.batter.y
        ux, uy = self.bat_u
        return bx + ux * HIT_OFF, by + uy * HIT_OFF

    def face_batter(self):
        """The batter turns to face the fielder (and the bat goes with them)."""
        if self.phase in ("flight", "hit") or self.state != "play":
            return
        b, f = self.batter, self.fielder
        self.bat_u = unit(f.x - b.x, f.y - b.y)
        b.facing = facing_for(*self.bat_u)

    def release_point(self, kind):
        f = self.fielder
        ca, sa = math.cos(self.aim_ang), math.sin(self.aim_ang)
        return f.x + ca * 0.25, f.y + sa * 0.25, (LOB_Z if kind == "lob" else HAND_Z)

    def aim_at_bat(self):
        bx, by = self.bat_point()
        f = self.fielder
        self.aim_ang = math.atan2(by - f.y, bx - f.x)

    def place_for_turn(self, snap=False):
        b, f = self.batter, self.fielder
        self.fallen = None
        if snap:
            b.x, b.y = BAT_SPOT
            f.x, f.y = BOWL_MARK
        self.x_mark = BOWL_MARK
        f.holding = True
        self.ball.resting = True
        self.phase = "aim"
        self.throw_clock = THROW_TIME
        self.clock_running = True
        self.charging = False
        self.power = 0.0
        self.throw_type = 0
        self.aim_i = 1
        self.streak = 0
        self.swing_t = None
        self.swing_cool = 0.0
        self.bat_u = unit(f.x - b.x, f.y - b.y)
        b.facing = facing_for(*self.bat_u)
        self.aim_at_bat()
        f.facing = facing_for(math.cos(self.aim_ang), math.sin(self.aim_ang))
        for r in self.runners:
            r.anim, r.anim_t = ("bat" if r is b else "idle"), 0.0
            if r.ai:
                r.field_brain.reset()
                r.bat_brain.plan = None
        b.turns += 1
        self.events.append(("new_turn", b))

    # ---------------------------------------------------------------- input from the keyboard (human = p1)
    def press(self, what, held=()):
        """Edge events for the human player: 'left', 'right', 'up', 'down', 'space', 'space_up'."""
        h = self.p1
        if h.ai or self.state != "play":
            return
        if h is self.batter:
            if what in ("left", "right"):
                self.aim_i = max(0, min(2, self.aim_i + (-1 if what == "left" else 1)))
                self.events.append(("aim", None))
            elif what == "space":
                self.swing(lofted="up" in held)
        else:
            if self.phase == "aim":
                if what in ("up", "down") and not self.charging:
                    self.throw_type = (self.throw_type + (1 if what == "up" else -1)) % len(THROW_TYPES)
                    self.events.append(("aim", None))
                elif what == "space":
                    self.charging = True
                    self.charge_t = 0.0
                    self.power = 0.0
                elif what == "space_up" and self.charging:
                    self.human_throw()

    def human_throw(self):
        kind = THROW_TYPES[self.throw_type]
        D = max(1.0, self.power * MAX_RANGE)
        rx, ry, rz = self.release_point(kind)
        a = self.aim_ang + math.radians(self.rng.gauss(0, 0.8))
        D *= 1 + self.rng.gauss(0, 0.015)
        tx, ty = rx + math.cos(a) * D, ry + math.sin(a) * D
        self.throw(kind, solve_throw(rx, ry, rz, tx, ty, BAT_H * 0.5, kind))

    def predicted_landing(self):
        """For the aiming guide: where the human's throw would come down."""
        kind = THROW_TYPES[self.throw_type]
        D = max(1.0, self.power * MAX_RANGE)
        if kind == "bouncer":
            D = max(0.6, D - min(1.5, 0.28 * D))
        rx, ry, rz = self.release_point(kind)
        return rx + math.cos(self.aim_ang) * D, ry + math.sin(self.aim_ang) * D

    # ---------------------------------------------------------------- actions
    def swing(self, lofted=False):
        if self.swing_cool > 0 or self.batter.anim == "swing":
            return
        self.swing_t = 0.0
        self.swing_checked = False
        self.swing_cool = SWING_RECOVER
        self.loft = lofted
        self.batter.anim, self.batter.anim_t = "swing", 0.0
        self.events.append(("swish", None))

    def throw(self, kind, v):
        f = self.fielder
        rx, ry, rz = self.release_point(kind)
        self.ball.launch(rx, ry, rz, *v)
        f.holding = False
        f.anim, f.anim_t = ("lob" if kind == "lob" else "throw"), 0.0
        self.phase = "flight"
        self.passed = False
        self.charging = False
        self.clock_running = False
        self.flight_t = 0.0
        self.last_throw = kind
        self.x_mark = None
        b = self.batter
        self.bat_u = unit(f.x - b.x, f.y - b.y)
        self.stats["throws"] += 1
        self.events.append(("throw", kind))
        if b.ai:
            b.bat_brain.read(self)
            self.aim_i = b.bat_brain.aim

    def ai_throw(self):
        f = self.fielder
        bx, by = self.bat_point()
        d = math.hypot(bx - f.x, by - f.y)
        sk = f.field_brain.skill
        # line of sight: try a flat throw in simulation; if it would hit something, lob it
        options = ["flat", "lob"]
        if d > 4.0 and self.rng.random() < 0.2:
            options.insert(0, "bouncer")
        kind = "lob"
        for k in options:
            self.aim_ang = math.atan2(by - f.y, bx - f.x)
            rx, ry, rz = self.release_point(k)
            v = solve_throw(rx, ry, rz, bx, by, BAT_H * 0.5, k)
            if self.would_reach_bat(rx, ry, rz, v):
                kind = k
                break
        self.aim_ang = math.atan2(by - f.y, bx - f.x) + math.radians(self.rng.gauss(0, 2.0 / sk))
        rx, ry, rz = self.release_point(kind)
        dd = math.hypot(bx - rx, by - ry) * (1 + self.rng.gauss(0, 0.03 / sk))
        tx, ty = rx + math.cos(self.aim_ang) * dd, ry + math.sin(self.aim_ang) * dd
        self.throw(kind, solve_throw(rx, ry, rz, tx, ty, BAT_H * 0.5, kind))

    def would_reach_bat(self, rx, ry, rz, v):
        b = Ball()
        b.launch(rx, ry, rz, *v)
        bx, by = self.bat_point()
        for i in range(240):
            ev = b.step(1 / 60, self.geom, 2)
            if any(k in ("tree", "leaves", "bench") for k, _ in ev):
                return False
            if math.hypot(b.x - bx, b.y - by) < 0.5 and b.z < BAT_H + 0.2:
                return True
            if b.resting:
                return False
        return False

    # ---------------------------------------------------------------- the step
    def update(self, dt, human=(0, 0), held=()):
        for c in self.callouts:
            c[2] += dt
        self.callouts = [c for c in self.callouts if c[2] < 2.2]
        for d in self.dust:
            d[2] += dt
        self.dust = [d for d in self.dust if d[2] < 0.6]
        for r in self.runners:
            r.anim_t += dt
            r.moved = 0.0
            if r.anim in ("throw", "lob") and r.anim_t > 0.45:
                r.anim = "idle"
            if r.anim == "pickup" and r.anim_t > 0.35:
                r.anim = "idle"
            if r.anim == "swing" and r.anim_t > SWING_LEN:
                r.anim = "bat"
            if r.anim in ("cheer", "sad", "catch") and r.anim_t > 1.6 and self.state == "play":
                r.anim = "bat" if r is self.batter else "idle"
        self.state_t -= dt
        if self.state == "toss":
            if self.state_t <= 0:
                self.state = "play"
                self.events.append(("whistle", None))
            return
        if self.state == "match_over":
            return
        if self.state == "swap":
            self.update_swap(dt)
            return
        self.update_play(dt, human, held)

    def update_play(self, dt, human, held):
        b, f = self.batter, self.fielder
        self.swing_cool = max(0.0, self.swing_cool - dt)
        self.face_batter()
        # --- the fielder
        if self.phase == "aim":
            f.x, f.y = self.x_mark
            if f.ai:
                br = f.field_brain
                if br.wait is None:
                    # a moment to line it up, but never so long the clock runs out
                    br.wait = min(self.rng.uniform(1.3, 2.2), max(0.4, self.throw_clock - 0.8))
                br.wait -= dt
                self.aim_at_bat()
                if br.wait < 0.35:
                    f.anim = "windup"
                if br.wait <= 0:
                    self.ai_throw()
            else:
                turn, _ = human
                if turn:
                    self.aim_ang += turn * AIM_TURN * dt
                if self.charging:
                    self.charge_t += dt
                    self.power = min(1.0, self.charge_t / CHARGE_S)
                    f.anim = "windup"
            if self.phase == "aim":
                f.facing = facing_for(math.cos(self.aim_ang), math.sin(self.aim_ang))
        elif f.ai:
            turn, move = self.ai_field(dt)
            self.drive(f, turn, move, dt)
        else:
            turn, move = human
            self.drive(f, turn, move, dt)
        # the throw clock runs from the pick-up to the throw
        if self.clock_running and f.holding:
            self.throw_clock -= dt
            if self.throw_clock <= 0:
                self.award(1, "Too slow! +1")
                self.stats["too_slow"] += 1
                self.throw_clock = THROW_TIME
                if self.state != "play":
                    return
        # --- the batter's swing
        if self.swing_t is not None:
            self.swing_t += dt
            if self.swing_t > SWING_LEN:
                self.swing_t = None
        if b.ai and self.phase == "flight" and b.bat_brain.plan is not None and self.flight_t >= b.bat_brain.plan:
            b.bat_brain.plan = None
            self.swing(lofted=b.bat_brain.loft)
        # --- the ball
        if self.phase in ("flight", "hit", "fetch") and not f.holding:
            self.flight_t += dt
            ev = self.ball.step(dt, self.geom)
            self.ball_events(ev)
            if self.state != "play":
                return
            if self.phase == "flight":
                self.check_flight()
            if self.phase == "hit":
                self.check_catch()
            if self.state != "play":
                return
            if self.phase == "fetch":
                self.nudge_from_batter()
                self.check_pickup()
        elif f.holding and self.phase == "fetch":
            if math.hypot(f.x - self.x_mark[0], f.y - self.x_mark[1]) < ON_X:
                f.x, f.y = self.x_mark
                self.phase = "aim"
                self.aim_at_bat()
                if f.ai:
                    f.field_brain.wait = None

    def check_flight(self):
        ball, b = self.ball, self.batter
        ux, uy = self.bat_u
        # the swing comes through
        if self.swing_t is not None and not self.swing_checked and self.swing_t >= SWING_HIT_T:
            self.swing_checked = True
            hx, hy = self.hit_point()
            d = math.hypot(ball.x - hx, ball.y - hy)
            if d < REACH and ball.z < REACH_Z:
                self.hit((ball.x - hx) * ux + (ball.y - hy) * uy)
                return
            else:
                self.events.append(("whiff", None))
        # the ball meets the bat: bat down!
        lifted = self.swing_t is not None and BAT_UP[0] < self.swing_t < BAT_UP[1]
        bx, by = self.bat_point()
        rx, ry = ball.x - bx, ball.y - by
        along = rx * ux + ry * uy
        lat = -rx * uy + ry * ux
        if not lifted and abs(along) < BAT_THICK + BALL_R and abs(lat) < BAT_HALF + BALL_R and ball.z < BAT_H + BALL_R:
            self.stats["bat_down"] += 1
            self.events.append(("clatter", None))
            self.start_swap("bat")
            return
        if (ball.x - b.x) * ux + (ball.y - b.y) * uy < -0.3:
            self.passed = True
        if ball.resting or self.flight_t > 6.0:
            self.missed((ball.x, ball.y))

    def missed(self, at):
        self.stats["missed"] += 1
        self.set_x(at)
        self.phase = "fetch"
        self.streak += 1
        if self.streak % 3 == 0:
            self.award(1, f"Streak of {self.streak}! +1")

    def hit(self, along):
        """Bat on ball. along > 0: the ball was still in front (early); < 0: late."""
        b = self.batter
        e = max(-1.0, min(1.0, along / REACH))
        ux, uy = self.bat_u
        base = math.atan2(uy, ux)
        aim = base + math.radians(AIMS[self.aim_i] + e * 35 + self.rng.gauss(0, 4))
        p = 1 - 0.5 * abs(e) ** 1.2
        if self.loft:
            v = 6.0 + 7.2 * p
            elev = math.radians(36 + 10 * abs(e))
        else:
            v = 5.5 + 7.5 * p
            elev = math.radians(12 + (26 if e < 0 else 6) * abs(e))   # late: a skier
        vh, vz = v * math.cos(elev), v * math.sin(elev)
        ball = self.ball
        ball.launch(ball.x, ball.y, max(ball.z, 0.45), math.cos(aim) * vh, math.sin(aim) * vh, vz)
        self.phase = "hit"
        self.on_full = True
        self.x_mark = None
        self.stats["hits"] += 1
        q = "sweet" if abs(e) < 0.35 else ("early" if e > 0 else "late")
        self.events.append(("thock", q))
        if b.ai:
            pass

    def check_catch(self):
        f, ball = self.fielder, self.ball
        if not self.on_full or ball.age < 0.12:
            return
        if math.hypot(ball.x - f.x, ball.y - f.y) < CATCH_R and CATCH_Z[0] < ball.z < CATCH_Z[1]:
            self.stats["caught"] += 1
            f.holding = True
            f.anim, f.anim_t = "catch", 0.0
            self.events.append(("catch", f))
            self.start_swap("catch")

    def ball_events(self, ev):
        for kind, data in ev:
            if kind == "ground":
                x, y, sp = data
                if sp > 1.5:
                    self.dust.append([x, y, 0.0])
                    self.events.append(("pock", min(1.0, sp / 8)))
                if self.phase == "hit" and self.x_mark is None:
                    if self.on_full:
                        self.on_full = False
                        d = math.hypot(x - BAT_SPOT[0], y - BAT_SPOT[1])
                        pts = 1 if d < RINGS[0] else (2 if d < RINGS[1] else 3)
                        words = {1: "Nice! +1", 2: "Good shot! +2", 3: "Great shot! +3"}[pts]
                        self.award(pts, words)
                        if self.state != "play":
                            return
                    self.set_x((x, y))
                    self.phase = "fetch"
                    self.streak += 1
                    if self.streak % 3 == 0:
                        self.award(1, f"Streak of {self.streak}! +1")
                        if self.state != "play":
                            return
                elif self.phase == "flight" and self.passed:
                    self.missed((x, y))
            elif kind == "wall":
                self.events.append(("wall", data))
                if self.phase == "hit" and self.on_full:
                    self.on_full = False
                    self.stats["boundary"] += 1
                    self.award(5, "Into the hedge! +5" if data == "back" else "Off the railings! +5")
                    if self.state != "play":
                        return
            elif kind in ("tree", "leaves", "bench"):
                self.events.append(("knock", kind))
            elif kind == "rest":
                if self.phase == "hit":
                    # stopped without landing (on a bench, say): it lands where it stops
                    self.on_full = False
                    self.set_x(data)
                    self.phase = "fetch"
                elif self.phase == "flight":
                    self.missed(data)

    def set_x(self, at):
        """The chalk X, where the fielder must throw from (never too close, never inside anything)."""
        x, y = at
        bx, by = BAT_SPOT
        d = math.hypot(x - bx, y - by)
        if d < MIN_THROW:
            ux, uy = unit(x - bx, y - by) if d > 0.05 else unit(BOWL_MARK[0] - bx, BOWL_MARK[1] - by)
            x, y = bx + ux * MIN_THROW, by + uy * MIN_THROW
        x = min(max(x, 0.45), N - 0.45)
        y = min(max(y, 0.45), N - 0.45)
        x, y = self.world.resolve(x, y, RADIUS + 0.05)
        self.x_mark = (x, y)
        self.events.append(("x_mark", self.x_mark))

    def nudge_from_batter(self):
        """A ball that stops at the batter's feet is tapped away so the fielder can reach it."""
        ball, b = self.ball, self.batter
        if ball.speed > 1.0 or ball.z > 0.3:
            return
        d = math.hypot(ball.x - b.x, ball.y - b.y)
        if d < 0.85:
            ux, uy = unit(ball.x - b.x, ball.y - b.y) if d > 0.05 else unit(-self.bat_u[1], self.bat_u[0])
            ball.x, ball.y = self.world.resolve(b.x + ux * 1.0, b.y + uy * 1.0, BALL_R)
            ball.x = min(max(ball.x, 0.3), N - 0.3)
            ball.y = min(max(ball.y, 0.3), N - 0.3)

    def check_pickup(self):
        f, ball = self.fielder, self.ball
        if f.holding:
            return
        if math.hypot(ball.x - f.x, ball.y - f.y) < PICK_R + RADIUS * 0.6 and ball.z < 1.2 and ball.speed < 5.0:
            f.holding = True
            ball.resting = True
            f.anim, f.anim_t = "pickup", 0.0
            self.throw_clock = THROW_TIME
            self.clock_running = True
            self.events.append(("pickup", None))
            if self.x_mark is None:
                self.set_x((f.x, f.y))

    def award(self, pts, words):
        b = self.batter
        b.score += pts
        self.say(words, (255, 230, 120) if pts >= 3 else (255, 255, 255))
        self.events.append(("points", (b, pts)))
        if b.score >= self.target:
            self.end_match()

    # ---------------------------------------------------------------- swap and turns
    def start_swap(self, reason):
        self.swap_reason = reason
        b, f = self.batter, self.fielder
        self.fallen = (*self.bat_point(), *self.bat_u)      # the bat is dropped where it stood
        self.say("Bat down! Swap!" if reason == "bat" else "Caught! Swap!", (255, 140, 120))
        b.anim, b.anim_t = "sad", 0.0
        if reason == "bat":
            f.anim, f.anim_t = "cheer", 0.0
        self.events.append(("swap", reason))
        self.batter, self.fielder = f, b
        self.phase = None
        self.clock_running = False
        self.charging = False
        self.swing_t = None
        if all(r.turns >= self.turns for r in self.runners):
            self.end_match()
            return
        self.state = "swap"
        self.state_t = 4.5
        self.swap_walk_t = 1.2           # a moment to react before they change ends

    def update_swap(self, dt):
        self.swap_walk_t -= dt
        if self.ball.resting is False:
            self.ball.step(dt, self.geom)
        arrived = True
        for r, (tx, ty) in ((self.batter, BAT_SPOT), (self.fielder, BOWL_MARK)):
            if self.swap_walk_t > 0:
                arrived = False
                continue
            d = math.hypot(tx - r.x, ty - r.y)
            if d > 0.15:
                arrived = False
                br = r.field_brain if r.ai else FieldBrain(r, self.rng)
                if not r.ai:
                    r.field_brain = br
                turn, move = br.steer(self.world, tx, ty, self.other(r))
                if d < 0.4:
                    # close enough: step straight onto the spot
                    k = min(1.0, dt * 3.0 / max(d, 1e-6))
                    r.x += (tx - r.x) * k
                    r.y += (ty - r.y) * k
                    r.moved = 0.0
                else:
                    self.drive(r, turn, move, dt, swap=True)
        if arrived or self.state_t <= 0:
            self.state = "play"
            self.place_for_turn(snap=True)
            self.say(f"{self.batter.name} to bat", (200, 230, 255))

    def end_match(self):
        self.state = "match_over"
        self.state_t = 3.0
        self.phase = None
        a, b = self.p1, self.p2
        self.winner = None if a.score == b.score else (a if a.score > b.score else b)
        self.events.append(("match_over", self.winner))
        for r in self.runners:
            r.anim, r.anim_t = ("cheer" if r is self.winner else ("sad" if self.winner else "idle")), 0.0

    # ---------------------------------------------------------------- movement
    def ai_field(self, dt):
        f, ball = self.fielder, self.ball
        br = f.field_brain
        if self.phase == "flight":
            return 0, 0
        if self.phase == "hit":
            br.react -= dt
            if br.react > 0:
                return 0, 0
            if br.target is None or int(self.flight_t * 10) % 3 == 0:
                br.target = self.predict_catch_point(f)
            tx, ty = br.target
        elif self.phase == "fetch" and not f.holding:
            tx, ty = self.predict_rest()
        elif self.phase == "fetch":
            tx, ty = self.x_mark
        else:
            return 0, 0
        tx = min(max(tx, RADIUS + 0.05), N - RADIUS - 0.05)
        ty = min(max(ty, RADIUS + 0.05), N - RADIUS - 0.05)
        d = math.hypot(tx - f.x, ty - f.y)
        if 0.02 < d < 0.55:
            # the last step: shuffle straight onto it rather than turning on the spot
            k = min(1.0, dt * SPEED * f.speed_k * 0.8 / d)
            f.x, f.y = self.world.resolve(f.x + (tx - f.x) * k, f.y + (ty - f.y) * k)
            f.moved = d * k
            f.walk_phase += f.moved
            return 0, 0
        if f.moved < 0.002 and d > 0.3:
            br.stuck = getattr(br, "stuck", 0.0) + dt
        else:
            br.stuck = 0.0
        if getattr(br, "stuck", 0.0) > 1.0:
            # wedged (against the batter, say): sidestep round
            ux, uy = unit(tx - f.x, ty - f.y)
            side = (-uy, ux)
            k = SPEED * f.speed_k * 0.6 * dt
            f.x, f.y = self.world.resolve(f.x + (ux * 0.4 + side[0]) * k, f.y + (uy * 0.4 + side[1]) * k)
            if br.stuck > 2.2:
                br.stuck = 0.0
            return 0, 0
        return br.steer(self.world, tx, ty, self.batter)

    def predict_catch_point(self, f):
        """Where to stand: under the ball at catching height if there's time, else where it lands."""
        b = self.ball.copy()
        t = 0.0
        spd = f.speed()
        first = None
        while t < 4.0:
            ev = b.step(1 / 60, self.geom, 2)
            t += 1 / 60
            if b.vz < 0 and CATCH_Z[0] + 0.2 < b.z < 1.6 and self.on_full:
                need = math.hypot(b.x - f.x, b.y - f.y) / spd + 0.25
                if need < t:
                    return self.world.resolve(b.x, b.y)
            if any(k in ("ground", "wall") for k, _ in ev):
                first = (b.x, b.y)
                break
        if first is None:
            first = (b.x, b.y)
        return self.world.resolve(*first)

    def predict_rest(self):
        b = self.ball
        if b.resting or b.speed < 0.6:
            return b.x, b.y
        c = b.copy()
        for i in range(30):
            c.step(1 / 30, self.geom, 2)
            if c.resting:
                break
        return self.world.resolve(c.x, c.y)

    def drive(self, r, turn, move, dt, swap=False):
        """Tank controls as in Tag. The batter never moves."""
        r.turn_t = max(0.0, r.turn_t - dt)
        if turn:
            if r.turn_held != turn or r.turn_t <= 0:
                r.facing = (r.facing + turn) % 4
                r.turn_t = TURN_S
        r.turn_held = turn
        r.moved = 0.0
        r.moving = move
        if move and r.anim not in ("pickup", "throw", "lob") or (swap and move):
            dx, dy = FACINGS[r.facing]
            v = SPEED * r.speed_k * (1.0 if move > 0 else BACK_SPEED) * move
            ox, oy = r.x, r.y
            nx, ny = self.world.resolve(r.x + dx * v * dt, r.y + dy * v * dt)
            o = self.other(r)
            ddx, ddy = nx - o.x, ny - o.y
            d = math.hypot(ddx, ddy)
            if d < 2 * RADIUS and d > 1e-6:
                nx, ny = o.x + ddx / d * 2 * RADIUS, o.y + ddy / d * 2 * RADIUS
                nx, ny = self.world.resolve(nx, ny)
            r.x, r.y = nx, ny
            r.moved = math.hypot(nx - ox, ny - oy)
            r.walk_phase += r.moved * (1 if move > 0 else -1)
            if r.moved > 0 and r.anim == "idle":
                pass
