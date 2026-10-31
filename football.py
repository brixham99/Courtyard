"""Football: the rules, the ball and the computer player. No drawing here, so
it can be run headless for tests (like basketball.py).

Rules (one on one, small-sided, cage football)
- A goal at each end. You attack the far goal (top left); the robot attacks
  the near goal (bottom right). The pitch is walled by low boards, so the ball
  never goes out: it comes back off the boards.
- Run into the ball to take it: it stays at your feet as you run.
- Hold Space to shoot: the power meter swings up and down. Let go in the
  green for a hard, low-to-mid shot; too much and it flies high (and over the
  bar), too little and it's a soft roller the keeper will gather.
- Without the ball, Space is a sliding tackle: get it in front of you and
  close enough and you may win it. Miss and you're on the floor for a moment.
- When a shot comes at your goal, Space dives for it (the robot keeps goal
  by itself).
- After a goal the side that conceded kicks off from the centre spot.
- First to 5 goals wins.

Units: x, y in tiles; z (height) in tiles, drawn at ZPX px per tile.
"""
import math
import random

from iso import N
from tag import Runner, World, FACINGS, RADIUS, SPEED, BACK_SPEED, TURN_S, ROBOT_SPEED
from batdown import FieldBrain, facing_for, unit

ZPX = 40.0
GRAV = 15.0
BALL_R = 0.2
GOAL_Y0, GOAL_Y1 = 4.8, 9.2      # the goal mouth (posts' centres)
GOAL_D = 1.0                     # depth of the net behind the line
BAR_Z = 3.2                      # crossbar height (a touch above the children's heads)
POST_R = 0.07
E_GROUND = 0.5
E_BOARD = 0.6
E_POST = 0.7
ROLL_DECEL = 1.5                 # artificial grass
ROLL_DRAG = 0.35                 # and a little drag proportional to speed
TARGET = 5
CHARGE_S = 1.1
FOOT_D = 0.44                    # the ball sits this far in front of the dribbler's feet
PICK_R = 0.5
TACKLE_R = 1.15
TACKLE_CHANCE = 0.55
SLIDE_S = 0.42
DOWN_S = 0.55                    # on the floor after a missed tackle
TACKLE_COOL = 1.0
DIVE_S = 0.5
DIVE_V = 3.2                     # the keeper's sideways dive speed (tiles/s)
BODY_R = 0.38
REACH_Z = 2.3                    # a keeper's reach, standing
DIVE_REACH = 0.62                # arms out in a dive
DRIBBLE_K = 0.9


class Goal:
    """side=+1: the far goal at x = 0 (the pitch is on its +x side); -1: the near goal at x = N."""

    def __init__(self, name, side):
        self.name = name
        self.side = side
        self.x = 0.0 if side > 0 else float(N)          # the goal line
        self.back = self.x - side * GOAL_D               # the back of the net
        self.cy = (GOAL_Y0 + GOAL_Y1) / 2
        self.net_t = 9.0                                  # time since the ball hit the net
        self.net_hit = (0.0, 0.0)                         # where (y, z)
        self.shake = 0.0                                  # the frame rattling after a post hit


def make_goals():
    return (Goal("far", 1), Goal("near", -1))


def pitch_obstacles():
    return []


def ideal_power(d):
    """The meter power (0..1) for a hard, well-placed shot from distance d."""
    return min(0.82, max(0.42, 0.36 + 0.05 * d))


def sweet(d):
    return 0.085


def power_at(t):
    u = (t / CHARGE_S) % 2.0
    return u if u <= 1.0 else 2.0 - u


