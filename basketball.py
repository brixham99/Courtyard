"""Basketball: the rules, the ball and the computer player. No drawing here, so
it can be run headless for tests (like tag.py and batdown.py).

Rules (one on one, full court, street rules)
- You and the robot each attack one hoop: the player shoots at the near hoop
  (bottom right), the robot at the far hoop (top left).
- Dribble while you move. Hold Space to shoot: the power meter swings up and
  down, and the shot goes in if you let go in the green (the further out, the
  more power it needs). A defender close in front puts you off a little.
- Without the ball, Space is a swipe-and-jump: it can steal from a dribbler
  in reach, or block a shot as it leaves the shooter's hands.
- 2 points a basket, 3 from beyond the arc. After a basket the other player
  takes the ball under the hoop they defend. Missed shots are loose: grab the
  rebound and it's your ball.
- A 12-second shot clock: shoot before it runs out, or it's the other
  player's ball.
- First to 21 wins.

Units: x, y in tiles; z (height) in tiles, drawn at ZPX px per tile.
"""
import math
import random

from iso import N
from tag import Runner, World, FACINGS, RADIUS, SPEED, BACK_SPEED, TURN_S, ROBOT_SPEED
from batdown import FieldBrain, facing_for, unit

ZPX = 40.0
GRAV = 15.0             # tiles/s^2
BALL_R = 0.24           # a child's size 5 ball, in this game's tiles
RIM_Z = 5.0             # a mini-basketball hoop: about 1.8 x a child's height
RIM_R = 0.52
RIM_TUBE = 0.035
HAND_Z = 1.3            # the top of the dribble
SHOOT_Z = 3.3           # release point, just above the head
E_FLOOR = 0.78          # a pumped-up ball on tarmac
E_RIM = 0.5
E_BOARD = 0.62
E_FENCE = 0.45
ROLL_DECEL = 1.6
ARC_R = 4.2             # three-point line, from the middle of the hoop
TARGET = 21
SHOT_CLOCK = 12.0
CHARGE_S = 1.2          # the power meter takes this long from 0 to full (then back down)
STEAL_R = 1.0
STEAL_CHANCE = 0.45
PICK_R = 0.62
PICK_Z = 2.5
JUMP_S = 0.5
JUMP_H = 0.7            # tiles at the top of a jump
REACH_Z = 3.5           # fingertips, standing, arms up
BLOCK_R = 0.75
BLOCK_CHANCE = 0.75
DRIBBLE_K = 0.92        # dribbling is a little slower than running
SWIPE_COOL = 0.75
BODY_SEP = 0.70         # players' centres stay this far apart (the sprites are about a tile wide)


class Hoop:
    """A hoop on a post behind the baseline. side=+1: the court is on the +x
    side of the backboard (the far hoop); side=-1: the near hoop."""

    def __init__(self, name, cx, cy, side):
        self.name = name
        self.cx, self.cy = cx, cy
        self.side = side
        self.bx = cx - side * 0.67           # the backboard's plane (x)
        self.post_x = cx - side * 1.35       # the post
        self.y0, self.y1 = cy - 0.95, cy + 0.95
        self.z0, self.z1 = RIM_Z - 0.28, RIM_Z + 1.25
        self.net_t = 9.0                    # time since the net last swished (for the drawing)
        self.shake = 0.0                    # the rim rattling


def make_hoops():
    return (Hoop("far", 1.65, 7.0, 1), Hoop("near", 12.35, 7.0, -1))


def court_obstacles():
    """The two posts are the only solid things on the court."""
    from scene import Obstacle
    return [Obstacle("tree", x=h.post_x, y=h.cy, r=0.14) for h in make_hoops()]


def ideal_power(d):
    """The power (0..1) that drops the ball in from distance d."""
    return min(0.95, max(0.32, 0.27 + 0.058 * d + 0.008 * max(0.0, d - 4.0)))


def sweet(d):
    """Half the width of the green zone on the meter (roughly where shots still drop)."""
    return min(0.1, max(0.035, 0.32 / max(0.1, d)))


def power_at(t):
    """The meter swings 0 -> 1 -> 0 ... while Space is held."""
    u = (t / CHARGE_S) % 2.0
    return u if u <= 1.0 else 2.0 - u


