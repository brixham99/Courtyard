"""Tag: the rules, the movement and the computer player. No drawing here, so
it can be run headless for tests.

Rules
- A match is 3 rounds of 60 seconds. One player is "it" at a time.
- Touch the other player while you are "it" to tag them: they become "it".
- No tag-backs: the newly tagged player has to count to 3 (frozen for 1.5 s)
  before they can chase, and the player who just tagged can't be tagged back
  for 2 s.
- Whoever spends less time being "it" wins the round; best of three rounds
  wins the match. The round starts with the loser of the last round as "it"
  (the robot is "it" first).
- The player who is "it" runs 10% faster, so a chase can be won.
"""
import math
import random
from collections import deque

from iso import N

FACINGS = ((1, 0), (0, 1), (-1, 0), (0, -1))   # E, S, W, N: clockwise on screen (SE, SW, NW, NE)
SPRITE_KEY = ("se", "sw", "nw", "ne")
RADIUS = 0.3            # players' body radius (tiles)
TAG_REACH = 0.82        # centre-to-centre distance for a tag (arms' reach)
SPEED = 3.3             # tiles per second, walking forwards
IT_BOOST = 1.10
BACK_SPEED = 0.55       # walking backwards (Down)
TURN_S = 0.22           # a quarter turn; held keys repeat at this pace (as Haunted Mansion)
FREEZE_S = 1.5          # the newly tagged player counts to 3
IMMUNE_S = 2.0          # the tagger can't be tagged straight back
ROUND_S = 60.0
ROUNDS = 3
ROBOT_SPEED = 0.94      # the robot's pace relative to the players (beatable)
ROBOT_THINK = 0.16      # seconds between the robot's decisions
CELL = 0.5              # path-finding grid cell (tiles)


class Runner:
    def __init__(self, kind, name, x, y, facing, ai=False, speed_k=1.0):
        self.kind = kind          # "archie", "holly" or "robot"
        self.name = name
        self.x, self.y = x, y
        self.facing = facing      # index into FACINGS
        self.ai = ai
        self.speed_k = speed_k
        self.it = False
        self.it_time = 0.0
        self.tags = 0
        self.frozen = 0.0
        self.immune = 0.0
        self.turn_t = 0.0         # time until the next quarter turn may happen
        self.turn_held = 0
        self.walk_phase = 0.0
        self.moved = 0.0          # distance moved this step
        self.moving = 0           # +1 forwards, -1 backwards, 0 still
        self.brain = None

    @property
    def sprite_key(self):
        return SPRITE_KEY[self.facing]

    def speed(self):
        return SPEED * self.speed_k * (IT_BOOST if self.it else 1.0)


class World:
    """The courtyard's solid things, as circles and boxes, plus a path grid."""

    def __init__(self, obstacles):
        self.circles = [(o.x, o.y, o.r) for o in obstacles if o.kind == "tree"]
        self.boxes = [(o.x0, o.y0, o.x1, o.y1) for o in obstacles if o.kind in ("planter", "bench")]
        self.gn = int(N / CELL)
        self.free = [[self.cell_free(i, j) for j in range(self.gn)] for i in range(self.gn)]

    def cell_free(self, i, j):
        x, y = (i + 0.5) * CELL, (j + 0.5) * CELL
        return not self.blocked(x, y, RADIUS * 0.9)

    def blocked(self, x, y, r=RADIUS):
        if x < r or y < r or x > N - r or y > N - r:
            return True
        for cx, cy, cr in self.circles:
            if (x - cx) ** 2 + (y - cy) ** 2 < (cr + r) ** 2:
                return True
        for x0, y0, x1, y1 in self.boxes:
            if x0 - r < x < x1 + r and y0 - r < y < y1 + r:
                nx, ny = min(max(x, x0), x1), min(max(y, y0), y1)
                if (x - nx) ** 2 + (y - ny) ** 2 < r * r:
                    return True
        return False

    def resolve(self, x, y, r=RADIUS):
        """Push a body out of walls and obstacles."""
        for _ in range(3):
            x = min(max(x, r), N - r)
            y = min(max(y, r), N - r)
            for cx, cy, cr in self.circles:
                dx, dy = x - cx, y - cy
                d = math.hypot(dx, dy)
                if d < cr + r:
                    if d < 1e-6:
                        dx, dy, d = 1, 0, 1
                    x, y = cx + dx / d * (cr + r), cy + dy / d * (cr + r)
            for x0, y0, x1, y1 in self.boxes:
                nx, ny = min(max(x, x0), x1), min(max(y, y0), y1)
                dx, dy = x - nx, y - ny
                d = math.hypot(dx, dy)
                if d < r:
                    if d < 1e-6:   # inside: out the nearest side
                        opts = ((x - x0, -1, 0), (x1 - x, 1, 0), (y - y0, 0, -1), (y1 - y, 0, 1))
                        _, ux, uy = min(opts)
                        x = x0 - r if ux < 0 else (x1 + r if ux > 0 else x)
                        y = y0 - r if uy < 0 else (y1 + r if uy > 0 else y)
                    else:
                        x, y = nx + dx / d * r, ny + dy / d * r
        return x, y

    def cell_of(self, x, y):
        return (min(self.gn - 1, max(0, int(x / CELL))), min(self.gn - 1, max(0, int(y / CELL))))

    def field(self, x, y):
        """Path distance (in cells) from (x, y) to every free cell (4-way BFS)."""
        gn = self.gn
        INF = 10 ** 6
        d = [[INF] * gn for _ in range(gn)]
        si, sj = self.cell_of(x, y)
        d[si][sj] = 0
        q = deque([(si, sj)])
        while q:
            i, j = q.popleft()
            for di, dj in FACINGS:
                a, b = i + di, j + dj
                if 0 <= a < gn and 0 <= b < gn and self.free[a][b] and d[a][b] == INF:
                    d[a][b] = d[i][j] + 1
                    q.append((a, b))
        return d

    def openness(self, x, y):
        """How far from walls (capped): keeps a fleeing robot out of corners."""
        w = min(x, y, N - x, N - y)
        return min(w, 3.0)