class Ball:
    def __init__(self):
        self.x, self.y, self.z = 7.0, 7.0, BALL_R
        self.vx = self.vy = self.vz = 0.0
        self.resting = True
        self.age = 0.0
        self.shot_by = None
        self.no_pick = (None, 0.0)
        self.spin = 0.0
        self.in_goal = None
        self.missed = False

    def copy(self):
        b = Ball.__new__(Ball)
        b.__dict__.update(self.__dict__)
        return b

    def launch(self, x, y, z, vx, vy, vz):
        self.x, self.y, self.z = x, y, z
        self.vx, self.vy, self.vz = vx, vy, vz
        self.resting = False
        self.age = 0.0
        self.missed = False

    @property
    def speed(self):
        return math.hypot(self.vx, self.vy)

    def _post(self, px, py, ev, gl):
        """An upright post (a cylinder up to the bar)."""
        if self.z > BAR_Z + POST_R:
            return
        dx, dy = self.x - px, self.y - py
        d = math.hypot(dx, dy)
        lim = POST_R + BALL_R
        if d < lim and d > 1e-6:
            nx, ny = dx / d, dy / d
            vn = self.vx * nx + self.vy * ny
            self.x, self.y = px + nx * lim, py + ny * lim
            if vn < 0:
                self.vx -= (1 + E_POST) * vn * nx
                self.vy -= (1 + E_POST) * vn * ny
                gl.shake = 0.4
                ev.append(("post", (gl, abs(vn))))

    def _bar(self, gl, ev):
        """The crossbar: a cylinder along y at the goal line."""
        if not (GOAL_Y0 < self.y < GOAL_Y1):
            return
        dx, dz = self.x - gl.x, self.z - BAR_Z
        d = math.hypot(dx, dz)
        lim = POST_R + BALL_R
        if d < lim and d > 1e-6:
            nx, nz = dx / d, dz / d
            vn = self.vx * nx + self.vz * nz
            self.x, self.z = gl.x + nx * lim, BAR_Z + nz * lim
            if vn < 0:
                self.vx -= (1 + E_POST) * vn * nx
                self.vz -= (1 + E_POST) * vn * nz
                gl.shake = 0.4
                ev.append(("bar", (gl, abs(vn))))

    def step(self, dt, goals, n=6):
        """Advance; events: ground, board, post, bar, net, goal, rest."""
        ev = []
        if self.resting:
            return ev
        self.age += dt
        self.spin += dt * math.hypot(self.vx, self.vy) * 4
        h = dt / n
        for _ in range(n):
            px = self.x
            on_ground = self.z <= BALL_R + 1e-3 and abs(self.vz) < 1e-3
            if on_ground:
                v = math.hypot(self.vx, self.vy)
                nv = max(0.0, v - (ROLL_DECEL + ROLL_DRAG * v) * h)
                if nv <= 0.04:
                    self.vx = self.vy = 0.0
                    self.resting = True
                    ev.append(("rest", None))
                    return ev
                self.vx *= nv / v
                self.vy *= nv / v
            else:
                self.vz -= GRAV * h
                self.vx *= 1 - 0.05 * h
                self.vy *= 1 - 0.05 * h
            self.x += self.vx * h
            self.y += self.vy * h
            self.z += self.vz * h
            # in the goal mouth?
            mouth = GOAL_Y0 + POST_R < self.y < GOAL_Y1 - POST_R and self.z < BAR_Z
            # the side boards (and the cage net above them)
            if self.y < BALL_R and self.vy < 0 or self.y > N - BALL_R and self.vy > 0:
                ev.append(("board", abs(self.vy)))
                self.y = min(max(self.y, BALL_R), N - BALL_R)
                self.vy = -self.vy * E_BOARD
                self.vx *= 0.9
            for gl in goals:
                s = gl.side
                beyond = (gl.x - self.x) * s          # > 0: past the goal line, into the goal end
                inside = self.in_goal is gl
                if not inside:
                    if beyond > -BALL_R and self.vx * s < 0:
                        if mouth and GOAL_Y0 + BALL_R * 0.5 < self.y < GOAL_Y1 - BALL_R * 0.5:
                            if beyond > 0:
                                self.in_goal = gl
                        elif not (GOAL_Y0 - BALL_R < self.y < GOAL_Y1 + BALL_R and self.z < BAR_Z + BALL_R):
                            # the end boards either side of the goal (and the net above it)
                            self.x = gl.x + s * BALL_R
                            ev.append(("board", abs(self.vx)))
                            self.vx = -self.vx * E_BOARD
                            self.vy *= 0.9
                    self._post(gl.x, GOAL_Y0, ev, gl)
                    self._post(gl.x, GOAL_Y1, ev, gl)
                    self._bar(gl, ev)
                    if self.in_goal is gl and (gl.x - self.x) * s > BALL_R:
                        pass
                else:
                    # inside the net: soft walls all round
                    hit = False
                    if (self.x - gl.back) * s < BALL_R:
                        self.x = gl.back + s * BALL_R
                        if self.vx * s < 0:
                            hit = abs(self.vx) > 0.6
                            self.vx = -self.vx * 0.12
                            self.vy *= 0.5
                            self.vz *= 0.5
                    if self.y < GOAL_Y0 + BALL_R:
                        self.y = GOAL_Y0 + BALL_R
                        hit = hit or self.vy < -0.6
                        self.vy = abs(self.vy) * 0.15
                    if self.y > GOAL_Y1 - BALL_R:
                        self.y = GOAL_Y1 - BALL_R
                        hit = hit or self.vy > 0.6
                        self.vy = -abs(self.vy) * 0.15
                    if self.z > BAR_Z - BALL_R:
                        self.z = BAR_Z - BALL_R
                        self.vz = -abs(self.vz) * 0.2
                    if hit and gl.net_t > 0.25:
                        gl.net_t = 0.0
                        gl.net_hit = (self.y, self.z)
                        ev.append(("net", gl))
                    if (self.x - gl.x) * s > BALL_R:          # back out onto the pitch
                        self.in_goal = None
            # over the line, fully: a goal
            for gl in goals:
                if self.in_goal is gl and (gl.x - self.x) * gl.side > BALL_R and (gl.x - px) * gl.side <= BALL_R:
                    ev.append(("goal", gl))
            # the ground
            if self.z <= BALL_R:
                self.z = BALL_R
                if self.vz < 0:
                    if self.vz < -0.8:
                        ev.append(("ground", -self.vz))
                    self.vz = -self.vz * E_GROUND
                    self.vx *= 0.85
                    self.vy *= 0.85
                    if self.vz < 0.8:
                        self.vz = 0.0
        return ev