class Ball:
    def __init__(self):
        self.x, self.y, self.z = 7.0, 7.0, BALL_R
        self.vx = self.vy = self.vz = 0.0
        self.rolling = False
        self.resting = True
        self.age = 0.0
        self.shot_by = None       # who shot it (cleared by a block or a steal)
        self.touched_rim = False
        self.through = None       # the hoop it has just dropped through
        self.no_pick = (None, 0.0)
        self.spin = 0.0

    def copy(self):
        b = Ball.__new__(Ball)
        b.__dict__.update(self.__dict__)
        return b

    def launch(self, x, y, z, vx, vy, vz):
        self.x, self.y, self.z = x, y, z
        self.vx, self.vy, self.vz = vx, vy, vz
        self.rolling = self.resting = False
        self.age = 0.0
        self.touched_rim = False
        self.through = None

    def step(self, dt, hoops, n=6):
        """Advance; returns events: floor, fence, board, rim, post, through, rest."""
        ev = []
        if self.resting:
            return ev
        self.age += dt
        self.spin += dt * math.hypot(self.vx, self.vy) * 3
        h = dt / n
        for _ in range(n):
            pz = self.z
            if self.rolling:
                v = math.hypot(self.vx, self.vy)
                nv = max(0.0, v - ROLL_DECEL * h)
                if nv <= 0.05:
                    self.vx = self.vy = 0.0
                    self.resting = True
                    ev.append(("rest", None))
                    return ev
                self.vx *= nv / v
                self.vy *= nv / v
            else:
                self.vz -= GRAV * h
            self.x += self.vx * h
            self.y += self.vy * h
            self.z += self.vz * h
            # the fences (tall chain-link at the back, an invisible net over the low front fence)
            for axis in ("x", "y"):
                p = getattr(self, axis)
                v = getattr(self, "v" + axis)
                if (p < BALL_R and v < 0) or (p > N - BALL_R and v > 0):
                    setattr(self, axis, min(max(p, BALL_R), N - BALL_R))
                    setattr(self, "v" + axis, -v * E_FENCE)
                    if abs(v) > 0.8:
                        ev.append(("fence", abs(v)))
            for hp in hoops:
                # the post (a thin upright)
                if self.z < hp.z1:
                    dx, dy = self.x - hp.post_x, self.y - hp.cy
                    d = math.hypot(dx, dy)
                    if d < 0.12 + BALL_R:
                        nx, ny = (dx / d, dy / d) if d > 1e-6 else (hp.side, 0.0)
                        self.x, self.y = hp.post_x + nx * (0.12 + BALL_R), hp.cy + ny * (0.12 + BALL_R)
                        vn = self.vx * nx + self.vy * ny
                        if vn < 0:
                            self.vx -= (1 + E_FENCE) * vn * nx
                            self.vy -= (1 + E_FENCE) * vn * ny
                            ev.append(("post", abs(vn)))
                # the backboard: a plane facing the court
                if hp.y0 - BALL_R * 0.5 < self.y < hp.y1 + BALL_R * 0.5 and hp.z0 - BALL_R * 0.5 < self.z < hp.z1 + BALL_R * 0.5:
                    d = (self.x - hp.bx) * hp.side
                    if -0.2 < d < BALL_R and self.vx * hp.side < 0:
                        self.x = hp.bx + hp.side * BALL_R
                        sp = abs(self.vx)
                        self.vx = -self.vx * E_BOARD
                        self.vy *= 0.85
                        self.vz *= 0.85
                        ev.append(("board", (hp, sp)))
                # the rim: a ring; bounce off the nearest point of it
                dx, dy = self.x - hp.cx, self.y - hp.cy
                r = math.hypot(dx, dy)
                if abs(self.z - RIM_Z) < BALL_R + RIM_TUBE + 0.05 and r < RIM_R + BALL_R + 0.05:
                    if r > 1e-6:
                        qx, qy = hp.cx + dx / r * RIM_R, hp.cy + dy / r * RIM_R
                    else:
                        qx, qy = hp.cx + RIM_R, hp.cy
                    ex, ey, ez = self.x - qx, self.y - qy, self.z - RIM_Z
                    dd = math.sqrt(ex * ex + ey * ey + ez * ez)
                    lim = BALL_R + RIM_TUBE
                    if dd < lim and dd > 1e-6:
                        nx, ny, nz = ex / dd, ey / dd, ez / dd
                        vn = self.vx * nx + self.vy * ny + self.vz * nz
                        if vn < 0:
                            self.vx -= (1 + E_RIM) * vn * nx
                            self.vy -= (1 + E_RIM) * vn * ny
                            self.vz -= (1 + E_RIM) * vn * nz
                            self.vx *= 0.92
                            self.vy *= 0.92
                            self.touched_rim = True
                            if abs(vn) > 0.5:          # a real knock, not rolling
                                hp.shake = 0.35
                                ev.append(("rim", (hp, abs(vn))))
                            else:                      # roll off, never perch
                                self.vx += nx * 0.12
                                self.vy += ny * 0.12
                        push = lim - dd
                        self.x += nx * push
                        self.y += ny * push
                        self.z += nz * push
                # through the hoop, downwards
                if pz >= RIM_Z > self.z and self.vz < 0 and r < RIM_R - 0.06 and self.through is None:
                    self.through = hp
                    hp.net_t = 0.0
                    self.vx *= 0.25
                    self.vy *= 0.25
                    self.vz = min(self.vz, -1.2) * 0.6
                    ev.append(("through", hp))
            # the floor
            if self.z <= BALL_R and not self.rolling:
                self.z = BALL_R
                if self.vz < 0:
                    ev.append(("floor", -self.vz))
                    self.vz = -self.vz * E_FLOOR
                    self.vx *= 0.9
                    self.vy *= 0.9
                    if self.vz < 0.9:
                        self.vz = 0.0
                        self.rolling = True
        return ev