class Brain:
    """The robot: chases when it's 'it', runs away (and circles) when it isn't."""

    def __init__(self, me, rng, skill=1.0):
        self.me = me
        self.rng = rng
        self.skill = skill
        self.think = 0.0
        self.want = me.facing
        self.wander = rng.uniform(0, 6.28)

    def decide(self, world, other, dt):
        me = self.me
        self.think -= dt
        if self.think > 0:
            return
        self.think = ROBOT_THINK * self.rng.uniform(0.8, 1.3) / self.skill
        if me.it:
            f = world.field(other.x, other.y)
            best, bscore = me.facing, None
            for k, (dx, dy) in enumerate(FACINGS):
                px, py = me.x + dx * CELL * 1.2, me.y + dy * CELL * 1.2
                if world.blocked(px, py):
                    continue
                i, j = world.cell_of(px, py)
                score = f[i][j] * CELL
                # in the open, close the bigger gap first, like a person would
                straight = abs(other.x - me.x) * (dx != 0) + abs(other.y - me.y) * (dy != 0)
                score -= 0.15 * straight
                if k == me.facing:
                    score -= 0.2           # don't dither
                if bscore is None or score < bscore:
                    best, bscore = k, score
            self.want = best
        else:
            f = world.field(other.x, other.y)
            best, bscore = me.facing, None
            dist = math.hypot(other.x - me.x, other.y - me.y)
            for k, (dx, dy) in enumerate(FACINGS):
                # look ahead along this direction until something solid
                px, py, run = me.x, me.y, 0.0
                while run < 2.5:
                    nx, ny = px + dx * 0.25, py + dy * 0.25
                    if world.blocked(nx, ny):
                        break
                    px, py, run = nx, ny, run + 0.25
                if run < 0.25:
                    continue
                i, j = world.cell_of(px, py)
                score = f[i][j] * CELL + 0.8 * world.openness(px, py) + 0.4 * run
                # don't run straight past the chaser
                tox, toy = other.x - me.x, other.y - me.y
                if (dx * tox + dy * toy) > 0 and dist < 4:
                    score -= 3.0
                if k == me.facing:
                    score += 0.35
                if k == (me.facing + 2) % 4:
                    score -= 0.6 * (1.0 if dist > 2.5 else 0.0)   # turning round costs time
                if dist > 6:   # far away: amble about rather than freeze
                    score += 0.5 * math.cos(self.wander + k * 1.57)
                if bscore is None or score > bscore:
                    best, bscore = k, score
            self.want = best
            self.wander += self.rng.uniform(-0.3, 0.3)

    def controls(self, world, other):
        """(turn, move) as if pressing keys: turn -1/0/+1, move +1/0."""
        me = self.me
        if me.frozen > 0:
            return 0, 0
        turn = 0
        if self.want != me.facing:
            diff = (self.want - me.facing) % 4
            turn = 1 if diff == 1 else (-1 if diff == 3 else self.rng.choice((-1, 1)))
        dist = math.hypot(other.x - me.x, other.y - me.y)
        move = 1
        if not me.it and dist > 7.5 and self.rng.random() < 0.02:
            move = 0
        return turn, move


