"""Courtyard: playground games for Archie and Holly, on one isometric screen.

Games: Tag (hands only) in the village school courtyard, and Batdown
(throw the ball at the bat, the batter hits it away) in the park, each
against the computer's robot.

    python game.py              play
    python game.py --shots DIR  write screenshots (headless is fine)
    python game.py --record OUT.mp4   record an AI-vs-AI demo video with sound
    python game.py --selftest   run several matches of both games' logic and exit
    python game.py --record-batdown OUT.mp4   the same for Batdown

Controls (tank-style, as in Daleks in Hedges and Haunted Mansion):
    Left/Right (A/D)  turn a quarter turn      Up (W)  run forwards
    Down (S)          step backwards           M  music on/off   Esc  back/quit
Batdown, batting:   Space swing (hold Up as you swing to loft it), Left/Right aim left/straight/right
Batdown, fielding:  run as above; on the chalk X: Left/Right aim, Up/Down throw type,
                    hold Space for power and let go to throw
"""
import json
import math
import os
import subprocess
import sys
import wave

import numpy as np
import pygame

import batdown
import batdown_view
import scene
import tag
from iso import WIN_W, WIN_H, N, P, SHADOW_K, mix, shade

HERE = os.path.dirname(os.path.abspath(__file__))
CH_DIR = os.path.join(HERE, "assets", "characters")
SND_DIR = os.path.join(HERE, "assets", "sounds")
FPS = 60
CH_SCALE = {"archie": 0.68, "holly": 0.68, "robot": 0.66}
NAMES = {"archie": "Archie", "holly": "Holly", "robot": "Robot"}
PLAYABLE = ("archie", "holly")
GAMES = (("Tag", True), ("Football", False), ("Basketball", False), ("Batdown", True))
TURN_KEYS = {pygame.K_LEFT: -1, pygame.K_a: -1, pygame.K_RIGHT: 1, pygame.K_d: 1}
MOVE_KEYS = {pygame.K_UP: 1, pygame.K_w: 1, pygame.K_DOWN: -1, pygame.K_s: -1}
GO_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
SOUND_VOL = {"whistle": 0.6, "whistle_long": 0.6, "slap": 0.8, "boing": 0.5, "beep": 0.35, "beep_hi": 0.4,
             "step1": 0.2, "step2": 0.2, "step3": 0.2, "rstep1": 0.22, "rstep2": 0.22, "rstep3": 0.22,
             "robot_happy": 0.45, "robot_sad": 0.45, "cheer": 0.55,
             "thock": 0.75, "clatter": 0.7, "pock": 0.35}
MUSIC_VOL = 0.35


def load_font(size, bold=False):
    for name in ("dejavusans", "helvetica", "arial"):
        try:
            f = pygame.font.SysFont(name, size, bold=bold)
            if f is not None:
                return f
        except Exception:
            pass
    return pygame.font.Font(None, size)


def fmt(s):
    s = max(0, int(math.ceil(s - 1e-6)))
    return f"{s // 60}:{s % 60:02d}"


def fmt_it(s):
    s = max(0, int(round(s)))
    return f"{s // 60}:{s % 60:02d}"


# ------------------------------------------------------------------ characters
class Character:
    """A character's walk frames for the four isometric facings, with anchors
    (where the feet touch the ground) and pre-made shadows."""

    def __init__(self, kind):
        self.kind = kind
        k = CH_SCALE[kind]
        meta = json.load(open(os.path.join(CH_DIR, f"{kind}_walk.json")))
        self.frames = meta["frames"]
        self.cycle = meta["cycle_tiles"] * 1.05   # its stride, in this game's tiles
        self.walk, self.still, self.anchor, self.shadow, self.shadow_still = {}, {}, {}, {}, {}
        for key in tag.SPRITE_KEY:
            sheet = pygame.image.load(os.path.join(CH_DIR, f"{kind}_{key}_walk.png")).convert_alpha()
            fw = sheet.get_width() // self.frames
            fh = sheet.get_height()
            sw, sh = round(fw * k), round(fh * k)
            fr = [pygame.transform.smoothscale(sheet.subsurface((i * fw, 0, fw, fh)), (sw, sh)) for i in range(self.frames)]
            still = pygame.image.load(os.path.join(CH_DIR, f"{kind}_{key}.png")).convert_alpha()
            still = pygame.transform.smoothscale(still, (round(still.get_width() * k), round(still.get_height() * k)))
            self.walk[key] = fr
            self.still[key] = still
            ax, ay = meta["facings"][key]["anchor"]
            self.anchor[key] = (ax * k, ay * k)
            self.shadow[key] = [self.make_shadow(f, self.anchor[key]) for f in fr]
            self.shadow_still[key] = self.make_shadow(still, self.anchor[key])
        self.big = {key: pygame.image.load(os.path.join(CH_DIR, f"{kind}_{key}.png")).convert_alpha() for key in ("se", "sw")}

    @staticmethod
    def make_shadow(img, anchor):
        """The figure's silhouette laid on the ground towards the west (screen
        left), as the sun is in the east; returns (surface, offset from feet)."""
        w, h = img.get_size()
        ax, ay = anchor
        m = pygame.mask.from_surface(img, 100).to_surface(setcolor=(18, 22, 14, 255), unsetcolor=(0, 0, 0, 0))
        m = m.subsurface((0, 0, w, min(h, int(ay + 4)))).copy()
        h2 = m.get_height()
        r = pygame.transform.rotate(m, 90)             # head to the left
        L = max(1, round(h2 * SHADOW_K))
        Wd = max(1, round(w * 0.42))
        r = pygame.transform.smoothscale(r, (L, Wd))
        r.set_alpha(80)
        fx = ay / h2 * L if h2 else 0
        fy = (w - ax) / w * Wd
        return r, (-fx, -fy)

    def frame(self, key, phase, moving):
        if not moving:
            return self.still[key], self.shadow_still[key]
        i = int((phase / self.cycle) * self.frames) % self.frames
        return self.walk[key][i], self.shadow[key][i]