def solve_shot(rx, ry, rz, tx, ty, d_extra=0.0):
    """Velocity from the release point to drop into the hoop at (tx, ty) on a
    good high arc; returns (vx, vy, vz, flight time)."""
    dx, dy = tx - rx, ty - ry
    d = max(0.2, math.hypot(dx, dy))
    ux, uy = dx / d, dy / d
    apex = RIM_Z + 1.0 + 0.11 * d
    vz = math.sqrt(2 * GRAV * (apex - rz))
    T = vz / GRAV + math.sqrt(2 * (apex - RIM_Z) / GRAV)
    vh = d / T
    return ux * vh, uy * vh, vz, T


# ------------------------------------------------------------------ the computer player
class Brain:
    def __init__(self, me, rng, skill=1.0, aim_sd=0.075):
        self.me = me
        self.rng = rng
        self.skill = skill
        self.aim_sd = aim_sd
        self.nav = FieldBrain(me, rng)
        self.spot = None
        self.shoot_p = None
        self.jump_in = None
        self.react = 0.0
        self.target = None
        self.retarget = 0.0
        self.stuck = 0.0
        self.patience = 0.0

    def reset(self):
        self.spot = None
        self.shoot_p = None
        self.jump_in = None
        self.target = None
        self.stuck = 0.0
        self.react = self.rng.uniform(0.15, 0.35) / self.skill

    def pick_spot(self, g):
        me, hp = self.me, self.me.goal
        roll = self.rng.random()
        if roll < 0.45:
            dist = self.rng.uniform(1.4, 2.6)          # drive to the basket
        elif roll < 0.75:
            dist = self.rng.uniform(2.8, 3.8)          # a mid-range jumper
        else:
            dist = self.rng.uniform(ARC_R + 0.3, ARC_R + 1.2)    # a three
        ang = self.rng.uniform(-1.05, 1.05)
        sx = hp.cx + hp.side * dist * math.cos(ang)
        sy = hp.cy + dist * math.sin(ang)
        self.spot = (min(max(sx, 0.6), N - 0.6), min(max(sy, 0.8), N - 0.8))
        self.patience = self.rng.uniform(2.5, 4.0)

    def steer_to(self, g, tx, ty, dt):
        me = self.me
        tx = min(max(tx, RADIUS + 0.05), N - RADIUS - 0.05)
        ty = min(max(ty, RADIUS + 0.05), N - RADIUS - 0.05)
        return self.nav.steer(g.world, tx, ty, g.other(me))

    def face(self, dx, dy):
        want = facing_for(dx, dy)
        me = self.me
        if want == me.facing:
            return 0
        diff = (want - me.facing) % 4
        return 1 if diff == 1 else -1

    def controls(self, g, dt):
        me = self.me
        o = g.other(me)
        if me.jump_t is not None:
            return 0, 0
        if self.react > 0:
            self.react -= dt
            return 0, 0
        # --- on the ball
        if g.holder is me:
            hp = me.goal
            if me.charging:
                if me.power >= self.shoot_p or me.power_t > CHARGE_S * 1.05:
                    g.shoot(me)
                return 0, 0
            if self.spot is None:
                self.pick_spot(g)
            self.patience -= dt
            d_hoop = math.hypot(hp.cx - me.x, hp.cy - me.y)
            do = math.hypot(o.x - me.x, o.y - me.y)
            ux, uy = unit(hp.cx - me.x, hp.cy - me.y)
            in_front = (o.x - me.x) * ux + (o.y - me.y) * uy > 0.25 and do < 1.15
            at_spot = math.hypot(self.spot[0] - me.x, self.spot[1] - me.y) < 0.5
            want_shot = False
            if g.shot_clock < 2.2:
                want_shot = True
            elif at_spot or self.patience < 0:
                if in_front and do < 0.85 and self.rng.random() < 0.7 and g.shot_clock > 4:
                    self.pick_spot(g)          # crowded: go round
                else:
                    want_shot = True
            elif d_hoop < ARC_R + 1.0 and do > 2.6 and self.rng.random() < dt * 0.5:
                want_shot = True               # wide open: take it
            if want_shot:
                p = ideal_power(d_hoop) + self.rng.gauss(0, self.aim_sd / self.skill)
                self.shoot_p = min(0.99, max(0.08, p))
                g.start_charge(me)
                return 0, 0
            if me.moved < 0.003:
                self.stuck += dt
                if self.stuck > 0.8:
                    self.stuck = 0.0
                    self.pick_spot(g)
            else:
                self.stuck = 0.0
            return self.steer_to(g, *self.spot, dt)
        # --- defending
        if g.holder is o:
            hp = me.home                       # the hoop the dribbler is going for
            dh = math.hypot(hp.cx - o.x, hp.cy - o.y)
            gap = min(1.1, max(0.6, dh * 0.4))
            ux, uy = unit(hp.cx - o.x, hp.cy - o.y)
            tx, ty = o.x + ux * gap, o.y + uy * gap
            d = math.hypot(o.x - me.x, o.y - me.y)
            if o.charging:
                if d < 1.7:
                    if self.jump_in is None:
                        self.jump_in = self.rng.uniform(0.05, 0.55) / self.skill
                    self.jump_in -= dt
                    if self.jump_in <= 0:
                        self.jump_in = None
                        g.swipe(me)
                        return 0, 0
                    return self.face(o.x - me.x, o.y - me.y), 0
            else:
                self.jump_in = None
                if d < STEAL_R * 0.95 and me.cool <= 0 and self.rng.random() < dt * 0.9 * self.skill:
                    g.swipe(me)
                    return 0, 0
            if math.hypot(tx - me.x, ty - me.y) < 0.3:
                return self.face(o.x - me.x, o.y - me.y), 0
            return self.steer_to(g, tx, ty, dt)
        # --- a loose ball (or one in the air): go and get it
        b = g.ball
        if b.through is not None:
            return 0, 0
        self.retarget -= dt
        if self.target is None or self.retarget <= 0:
            self.retarget = 0.2
            self.target = g.predict_ball(me)
        return self.steer_to(g, *self.target, dt)