class TagGame:
    def __init__(self, player_kind, player_name, opponent=("robot", "Robot"), player_ai=False, seed=None,
                 obstacles=None, round_s=ROUND_S, rounds=ROUNDS):
        from scene import courtyard_obstacles
        self.rng = random.Random(seed)
        self.world = World(obstacles or courtyard_obstacles())
        self.round_s = round_s
        self.rounds = rounds
        self.p1 = Runner(player_kind, player_name, 3.0, 3.0, 0, ai=player_ai,
                         speed_k=ROBOT_SPEED if player_ai else 1.0)
        self.p2 = Runner(opponent[0], opponent[1], 11.0, 11.0, 2, ai=True, speed_k=ROBOT_SPEED)
        for r in (self.p1, self.p2):
            if r.ai:
                r.brain = Brain(r, self.rng)
        self.round = 0
        self.wins = [0, 0]
        self.events = []          # (kind, data) for sound and effects; the caller drains it
        self.state = "ready"      # ready -> playing -> round_over -> (ready | match_over)
        self.state_t = 0.0
        self.clock = 0.0
        self.tag_fx = []          # (x, y, age)
        self.round_results = []
        self.next_round()

    @property
    def runners(self):
        return (self.p1, self.p2)

    def other(self, r):
        return self.p2 if r is self.p1 else self.p1

    def next_round(self):
        self.round += 1
        starts = [((2.5, 2.5, 0)), ((11.5, 11.5, 2))]
        if self.round % 2 == 0:
            starts.reverse()
        for r, (x, y, f) in zip(self.runners, starts):
            r.x, r.y, r.facing = x, y, f
            r.it = False
            r.it_time = 0.0
            r.tags = 0
            r.frozen = r.immune = 0.0
            r.walk_phase = 0.0
        # the robot starts as "it"; after that, last round's loser
        if self.round_results:
            loser = self.round_results[-1]["loser"]
            it = self.p1 if loser == 0 else self.p2
        else:
            it = self.p2
        it.it = True
        it.frozen = FREEZE_S + 1.0          # it counts to 3 while the other runs off
        self.clock = self.round_s
        self.state = "ready"
        self.state_t = 2.0
        self.events.append(("round_ready", self.round))

    def update(self, dt, human=(0, 0)):
        """human: (turn, move) from the keyboard for p1 (ignored if p1 is AI)."""
        self.state_t -= dt
        for fx in self.tag_fx:
            fx[2] += dt
        self.tag_fx = [f for f in self.tag_fx if f[2] < 0.8]
        if self.state == "ready":
            if self.state_t <= 0:
                self.state = "playing"
                self.events.append(("whistle", None))
            return
        if self.state == "round_over":
            return
        if self.state == "match_over":
            return
        # playing
        self.clock -= dt
        for r in self.runners:
            if r.it:
                r.it_time += dt
            r.frozen = max(0.0, r.frozen - dt)
            r.immune = max(0.0, r.immune - dt)
        for r in self.runners:
            o = self.other(r)
            if r.ai:
                r.brain.decide(self.world, o, dt)
                turn, move = r.brain.controls(self.world, o)
            else:
                turn, move = human
                if r.frozen > 0:
                    turn, move = 0, 0
            self.drive(r, turn, move, dt)
        self.check_tag()
        if self.clock <= 0:
            self.end_round()

    def drive(self, r, turn, move, dt):
        """Tank controls: turn a quarter at a time (held: repeat), walk forwards or back."""
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
            v = r.speed() * (1.0 if move > 0 else BACK_SPEED) * move
            ox, oy = r.x, r.y
            nx, ny = self.world.resolve(r.x + dx * v * dt, r.y + dy * v * dt)
            # keep the players apart (they touch, they don't overlap)
            o = self.other(r)
            ddx, ddy = nx - o.x, ny - o.y
            d = math.hypot(ddx, ddy)
            if d < 2 * RADIUS and d > 1e-6:
                nx, ny = o.x + ddx / d * 2 * RADIUS, o.y + ddy / d * 2 * RADIUS
                nx, ny = self.world.resolve(nx, ny)
            r.x, r.y = nx, ny
            r.moved = math.hypot(nx - ox, ny - oy)
            r.walk_phase += r.moved * (1 if move > 0 else -1)

    def check_tag(self):
        it = self.p1 if self.p1.it else self.p2
        o = self.other(it)
        if it.frozen > 0 or o.immune > 0:
            return
        if math.hypot(it.x - o.x, it.y - o.y) < TAG_REACH:
            it.it, o.it = False, True
            it.tags += 1
            it.immune = IMMUNE_S
            o.frozen = FREEZE_S
            self.tag_fx.append([(it.x + o.x) / 2, (it.y + o.y) / 2, 0.0])
            self.events.append(("tag", (it, o)))

    def end_round(self):
        a, b = self.p1, self.p2
        if abs(a.it_time - b.it_time) < 0.05:
            win = 0 if a.tags >= b.tags else 1
        else:
            win = 0 if a.it_time < b.it_time else 1
        self.wins[win] += 1
        self.round_results.append({"winner": win, "loser": 1 - win, "it": (a.it_time, b.it_time),
                                   "tags": (a.tags, b.tags)})
        self.events.append(("round_over", win))
        need = self.rounds // 2 + 1
        if max(self.wins) >= need or self.round >= self.rounds:
            self.state = "match_over"
            self.events.append(("match_over", 0 if self.wins[0] > self.wins[1] else 1))
        else:
            self.state = "round_over"
        self.state_t = 3.0

    def continue_(self):
        if self.state == "round_over":
            self.next_round()