# ------------------------------------------------------------------ sound
class Sound:
    def __init__(self, enabled=True):
        self.ok = False
        self.log = []          # (time, name) for recordings
        self.t = 0.0
        self.music_on = True
        self.snd = {}
        if not enabled:
            return
        try:
            pygame.mixer.init(22050, -16, 2, 512)
            for f in os.listdir(SND_DIR):
                n, ext = os.path.splitext(f)
                if ext == ".wav":
                    s = pygame.mixer.Sound(os.path.join(SND_DIR, f))
                    s.set_volume(SOUND_VOL.get(n, 0.5))
                    self.snd[n] = s
            self.ok = True
        except Exception:
            self.ok = False

    def play(self, name, vol=1.0):
        self.log.append((self.t, name, vol))
        if self.ok and name in self.snd:
            ch = self.snd[name].play()
            if ch and vol != 1.0:
                ch.set_volume(vol)

    TRACKS = {"title": "title_theme.ogg", "game": "game_music.ogg"}   # game: the Dinosaur vs Bees loop

    def set_track(self, name):
        if getattr(self, "track", "title") == name:
            return
        self.track = name
        if self.music_on:
            self.music(True)

    def music(self, on=True):
        self.music_on = on
        if not self.ok:
            return
        try:
            if on:
                pygame.mixer.music.load(os.path.join(SND_DIR, self.TRACKS[getattr(self, "track", "title")]))
                pygame.mixer.music.set_volume(MUSIC_VOL)
                pygame.mixer.music.play(-1)
            else:
                pygame.mixer.music.stop()
        except Exception:
            pass