# ------------------------------------------------------------------ the game
class BasketballGame:
    def __init__(self, player_kind, player_name, opponent=("robot", "Robot"), player_ai=False, seed=None,
                 target=TARGET):
        self.rng = random.Random(seed)
        self.hoops = make_hoops()
        self.world = World(court_obstacles())
        self.target = target
        self.p1 = Runner(player_kind, player_name, 3.0, 7.0, 0, ai=player_ai, speed_k=ROBOT_SPEED if player_ai else 1.0)
        self.p2 = Runner(opponent[0], opponent[1], 11.0, 7.0, 2, ai=True, speed_k=ROBOT_SPEED)
        far, near = self.hoops
        self.p1.goal, self.p1.home = near, far
        self.p2.goal, self.p2.home = far, near
        for r in self.runners:
            r.score = 0
            r.made2 = r.made3 = r.shots = 0
            r.anim, r.anim_t = "idle", 0.0
            r.jump_t = None
            r.cool = 0.0
            r.charging = False
            r.power_t = 0.0
            r.power = 0.0
            r.dribble = 0.0
            if r.ai:
                r.brain = Brain(r, self.rng)
        self.ball = Ball()
        self.holder = None
        self.events = []
        self.callouts = []
        self.state = "tipoff"          # tipoff -> play <-> scored -> match_over
        self.state_t = 2.4
        self.shot_clock = SHOT_CLOCK
        self.shot_pts = 2
        self.next_ball = None
        self.winner = None
        self.last_score = None
        self.stats = {"shots": 0, "made": 0, "threes": 0, "steals": 0, "blocks": 0, "rebounds": 0,
                      "rim": 0, "board": 0, "swish": 0, "clock": 0}
        first = self.rng.choice(self.runners)
        self.give(first)
        self.events.append(("tipoff", first))

    # ---------------------------------------------------------------- helpers
    @property
    def runners(self):
        return (self.p1, self.p2)

    def other(self, r):
        return self.p2 if r is self.p1 else self.p1

    def say(self, text, col=(255, 255, 255)):
        self.callouts.append([text, col, 0.0])

    def dribble_pos(self, r):
        """Where the ball is while r dribbles: beside the leading hand, bouncing."""
        fx, fy = FACINGS[r.facing]
        sx, sy = -fy, fx                      # the right-hand side
        z = BALL_R + (HAND_Z - BALL_R) * abs(math.cos(r.dribble))
        return r.x + fx * 0.36 + sx * 0.22, r.y + fy * 0.36 + sy * 0.22, z

    def held_pos(self, r):
        if r.charging or r.anim == "release":
            ux, uy = unit(r.goal.cx - r.x, r.goal.cy - r.y)
            return r.x + ux * 0.18, r.y + uy * 0.18, SHOOT_Z
        return self.dribble_pos(r)

    def give(self, r, place=True):
        """r takes the ball under the hoop they defend; the other player drops back to defend."""
        o = self.other(r)
        hp = r.home
        if place:
            r.x, r.y = hp.cx + hp.side * 0.9, hp.cy + 1.35
            r.facing = 0 if hp.side > 0 else 2
            o.x, o.y = hp.cx + hp.side * 4.6, hp.cy - 0.3
            o.facing = 2 if hp.side > 0 else 0
        for q in self.runners:
            q.charging = False
            q.power = q.power_t = 0.0
            q.jump_t = None
            if q.anim in ("set", "release", "swipe", "jump"):
                q.anim = "idle"
            if q.ai:
                q.brain.reset()
        self.holder = r
        self.ball.resting = True
        self.ball.shot_by = None
        self.ball.through = None
        self.ball.x, self.ball.y, self.ball.z = self.dribble_pos(r)
        self.shot_clock = SHOT_CLOCK

    def take(self, r, how):
        """r gathers a loose ball."""
        self.holder = r
        b = self.ball
        b.resting = True
        b.shot_by = None
        r.dribble = math.acos(max(-1.0, min(1.0, (min(b.z, HAND_Z) - BALL_R) / (HAND_Z - BALL_R))))
        self.shot_clock = SHOT_CLOCK
        for q in self.runners:
            if q.ai:
                q.brain.reset()
                q.brain.react = 0.1
        self.events.append(("catch", (r, how)))
        if how == "rebound":
            self.stats["rebounds"] += 1

    # ---------------------------------------------------------------- actions
    def press(self, what, held=()):
        r = self.p1
        if r.ai or self.state != "play":
            return
        if what == "space":
            if self.holder is r:
                self.start_charge(r)
            else:
                self.swipe(r)
        elif what == "space_up":
            if r.charging:
                self.shoot(r)

    def start_charge(self, r):
        if self.holder is not r or r.charging:
            return
        r.charging = True
        r.power_t = 0.0
        r.power = 0.0
        r.facing = facing_for(r.goal.cx - r.x, r.goal.cy - r.y)
        r.anim, r.anim_t = "set", 0.0
        self.events.append(("set", r))

    def shoot(self, r):
        if self.holder is not r or not r.charging:
            return
        hp = r.goal
        o = self.other(r)
        rx, ry, rz = self.held_pos(r)
        d = math.hypot(hp.cx - r.x, hp.cy - r.y)
        e = r.power - ideal_power(d)
        vx, vy, vz, T = solve_shot(rx, ry, rz, hp.cx, hp.cy)
        # long or short with the power; a touch of wobble left and right,
        # more with a defender right in your face
        k = 1.0 + e * (0.62 + 1.4 / max(1.0, d))
        do = math.hypot(o.x - r.x, o.y - r.y)
        ux, uy = unit(hp.cx - r.x, hp.cy - r.y)
        front = (o.x - r.x) * ux + (o.y - r.y) * uy > 0
        contest = max(0.0, 1.3 - do) / 1.3 if front else 0.0
        sd = 0.01 + 0.0025 * d + 0.03 * contest
        ang = self.rng.gauss(0, sd)
        ca, sa = math.cos(ang), math.sin(ang)
        vx, vy = (vx * ca - vy * sa) * k, (vx * sa + vy * ca) * k
        vz *= 1.0 + 0.2 * e + self.rng.gauss(0, 0.01 + 0.03 * contest)
        b = self.ball
        b.launch(rx, ry, rz, vx, vy, vz)
        b.shot_by = r
        b.no_pick = (r, 0.45)
        self.shot_pts = 3 if d >= ARC_R else 2
        self.holder = None
        r.charging = False
        r.anim, r.anim_t = "release", 0.0
        r.shots += 1
        self.stats["shots"] += 1
        self.shot_quality = e
        self.events.append(("shot", (r, e, self.shot_pts)))
        for q in self.runners:
            if q.ai and q is not r:
                q.brain.reset()
                q.brain.react = 0.25
            elif q.ai:
                q.brain.reset()
                q.brain.react = 0.6          # hold the follow-through

    def swipe(self, r):
        """Space without the ball: reach in for a steal, jumping with arms up."""
        if r.cool > 0 or r.jump_t is not None or self.holder is r:
            return
        r.cool = SWIPE_COOL
        r.jump_t = 0.0
        r.anim, r.anim_t = "jump", 0.0
        r.blocked_try = False
        h = self.holder
        self.events.append(("swipe", r))
        if h is not None and h is not r and not h.charging:
            dx, dy = h.x - r.x, h.y - r.y
            d = math.hypot(dx, dy)
            fx, fy = FACINGS[r.facing]
            facing_ok = d < 1e-6 or (fx * dx + fy * dy) / d > 0.2
            if d < STEAL_R and facing_ok:
                if self.rng.random() < STEAL_CHANCE:
                    bx, by, bz = self.dribble_pos(h)
                    ux, uy = unit(r.x - h.x, r.y - h.y)
                    b = self.ball
                    b.launch(bx, by, max(bz, 0.6), ux * 1.6 + self.rng.uniform(-0.4, 0.4),
                             uy * 1.6 + self.rng.uniform(-0.4, 0.4), 2.6)
                    b.shot_by = None
                    b.no_pick = (h, 0.4)
                    self.holder = None
                    self.stats["steals"] += 1
                    self.say("Steal!", (120, 220, 255))
                    self.events.append(("steal", (r, h)))
                    for q in self.runners:
                        if q.ai:
                            q.brain.reset()
                            q.brain.react = 0.05 if q is r else 0.3

    # ---------------------------------------------------------------- the step
    def update(self, dt, human=(0, 0), held=()):
        for c in self.callouts:
            c[2] += dt
        self.callouts = [c for c in self.callouts if c[2] < 2.2]
        for hp in self.hoops:
            hp.net_t += dt
            hp.shake = max(0.0, hp.shake - dt)
        for r in self.runners:
            r.anim_t += dt
            r.moved = 0.0
            r.cool = max(0.0, r.cool - dt)
            if r.jump_t is not None:
                r.jump_t += dt
                if r.jump_t >= JUMP_S:
                    r.jump_t = None
                    if r.anim == "jump":
                        r.anim = "idle"
            if r.anim == "release" and r.anim_t > 0.45:
                r.anim = "idle"
            if r.anim in ("cheer", "sad") and r.anim_t > 1.8 and self.state == "play":
                r.anim = "idle"
        self.state_t -= dt
        if self.state == "tipoff":
            if self.state_t <= 0:
                self.state = "play"
                self.events.append(("whistle", None))
            return
        if self.state in ("scored", "match_over"):
            self.step_ball(dt)
            if self.state == "scored" and self.state_t <= 0:
                self.give(self.next_ball)
                self.state = "play"
                self.events.append(("whistle_short", None))
            return
        self.update_play(dt, human)

    def update_play(self, dt, human):
        b = self.ball
        h = self.holder
        if h is not None:
            self.shot_clock -= dt
            if self.shot_clock <= 0:
                self.stats["clock"] += 1
                self.say("Shot clock!", (255, 170, 90))
                self.events.append(("shot_clock", h))
                self.next_ball = self.other(h)
                h.charging = False
                self.holder = None
                b.launch(*self.dribble_pos(h), 0.0, 0.0, 0.0)
                b.shot_by = None
                self.state, self.state_t = "scored", 1.4
                return
        for r in self.runners:
            if r.ai:
                turn, move = r.brain.controls(self, dt)
            else:
                turn, move = human
            if r.charging:
                r.power_t += dt
                r.power = power_at(r.power_t)
                turn, move = 0, 0
            if r.jump_t is not None:
                move = 0
            self.drive(r, turn, move, dt)
        self.separate(dt)
        # the dribble
        h = self.holder
        if h is not None:
            if not h.charging:
                rate = 2 * math.pi * (1.15 if h.moved > 0 else 0.85)
                before = int((h.dribble + math.pi / 2) // math.pi)
                h.dribble += rate * dt / 2
                after = int((h.dribble + math.pi / 2) // math.pi)
                if after != before:
                    self.events.append(("bounce", 0.6))
            b.x, b.y, b.z = self.held_pos(h)
        else:
            self.step_ball(dt)
            self.check_block()
            self.check_pickup(dt)

    def separate(self, dt):
        """Ease the two players apart if they've ended up overlapping (after a jump, a landing or a take)."""
        a, o = self.p1, self.p2
        dx, dy = a.x - o.x, a.y - o.y
        d = math.hypot(dx, dy)
        if d >= BODY_SEP:
            return
        if d < 1e-6:
            dx, dy, d = 1.0, 0.0, 1.0
        push = min(BODY_SEP - d, 2.5 * dt) / 2
        ux, uy = dx / d, dy / d
        a.x, a.y = self.world.resolve(a.x + ux * push, a.y + uy * push)
        o.x, o.y = self.world.resolve(o.x - ux * push, o.y - uy * push)

    def step_ball(self, dt):
        b = self.ball
        for kind, data in b.step(dt, self.hoops):
            if kind == "floor":
                if data > 0.8:
                    self.events.append(("bounce", min(1.0, data / 7)))
            elif kind == "fence":
                self.events.append(("fence", min(1.0, data / 6)))
            elif kind == "post":
                self.events.append(("clank", min(1.0, data / 6) * 0.6))
            elif kind == "board":
                hp, sp = data
                self.stats["board"] += 1
                self.events.append(("board", min(1.0, sp / 5)))
            elif kind == "rim":
                hp, sp = data
                self.stats["rim"] += 1
                self.events.append(("clank", min(1.0, 0.3 + sp / 5)))
            elif kind == "through":
                self.scored(data)

    def scored(self, hp):
        b = self.ball
        r = b.shot_by
        if self.state != "play" or r is None or r.goal is not hp:
            self.events.append(("swish", 0.6))
            return
        pts = self.shot_pts
        r.score += pts
        if pts == 3:
            r.made3 += 1
            self.stats["threes"] += 1
        else:
            r.made2 += 1
        self.stats["made"] += 1
        clean = not b.touched_rim
        if clean:
            self.stats["swish"] += 1
        self.events.append(("swish", 1.0 if clean else 0.7))
        self.events.append(("score", (r, pts, clean)))
        words = ("Three points!" if pts == 3 else "Two points!")
        if clean:
            words = "Swish! " + words
        self.say(words, (255, 230, 120) if pts == 3 else (255, 255, 255))
        self.last_score = (r, pts)
        o = self.other(r)
        r.anim, r.anim_t = "cheer", 0.0
        o.anim, o.anim_t = "idle", 0.0
        o.jump_t = None
        b.shot_by = None
        if r.score >= self.target:
            self.end_match()
            return
        self.next_ball = o
        self.state, self.state_t = "scored", 1.9

    def check_block(self):
        b = self.ball
        s = b.shot_by
        if s is None or b.age > 0.6:
            return
        r = self.other(s)
        if r.jump_t is None or getattr(r, "blocked_try", False):
            return
        jz = JUMP_H * math.sin(math.pi * min(1.0, r.jump_t / JUMP_S))
        if math.hypot(b.x - r.x, b.y - r.y) < BLOCK_R and b.z < REACH_Z + jz + 0.2:
            r.blocked_try = True
            if self.rng.random() < BLOCK_CHANCE:
                ux, uy = unit(b.vx, b.vy)
                b.vx = -ux * 1.6 + self.rng.uniform(-1.2, 1.2)
                b.vy = -uy * 1.6 + self.rng.uniform(-1.2, 1.2)
                b.vz = 1.5
                b.shot_by = None
                self.stats["blocks"] += 1
                self.say("Blocked!", (255, 140, 120))
                self.events.append(("block", (r, s)))
                for q in self.runners:
                    if q.ai:
                        q.brain.reset()
                        q.brain.react = 0.15

    def check_pickup(self, dt):
        b = self.ball
        if b.through is not None and b.z > 1.0:
            return
        who, t = b.no_pick
        if t > 0:
            b.no_pick = (who, t - dt)
        best = None
        for r in self.runners:
            if who is r and t > 0:
                continue
            if r.charging:
                continue
            d = math.hypot(b.x - r.x, b.y - r.y)
            reach = PICK_Z + (JUMP_H if r.jump_t is not None else 0)
            if d < PICK_R and b.z < reach:
                if best is None or d < best[0]:
                    best = (d, r)
        if best:
            self.take(best[1], "rebound" if b.shot_by is not None or b.touched_rim else "loose")

    def end_match(self):
        self.state = "match_over"
        self.state_t = 3.0
        a, b = self.p1, self.p2
        self.winner = None if a.score == b.score else (a if a.score > b.score else b)
        self.events.append(("match_over", self.winner))
        for r in self.runners:
            r.charging = False
            r.anim, r.anim_t = ("cheer" if r is self.winner else "idle"), 0.0

    def continue_(self):
        pass

    # ---------------------------------------------------------------- movement
    def predict_ball(self, r):
        """Where to run for a loose ball: where it will be low enough to grab
        by the time r could get there."""
        b = self.ball
        if b.resting:
            return b.x, b.y
        c = b.copy()
        spd = SPEED * r.speed_k
        t = 0.0
        hoops = make_hoops()
        for i in range(90):
            c.step(1 / 30, hoops, 2)
            t += 1 / 30
            if c.z < PICK_Z - 0.3 and math.hypot(c.x - r.x, c.y - r.y) / spd + 0.15 < t:
                return c.x, c.y
            if c.resting:
                break
        return c.x, c.y

    def drive(self, r, turn, move, dt):
        """Tank controls as in Tag."""
        r.turn_t = max(0.0, r.turn_t - dt)
        if turn:
            if r.turn_held != turn or r.turn_t <= 0:
                r.facing = (r.facing + turn) % 4
                r.turn_t = TURN_S
        r.turn_held = turn
        r.moved = 0.0
        r.moving = move
        if move:
            dx, dy = FACINGS[r.facing]
            k = DRIBBLE_K if self.holder is r else 1.0
            v = SPEED * r.speed_k * k * (1.0 if move > 0 else BACK_SPEED) * move
            ox, oy = r.x, r.y
            nx, ny = self.world.resolve(r.x + dx * v * dt, r.y + dy * v * dt)
            o = self.other(r)
            ddx, ddy = nx - o.x, ny - o.y
            d = math.hypot(ddx, ddy)
            if d < BODY_SEP and d > 1e-6:
                nx, ny = o.x + ddx / d * BODY_SEP, o.y + ddy / d * BODY_SEP
                nx, ny = self.world.resolve(nx, ny)
            r.x, r.y = nx, ny
            r.moved = math.hypot(nx - ox, ny - oy)
            r.walk_phase += r.moved * (1 if move > 0 else -1)