# ------------------------------------------------------------------ the computer player
class Brain:
    def __init__(self, me, rng, skill=1.0, aim_sd=0.07):
        self.me = me
        self.rng = rng
        self.skill = skill
        self.aim_sd = aim_sd
        self.nav = FieldBrain(me, rng)
        self.spot = None
        self.shoot_p = None
        self.react = 0.0
        self.target = None
        self.retarget = 0.0
        self.stuck = 0.0
        self.patience = 0.0
        self.dive_in = None

    def reset(self):
        self.spot = None
        self.shoot_p = None
        self.target = None
        self.stuck = 0.0
        self.dive_in = None
        self.react = self.rng.uniform(0.15, 0.35) / self.skill

    def pick_spot(self, g):
        me, gl = self.me, self.me.goal
        o = g.other(me)
        dist = self.rng.uniform(3.2, 6.2)
        # go round the defender: the side of the pitch away from them
        if self.rng.random() < 0.7:
            side = 1 if o.y < me.y else -1
        else:
            side = self.rng.choice((-1, 1))
        sy = 7 + side * self.rng.uniform(0.5, 3.6)
        sx = gl.x + gl.side * dist
        self.spot = (min(max(sx, 0.8), N - 0.8), min(max(sy, 1.0), N - 1.0))
        self.patience = self.rng.uniform(2.0, 3.6)

    def steer_to(self, g, tx, ty, dt):
        tx = min(max(tx, RADIUS + 0.05), N - RADIUS - 0.05)
        ty = min(max(ty, RADIUS + 0.05), N - RADIUS - 0.05)
        return self.nav.steer(g.world, tx, ty, g.other(self.me))

    def face(self, dx, dy):
        want = facing_for(dx, dy)
        me = self.me
        if want == me.facing:
            return 0
        diff = (want - me.facing) % 4
        return 1 if diff == 1 else -1

    def keeper_spot(self, g, bx, by):
        """On the line from the ball to the middle of my goal, a little off the line."""
        gl = self.me.home
        out = 0.75
        dx, dy = bx - gl.x, by - gl.cy
        d = max(0.5, math.hypot(dx, dy))
        k = out / max(0.3, abs(dx) / d)
        tx = gl.x + gl.side * out
        ty = gl.cy + dy / max(0.3, abs(dx)) * out
        ty = min(max(ty, GOAL_Y0 + 0.4), GOAL_Y1 - 0.4)
        return tx, ty

    def controls(self, g, dt):
        me = self.me
        o = g.other(me)
        if me.slide_t is not None or me.dive_t is not None:
            return 0, 0
        b = g.ball
        # a shot coming at my goal: dive (if I'm in the way-ish)
        if b.shot_by is o and g.holder is None:
            cross = g.predict_cross(me.home)
            if cross is not None:
                cy, cz, ct = cross
                near_goal = (me.x - me.home.x) * me.home.side < 2.6
                if near_goal:
                    if self.dive_in is None:
                        self.dive_in = self.rng.uniform(0.16, 0.3) / self.skill
                    self.dive_in -= dt
                    if self.dive_in <= 0:
                        self.dive_in = None
                        g.dive(me)
                        return 0, 0
                    return 0, 0
        if self.react > 0:
            self.react -= dt
            return 0, 0
        # --- on the ball
        if g.holder is me:
            gl = me.goal
            if me.charging:
                if me.power >= self.shoot_p or me.power_t > CHARGE_S * 1.05:
                    g.shoot(me)
                return 0, 0
            if self.spot is None:
                self.pick_spot(g)
            self.patience -= dt
            d_goal = abs(me.x - gl.x)
            do = math.hypot(o.x - me.x, o.y - me.y)
            at_spot = math.hypot(self.spot[0] - me.x, self.spot[1] - me.y) < 0.6
            want = False
            if d_goal < 7.0 and (at_spot or self.patience < 0):
                want = True
            elif d_goal < 6.5 and do < 1.3 and self.rng.random() < dt * 1.5:
                want = True                # closed down: get it away
            elif self.patience < -2.5:
                self.pick_spot(g)
            if want:
                p = ideal_power(math.hypot(gl.x - me.x, gl.cy - me.y)) + self.rng.gauss(0, self.aim_sd / self.skill)
                self.shoot_p = min(0.99, max(0.1, p))
                g.start_charge(me)
                return 0, 0
            if me.moved < 0.003:
                self.stuck += dt
                if self.stuck > 0.7:
                    self.stuck = 0.0
                    self.pick_spot(g)
            else:
                self.stuck = 0.0
            return self.steer_to(g, *self.spot, dt)
        # --- defending
        if g.holder is o:
            gl = me.home
            d_att = abs(o.x - gl.x)
            d = math.hypot(o.x - me.x, o.y - me.y)
            if o.charging and d < 1.4:
                # block the shot: square up
                return self.face(o.x - me.x, o.y - me.y), 0
            if d_att < 7.2:
                # keep goal; rush out and smother when they get close
                tx, ty = self.keeper_spot(g, o.x, o.y)
                if d_att < 3.0:
                    tx, ty = o.x - gl.side * 0.7, o.y
                    if d < TACKLE_R * 0.9 and me.cool <= 0 and self.rng.random() < dt * 3.0 * self.skill:
                        me.facing = facing_for(o.x - me.x, o.y - me.y)
                        g.tackle(me)
                        return 0, 0
                if math.hypot(tx - me.x, ty - me.y) < 0.25:
                    return self.face(o.x - me.x, o.y - me.y), 0
                return self.steer_to(g, tx, ty, dt)
            # close down: between the ball and my goal
            ux, uy = unit(gl.x - o.x, gl.cy - o.y)
            gap = 0.75
            tx, ty = o.x + ux * gap, o.y + uy * gap
            if d < TACKLE_R * 0.95 and me.cool <= 0:
                fx, fy = FACINGS[me.facing]
                bx, by = g.ball.x, g.ball.y
                front = (bx - me.x) * fx + (by - me.y) * fy > 0.2
                if front and self.rng.random() < dt * 2.2 * self.skill:
                    g.tackle(me)
                    return 0, 0
                if not front:
                    return self.face(bx - me.x, by - me.y), 0
            if math.hypot(tx - me.x, ty - me.y) < 0.3:
                return self.face(o.x - me.x, o.y - me.y), 0
            return self.steer_to(g, tx, ty, dt)
        # --- a loose ball: go and get it (unless it's dribbling into my net: then too)
        self.retarget -= dt
        if self.target is None or self.retarget <= 0:
            self.retarget = 0.2
            self.target = g.predict_ball(me)
        return self.steer_to(g, *self.target, dt)