# ------------------------------------------------------------------ the app
class App:
    def __init__(self, sound=True):
        pygame.init()
        pygame.display.set_caption("Courtyard")
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        self.clock = pygame.time.Clock()
        self.f_logo = load_font(96, True)
        self.f_big = load_font(46, True)
        self.f_mid = load_font(28, True)
        self.f_hud = load_font(22, True)
        self.f_small = load_font(17)
        self.f_small_b = load_font(17, True)
        self.f_tiny = load_font(14)
        self.fonts = {"sign": load_font(12, True)}
        self.setting = "village_school"
        self.obstacles = scene.courtyard_obstacles()
        self.bg = scene.build_background(self.setting, self.fonts)
        scene.draw_obstacle_shadows(self.bg, self.obstacles)
        self.bg = self.bg.convert()   # opaque copy in the display's own format
        self.front = scene.build_front()
        self.tree_art = scene.TreeArt()
        self.contact = pygame.Surface((32, 12), pygame.SRCALPHA)
        pygame.draw.ellipse(self.contact, (20, 22, 14, 90), self.contact.get_rect())
        self.chars = {k: Character(k) for k in ("archie", "holly", "robot")}
        self.scenes = {}
        self.bd_view = batdown_view.BatdownView(self)
        self.sound = Sound(sound)
        self.state = "title"
        self.sel_char = 0
        self.sel_game = 0
        self.t = 0.0
        self.game = None
        self.held_turn = []
        self.held_move = []
        self.step_phase = {}

    def scene(self, setting):
        """The static art for a setting (built once): background, front layer, obstacles."""
        if setting not in self.scenes:
            obs = scene.obstacles_for(setting)
            bg = scene.build_background(setting, self.fonts)
            scene.draw_obstacle_shadows(bg, obs)
            self.scenes[setting] = {"bg": bg.convert(), "front": scene.build_front_for(setting), "obstacles": obs}
        return self.scenes[setting]

    @property
    def is_bd(self):
        return isinstance(self.game, batdown.BatdownGame)

    def title_is_bd(self):
        return GAMES[self.sel_game][0] == "Batdown"

    # -------------------------------------------------------------- flow
    def start_game(self, player_ai=False, seed=None, round_s=tag.ROUND_S, **bd):
        k = PLAYABLE[self.sel_char]
        if self.title_is_bd():
            self.game = batdown.BatdownGame(k, NAMES[k], player_ai=player_ai, seed=seed,
                                            obstacles=self.scene("park")["obstacles"], **bd)
        else:
            self.game = tag.TagGame(k, NAMES[k], player_ai=player_ai, seed=seed, obstacles=self.obstacles, round_s=round_s)
        self.state = "play"
        self.sound.set_track("game")
        self.step_phase = {}
        self.held_turn, self.held_move = [], []

    def human_controls(self):
        turn = TURN_KEYS[self.held_turn[-1]] if self.held_turn else 0
        move = MOVE_KEYS[self.held_move[-1]] if self.held_move else 0
        return turn, move

    def handle(self, e):
        if e.type == pygame.QUIT:
            return False
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_m:
                self.sound.music(not self.sound.music_on)
            if self.state == "title":
                if e.key == pygame.K_ESCAPE:
                    return False
                if e.key in TURN_KEYS:
                    self.sel_char = (self.sel_char + TURN_KEYS[e.key]) % len(PLAYABLE)
                    self.sound.play("beep")
                elif e.key in MOVE_KEYS:
                    self.sel_game = (self.sel_game - MOVE_KEYS[e.key]) % len(GAMES)
                    self.sound.play("beep")
                elif e.key in GO_KEYS:
                    if GAMES[self.sel_game][1]:
                        self.sound.play("beep_hi")
                        self.start_game()
                    else:
                        self.sound.play("boing")
            elif self.state == "play":
                if e.key == pygame.K_ESCAPE:
                    self.state = "title"
                    self.sound.set_track("title")
                    return True
                if e.key in TURN_KEYS and e.key not in self.held_turn:
                    self.held_turn.append(e.key)
                if e.key in MOVE_KEYS and e.key not in self.held_move:
                    self.held_move.append(e.key)
                if self.is_bd:
                    name = {pygame.K_LEFT: "left", pygame.K_a: "left", pygame.K_RIGHT: "right", pygame.K_d: "right",
                            pygame.K_UP: "up", pygame.K_w: "up", pygame.K_DOWN: "down", pygame.K_s: "down",
                            pygame.K_SPACE: "space"}.get(e.key)
                    if name:
                        self.game.press(name, self.bd_held())
                if e.key in GO_KEYS:
                    g = self.game
                    if g.state == "round_over" and g.state_t < 2.5:
                        g.continue_()
                    elif g.state == "match_over" and g.state_t < 2.0:
                        self.state = "title"
                        self.sound.set_track("title")
        if e.type == pygame.KEYUP:
            if self.state == "play" and self.is_bd and e.key == pygame.K_SPACE:
                self.game.press("space_up", self.bd_held())
            if e.key in self.held_turn:
                self.held_turn.remove(e.key)
            if e.key in self.held_move:
                self.held_move.remove(e.key)
        return True

    def bd_held(self):
        h = set()
        if any(MOVE_KEYS[k] > 0 for k in self.held_move):
            h.add("up")
        return h

    def update(self, dt, auto=False):
        self.t += dt
        self.sound.t = self.t
        if self.state != "play":
            return
        g = self.game
        if self.is_bd:
            self.update_bd(dt)
            return
        g.update(dt, self.human_controls())
        if auto:
            if g.state == "round_over" and g.state_t < 1.0:
                g.continue_()
        for kind, data in g.events:
            if kind == "whistle":
                self.sound.play("whistle")
            elif kind == "tag":
                tagger, tagged = data
                self.sound.play("slap")
                self.sound.play("boing", 0.8)
                if tagger.kind == "robot":
                    self.sound.play("robot_happy")
                elif tagged.kind == "robot":
                    self.sound.play("robot_sad")
            elif kind == "round_over":
                self.sound.play("whistle_long")
            elif kind == "match_over":
                if g.p1.kind != "robot" and data == 0:
                    self.sound.play("cheer")
        g.events.clear()
        # countdown pips for whoever is counting to 3
        for r in g.runners:
            key = ("count", id(r))
            n = math.ceil(r.frozen / 0.5) if r.frozen > 0 and g.state == "playing" else 0
            if n and n <= 3 and self.step_phase.get(key) != n:
                self.sound.play("beep", 0.6)
            self.step_phase[key] = n
        # footsteps on the walk cycle's two contacts
        for r in g.runners:
            ch = self.chars[r.kind]
            if r.moved > 0:
                c = int(r.walk_phase / ch.cycle * 2)
                if self.step_phase.get(id(r)) != c:
                    self.step_phase[id(r)] = c
                    base = "rstep" if r.kind == "robot" else "step"
                    self.sound.play(f"{base}{c % 3 + 1}", 0.7)

    def update_bd(self, dt):
        g = self.game
        last_clock = g.throw_clock
        g.update(dt, self.human_controls(), self.bd_held())
        snd = self.sound.play
        for kind, data in g.events:
            if kind == "whistle":
                snd("whistle")
            elif kind == "throw":
                snd("pock", 0.4)
            elif kind == "thock":
                snd("thock", 1.0 if data == "sweet" else 0.75)
            elif kind == "whiff":
                snd("boing", 0.35)
            elif kind == "clatter":
                snd("clatter")
                snd("robot_happy" if g.fielder.kind == "robot" else "robot_sad")   # (already swapped: fielder = old batter)
            elif kind == "catch":
                snd("slap", 0.7)
                if data.kind == "robot":
                    snd("robot_happy")
                elif not data.ai:
                    snd("cheer", 0.7)
            elif kind == "pock":
                snd("pock", 0.4 + 0.6 * data)
            elif kind == "wall":
                snd("pock", 0.9)
            elif kind == "knock" and data == "tree":
                snd("thock", 0.45)
            elif kind == "points":
                r, pts = data
                if pts >= 5:
                    snd("cheer", 0.8)
                elif pts >= 2:
                    snd("beep_hi", 0.8)
                else:
                    snd("beep", 0.8)
            elif kind == "swap":
                snd("whistle", 0.8)
            elif kind == "match_over":
                snd("whistle_long")
                if data is not None and data.kind != "robot" and not data.ai:
                    snd("cheer")
        g.events.clear()
        # the last three seconds of the throw clock tick
        if g.state == "play" and g.fielder.holding and g.clock_running:
            if math.ceil(g.throw_clock) != math.ceil(last_clock) and g.throw_clock < 3.0:
                snd("beep", 0.5)
        for r in g.runners:
            ch = self.chars[r.kind]
            if r.moved > 0:
                c = int(r.walk_phase / ch.cycle * 2)
                if self.step_phase.get(id(r)) != c:
                    self.step_phase[id(r)] = c
                    base = "rstep" if r.kind == "robot" else "step"
                    snd(f"{base}{c % 3 + 1}", 0.7)

    # -------------------------------------------------------------- drawing: the courtyard
    def draw_runner(self, s, r, t):
        ch = self.chars[r.kind]
        key = r.sprite_key
        img, (shd, (sx, sy)) = ch.frame(key, r.walk_phase, r.moved > 0)
        ax, ay = ch.anchor[key]
        gx, gy = P(r.x, r.y)
        bob = 0
        if r.moved > 0:
            bob = abs(math.sin(r.walk_phase / ch.cycle * 2 * math.pi)) * 2.0
        if r.frozen > 0 and self.game.state == "playing":
            bob = 0
        # soft contact shadow under the feet, then the long one to the west
        s.blit(self.contact, (round(gx - 16), round(gy - 6)))
        s.blit(shd, (round(gx + sx), round(gy + sy)))
        x0, y0 = round(gx - ax), round(gy - ay - bob)
        if r.immune > 0 and int(r.immune * 8) % 2 == 0 and self.game.state == "playing":
            img = img.copy()
            img.fill((60, 60, 60, 0), special_flags=pygame.BLEND_RGBA_ADD)
        s.blit(img, (x0, y0))
        return pygame.Rect(x0, y0, img.get_width(), img.get_height())

    def draw_world(self, s, runners, t, game=None):
        s.blit(self.bg, (0, 0))
        items = []
        for o in self.obstacles:
            items.append(("ob", o))
        for r in runners:
            items.append(("run", r))

        def depth_cmp(a, b):
            def in_front(p, q):   # is item p drawn after q?
                kp, op = p
                kq, oq = q
                if kp == "run" and kq == "run":
                    return (op.x + op.y) > (oq.x + oq.y)
                if kp == "run":
                    return self.run_in_front(op, oq)
                if kq == "run":
                    return not self.run_in_front(oq, op)
                return self.ob_depth(op) > self.ob_depth(oq)
            return 1 if in_front(a, b) else -1
        import functools
        items.sort(key=functools.cmp_to_key(depth_cmp))
        rects = {}
        tree_items = []
        for kind, o in items:
            if kind == "run":
                rects[id(o)] = self.draw_runner(s, o, t)
            elif o.kind == "planter":
                scene.draw_planter(s, o)
            elif o.kind == "bench":
                scene.draw_bench(s, o)
            elif o.kind == "tree":
                scene.draw_tree_base(s, o)
                tree_items.append(o)
        # the canopy goes over everything inside (fully opaque)
        for o in tree_items:
            s.blit(self.tree_art.canopy, scene.tree_canopy_rect(o, self.tree_art))
        s.blit(self.front, (0, 0))
        # markers above heads (always on top)
        if game:
            for r in runners:
                self.draw_marker(s, r, rects[id(r)], t, game)
            for fx in game.tag_fx:
                self.draw_tag_fx(s, fx)
        return rects

    @staticmethod
    def ob_depth(o):
        if o.kind == "tree":
            return o.x + o.y
        return (o.x0 + o.x1) / 2 + (o.y0 + o.y1) / 2

    @staticmethod
    def run_in_front(r, o):
        if o.kind == "tree":
            return (r.x + r.y) > (o.x + o.y)
        if r.x >= o.x1 or r.y >= o.y1:
            return True
        if r.x <= o.x0 or r.y <= o.y0:
            return False
        return True

    def draw_marker(self, s, r, rect, t, g):
        cx = rect.centerx
        top = max(rect.top - 6, 128)       # keep clear of the HUD bar
        badge_y = top - 18
        if r.it:
            b = math.sin(t * 6) * 3
            lab = self.f_hud.render("IT", True, (255, 255, 255))
            w, h = lab.get_width() + 16, lab.get_height() + 2
            box = pygame.Rect(0, 0, w, h)
            box.midbottom = (cx, top - 8 + b)
            pygame.draw.rect(s, (120, 16, 20), box.move(0, 2), border_radius=8)
            pygame.draw.rect(s, (220, 40, 44), box, border_radius=8)
            pygame.draw.rect(s, (255, 220, 200), box, 2, border_radius=8)
            s.blit(lab, (box.x + 8, box.y + 1))
            pygame.draw.polygon(s, (220, 40, 44), [(cx - 7, box.bottom), (cx + 7, box.bottom), (cx, box.bottom + 8)])
            badge_y = box.centery
        if r.frozen > 0 and g.state == "playing":
            n = math.ceil(r.frozen / 0.5)
            frac = (r.frozen % 0.5) / 0.5
            c = (cx + 44, badge_y)
            pygame.draw.circle(s, (255, 255, 255), c, 16)
            pygame.draw.circle(s, (40, 40, 60), c, 16, 2)
            if frac > 0:
                pygame.draw.arc(s, (230, 60, 60), (c[0] - 16, c[1] - 16, 32, 32), math.pi / 2, math.pi / 2 + 2 * math.pi * frac, 4)
            lab = self.f_hud.render(str(min(3, n)), True, (40, 40, 60))
            s.blit(lab, lab.get_rect(center=c))
        if r.immune > 0 and g.state == "playing":
            # safe from a tag-back: a green ring round the feet with a little label
            gx, gy = P(r.x, r.y)
            pygame.draw.ellipse(s, (90, 220, 90), (gx - 22, gy - 8, 44, 16), 3)
            lab = self.f_tiny.render("Safe!", True, (20, 90, 20))
            bg = pygame.Rect(0, 0, lab.get_width() + 8, lab.get_height())
            bg.midtop = (gx, gy + 9)
            pygame.draw.rect(s, (230, 250, 220), bg, border_radius=6)
            s.blit(lab, (bg.x + 4, bg.y))

    def draw_tag_fx(self, s, fx):
        x, y, age = fx
        gx, gy = P(x, y, 60 + age * 50)
        k = min(1.0, age / 0.12)
        r = 26 + 10 * k
        pts = []
        for i in range(16):
            a = i * math.pi / 8 + age
            rr = r if i % 2 == 0 else r * 0.55
            pts.append((gx + math.cos(a) * rr * 1.3, gy + math.sin(a) * rr))
        alpha = 255 if age < 0.5 else int(255 * (1 - (age - 0.5) / 0.3))
        surf = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        pygame.draw.polygon(surf, (255, 222, 60, alpha), pts)
        pygame.draw.polygon(surf, (200, 60, 30, alpha), pts, 3)
        lab = self.f_mid.render("TAG!", True, (190, 30, 30))
        lab.set_alpha(alpha)
        surf.blit(lab, lab.get_rect(center=(gx, gy)))
        s.blit(surf, (0, 0))

    # -------------------------------------------------------------- drawing: HUD
    def panel(self, s, rect, col=(20, 24, 36), alpha=200, border=(255, 255, 255)):
        p = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(p, (*col, alpha), p.get_rect(), border_radius=12)
        pygame.draw.rect(p, (*border, 120), p.get_rect(), 2, border_radius=12)
        s.blit(p, rect.topleft)

    def text(self, s, font, txt, col, pos, anchor="topleft", shadow=True):
        im = font.render(txt, True, col)
        r = im.get_rect(**{anchor: pos})
        if shadow:
            sh = font.render(txt, True, (0, 0, 0))
            sh.set_alpha(140)
            s.blit(sh, r.move(2, 2))
        s.blit(im, r)
        return r

    def portrait(self, kind, h):
        img = self.chars[kind].big["se" if kind != "robot" else "sw"]
        bb = img.get_bounding_rect()
        head = img.subsurface((bb.x, bb.y, bb.w, min(bb.h, int(bb.w * 1.05)))).copy()
        k = h / head.get_height()
        return pygame.transform.smoothscale(head, (round(head.get_width() * k), h))

    def draw_stars(self, s, won, n, x, cy, right):
        # drawn as polygons: the star characters are missing from some Mac fonts
        r, gap = 10, 24
        for i in range(n):
            cx = (x - r - i * gap) if right else (x + r + i * gap)
            pts = []
            for k in range(10):
                rad = r if k % 2 == 0 else r * 0.45
                a = -math.pi / 2 + k * math.pi / 5
                pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
            filled = (i < won) if not right else (i < won)
            if filled:
                pygame.draw.polygon(s, (255, 210, 70), pts)
            pygame.draw.polygon(s, (255, 210, 70), pts, 2)

    def draw_hud(self, s, g):
        bar = pygame.Rect(10, 8, WIN_W - 20, 66)
        self.panel(s, bar, alpha=190)
        for side, r in ((0, g.p1), (1, g.p2)):
            por = self.portrait(r.kind, 54)
            label = r.name + (" (you)" if not r.ai else "")
            col = (255, 120, 110) if r.it else (230, 236, 250)
            nstars = 2 if g.rounds == 3 else 0
            if side == 0:
                s.blit(por, (bar.x + 10, bar.y + 6))
                x = bar.x + 20 + por.get_width()
                self.text(s, self.f_hud, label, col, (x, bar.y + 6))
                self.text(s, self.f_small, f"It for {fmt_it(r.it_time)}   Tags {r.tags}", (210, 216, 230), (x, bar.y + 36))
                self.draw_stars(s, g.wins[side], nstars, x + 250, bar.y + 17, False)
            else:
                s.blit(por, (bar.right - 10 - por.get_width(), bar.y + 6))
                x = bar.right - 20 - por.get_width()
                self.text(s, self.f_hud, label, col, (x, bar.y + 6), "topright")
                self.text(s, self.f_small, f"It for {fmt_it(r.it_time)}   Tags {r.tags}", (210, 216, 230), (x, bar.y + 36), "topright")
                self.draw_stars(s, g.wins[side], nstars, x - 250, bar.y + 17, True)
        cx = WIN_W // 2
        self.text(s, self.f_small_b, f"TAG  ·  Round {g.round} of {g.rounds}", (190, 200, 220), (cx, bar.y + 4), "midtop")
        tcol = (255, 90, 80) if (g.clock < 10 and g.state == "playing" and int(g.clock * 2) % 2 == 0) else (255, 255, 255)
        self.text(s, self.f_big, fmt(g.clock), tcol, (cx, bar.y + 20), "midtop")
        # who's it banner
        it = g.p1 if g.p1.it else g.p2
        human = g.p1 if not g.p1.ai else None
        if g.state in ("playing", "ready"):
            if human is None:
                msg = f"{it.name} is it!"
                col = (200, 50, 50)
            elif it is human:
                msg = "You're it! Count to 3…" if it.frozen > 0 else f"You're it! Tag {g.p2.name}!"
                col = (200, 40, 44)
            else:
                msg = f"Run! {it.name} is it" + (" and counting…" if it.frozen > 0 else "!")
                col = (40, 100, 190)
            im = self.f_mid.render(msg, True, (255, 255, 255))
            r = pygame.Rect(0, 0, im.get_width() + 36, im.get_height() + 10)
            r.bottomleft = (16, WIN_H - 14)
            pygame.draw.rect(s, shade(col, 0.6), r.move(0, 3), border_radius=18)
            pygame.draw.rect(s, col, r, border_radius=18)
            s.blit(im, im.get_rect(center=r.center))
        if g.state == "ready":
            self.centre_card(s, [(self.f_big, f"Round {g.round}", (255, 230, 120)),
                                 (self.f_mid, "Get ready…", (255, 255, 255))])
        elif g.state == "round_over":
            res = g.round_results[-1]
            w = g.runners[res["winner"]]
            lines = [(self.f_big, f"Round {g.round} to {w.name}!", (255, 230, 120))]
            for i, r in enumerate(g.runners):
                lines.append((self.f_hud, f"{r.name} was it for {fmt_it(res['it'][i])}  ·  {res['tags'][i]} tag{'s' if res['tags'][i] != 1 else ''}", (235, 240, 250)))
            lines.append((self.f_small, f"Press Space for round {g.round + 1}", (190, 200, 220)))
            self.centre_card(s, lines)
        elif g.state == "match_over":
            wi = 0 if g.wins[0] > g.wins[1] else 1
            w = g.runners[wi]
            score = f"{max(g.wins)}–{min(g.wins)}"
            if not g.p1.ai and wi == 0:
                head = f"{w.name} wins the match {score}!"
                sub = "Well played! The robot wants a rematch."
            elif not g.p1.ai:
                head = f"The {w.name} wins {score}"
                sub = "So close! Have another go."
            else:
                head = f"{w.name} wins the match {score}!"
                sub = ""
            lines = [(self.f_big, head, (255, 230, 120))]
            res = g.round_results[-1]
            for i, r in enumerate(g.runners):
                lines.append((self.f_hud, f"{r.name}: it for {fmt_it(res['it'][i])} in the last round", (235, 240, 250)))
            if sub:
                lines.append((self.f_hud, sub, (235, 240, 250)))
            lines.append((self.f_small, "Press Enter for the title screen", (190, 200, 220)))
            self.centre_card(s, lines)

    def centre_card(self, s, lines):
        ims = [f.render(t, True, c) for f, t, c in lines]
        w = max(i.get_width() for i in ims) + 60
        h = sum(i.get_height() + 8 for i in ims) + 34
        r = pygame.Rect(0, 0, w, h)
        r.center = (WIN_W // 2, WIN_H // 2 + 10)
        self.panel(s, r, (16, 20, 34), 215)
        y = r.y + 18
        for im in ims:
            s.blit(im, (r.centerx - im.get_width() // 2, y))
            y += im.get_height() + 8

    # -------------------------------------------------------------- title
    # ---------------------------------------------------------------- spotlight
    SPOT_W, SPOT_H = 172, 48                       # the pool of light, a 2:1-ish iso ellipse

    def spot_surfaces(self, beam_h):
        """Additive (premultiplied) light: a feathered elliptical pool and a soft beam."""
        if getattr(self, "_spot", None) and self._spot[0] == beam_h:
            return self._spot[1], self._spot[2]
        warm = np.array([255, 236, 196], dtype=float)
        w, h = self.SPOT_W, self.SPOT_H
        yy, xx = np.mgrid[0:h, 0:w]
        d = np.sqrt(((xx - (w - 1) / 2) / (w / 2)) ** 2 + ((yy - (h - 1) / 2) / (h / 2)) ** 2)
        a = np.clip(1 - d * d, 0, 1) ** 1.3 * 0.55 + np.clip(1 - d / 0.5, 0, 1) ** 1.5 * 0.3
        pool = pygame.surfarray.make_surface((warm[None, None, :] * a.T[:, :, None]).astype(np.uint8))
        # beam: narrow at the top, as wide as the pool at the bottom, fading upwards
        bw = w
        yy, xx = np.mgrid[0:beam_h, 0:bw]
        v = yy / max(1, beam_h - 1)                          # 0 at the top, 1 at the floor
        half = 16 + (bw / 2 - 22 - 16) * v
        u = np.abs(xx - (bw - 1) / 2) / half
        a = np.clip(1 - u, 0, 1) ** 1.1 * (0.10 + 0.26 * v ** 1.2)
        beam = pygame.surfarray.make_surface((warm[None, None, :] * a.T[:, :, None]).astype(np.uint8))
        self._spot = (beam_h, pool, beam)
        return pool, beam

    def draw_spotlight(self, s, pr, t):
        target = pr.x + 130 + self.sel_char * 190
        last = getattr(self, "_spot_t", None)
        if last is None or not (0 <= t - last < 0.5) or getattr(self, "spot_x", None) is None:
            self.spot_x = float(target)                     # first frame or a jump: snap
        else:
            self.spot_x += (target - self.spot_x) * (1 - math.exp(-(t - last) * 9))
        self._spot_t = t
        floor_y = pr.y + 247
        top = pr.y + 44
        pool, beam = self.spot_surfaces(floor_y - top)
        x = round(self.spot_x)
        flick = 1.0 + 0.03 * math.sin(t * 7.3)            # the faintest shimmer
        s.blit(beam, (x - beam.get_width() // 2, top), special_flags=pygame.BLEND_RGB_ADD)
        p = pool if abs(flick - 1) < 1e-3 else pygame.transform.smoothscale(
            pool, (round(self.SPOT_W * flick), round(self.SPOT_H * flick)))
        s.blit(p, (x - p.get_width() // 2, floor_y - p.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)

    def draw_title(self, s, t):
        # the setting of the chosen game, dimmed
        if self.title_is_bd():
            self.bd_view.draw_world(s, None, t, title=True)
        else:
            self.draw_world(s, [], t)
        shade_s = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        for y in range(WIN_H):
            a = int(170 - 90 * math.sin(min(1, y / WIN_H) * math.pi))
            pygame.draw.line(shade_s, (10, 14, 30, a), (0, y), (WIN_W, y))
        s.blit(shade_s, (0, 0))
        # logo
        title = "COURTYARD"
        x = WIN_W // 2
        cols = [(232, 64, 60), (250, 160, 40), (250, 214, 60), (90, 190, 90), (60, 150, 230), (150, 100, 220)]
        ims = [self.f_logo.render(ch, True, cols[i % len(cols)]) for i, ch in enumerate(title)]
        tw = sum(i.get_width() for i in ims) + 4 * (len(ims) - 1)
        cx = x - tw // 2
        for i, im in enumerate(ims):
            y = 34 + math.sin(t * 3 + i * 0.6) * 5
            sh = self.f_logo.render(title[i], True, (20, 16, 30))
            s.blit(sh, (cx + 5, y + 6))
            out = self.f_logo.render(title[i], True, (255, 255, 255))
            for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                s.blit(out, (cx + ox, y + oy))
            s.blit(im, (cx, y))
            cx += im.get_width() + 4
        self.text(s, self.f_mid, "Playground games for Archie and Holly", (240, 240, 250), (x, 146), "midtop")
        # character choice
        pr = pygame.Rect(0, 0, 640, 300)
        pr.midtop = (x - 150, 200)
        self.panel(s, pr, (16, 20, 36), 200)
        self.text(s, self.f_hud, "Choose your player", (255, 230, 120), (pr.centerx, pr.y + 12), "midtop")
        for i, k in enumerate(PLAYABLE):
            ch = self.chars[k]
            cxp = pr.x + 130 + i * 190
            sel = i == self.sel_char
            if i == 0:
                self.draw_spotlight(s, pr, t)
            img = ch.walk["se"][int(t * 10) % ch.frames] if sel else ch.still["se"]
            img = pygame.transform.smoothscale(img, (round(img.get_width() * 1.5), round(img.get_height() * 1.5)))
            lit = max(0.0, 1 - abs(self.spot_x - cxp) / 120)
            if lit > 0.02:     # lit by the spotlight: a touch brighter and warmer
                img = img.copy()
                img.fill((round(34 * lit), round(28 * lit), round(14 * lit)), special_flags=pygame.BLEND_RGB_ADD)
            ax, ay = ch.anchor["se"]
            s.blit(img, (cxp - ax * 1.5, pr.y + 248 - ay * 1.5))
            self.text(s, self.f_mid, NAMES[k], (255, 255, 255) if sel else (150, 156, 170), (cxp, pr.y + 262), "midtop")
        vx = pr.x + 130 + 2 * 190 + 10
        self.text(s, self.f_big, "vs", (255, 120, 100), (vx - 50, pr.y + 130), "center")
        rch = self.chars["robot"]
        img = rch.still["sw"]
        img = pygame.transform.smoothscale(img, (round(img.get_width() * 1.5), round(img.get_height() * 1.5)))
        ax, ay = rch.anchor["sw"]
        s.blit(img, (vx + 30 - ax * 1.5, pr.y + 248 - ay * 1.5))
        self.text(s, self.f_mid, "Robot", (200, 220, 255), (vx + 30, pr.y + 262), "midtop")
        # games
        gr = pygame.Rect(0, 0, 280, 300)
        gr.topleft = (pr.right + 20, pr.y)
        self.panel(s, gr, (16, 20, 36), 200)
        self.text(s, self.f_hud, "Choose a game", (255, 230, 120), (gr.centerx, gr.y + 12), "midtop")
        for i, (name, ok) in enumerate(GAMES):
            y = gr.y + 56 + i * 58
            sel = i == self.sel_game
            rr = pygame.Rect(gr.x + 18, y, gr.w - 36, 48)
            if sel:
                pygame.draw.rect(s, (60, 80, 140), rr, border_radius=10)
                pygame.draw.rect(s, (255, 220, 80), rr, 2, border_radius=10)
            col = (255, 255, 255) if ok else (130, 136, 150)
            if ok:
                self.text(s, self.f_mid, name, col, (rr.x + 16, rr.centery), "midleft")
            else:
                self.text(s, self.f_hud, name, col, (rr.x + 16, rr.y + 3), "topleft")
                self.text(s, self.f_tiny, "coming soon", (150, 156, 170), (rr.x + 17, rr.bottom - 4), "bottomleft", False)
        # rules + controls
        rr = pygame.Rect(0, 0, 940, 120)
        rr.midtop = (x, pr.bottom + 14)
        self.panel(s, rr, (16, 20, 36), 200)
        if self.title_is_bd():
            lines = ["Batdown: the fielder throws at the bat, the batter hits it away. Bat knocked down or caught on the full: swap!",
                     "Throw from the chalk X where the ball first lands. Rings score 1, 2, 3; the hedge or railings on the full 5. First to 30.",
                     "Bat: Space swing (+Up loft), Left/Right aim  ·  Field: run to the X, Left/Right aim, Up/Down throw, hold Space",
                     "Left/Right choose a player  ·  Up/Down choose a game  ·  Enter or Space to play"]
        else:
            lines = ["Tag: if you're it, touch the other player to tag them. They count to 3 before chasing – no tag-backs!",
                     "Three rounds of a minute. Whoever is it for less time wins the round. Best of three wins the match.",
                     "Controls: Left/Right turn  ·  Up run  ·  Down step back  ·  M music on/off  ·  Esc back",
                     "Left/Right choose a player  ·  Up/Down choose a game  ·  Enter or Space to play"]
        for i, l in enumerate(lines):
            self.text(s, self.f_small_b if i == 3 else self.f_small, l, (255, 230, 120) if i == 3 else (225, 230, 240), (x, rr.y + 12 + i * 25), "midtop", False)

    def draw(self):
        s = self.screen
        if self.state == "title":
            self.draw_title(s, self.t)
        elif self.is_bd:
            self.bd_view.draw_world(s, self.game, self.t)
            self.bd_view.draw_hud(s, self.game, self.t)
        else:
            self.draw_world(s, self.game.runners, self.t, self.game)
            self.draw_hud(s, self.game)

    # -------------------------------------------------------------- main loop
    def run(self):
        self.sound.music(True)
        running = True
        while running:
            dt = min(0.05, self.clock.tick(FPS) / 1000)
            for e in pygame.event.get():
                if not self.handle(e):
                    running = False
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()


# ------------------------------------------------------------------ headless helpers
def selftest(matches=6):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    app = App(sound=False)
    total_tags = 0
    for m in range(matches):
        app.sel_char = m % 2
        app.start_game(player_ai=True, seed=m)
        steps = 0
        while app.state == "play" and app.game.state != "match_over":
            app.update(1 / 30, auto=True)
            if steps % 15 == 0:
                app.draw()
            steps += 1
            assert steps < 30 * 400, "match never ended"
        g = app.game
        tags_ = sum(r["tags"][0] + r["tags"][1] for r in g.round_results)
        total_tags += tags_
        print(f"match {m + 1}: {g.p1.name} v Robot  rounds {g.wins[0]}-{g.wins[1]}  tags {tags_}  "
              + "  ".join(f"[it {a:.0f}s/{b:.0f}s]" for a, b in (r['it'] for r in g.round_results)))
        for r in g.runners:
            assert 0 <= r.x <= N and 0 <= r.y <= N
            assert not app.game.world.blocked(r.x, r.y, tag.RADIUS * 0.95), "ended inside something"
    print("selftest ok, tags", total_tags)


def selftest_batdown(matches=6):
    """AI against AI: every match must finish, by 30 points or the turns running out."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    app = App(sound=False)
    app.sel_game = [n for n, _ in GAMES].index("Batdown")
    tot = {}
    for m in range(matches):
        app.sel_char = m % 2
        app.start_game(player_ai=True, seed=100 + m)
        g = app.game
        steps = 0
        while g.state != "match_over":
            app.update(1 / 30)
            if steps % 20 == 0:
                app.draw()
            steps += 1
            assert steps < 30 * 600, f"match never ended ({g.state}/{g.phase})"
            for r in g.runners:
                assert 0 <= r.x <= N and 0 <= r.y <= N
            b = g.ball
            assert -0.01 <= b.x <= N + 0.01 and -0.01 <= b.y <= N + 0.01 and b.z >= -0.01, "ball escaped"
        assert max(g.p1.score, g.p2.score) >= g.target or all(r.turns >= g.turns for r in g.runners)
        for r in g.runners:
            assert not g.world.blocked(r.x, r.y, tag.RADIUS * 0.9), "ended inside something"
        for k, v in g.stats.items():
            tot[k] = tot.get(k, 0) + v
        w = g.winner.name if g.winner else "draw"
        print(f"batdown {m + 1}: {g.p1.name} {g.p1.score} v Robot {g.p2.score}  turns {g.p1.turns}/{g.p2.turns}  "
              f"{steps / 30:.0f}s  winner {w}  {g.stats}")
    assert tot["hits"] > 0 and tot["bat_down"] > 0 and tot["caught"] > 0, tot
    print("batdown selftest ok", tot)


def mix_audio(log, dur, out_wav, game_from=None):
    """Mix the sound log (and the music) into a wav for the recording."""
    import numpy as np
    SR = 22050
    n = int(dur * SR) + SR
    mixbuf = np.zeros(n)

    def read(path):
        if path.endswith(".ogg"):
            raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                                 capture_output=True).stdout
            return np.frombuffer(raw, np.int16).astype(np.float64) / 32768
        with wave.open(path) as w:
            return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float64) / 32768

    mus = read(os.path.join(SND_DIR, "title_theme.ogg"))
    reps = int(n / len(mus)) + 1
    if game_from is None:
        mixbuf += np.tile(mus, reps)[:n] * MUSIC_VOL
    else:
        # the title theme, then the game music from the moment the game starts (as in the app)
        i = int(game_from * SR)
        mixbuf[:i] += np.tile(mus, reps)[:i] * MUSIC_VOL
        gm = read(os.path.join(SND_DIR, "game_music.ogg"))
        mixbuf[i:] += np.tile(gm, int((n - i) / len(gm)) + 1)[: n - i] * MUSIC_VOL
    cache = {}
    for t, name, vol in log:
        if name not in cache:
            p = os.path.join(SND_DIR, name + ".wav")
            cache[name] = read(p) if os.path.exists(p) else None
        x = cache[name]
        if x is None:
            continue
        i = int(t * SR)
        seg = x[: max(0, n - i)] * SOUND_VOL.get(name, 0.5) * vol
        mixbuf[i:i + len(seg)] += seg
    mixbuf = np.clip(mixbuf / max(1.0, np.abs(mixbuf).max() / 0.95), -1, 1)
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mixbuf[: int(dur * SR)] * 32767).astype(np.int16).tobytes())


def record(out, seconds=28, fps=30):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    app = App(sound=False)
    tmp_v = out + ".video.mp4"
    tmp_a = out + ".wav"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIN_W}x{WIN_H}",
                           "-r", str(fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", tmp_v],
                          stdin=subprocess.PIPE)
    dt = 1 / fps
    frames = int(seconds * fps)
    title_frames = int(3.0 * fps)
    for f in range(frames):
        if f == int(1.6 * fps):
            app.sel_char = 0
        if f < title_frames:
            if f == int(1.2 * fps):
                app.sel_char = 1
                app.sound.play("beep")
            if f == int(2.0 * fps):
                app.sel_char = 0
                app.sound.play("beep")
        if f == title_frames:
            app.sound.play("beep_hi")
            app.start_game(player_ai=True, seed=3, round_s=18)
        app.update(dt, auto=True)
        app.draw()
        ff.stdin.write(pygame.image.tobytes(app.screen, "RGB"))
    ff.stdin.close()
    ff.wait()
    mix_audio(app.sound.log, seconds, tmp_a)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp_v, "-i", tmp_a, "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                    "-shortest", "-movflags", "+faststart", out], check=True)
    os.remove(tmp_v)
    os.remove(tmp_a)
    print("wrote", out)


def record_batdown(out, seconds=28, fps=30, seed=None):
    """A Batdown demo: the title with Batdown picked, then the robot against an AI Archie."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    app = App(sound=False)
    seed = 7 if seed is None else seed
    tmp_v = out + ".video.mp4"
    tmp_a = out + ".wav"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIN_W}x{WIN_H}",
                           "-r", str(fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", tmp_v],
                          stdin=subprocess.PIPE)
    dt = 1 / fps
    frames = int(seconds * fps)
    title_frames = int(3.0 * fps)
    bd = [n for n, _ in GAMES].index("Batdown")
    for f in range(frames):
        if f < title_frames:
            k = f / fps
            for when, idx in ((0.6, 1), (1.1, 2), (1.6, 3)):
                if f == int(when * fps):
                    app.sel_game = idx
                    app.sound.play("beep")
        if f == title_frames:
            app.sound.play("beep_hi")
            app.start_game(player_ai=True, seed=seed)
            app.game.state_t = 1.6          # a shorter toss card for the demo
        app.update(dt, auto=True)
        app.draw()
        ff.stdin.write(pygame.image.tobytes(app.screen, "RGB"))
    ff.stdin.close()
    ff.wait()
    mix_audio(app.sound.log, seconds, tmp_a, game_from=title_frames / fps)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp_v, "-i", tmp_a, "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                    "-shortest", "-movflags", "+faststart", out], check=True)
    os.remove(tmp_v)
    os.remove(tmp_a)
    print("wrote", out, "stats", app.game.stats, "score", app.game.p1.score, app.game.p2.score)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        selftest_batdown()
    elif "--selftest-batdown" in sys.argv:
        selftest_batdown()
    elif "--record-batdown" in sys.argv:
        i = sys.argv.index("--record-batdown")
        seed = int(sys.argv[i + 2]) if len(sys.argv) > i + 2 else None
        record_batdown(sys.argv[i + 1], seed=seed)
    elif "--record" in sys.argv:
        record(sys.argv[sys.argv.index("--record") + 1])
    elif "--shots-batdown" in sys.argv:
        import shots
        shots.batdown(sys.argv[sys.argv.index("--shots-batdown") + 1])
    elif "--shots" in sys.argv:
        import shots
        shots.main(sys.argv[sys.argv.index("--shots") + 1])
    else:
        App().run()