# ------------------------------------------------------------------ the game
class FootballGame:
    def __init__(self, player_kind, player_name, opponent=("robot", "Robot"), player_ai=False, seed=None,
                 target=TARGET):
        self.rng = random.Random(seed)
        self.goals = make_goals()
        self.world = World(pitch_obstacles())
        self.target = target
        self.p1 = Runner(player_kind, player_name, 5.0, 7.0, 2, ai=player_ai, speed_k=ROBOT_SPEED if player_ai else 1.0)
        self.p2 = Runner(opponent[0], opponent[1], 9.0, 7.0, 0, ai=True, speed_k=ROBOT_SPEED)
        far, near = self.goals
        self.p1.goal, self.p1.home = far, near        # p1 shoots at the far goal, defends the near one
        self.p2.goal, self.p2.home = near, far
        for r in self.runners:
            r.score = 0
            r.shots = 0
            r.on_target = 0
            r.saves = 0
            r.anim, r.anim_t = "idle", 0.0
            r.slide_t = None
            r.dive_t = None
            r.dive_v = (0.0, 0.0)
            r.down_t = 0.0
            r.cool = 0.0
            r.charging = False
            r.power_t = 0.0
            r.power = 0.0
            r.touch = 0.0
            if r.ai:
                r.brain = Brain(r, self.rng)
        self.ball = Ball()
        self.holder = None
        self.events = []
        self.callouts = []
        self.state = "kickoff"        # kickoff -> play <-> goal -> match_over
        self.state_t = 2.4
        self.next_ball = None
        self.winner = None
        self.last_goal = None
        self.woodwork = None              # [delay, callout] for a shot off the post or bar
        self.stats = {"shots": 0, "goals": 0, "saves": 0, "post": 0, "bar": 0, "tackles": 0, "won": 0,
                      "over": 0, "wide": 0, "lofted": 0}
        first = self.rng.choice(self.runners)
        self.kickoff(first)
        self.events.append(("kickoff", first))

    @property
    def runners(self):
        return (self.p1, self.p2)

    def other(self, r):
        return self.p2 if r is self.p1 else self.p1

    def say(self, text, col=(255, 255, 255)):
        self.callouts.append([text, col, 0.0])

    def foot_pos(self, r):
        fx, fy = FACINGS[r.facing]
        k = FOOT_D + (0.1 * abs(math.sin(r.touch)) if r.moved > 0 else 0.0)
        lo, hi = BALL_R + 0.02, N - BALL_R - 0.02
        return min(max(r.x + fx * k, lo), hi), min(max(r.y + fy * k, lo), hi), BALL_R

    def kickoff(self, r):
        """r kicks off from the centre spot; the other waits in their own half."""
        self.woodwork = None
        o = self.other(r)
        s = r.goal.side                       # r attacks towards x decreasing when s > 0
        r.x, r.y = 7.0 + s * 0.5, 7.0
        r.facing = 2 if s > 0 else 0
        o.x, o.y = 7.0 - s * 3.2, 7.0 + self.rng.uniform(-0.6, 0.6)
        o.facing = 0 if s > 0 else 2
        for q in self.runners:
            q.charging = False
            q.power = q.power_t = 0.0
            q.slide_t = q.dive_t = None
            q.down_t = 0.0
            if q.anim not in ("cheer",):
                q.anim = "idle"
            if q.ai:
                q.brain.reset()
        self.holder = r
        b = self.ball
        b.resting = True
        b.in_goal = None
        b.shot_by = None
        b.vx = b.vy = b.vz = 0.0
        b.x, b.y, b.z = self.foot_pos(r)

    def take(self, r, how):
        self.holder = r
        b = self.ball
        b.resting = True
        b.shot_by = None
        b.vx = b.vy = b.vz = 0.0
        for q in self.runners:
            if q.ai:
                q.brain.reset()
                q.brain.react = 0.08 if q is r else 0.2
        self.events.append(("trap", (r, how)))

    # ---------------------------------------------------------------- actions
    def press(self, what, held=()):
        r = self.p1
        if r.ai or self.state != "play":
            return
        if what == "space":
            if self.holder is r:
                self.start_charge(r)
            elif self.ball.shot_by is self.p2 and self.holder is None and abs(r.x - r.home.x) < 3.0:
                self.dive(r)
            else:
                self.tackle(r)
        elif what == "space_up":
            if r.charging:
                self.shoot(r)

    def start_charge(self, r):
        if self.holder is not r or r.charging:
            return
        r.charging = True
        r.power_t = 0.0
        r.power = 0.0
        r.facing = facing_for(r.goal.x - r.x, r.goal.cy - r.y)
        r.anim, r.anim_t = "set", 0.0
        self.events.append(("set", r))

    def aim_point(self, r):
        """Which side of the goal to go for: away from the keeper."""
        gl = r.goal
        o = self.other(r)
        k_in = abs(o.x - gl.x) < 3.0 and GOAL_Y0 - 0.5 < o.y < GOAL_Y1 + 0.5
        if k_in:
            ty = GOAL_Y1 - 0.6 if o.y < gl.cy else GOAL_Y0 + 0.6
        else:
            ty = gl.cy + self.rng.uniform(-1.0, 1.0)
        return gl.x, ty

    def shoot(self, r):
        if self.holder is not r or not r.charging:
            return
        gl = r.goal
        o = self.other(r)
        bx, by, bz = self.foot_pos(r)
        tx, ty = self.aim_point(r)
        d = math.hypot(tx - bx, ty - by)
        e = r.power - ideal_power(math.hypot(gl.x - r.x, gl.cy - r.y))
        # pace: harder with more power
        v = 7.0 + 9.0 * min(1.0, r.power)
        # height at the goal line: low and hard in the green; high (over) with too much
        z_t = 0.9 + e * 10.0
        if e < -0.12:
            z_t = 0.2                      # a soft one along the ground
            v *= 0.85
        # a wobble left and right: more from far out, off the green, or under pressure
        do = math.hypot(o.x - r.x, o.y - r.y)
        ux, uy = unit(tx - bx, ty - by)
        front = (o.x - r.x) * ux + (o.y - r.y) * uy > 0
        contest = max(0.0, 1.3 - do) / 1.3 if front else 0.0
        sd = 0.02 + 0.006 * d + 0.35 * max(0.0, abs(e) - 0.08) + 0.05 * contest
        ang = self.rng.gauss(0, sd)
        ca, sa = math.cos(ang), math.sin(ang)
        ux, uy = ux * ca - uy * sa, ux * sa + uy * ca
        t = d / v
        vz = (z_t - bz + 0.5 * GRAV * t * t) / t if z_t > 0.35 else 0.0
        vz = max(0.0, vz + self.rng.gauss(0, 0.25 + 1.0 * contest))
        b = self.ball
        b.launch(bx, by, bz, ux * v, uy * v, vz)
        b.shot_by = r
        b.no_pick = (r, 0.3)
        self.holder = None
        r.charging = False
        r.anim, r.anim_t = "kick", 0.0
        r.shots += 1
        self.stats["shots"] += 1
        if z_t > 1.6:
            self.stats["lofted"] += 1
        self.events.append(("kick", (r, min(1.0, v / 16))))
        self.events.append(("shot", (r, e)))
        for q in self.runners:
            if q.ai:
                q.brain.reset()
                q.brain.react = 0.5 if q is r else 0.0
                if q is not r:
                    q.brain.dive_in = None

    def tackle(self, r):
        """A sliding tackle in the way you're facing."""
        if r.cool > 0 or r.slide_t is not None or r.dive_t is not None or self.holder is r or r.down_t > 0:
            return
        r.cool = TACKLE_COOL
        r.slide_t = 0.0
        r.anim, r.anim_t = "slide", 0.0
        r.tackled = False
        self.stats["tackles"] += 1
        self.events.append(("slide", r))

    def dive(self, r):
        """The keeper's dive: sideways towards where the shot is going."""
        if r.dive_t is not None or r.slide_t is not None:
            return
        cross = self.predict_cross(r.home)
        gl = r.home
        if cross is not None:
            ty = cross[0] + (self.rng.gauss(0, 0.35) if r.ai else 0.0)
        else:
            ty = self.ball.y
        dy = ty - r.y
        r.dive_t = 0.0
        r.dive_v = (0.0, max(-DIVE_V, min(DIVE_V, dy / 0.28)))
        r.dive_dir = 1 if dy >= 0 else -1
        r.anim, r.anim_t = "dive", 0.0
        self.events.append(("dive", r))

    # ---------------------------------------------------------------- the step
    def update(self, dt, human=(0, 0), held=()):
        for c in self.callouts:
            c[2] += dt
        self.callouts = [c for c in self.callouts if c[2] < 2.2]
        for gl in self.goals:
            gl.net_t += dt
            gl.shake = max(0.0, gl.shake - dt)
        for r in self.runners:
            r.anim_t += dt
            r.moved = 0.0
            r.cool = max(0.0, r.cool - dt)
            if r.anim == "kick" and r.anim_t > 0.4:
                r.anim = "idle"
            if r.anim in ("cheer", "sad") and r.anim_t > 1.8 and self.state == "play":
                r.anim = "idle"
        self.state_t -= dt
        if self.state == "kickoff":
            if self.state_t <= 0:
                self.state = "play"
                self.events.append(("whistle", None))
            return
        if self.state in ("goal", "match_over"):
            self.step_ball(dt)
            for r in self.runners:
                self.step_moves(r, dt)
            if self.state == "goal" and self.state_t <= 0:
                self.kickoff(self.next_ball)
                self.state = "kickoff"
                self.state_t = 1.2
            return
        self.update_play(dt, human)

    def step_moves(self, r, dt):
        """Slides, dives and getting up again."""
        if r.slide_t is not None:
            r.slide_t += dt
            fx, fy = FACINGS[r.facing]
            v = SPEED * 1.6 * max(0.0, 1 - r.slide_t / SLIDE_S)
            nx, ny = self.world.resolve(r.x + fx * v * dt, r.y + fy * v * dt)
            r.moved = math.hypot(nx - r.x, ny - r.y)
            r.x, r.y = nx, ny
            if self.state == "play":
                self.check_tackle(r)
            if r.slide_t >= SLIDE_S:
                r.slide_t = None
                if not r.tackled:
                    r.down_t = DOWN_S
                    r.anim, r.anim_t = "down", 0.0
                else:
                    r.anim = "idle"
        elif r.dive_t is not None:
            r.dive_t += dt
            k = max(0.0, 1 - r.dive_t / DIVE_S)
            vy = r.dive_v[1] * (1.0 if r.dive_t < 0.3 else k * 2)
            nx, ny = self.world.resolve(r.x, r.y + vy * dt)
            r.x, r.y = nx, ny
            if r.dive_t >= DIVE_S:
                r.dive_t = None
                r.down_t = 0.45
                r.anim, r.anim_t = "down", 0.0
        elif r.down_t > 0:
            r.down_t -= dt
            if r.down_t <= 0 and r.anim == "down":
                r.anim = "idle"

    def update_play(self, dt, human):
        b = self.ball
        if self.woodwork is not None:
            self.woodwork[0] -= dt
            if self.woodwork[0] <= 0:
                self.say(self.woodwork[1], (255, 220, 140))
                self.events.append(("groan", 1.0))
                self.woodwork = None
        for r in self.runners:
            if r.ai:
                turn, move = r.brain.controls(self, dt)
            else:
                turn, move = human
            if r.charging:
                r.power_t += dt
                r.power = power_at(r.power_t)
                turn, move = 0, 0
            if r.slide_t is not None or r.dive_t is not None or r.down_t > 0:
                self.step_moves(r, dt)
                continue
            self.drive(r, turn, move, dt)
        h = self.holder
        if h is not None:
            if h.moved > 0:
                before = int(h.touch / math.pi)
                h.touch += dt * 9.0
                if int(h.touch / math.pi) != before:
                    self.events.append(("touch", 0.4))
            b.x, b.y, b.z = self.foot_pos(h)
            b.spin += dt * h.moved * 60
        else:
            self.step_ball(dt)
            self.check_keeper()
            self.check_pickup(dt)

    def step_ball(self, dt):
        b = self.ball
        evs = b.step(dt, self.goals)
        for kind, data in evs:
            if kind == "ground":
                self.events.append(("bounce", min(1.0, data / 6)))
            elif kind == "board":
                if data > 1.0:
                    self.events.append(("board", min(1.0, data / 10)))
            elif kind in ("post", "bar"):
                gl, sp = data
                self.stats[kind] += 1
                self.events.append(("post", min(1.0, 0.3 + sp / 10)))
                if b.shot_by is not None and self.state == "play" and self.woodwork is None:
                    # wait a moment: if it goes in off the woodwork the crowd cheers instead
                    self.woodwork = [0.3, "Off the post!" if kind == "post" else "Off the bar!"]
            elif kind == "net":
                self.events.append(("net", 1.0))
            elif kind == "goal":
                self.scored(data)
        # a shot that's gone wide or over: it comes back off the end boards
        if b.shot_by is not None and self.state == "play":
            gl = b.shot_by.goal
            if any(k == "board" for k, _ in evs) and abs(b.x - gl.x) < 0.5 and not b.missed:
                b.missed = True
                over = GOAL_Y0 - 0.3 < b.y < GOAL_Y1 + 0.3
                self.stats["over" if over else "wide"] += 1
                self.say("Over the bar!" if over else "Just wide!", (220, 226, 240))
                self.events.append(("groan", 0.8))
            if b.age > 1.6:
                b.shot_by = None

    def scored(self, gl):
        b = self.ball
        if self.state != "play":
            return
        r = self.p1 if self.p1.goal is gl else self.p2       # the side attacking that goal
        o = self.other(r)
        r.score += 1
        if b.shot_by is r:
            r.on_target += 1
        self.stats["goals"] += 1
        self.events.append(("goal", (r, gl)))
        if self.woodwork is not None:
            self.say("In off the " + ("post!" if "post" in self.woodwork[1] else "bar!"), (255, 220, 140))
            self.woodwork = None
        self.say("GOAL!", (255, 230, 120))
        self.last_goal = (r, gl)
        self.holder = None
        r.anim, r.anim_t = "cheer", 0.0
        o.anim, o.anim_t = "idle", 0.0
        b.shot_by = None
        if r.score >= self.target:
            self.end_match()
            return
        self.next_ball = o
        self.state, self.state_t = "goal", 2.2

    def check_keeper(self):
        """The ball against a player's body: a dive or a block can save it."""
        b = self.ball
        for r in self.runners:
            if b.no_pick[0] is r and b.no_pick[1] > 0:
                continue
            diving = r.dive_t is not None
            # the body is a slim upright; a dive stretches it sideways (along y) as it goes
            reach = BODY_R + (DIVE_REACH * min(1.0, r.dive_t / 0.16) if diving else 0.0)
            zr = REACH_Z + (0.3 if diving else 0.0)
            dx, dy = b.x - r.x, b.y - r.y
            d = math.hypot(dx, dy)
            if abs(dx) < 0.36 and abs(dy) < reach and b.z < zr and b.speed > 4.5:
                if (b.x - r.home.x) * r.home.side < -0.05:
                    continue                    # already in the net behind them
                shot = b.shot_by is not None and b.shot_by is not r
                # a dive or a body in the way: parry it
                k = 0.72 if diving else 0.5
                if self.rng.random() > k:
                    continue
                sp = b.speed
                nx, ny = unit(dx, dy) if d > 1e-6 else (r.home.side, 0.0)
                # away from goal, out to the side
                ox = r.home.side * abs(nx) if True else nx
                vx = ox * sp * 0.35 + r.home.side * 1.5
                vy = (ny if abs(ny) > 0.2 else self.rng.choice((-1, 1))) * sp * 0.4
                b.launch(b.x, b.y, max(b.z, BALL_R), vx, vy, 1.5 + self.rng.uniform(0, 2))
                b.no_pick = (r, 0.25)
                if shot:
                    self.stats["dives" if diving else "blocks"] = self.stats.get("dives" if diving else "blocks", 0) + 1
                    r.saves += 1
                    self.stats["saves"] += 1
                    self.say("Great save!" if diving else "Blocked!", (140, 220, 255))
                    self.events.append(("save", r))
                    self.events.append(("groan", 0.7))
                b.shot_by = None
                for q in self.runners:
                    if q.ai:
                        q.brain.reset()
                        q.brain.react = 0.1
                return

    def check_tackle(self, r):
        if r.tackled:
            return
        h = self.holder
        b = self.ball
        if h is r:
            return
        dx, dy = b.x - r.x, b.y - r.y
        d = math.hypot(dx, dy)
        if d > 0.62 or b.z > 0.8:
            return
        r.tackled = True
        if h is None:
            # a loose ball: poke it on
            fx, fy = FACINGS[r.facing]
            b.launch(b.x, b.y, BALL_R, fx * 4.5, fy * 4.5, 0.0)
            b.shot_by = None
            b.no_pick = (r, 0.15)
            return
        if self.rng.random() < TACKLE_CHANCE:
            fx, fy = FACINGS[r.facing]
            b.launch(b.x, b.y, BALL_R, fx * 4.0 + self.rng.uniform(-1.2, 1.2), fy * 4.0 + self.rng.uniform(-1.2, 1.2), 0.6)
            b.shot_by = None
            b.no_pick = (h, 0.5)
            self.holder = None
            h.charging = False
            self.stats["won"] += 1
            self.say("Tackle!", (120, 220, 255))
            self.events.append(("tackle", (r, h)))
            for q in self.runners:
                if q.ai:
                    q.brain.reset()
                    q.brain.react = 0.05 if q is r else 0.35

    def check_pickup(self, dt):
        b = self.ball
        if b.in_goal is not None:
            return
        who, t = b.no_pick
        if t > 0:
            b.no_pick = (who, t - dt)
        best = None
        for r in self.runners:
            if who is r and t > 0:
                continue
            if r.charging or r.slide_t is not None or r.down_t > 0:
                continue
            if r.dive_t is not None:
                continue
            d = math.hypot(b.x - r.x, b.y - r.y)
            if d < PICK_R + (0.1 if r.moved > 0 else 0) and b.z < 0.9 and b.speed < 9.0:
                if best is None or d < best[0]:
                    best = (d, r)
        if best:
            self.take(best[1], "loose")

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

    # ---------------------------------------------------------------- prediction
    def predict_cross(self, gl, horizon=1.4):
        """Where a ball in flight will cross gl's goal line: (y, z, t) or None."""
        b = self.ball
        if b.resting or (b.vx * gl.side) >= 0:
            return None
        c = b.copy()
        c.in_goal = None
        t = 0.0
        for i in range(int(horizon * 60)):
            px = c.x
            c.step(1 / 60, (), 1)
            t += 1 / 60
            if (gl.x - c.x) * gl.side >= 0 >= (gl.x - px) * gl.side or (c.x - gl.x) * gl.side < 0:
                if GOAL_Y0 - 0.6 < c.y < GOAL_Y1 + 0.6 and c.z < BAR_Z + 0.4:
                    return c.y, c.z, t
                return None
            if c.resting:
                return None
        return None

    def predict_ball(self, r):
        b = self.ball
        if b.resting:
            return b.x, b.y
        c = b.copy()
        spd = SPEED * r.speed_k
        t = 0.0
        goals = self.goals
        for i in range(60):
            c.step(1 / 30, goals, 2)
            t += 1 / 30
            if c.z < 0.8 and math.hypot(c.x - r.x, c.y - r.y) / spd + 0.1 < t:
                break
            if c.resting:
                break
        x = min(max(c.x, 0.3), N - 0.3)
        return x, c.y

    # ---------------------------------------------------------------- movement
    def drive(self, r, turn, move, dt):
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
            if d < 2 * RADIUS and d > 1e-6:
                nx, ny = o.x + ddx / d * 2 * RADIUS, o.y + ddy / d * 2 * RADIUS
                nx, ny = self.world.resolve(nx, ny)
            r.x, r.y = nx, ny
            r.moved = math.hypot(nx - ox, ny - oy)
            r.walk_phase += r.moved * (1 if move > 0 else -1)
