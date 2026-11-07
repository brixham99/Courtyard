"""Courtyard: playground games for Archie and Holly, on one isometric screen.

Games: Tag (hands only) in the village school courtyard, Batdown
(throw the ball at the bat, the batter hits it away) in the park, and
Basketball (one on one, a hoop at each end) on a city street court, and
Football (one on one, a goal at each end) in a mini stadium beside a farmers
market, each against the computer's robot.

    python game.py              play
    python game.py --shots DIR  write screenshots (headless is fine)
    python game.py --record OUT.mp4   record an AI-vs-AI demo video with sound
    python game.py --selftest   run several matches of both games' logic and exit
    python game.py --record-batdown OUT.mp4   the same for Batdown
    python game.py --record-basketball OUT.mp4   the same for Basketball
    python game.py --selftest-basketball / --shots-basketball DIR
    python game.py --record-football OUT.mp4 [seed]   the same for Football
    python game.py --selftest-football / --shots-football DIR

Controls (tank-style, as in Daleks in Hedges and Haunted Mansion):
    Left/Right (A/D)  turn a quarter turn      Up (W)  run forwards
    Down (S)          step backwards           M  music on/off   Esc  back/quit
Batdown, batting:   Space swing (hold Up as you swing to loft it), Left/Right aim left/straight/right
Batdown, fielding:  run as above; on the chalk X: Left/Right aim, Up/Down throw type,
                    hold Space for power and let go to throw
Basketball:         run with the ball to dribble; hold Space and let go with the meter
                    in the green to shoot; without the ball, Space swipes for a steal
                    or jumps to block
Football:           run into the ball to dribble; hold Space and let go with the meter
                    in the green to shoot (too much and it balloons over); without the
                    ball, Space slide-tackles, or dives when a shot is coming at your goal

A gamepad (Xbox or PlayStation, SDL GameController) does the same jobs when it
is plugged in: stick or D-pad to move, A/Cross to confirm and to do the main
action, B/Circle to go back, Y/Triangle for the music, Start/Options to pause.
Hold Back/Share for about a second to quit. Prompts switch to the pad's buttons
while one is connected, and stay on the keyboard otherwise.

Full-screen:  ZENSTATION=1, or --fullscreen. The picture is still drawn at
1280×720 and scaled to the television, with bars if the screen is not 16:9.
"""
import json
import math
import os
import random
import subprocess
import sys
import wave

import numpy as np
import pygame
import aa

import basketball
import basketball_view
import football
import football_view
import batdown
import batdown_view
import pads as pads_mod
import scene
import screenmode
import tag
from iso import WIN_W, WIN_H, N, P, SHADOW_K, mix, shade

HERE = os.path.dirname(os.path.abspath(__file__))
CH_DIR = os.path.join(HERE, "assets", "characters")
SND_DIR = os.path.join(HERE, "assets", "sounds")
FPS = 60
CH_SCALE = {"archie": 0.68, "holly": 0.68, "robot": 0.66}
NAMES = {"archie": "Archie", "holly": "Holly", "robot": "Robot"}
PLAYABLE = ("archie", "holly")
GAMES = (("Tag", True), ("Football", True), ("Basketball", True), ("Batdown", True))
TURN_KEYS = {pygame.K_LEFT: -1, pygame.K_a: -1, pygame.K_RIGHT: 1, pygame.K_d: 1}
MOVE_KEYS = {pygame.K_UP: 1, pygame.K_w: 1, pygame.K_DOWN: -1, pygame.K_s: -1}
GO_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
# balanced by ear-loudness (RMS): the whistle and the robot's square-wave beeps sat ~6-10 dB above the rest
SOUND_VOL = {"whistle": 0.32, "whistle_long": 0.32, "slap": 0.8, "boing": 0.5, "beep": 0.25, "beep_hi": 0.28,
             "step1": 0.2, "step2": 0.2, "step3": 0.2, "rstep1": 0.22, "rstep2": 0.22, "rstep3": 0.22,
             "robot_happy": 0.3, "robot_sad": 0.3, "cheer": 0.7,
             "thock": 0.75, "clatter": 0.7, "pock": 0.35,
             "bounce": 0.5, "swish": 0.75, "clank": 0.55, "backboard": 0.6,
             "kick": 0.7, "post": 0.6, "net": 0.6, "board": 0.5, "crowd_cheer": 0.5, "crowd_groan": 0.45}
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
    def __init__(self, sound=True, fullscreen=False, display_size=None):
        pygame.init()
        pygame.display.set_caption("Courtyard")
        self.display = screenmode.Display(fullscreen, display_size)
        self.screen = self.display.canvas          # always the internal 1280×720 frame
        self.fullscreen = bool(fullscreen)
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
        aa.ellipse(self.contact, (20, 22, 14, 90), self.contact.get_rect())
        self.chars = {k: Character(k) for k in ("archie", "holly", "robot")}
        self.scenes = {}
        self.bd_view = batdown_view.BatdownView(self)
        self.bb_view = basketball_view.BasketballView(self)
        self.fb_view = football_view.FootballView(self)
        self.sound = Sound(sound)
        self.state = "title"
        self.sel_char = 0
        self.sel_game = 0
        self.t = 0.0
        self.game = None
        self.held_turn = []
        self.held_move = []
        self.step_phase = {}
        self.pads = pads_mod.Pads()
        self.paused = False
        self.pad_turn = 0
        self.pad_move = 0
        self._leave = False
        self._rep_axis = None
        self._rep_t = 0.0
        self._rep_count = 0
        self.name_entry = None

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

    @property
    def is_bb(self):
        return isinstance(self.game, basketball.BasketballGame)

    def title_is_bb(self):
        return GAMES[self.sel_game][0] == "Basketball"

    @property
    def is_fb(self):
        return isinstance(self.game, football.FootballGame)

    def title_is_fb(self):
        return GAMES[self.sel_game][0] == "Football"

    # -------------------------------------------------------------- flow
    def start_game(self, player_ai=False, seed=None, round_s=tag.ROUND_S, **bd):
        k = PLAYABLE[self.sel_char]
        if self.title_is_bb():
            self.game = basketball.BasketballGame(k, NAMES[k], player_ai=player_ai, seed=seed, **bd)
        elif self.title_is_fb():
            self.game = football.FootballGame(k, NAMES[k], player_ai=player_ai, seed=seed, **bd)
        elif self.title_is_bd():
            self.game = batdown.BatdownGame(k, NAMES[k], player_ai=player_ai, seed=seed,
                                            obstacles=self.scene("park")["obstacles"], **bd)
        else:
            self.game = tag.TagGame(k, NAMES[k], player_ai=player_ai, seed=seed, obstacles=self.obstacles, round_s=round_s)
        self.state = "play"
        self.sound.set_track("game")
        self.step_phase = {}
        self.confetti_t0 = None
        self.held_turn, self.held_move = [], []

    def human_controls(self):
        turn = TURN_KEYS[self.held_turn[-1]] if self.held_turn else 0
        move = MOVE_KEYS[self.held_move[-1]] if self.held_move else 0
        # A stick at rest must not cancel keys that are still held.
        if self.pad_turn:
            turn = self.pad_turn
        if self.pad_move:
            move = self.pad_move
        return turn, move

    def handle(self, e):
        if e.type == pygame.QUIT:
            return False
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_m:
                self.sound.music(not self.sound.music_on)
            if self.state == "name" and self.name_entry is not None:
                return self.handle_name_key(e)
            # Paused: Space/Enter resumes, Esc still leaves for the title. Other new
            # presses wait, so a pause does not also shoot. Key-ups still fall through.
            if self.paused and e.key != pygame.K_ESCAPE:
                if e.key in GO_KEYS:
                    self.paused = False
                return True
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
                    self.paused = False
                    self.state = "title"
                    self.sound.set_track("title")
                    return True
                if e.key in TURN_KEYS and e.key not in self.held_turn:
                    self.held_turn.append(e.key)
                if e.key in MOVE_KEYS and e.key not in self.held_move:
                    self.held_move.append(e.key)
                if (self.is_bb or self.is_fb) and e.key == pygame.K_SPACE:
                    self.game.press("space")
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
            if self.state == "play" and (self.is_bb or self.is_fb) and e.key == pygame.K_SPACE:
                self.game.press("space_up")
            if e.key in self.held_turn:
                self.held_turn.remove(e.key)
            if e.key in self.held_move:
                self.held_move.remove(e.key)
        return True

    def handle_name_key(self, e):
        """Arrow keys edit a name the same way a pad does. Enter or Space accepts, Esc cancels."""
        ne = self.name_entry
        if e.type != pygame.KEYDOWN or ne is None:
            return True
        if e.key in (pygame.K_LEFT, pygame.K_a):
            ne.move(-1)
        elif e.key in (pygame.K_RIGHT, pygame.K_d):
            ne.move(1)
        elif e.key in (pygame.K_UP, pygame.K_w):
            ne.cycle(1)
        elif e.key in (pygame.K_DOWN, pygame.K_s):
            ne.cycle(-1)
        elif e.key in GO_KEYS:
            ne.accept()
        elif e.key == pygame.K_ESCAPE:
            ne.back()
        if ne.done or ne.cancelled:
            self.state = "title"
        return True

    def bd_held(self):
        h = set()
        if any(MOVE_KEYS[k] > 0 for k in self.held_move):
            h.add("up")
        if self.pad_move > 0:
            h.add("up")
        return h

    def synth(self, key, down):
        """Feed one key through the keyboard path, so a pad does what that key does."""
        et = pygame.KEYDOWN if down else pygame.KEYUP
        ok = self.handle(pygame.event.Event(et, key=key, mod=0, unicode="", scancode=0))
        if ok is False:
            self._leave = True
        return ok

    def on_direction(self, name):
        if self.state == "name" and self.name_entry is not None:
            ne = self.name_entry
            if name in ("left", "right"):
                ne.move(-1 if name == "left" else 1)
            else:
                ne.cycle(1 if name == "up" else -1)
            if ne.done or ne.cancelled:
                self.state = "title"
            return
        if self.state == "title":
            if name in ("left", "right"):
                self.sel_char = (self.sel_char + (-1 if name == "left" else 1)) % len(PLAYABLE)
                self.sound.play("beep")
            else:
                self.sel_game = (self.sel_game + (-1 if name == "up" else 1)) % len(GAMES)
                self.sound.play("beep")
        elif self.state == "play" and self.is_bd:
            self.game.press(name, self.bd_held())

    def on_pad_down(self, name):
        if self.state == "name" and self.name_entry is not None:
            ne = self.name_entry
            if name == "a" or name == "start":
                ne.accept()
            elif name == "b":
                ne.back()
            elif name == "y":
                self.synth(pygame.K_m, True)
            if ne.done or ne.cancelled:
                self.state = "title"
            return
        if self.paused:
            if name in ("a", "start"):
                self.paused = False
            elif name == "b":
                self.synth(pygame.K_ESCAPE, True)
            elif name == "y":
                self.synth(pygame.K_m, True)
            return
        if name == "a":
            self.synth(pygame.K_SPACE, True)
        elif name == "b":
            self.synth(pygame.K_ESCAPE, True)
        elif name == "y":
            self.synth(pygame.K_m, True)
        elif name == "start":
            self.on_start()
        elif name == "x":
            self.on_x()

    def on_pad_up(self, name):
        if name == "a" and self.state == "play":
            self.synth(pygame.K_SPACE, False)

    def on_start(self):
        """Start confirms on the title and the win screen, and pauses a game that is under way."""
        if self.state == "title":
            self.synth(pygame.K_RETURN, True)
            return
        if self.state == "play" and self.game is not None and self.game.state == "match_over":
            self.synth(pygame.K_RETURN, True)
            return
        if self.state == "play":
            self.paused = not self.paused

    def on_x(self):
        """Square / X lofts the bat in Batdown. Everywhere else it has no job."""
        if self.state != "play" or not self.is_bd or self.game is None or self.paused:
            return
        g = self.game
        if g.p1 is g.batter and not g.p1.ai:
            g.press("space", {"up"})

    def _repeat_menu(self, dt, inp):
        """Hold the stick on the title (or a name) and it keeps stepping. Keys do not repeat."""
        if self.state not in ("title", "name"):
            self._rep_axis = None
            self._rep_t = 0.0
            self._rep_count = 0
            return
        axis = ("h", inp.turn) if inp.turn else (("v", inp.move) if inp.move else None)
        if axis != self._rep_axis:
            self._rep_axis = axis
            self._rep_t = 0.0
            self._rep_count = 0
            return
        if axis is None:
            return
        self._rep_t += dt
        gap = 0.42 if self._rep_count == 0 else 0.17
        if self._rep_t >= gap:
            self._rep_t = 0.0
            self._rep_count += 1
            if axis[0] == "h":
                self.on_direction("left" if axis[1] < 0 else "right")
            else:
                self.on_direction("up" if axis[1] > 0 else "down")

    def apply_pads(self, dt):
        inp = self.pads.player(0)
        old_turn, old_move = self.pad_turn, self.pad_move
        move = inp.move
        if not move and getattr(inp, "forward", False) and self.state == "play":
            move = 1                       # right trigger: forwards, like Up
        self.pad_turn, self.pad_move = inp.turn, move
        if self.paused:
            for name in inp.down:
                self.on_pad_down(name)
            for name in inp.up:
                self.on_pad_up(name)
            return
        if inp.turn != old_turn and inp.turn:
            self.on_direction("left" if inp.turn < 0 else "right")
        if move != old_move and move:
            self.on_direction("up" if move > 0 else "down")
        self._repeat_menu(dt, inp)
        for name in inp.down:
            self.on_pad_down(name)
        for name in inp.up:
            self.on_pad_up(name)

    def update(self, dt, auto=False):
        if self.paused:
            return
        self.t += dt
        self.sound.t = self.t
        if self.state != "play":
            return
        g = self.game
        if g.state == "match_over" and getattr(self, "confetti_t0", None) is None and self.player_won(g):
            self.confetti_t0 = self.t
        if self.is_bd:
            self.update_bd(dt)
            return
        if self.is_bb:
            self.update_bb(dt)
            return
        if self.is_fb:
            self.update_fb(dt)
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
                else:
                    self.sound.play("robot_happy")
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

    def update_bb(self, dt):
        g = self.game
        last_clock = g.shot_clock
        g.update(dt, self.human_controls())
        snd = self.sound.play
        for kind, data in g.events:
            if kind in ("whistle", "whistle_short"):
                snd("whistle", 1.0 if kind == "whistle" else 0.6)
            elif kind == "bounce":
                snd("bounce", 0.35 + 0.65 * data)
            elif kind == "fence":
                snd("clank", 0.25 * data + 0.1)
            elif kind == "clank":
                snd("clank", data)
            elif kind == "board":
                snd("backboard", 0.4 + 0.6 * data)
            elif kind == "swish":
                snd("swish", data)
            elif kind == "score":
                r, pts, clean = data
                snd("beep_hi", 0.8)
                if r.kind == "robot":
                    snd("robot_happy")
                elif not r.ai:
                    snd("cheer", 0.7 if pts == 2 else 1.0)
            elif kind == "steal":
                snd("slap", 0.7)
                if data[0].kind == "robot":
                    snd("robot_happy", 0.7)
            elif kind == "block":
                snd("slap", 0.9)
                snd("boing", 0.5)
            elif kind == "swipe":
                snd("boing", 0.2)
            elif kind == "shot":
                snd("pock", 0.3)
            elif kind == "catch":
                snd("pock", 0.4)
            elif kind == "shot_clock":
                snd("whistle", 0.8)
            elif kind == "match_over":
                snd("whistle_long")
                if data is not None and data.kind != "robot" and not data.ai:
                    snd("cheer")
                elif data is not None and data.kind == "robot":
                    snd("robot_happy")
        g.events.clear()
        # the last three seconds of the shot clock tick
        if g.state == "play" and g.holder is not None:
            if math.ceil(g.shot_clock) != math.ceil(last_clock) and g.shot_clock < 3.0:
                snd("beep", 0.5)
        for r in g.runners:
            ch = self.chars[r.kind]
            if r.moved > 0:
                c = int(r.walk_phase / ch.cycle * 2)
                if self.step_phase.get(id(r)) != c:
                    self.step_phase[id(r)] = c
                    base = "rstep" if r.kind == "robot" else "step"
                    snd(f"{base}{c % 3 + 1}", 0.6)

    def update_fb(self, dt):
        g = self.game
        g.update(dt, self.human_controls())
        snd = self.sound.play
        for kind, data in g.events:
            if kind == "whistle":
                snd("whistle", 0.9)
            elif kind == "kick":
                snd("kick", 0.45 + 0.55 * data[1])
            elif kind == "touch":
                snd("kick", 0.12)
            elif kind == "trap":
                snd("kick", 0.2)
            elif kind == "bounce":
                if data > 0.15:
                    snd("kick", 0.1 + 0.25 * data)
            elif kind == "board":
                snd("board", 0.3 + 0.7 * data)
            elif kind == "post":
                snd("post", data)
            elif kind == "net":
                snd("net", data)
            elif kind == "goal":
                r = data[0]
                snd("whistle", 0.6)
                if football.CROWD:
                    snd("crowd_cheer", 1.0)
                if r.kind == "robot":
                    snd("robot_happy", 0.8)
            elif kind == "groan":
                if football.CROWD:
                    snd("crowd_groan", data)
            elif kind == "save":
                snd("slap", 0.8)
            elif kind == "tackle":
                snd("slap", 0.6)
                if data[0].kind == "robot":
                    snd("robot_happy", 0.6)
            elif kind in ("slide", "dive"):
                snd("swish", 0.3)
            elif kind == "match_over":
                snd("whistle_long")
                if football.CROWD:
                    snd("crowd_cheer", 0.8)
                if data is not None and data.kind != "robot" and not data.ai:
                    snd("cheer")
                elif data is not None and data.kind == "robot":
                    snd("robot_happy")
        g.events.clear()
        for r in g.runners:
            ch = self.chars[r.kind]
            if r.moved > 0 and r.slide_t is None and r.dive_t is None:
                c = int(r.walk_phase / ch.cycle * 2)
                if self.step_phase.get(id(r)) != c:
                    self.step_phase[id(r)] = c
                    base = "rstep" if r.kind == "robot" else "step"
                    snd(f"{base}{c % 3 + 1}", 0.5)

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
        scene.draw_clock_hands(s)          # the clock tower keeps the computer's time
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
            aa.polygon(s, (220, 40, 44), [(cx - 7, box.bottom), (cx + 7, box.bottom), (cx, box.bottom + 8)])
            badge_y = box.centery
        if r.frozen > 0 and g.state == "playing":
            n = math.ceil(r.frozen / 0.5)
            frac = (r.frozen % 0.5) / 0.5
            c = (cx + 44, badge_y)
            aa.circle(s, (255, 255, 255), c, 16)
            aa.circle(s, (40, 40, 60), c, 16, 2)
            if frac > 0:
                aa.arc(s, (230, 60, 60), (c[0] - 16, c[1] - 16, 32, 32), math.pi / 2, math.pi / 2 + 2 * math.pi * frac, 4)
            lab = self.f_hud.render(str(min(3, n)), True, (40, 40, 60))
            s.blit(lab, lab.get_rect(center=c))
        if r.immune > 0 and g.state == "playing":
            # safe from a tag-back: a green ring round the feet with a little label
            gx, gy = P(r.x, r.y)
            aa.ellipse(s, (90, 220, 90), (gx - 22, gy - 8, 44, 16), 3)
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
        aa.polygon(surf, (255, 222, 60, alpha), pts)
        aa.polygon(surf, (200, 60, 30, alpha), pts, 3)
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
                aa.polygon(s, (255, 210, 70), pts)
            aa.polygon(s, (255, 210, 70), pts, 2)

    def draw_hud(self, s, g):
        bar = pygame.Rect(10, 8, WIN_W - 20, 66)
        self.panel(s, bar, alpha=228)
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
            lines.append((self.f_small, self.next_round_line(g.round + 1), (190, 200, 220)))
            self.centre_card(s, lines)
        elif g.state == "match_over":
            wi = 0 if g.wins[0] > g.wins[1] else 1
            w = g.runners[wi]
            score = f"{max(g.wins)}–{min(g.wins)}"
            if not g.p1.ai and wi == 0:
                head = f"{w.name} wins the match {score}!"
                sub = "Well played! The Robot wants a rematch."
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
            lines.append((self.f_small, self.enter_title_line(), (190, 200, 220)))
            self.centre_card(s, lines)

    def using_pad(self):
        return self.pads.connected

    def enter_title_line(self):
        if self.using_pad():
            return f"Press {self.pads.hints.action} for the title screen"
        return "Press Enter for the title screen"

    def next_round_line(self, n):
        if self.using_pad():
            return f"Press {self.pads.hints.action} for round {n}"
        return f"Press Space for round {n}"

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
        if self.title_is_bb():
            self.bb_view.draw_world(s, None, t, title=True)
        elif self.title_is_fb():
            self.fb_view.draw_world(s, None, t, title=True)
        elif self.title_is_bd():
            self.bd_view.draw_world(s, None, t, title=True)
        else:
            self.draw_world(s, [], t)
        shade_s = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        for y in range(WIN_H):
            a = int(170 - 90 * math.sin(min(1, y / WIN_H) * math.pi))
            aa.line(shade_s, (10, 14, 30, a), (0, y), (WIN_W, y))
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
        self.text(s, self.f_mid, "Traditional Playground Games", (240, 240, 250), (x, 146), "midtop")
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
        lines = self.title_lines()
        # one size for the three rules lines: the largest that keeps them all inside the panel with padding
        room = rr.w - 2 * 24
        f = self.f_small
        for size in (17, 16, 15, 14, 13):
            f = self.rules_font(size)
            if all(f.size(l)[0] <= room for l in lines[:3]):
                break
        nav_font = self.f_small_b
        if nav_font.size(lines[3])[0] > room:
            nav_font = f
        for i, l in enumerate(lines):
            self.text(s, nav_font if i == 3 else f, l, (255, 230, 120) if i == 3 else (225, 230, 240), (x, rr.y + 12 + i * 25), "midtop", False)
        if self.using_pad():
            self.text(s, self.f_tiny, f"Hold {self.pads.hints.quit} to quit", (170, 176, 190),
                      (WIN_W - 16, WIN_H - 8), "bottomright", False)

    def title_lines(self):
        """The four lines under the title. With no pad these are the keyboard lines, unchanged."""
        h = self.pads.hints
        if self.title_is_bb():
            rules = ["Basketball: one on one, a hoop at each end. Dribble as you run; steal it or block the shot to win it back.",
                     "Hold Space and let go with the meter in the green to shoot. 2 points a basket, 3 from beyond the arc. First to 21.",
                     "Controls: Left/Right turn  ·  Up run  ·  Down step back  ·  Space shoot / swipe / jump  ·  M music  ·  Esc back"]
            if h.pad:
                rules[1] = f"Hold {h.action} and let go with the meter in the green to shoot. 2 points a basket, 3 from beyond the arc. First to 21."
                rules[2] = (f"Stick or D-pad: turn and run  ·  {h.action} shoot, swipe or jump  ·  "
                            f"{h.music} music  ·  {h.back} back  ·  {h.pause} pause")
        elif self.title_is_fb():
            rules = ["Football: one on one, a goal at each end. Run into the ball to dribble; slide in to tackle. Who concedes kicks off.",
                     "Hold Space and let go with the meter in the green to shoot – too hard and it flies over. Dive to save. First to 5.",
                     "Controls: Left/Right turn  ·  Up run  ·  Down step back  ·  Space shoot / tackle / dive  ·  M music  ·  Esc back"]
            if h.pad:
                rules[1] = (f"Hold {h.action} and let go with the meter in the green to shoot – too hard and it flies over. "
                            f"Dive to save. First to 5.")
                rules[2] = (f"Stick or D-pad: turn and run  ·  {h.action} shoot, tackle or dive  ·  "
                            f"{h.music} music  ·  {h.back} back  ·  {h.pause} pause")
        elif self.title_is_bd():
            rules = ["Batdown: the fielder throws at the bat, the batter hits it away. Bat knocked down or caught on the full: swap!",
                     "Throw from the chalk X where the ball first lands. Rings score 1, 2, 3; the hedge or railings on the full 5. First to 30.",
                     "Bat: Space swing (+Up loft), Left/Right aim  ·  Field: run to the X, Left/Right aim, Up/Down throw, hold Space"]
            if h.pad:
                rules[2] = (f"Bat: {h.action} swing (hold up or {h.extra} to loft), stick aims  ·  "
                            f"Field: run to the X, stick aims, up/down throw, hold {h.action}")
        else:
            rules = ["Tag: if you're it, touch the other player to tag them. They count to 3 before chasing – no tag-backs!",
                     "Three rounds of a minute. Whoever is it for less time wins the round. Best of three wins the match.",
                     "Controls: Left/Right turn  ·  Up run  ·  Down step back  ·  M music on/off  ·  Esc back"]
            if h.pad:
                rules[2] = (f"Stick or D-pad: turn and run  ·  {h.music} music on/off  ·  "
                            f"{h.back} back  ·  {h.pause} pause")
        if h.pad:
            nav = f"Left and right choose a player  ·  up and down choose a game  ·  {h.action} to play"
        else:
            nav = "Left/Right choose a player  ·  Up/Down choose a game  ·  Enter or Space to play"
        return rules + [nav]

    def rules_font(self, size):
        if not hasattr(self, "_rules_fonts"):
            self._rules_fonts = {17: self.f_small}
        if size not in self._rules_fonts:
            self._rules_fonts[size] = load_font(size)
        return self._rules_fonts[size]

    @staticmethod
    def player_won(g):
        """Did Archie or Holly (player one) win the match?"""
        if g.p1.kind == "robot":
            return False
        if hasattr(g, "wins"):                  # Tag: best of three rounds
            return g.wins[0] > g.wins[1]
        return getattr(g, "winner", None) is g.p1

    CONFETTI = ((236, 64, 72), (255, 196, 40), (64, 170, 240), (90, 200, 100), (250, 250, 250), (255, 120, 200))

    def draw_confetti(self, s):
        """A shower of paper confetti when you beat the Robot (about 8 seconds)."""
        t0 = getattr(self, "confetti_t0", None)
        if t0 is None or self.state != "play" or self.game.state != "match_over":
            return
        el = self.t - t0
        if el > 9.0:
            return
        rng = random.Random(7)
        for i in range(160):
            delay = rng.uniform(0, 4.0)
            x0 = rng.uniform(-20, WIN_W + 20)
            v = rng.uniform(120, 230)
            amp, fq, ph = rng.uniform(8, 26), rng.uniform(1.2, 2.6), rng.uniform(0, 6.3)
            spin, rot = rng.uniform(4, 9), rng.uniform(0, 3.14)
            col = self.CONFETTI[i % len(self.CONFETTI)]
            tt = el - delay
            if tt < 0:
                continue
            y = -16 + v * tt
            if y > WIN_H + 16:
                continue
            x = x0 + amp * math.sin(fq * tt + ph)
            a = rot + 1.3 * math.sin(fq * tt + ph)
            hw = 6 * abs(math.cos(spin * tt)) + 0.9          # flipping over as it falls
            hh = 4.0
            ca, sa = math.cos(a), math.sin(a)
            pts = [(x + ca * dx - sa * dy, y + sa * dx + ca * dy) for dx, dy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]
            aa.polygon(s, shade(col, 0.75 + 0.25 * abs(math.cos(spin * tt))), pts)

    def draw_pause(self, s):
        dim = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        dim.fill((8, 10, 20, 150))
        s.blit(dim, (0, 0))
        h = self.pads.hints
        if h.pad:
            sub = f"{h.action} resume  ·  {h.back} title screen  ·  hold {h.quit} to quit"
        else:
            sub = "Space resume  ·  Esc title screen"
        self.centre_card(s, [(self.f_big, "Paused", (255, 230, 120)),
                             (self.f_hud, sub, (225, 230, 240))])

    def draw_name(self, s):
        s.fill((16, 20, 36))
        ne = self.name_entry
        h = self.pads.hints
        shown = []
        for i, ch in enumerate(ne.slots):
            shown.append(ch if ch != " " else "·")
        word = " ".join(shown)
        if h.pad:
            hint = f"Up and down change the letter  ·  left and right move  ·  {h.action} accepts  ·  {h.back} cancels"
        else:
            hint = "Up and down change the letter  ·  left and right move  ·  Enter accepts  ·  Esc cancels"
        self.centre_card(s, [(self.f_hud, "Your name", (255, 230, 120)),
                             (self.f_big, word, (255, 255, 255)),
                             (self.f_small, hint, (210, 216, 230)),
                             (self.f_tiny, f"letter {ne.i + 1} of {ne.length}", (190, 200, 220))])

    def draw(self):
        s = self.screen
        if self.state == "name" and self.name_entry is not None:
            self.draw_name(s)
            return
        if self.state == "title":
            self.draw_title(s, self.t)
        elif self.is_bd:
            self.bd_view.draw_world(s, self.game, self.t)
            self.draw_confetti(s)
            self.bd_view.draw_hud(s, self.game, self.t)
        elif self.is_bb:
            self.bb_view.draw_world(s, self.game, self.t)
            self.draw_confetti(s)
            self.bb_view.draw_hud(s, self.game, self.t)
        elif self.is_fb:
            self.fb_view.draw_world(s, self.game, self.t)
            self.draw_confetti(s)
            self.fb_view.draw_hud(s, self.game, self.t)
        else:
            self.draw_world(s, self.game.runners, self.t, self.game)
            self.draw_confetti(s)
            self.draw_hud(s, self.game)
        if self.paused:
            self.draw_pause(s)

    # -------------------------------------------------------------- main loop
    def frame(self, dt, events=None):
        """One frame. Returns False when the game should close (exit code 0)."""
        self._leave = False
        if events is None:
            events = pygame.event.get()
        self.pads.poll(dt)
        if self.pads.quit_requested:
            return False
        for e in events:
            if not self.handle(e):
                return False
        self.apply_pads(dt)
        if self._leave:
            return False
        self.update(dt)
        self.draw()
        self.display.present()
        return True

    def run(self):
        self.sound.music(True)
        running = True
        try:
            while running:
                dt = min(0.05, self.clock.tick(FPS) / 1000.0)
                running = self.frame(dt)
        finally:
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


def selftest_basketball(matches=6):
    """AI against AI: every match must reach 21, with baskets at both ends."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    app = App(sound=False)
    app.sel_game = [n for n, _ in GAMES].index("Basketball")
    tot = {}
    for m in range(matches):
        app.sel_char = m % 2
        app.start_game(player_ai=True, seed=200 + m)
        g = app.game
        steps = 0
        while g.state != "match_over":
            app.update(1 / 30)
            if steps % 20 == 0:
                app.draw()
            steps += 1
            assert steps < 30 * 900, f"match never ended ({g.state})"
            for r in g.runners:
                assert 0 <= r.x <= N and 0 <= r.y <= N
            b = g.ball
            assert -0.01 <= b.x <= N + 0.01 and -0.01 <= b.y <= N + 0.01 and b.z >= -0.01, "ball escaped"
        assert max(g.p1.score, g.p2.score) >= g.target
        for r in g.runners:
            assert not g.world.blocked(r.x, r.y, tag.RADIUS * 0.9), "ended inside something"
            assert r.made2 + r.made3 > 0, f"{r.name} never scored"
        for k, v in g.stats.items():
            tot[k] = tot.get(k, 0) + v
        w = g.winner.name if g.winner else "draw"
        print(f"basketball {m + 1}: {g.p1.name} {g.p1.score} v Robot {g.p2.score}  {steps / 30:.0f}s  winner {w}  {g.stats}")
    assert tot["made"] > 0 and tot["threes"] > 0 and tot["steals"] > 0 and tot["blocks"] > 0, tot
    # the street: ten minutes at 60 steps a second, and no two vehicles ever share screen space
    import traffic
    n, kinds, longest = traffic.check_no_clash(600.0, 1 / 60)
    assert kinds == {"bus", "cab"} and n >= 30, (n, kinds)
    assert longest < 16, f"the street was empty for {longest:.1f}s"
    print(f"traffic ok: {n} vehicles in 10 minutes, never more than one in view, longest empty spell {longest:.1f}s")
    print("basketball selftest ok", tot)


def selftest_football(matches=6):
    """AI against AI: every match must reach the target, with goals at both ends."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    app = App(sound=False)
    app.sel_game = [n for n, _ in GAMES].index("Football")
    tot = {}
    ends = set()
    for m in range(matches):
        app.sel_char = m % 2
        app.start_game(player_ai=True, seed=300 + m)
        g = app.game
        steps = 0
        while g.state != "match_over":
            app.update(1 / 30)
            if steps % 20 == 0:
                app.draw()
            if g.state == "goal" and g.last_goal:
                ends.add(g.last_goal[1].name)
            steps += 1
            assert steps < 30 * 900, f"match never ended ({g.state})"
            for r in g.runners:
                assert 0 <= r.x <= N and 0 <= r.y <= N
            b = g.ball
            assert -1.2 <= b.x <= N + 1.2 and -0.01 <= b.y <= N + 0.01 and b.z >= -0.01, "ball escaped"
        if g.last_goal:
            ends.add(g.last_goal[1].name)
        assert max(g.p1.score, g.p2.score) >= g.target
        for k, v in g.stats.items():
            tot[k] = tot.get(k, 0) + v
        w = g.winner.name if g.winner else "draw"
        print(f"football {m + 1}: {g.p1.name} {g.p1.score} v Robot {g.p2.score}  {steps / 30:.0f}s  winner {w}  {g.stats}")
    assert len(ends) == 2, f"goals only at {ends}"
    assert tot["goals"] > 0 and tot["saves"] > 0 and tot["won"] > 0, tot
    print("football selftest ok", tot)


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
    seed = 55 if seed is None else seed
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


def record_basketball(out, seconds=28, fps=30, seed=None):
    """A Basketball demo: the title with Basketball picked, then the robot against an AI Holly."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    app = App(sound=False)
    seed = 5 if seed is None else seed
    tmp_v = out + ".video.mp4"
    tmp_a = out + ".wav"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIN_W}x{WIN_H}",
                           "-r", str(fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", tmp_v],
                          stdin=subprocess.PIPE)
    dt = 1 / fps
    frames = int(seconds * fps)
    title_frames = int(3.0 * fps)
    for f in range(frames):
        if f < title_frames:
            for when, idx in ((0.6, 1), (1.1, 2)):
                if f == int(when * fps):
                    app.sel_game = idx
                    app.sound.play("beep")
            if f == int(1.8 * fps):
                app.sel_char = 1
                app.sound.play("beep")
        if f == title_frames:
            app.sound.play("beep_hi")
            app.start_game(player_ai=True, seed=seed)
            app.game.state_t = 1.6          # a shorter tip-off card for the demo
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
    g = app.game
    print("wrote", out, "stats", g.stats, "score", g.p1.score, g.p2.score)


def record_football(out, seconds=28, fps=30, seed=None):
    """A Football demo: the title with Football picked, then the robot against an AI Archie."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    app = App(sound=False)
    seed = 55 if seed is None else seed
    tmp_v = out + ".video.mp4"
    tmp_a = out + ".wav"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIN_W}x{WIN_H}",
                           "-r", str(fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", tmp_v],
                          stdin=subprocess.PIPE)
    dt = 1 / fps
    frames = int(seconds * fps)
    title_frames = int(3.0 * fps)
    for f in range(frames):
        if f < title_frames:
            if f == int(0.8 * fps):
                app.sel_game = [n for n, _ in GAMES].index("Football")
                app.sound.play("beep")
        if f == title_frames:
            app.sound.play("beep_hi")
            app.start_game(player_ai=True, seed=seed)
            app.game.state_t = 1.6          # a shorter kick-off card for the demo
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
    g = app.game
    print("wrote", out, "stats", g.stats, "score", g.p1.score, g.p2.score)


def _key(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0)


def selftest_input():
    """Pads, pause, name entry and full-screen scaling, with no real display or pad.

    SDL_VIDEODRIVER=dummy and SDL_AUDIODRIVER=dummy. Display sizes 1920×1080 and
    3840×2160 are opened explicitly (the dummy driver only pretends to be 1024×768).
    """
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    art = os.environ.get("COURTYARD_ARTIFACTS", "/opt/cursor/artifacts")
    os.makedirs(art, exist_ok=True)

    # geometry of the scale, independent of a window
    assert pads_mod.family_of("Xbox 360 Controller") == "xbox"
    assert pads_mod.family_of("Xbox Wireless Controller") == "xbox"
    assert pads_mod.family_of("Sony DualShock 4") == "playstation"
    assert pads_mod.family_of("PS4 Controller") == "playstation"
    assert pads_mod.family_of("Wireless Controller") == "playstation"
    assert pads_mod.family_of("DualSense") == "playstation"
    assert screenmode.fit_rect(1280, 720, 1920, 1080) == (0, 0, 1920, 1080)
    assert screenmode.fit_rect(1280, 720, 3840, 2160) == (0, 0, 3840, 2160)
    assert screenmode.scaler_name((1280, 720), (3840, 2160)) == "nearest"
    assert screenmode.scaler_name((1280, 720), (1920, 1080)) == "smooth"
    x, y, w, h = screenmode.fit_rect(1280, 720, 1920, 1200)
    assert y > 0 and w == 1920 and h == 1080          # letterbox on a taller screen
    x, y, w, h = screenmode.fit_rect(1280, 720, 2560, 1080)
    assert x > 0 and h == 1080 and w == 1920          # pillarbox on a wider screen
    assert abs((w / h) - (1280 / 720)) < 0.01

    # --- keyboard, with no pad, stays on the old words and the old keys
    app = App(sound=False)
    assert app.screen.get_size() == (WIN_W, WIN_H)
    assert not app.fullscreen
    assert pygame.mouse.get_visible()
    assert not app.pads.connected
    lines = app.title_lines()
    assert lines[3] == "Left/Right choose a player  ·  Up/Down choose a game  ·  Enter or Space to play"
    assert lines[2] == "Controls: Left/Right turn  ·  Up run  ·  Down step back  ·  M music on/off  ·  Esc back"
    assert "Space" not in lines[2]
    app.sel_game = [n for n, _ in GAMES].index("Basketball")
    assert "Hold Space and let go" in app.title_lines()[1]
    assert "Space shoot / swipe / jump" in app.title_lines()[2]
    app.sel_game = 0
    assert app.handle(_key(pygame.K_RIGHT))
    assert app.sel_char == 1
    assert app.handle(_key(pygame.K_UP))
    assert app.sel_game == len(GAMES) - 1
    assert app.handle(_key(pygame.K_ESCAPE)) is False

    # a fresh app for the pad, so the quit above is not this one's
    app = App(sound=False)
    assert app.handle(_key(pygame.K_RIGHT))
    assert app.sel_char == 1

    xbox = app.pads.attach_virtual("xbox")
    app.pads.poll(0.016)
    assert app.pads.connected
    assert app.pads.hints.family == "xbox"
    assert app.pads.hints.action == "A"
    assert app.pads.hints.back == "B"
    assert app.pads.hints.pause == "Start"
    assert app.pads.hints.quit == "Back"
    assert "Stick or D-pad" in app.title_lines()[2]
    assert "A to play" in app.title_lines()[3]
    assert "Enter or Space to play" not in app.title_lines()[3]

    # deadzone: 0.2 does nothing, 0.35 is a direction
    app.sel_char = 0
    app.sel_game = 0
    xbox.set_axis(pygame.CONTROLLER_AXIS_LEFTX, 0.2)
    assert app.frame(1 / 60, events=[])
    assert app.sel_char == 0
    xbox.set_axis(pygame.CONTROLLER_AXIS_LEFTX, 0.0)
    assert app.frame(1 / 60, events=[])
    xbox.set_axis(pygame.CONTROLLER_AXIS_LEFTX, 0.35)
    assert app.frame(1 / 60, events=[])
    assert app.sel_char == 1
    xbox.set_axis(pygame.CONTROLLER_AXIS_LEFTX, 0.0)
    assert app.frame(1 / 60, events=[])

    # D-pad down changes the game. Keyboard still works while the stick is centred.
    before = app.sel_game
    xbox.set_button(pygame.CONTROLLER_BUTTON_DPAD_DOWN, True)
    assert app.frame(1 / 60, events=[])
    assert app.sel_game == (before + 1) % len(GAMES)
    xbox.set_button(pygame.CONTROLLER_BUTTON_DPAD_DOWN, False)
    assert app.frame(1 / 60, events=[])
    held = app.sel_char
    assert app.handle(_key(pygame.K_LEFT))
    assert app.sel_char == (held - 1) % len(PLAYABLE)

    # holding the D-pad repeats
    xbox.set_button(pygame.CONTROLLER_BUTTON_DPAD_DOWN, True)
    seen = {app.sel_game}
    for _ in range(40):
        assert app.frame(1 / 60, events=[])
        seen.add(app.sel_game)
    xbox.set_button(pygame.CONTROLLER_BUTTON_DPAD_DOWN, False)
    assert app.frame(1 / 60, events=[])
    assert len(seen) >= 3

    app.sel_game = 0
    app.t = 0.8
    app.draw()
    pygame.image.save(app.screen, os.path.join(art, "title-pad-xbox.png"))

    # A starts Tag. Stick-up runs. Start pauses and freezes. A resumes. B returns.
    xbox.set_button(pygame.CONTROLLER_BUTTON_A, True)
    assert app.frame(1 / 60, events=[])
    assert app.state == "play" and isinstance(app.game, tag.TagGame)
    xbox.set_button(pygame.CONTROLLER_BUTTON_A, False)
    assert app.frame(1 / 60, events=[])
    app.game.state = "playing"
    app.game.p1.frozen = 0.0
    x0 = app.game.p1.x
    xbox.set_axis(pygame.CONTROLLER_AXIS_LEFTY, -0.8)     # stick up: run forwards
    assert app.frame(0.3, events=[])
    assert app.game.p1.x > x0 + 0.2
    xbox.set_axis(pygame.CONTROLLER_AXIS_LEFTY, 0.0)
    assert app.frame(0.3, events=[])
    xr = app.game.p1.x
    assert app.frame(0.3, events=[])
    assert abs(app.game.p1.x - xr) < 0.05, "a resting right trigger must not run"
    xbox.set_axis(pygame.CONTROLLER_AXIS_TRIGGERRIGHT, 1.0)  # right trigger: forwards too
    assert app.frame(0.3, events=[])
    assert app.game.p1.x > xr + 0.2, "right trigger runs forwards"
    xbox.set_axis(pygame.CONTROLLER_AXIS_TRIGGERRIGHT, -1.0)
    assert app.frame(1 / 60, events=[])
    x1 = app.game.p1.x
    xbox.set_button(pygame.CONTROLLER_BUTTON_START, True)
    assert app.frame(1 / 60, events=[])
    assert app.paused
    xbox.set_button(pygame.CONTROLLER_BUTTON_START, False)
    for _ in range(5):
        assert app.frame(0.1, events=[])
    assert app.paused and abs(app.game.p1.x - x1) < 1e-6
    app.draw()
    pygame.image.save(app.screen, os.path.join(art, "pause-pad-xbox.png"))
    xbox.set_button(pygame.CONTROLLER_BUTTON_A, True)
    assert app.frame(1 / 60, events=[])
    assert not app.paused
    xbox.set_button(pygame.CONTROLLER_BUTTON_A, False)
    xbox.set_axis(pygame.CONTROLLER_AXIS_LEFTY, 0.0)
    assert app.frame(1 / 60, events=[])
    xbox.set_button(pygame.CONTROLLER_BUTTON_B, True)
    assert app.frame(1 / 60, events=[])
    assert app.state == "title" and not app.paused
    xbox.set_button(pygame.CONTROLLER_BUTTON_B, False)
    assert app.frame(1 / 60, events=[])

    # win screen and the next-round card accept A
    app.sel_game = 0
    app.start_game()
    app.game.state = "round_over"
    app.game.state_t = 0.0
    xbox.set_button(pygame.CONTROLLER_BUTTON_A, True)
    assert app.frame(1 / 60, events=[])
    assert app.state == "play" and app.game.state != "round_over"
    xbox.set_button(pygame.CONTROLLER_BUTTON_A, False)
    assert app.frame(1 / 60, events=[])
    app.game.state = "match_over"
    app.game.state_t = 0.0
    xbox.set_button(pygame.CONTROLLER_BUTTON_A, True)
    assert app.frame(1 / 60, events=[])
    assert app.state == "title"
    xbox.set_button(pygame.CONTROLLER_BUTTON_A, False)
    assert app.frame(1 / 60, events=[])

    # Y is the music button
    assert app.sound.music_on
    xbox.set_button(pygame.CONTROLLER_BUTTON_Y, True)
    assert app.frame(1 / 60, events=[])
    assert not app.sound.music_on
    xbox.set_button(pygame.CONTROLLER_BUTTON_Y, False)
    assert app.frame(1 / 60, events=[])

    # basketball: A charges a shot and letting go releases it. Same path as football.
    app.sel_game = [n for n, _ in GAMES].index("Basketball")
    app.start_game(seed=1)
    g = app.game
    g.state = "play"
    g.give(g.p1)
    xbox.set_button(pygame.CONTROLLER_BUTTON_A, True)
    assert app.frame(1 / 60, events=[])
    assert g.p1.charging
    xbox.set_button(pygame.CONTROLLER_BUTTON_A, False)
    assert app.frame(1 / 60, events=[])
    assert not g.p1.charging

    # batdown: X lofts the swing, and the stick still aims
    app.sel_game = [n for n, _ in GAMES].index("Batdown")
    app.start_game(seed=1)
    g = app.game
    g.state = "play"
    g.batter, g.fielder = g.p1, g.p2
    g.phase = "flight"
    xbox.set_button(pygame.CONTROLLER_BUTTON_X, True)
    assert app.frame(1 / 60, events=[])
    assert g.loft and g.swing_t is not None
    xbox.set_button(pygame.CONTROLLER_BUTTON_X, False)
    assert app.frame(1 / 60, events=[])

    # football uses the same A-as-Space path
    app.sel_game = [n for n, _ in GAMES].index("Football")
    app.start_game(seed=1)
    g = app.game
    g.state = "play"
    g.holder = g.p1
    xbox.set_button(pygame.CONTROLLER_BUTTON_A, True)
    assert app.frame(1 / 60, events=[])
    assert g.p1.charging
    xbox.set_button(pygame.CONTROLLER_BUTTON_A, False)
    assert app.frame(1 / 60, events=[])

    # name entry: up/down cycle, left/right move, A accepts
    ne = pads_mod.NameEntry(length=4)
    ne.cycle(1)
    assert ne.slots[0] == "B"
    ne.move(1)
    ne.cycle(-1)          # slot 1 starts as a space; down wraps to Z
    assert ne.slots[1] == "Z"
    app.state = "name"
    app.name_entry = pads_mod.NameEntry(length=4)
    xbox.set_axis(pygame.CONTROLLER_AXIS_LEFTY, -1.0)
    assert app.frame(1 / 60, events=[])
    assert app.name_entry.slots[0] == "B"
    xbox.set_axis(pygame.CONTROLLER_AXIS_LEFTY, 0.0)
    assert app.frame(1 / 60, events=[])
    xbox.set_button(pygame.CONTROLLER_BUTTON_DPAD_RIGHT, True)
    assert app.frame(1 / 60, events=[])
    assert app.name_entry.i == 1
    xbox.set_button(pygame.CONTROLLER_BUTTON_DPAD_RIGHT, False)
    xbox.set_button(pygame.CONTROLLER_BUTTON_A, True)
    assert app.frame(1 / 60, events=[])
    assert app.name_entry.done and app.state == "title"
    assert app.name_entry.text.startswith("B")
    xbox.set_button(pygame.CONTROLLER_BUTTON_A, False)
    assert app.frame(1 / 60, events=[])
    app.draw()

    # second pad is player 2 and does not drive player 1
    ps = app.pads.attach_virtual("playstation")
    app.pads.poll(0.016)
    assert app.pads.player(0).connected and app.pads.player(1).connected
    assert app.pads.player(0).family == "xbox"
    assert app.pads.player(1).family == "playstation"
    ps.set_axis(pygame.CONTROLLER_AXIS_LEFTX, 1.0)
    app.pads.poll(0.016)
    assert app.pads.player(1).turn == 1
    assert app.pads.player(0).turn == 0
    ps.set_axis(pygame.CONTROLLER_AXIS_LEFTX, 0.0)

    # hot-plug: unplugging the first pad stops its direction and the hints follow whoever is left
    xbox.set_axis(pygame.CONTROLLER_AXIS_LEFTX, -1.0)
    app.pads.poll(0.016)
    assert app.pads.player(0).turn == -1
    app.pads.detach_virtual(xbox)
    app.pads.poll(0.016)
    assert app.pads.player(0).family == "playstation"
    assert app.pads.player(0).turn == 0
    assert app.pads.hints.action == "Cross"
    app.sel_game = 0
    app.state = "title"
    app.t = 0.4
    app.draw()
    pygame.image.save(app.screen, os.path.join(art, "title-pad-playstation.png"))
    assert "Cross" in " ".join(app.title_lines())
    app.pads.detach_virtual(ps)
    app.pads.poll(0.016)
    assert not app.pads.connected
    assert app.title_lines()[3] == "Left/Right choose a player  ·  Up/Down choose a game  ·  Enter or Space to play"

    # holding Back for about a second quits; a shorter hold does not
    xbox = app.pads.attach_virtual("xbox")
    xbox.set_button(pygame.CONTROLLER_BUTTON_BACK, True)
    quit_at = None
    for i in range(8):
        alive = app.frame(0.25, events=[])
        if not alive:
            quit_at = (i + 1) * 0.25
            break
    assert quit_at is not None and abs(quit_at - 1.0) < 0.05
    xbox.set_button(pygame.CONTROLLER_BUTTON_BACK, False)
    app.pads.detach_virtual()

    # full-screen at 1080p and 4K: native pixels, aspect kept, cursor hidden, no border flag
    def check_display(size, scaler):
        disp = App(sound=False, fullscreen=True, display_size=size)
        assert disp.screen.get_size() == (WIN_W, WIN_H)
        assert disp.display.size == size
        assert disp.display.fit == screenmode.fit_rect(WIN_W, WIN_H, *size)
        assert disp.display.scaler == scaler
        assert disp.display.flags & pygame.NOFRAME
        assert not pygame.mouse.get_visible()
        disp.t = 0.6
        disp.draw()
        dt = disp.display.present()
        print(f"present {size[0]}x{size[1]} {disp.display.scaler} {dt * 1000:.2f} ms")
        assert dt < 0.025
        return disp

    d1080 = check_display((1920, 1080), "smooth")
    # the television is filled: the corner is the picture, not a black bar
    show = d1080.pads.attach_virtual("xbox")
    d1080.pads.poll(1 / 60)
    d1080.t = 0.6
    d1080.draw()
    d1080.display.present()
    assert d1080.display.out.get_at((4, 4))[:3] != (0, 0, 0)
    assert d1080.display.out.get_at((1910, 1070))[:3] != (0, 0, 0)
    assert "A to play" in d1080.title_lines()[3]
    pygame.image.save(d1080.display.out, os.path.join(art, "title-fullscreen-1080.png"))
    d1080.pads.detach_virtual(show)

    d4k = check_display((3840, 2160), "nearest")
    assert d4k.display.out.get_at((6, 6))[:3] != (0, 0, 0)
    assert d4k.display.fit == (0, 0, 3840, 2160)

    # a screen that is not 16:9 is letterboxed
    tall = App(sound=False, fullscreen=True, display_size=(1920, 1200))
    assert tall.display.fit[1] > 0
    tall.draw()
    tall.display.present()
    assert tall.display.out.get_at((960, 2))[:3] == (0, 0, 0)
    assert tall.display.out.get_at((960, 600))[:3] != (0, 0, 0)

    # Zen Station path: no pinned size, so the dummy desktop (1024×768) is used, full-screen flag set
    desk = App(sound=False, fullscreen=True)
    assert desk.display.flags & pygame.FULLSCREEN
    assert desk.display.flags & pygame.NOFRAME
    assert desk.display.size == tuple(screenmode.desktop_size())
    assert desk.screen.get_size() == (WIN_W, WIN_H)
    fx, fy, fw, fh = desk.display.fit
    assert abs((fw / fh) - (WIN_W / WIN_H)) < 0.02
    assert not pygame.mouse.get_visible()
    print("selftest input ok", "desktop", desk.display.size, "fit", desk.display.fit)
    print("screenshots in", art)


def want_fullscreen(argv=None):
    argv = sys.argv if argv is None else argv
    if "--fullscreen" in argv:
        return True
    return os.environ.get("ZENSTATION", "").strip() == "1"


def display_size_arg():
    """COURTYARD_DISPLAY=1920x1080 pins the full-screen framebuffer (used by the headless check)."""
    raw = os.environ.get("COURTYARD_DISPLAY", "").strip().lower()
    if "x" not in raw:
        return None
    w, h = raw.split("x", 1)
    try:
        return (int(w), int(h))
    except ValueError:
        return None


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest_input()
        selftest()
        selftest_batdown()
        selftest_basketball()
        selftest_football()
    elif "--selftest-input" in sys.argv:
        selftest_input()
    elif "--selftest-football" in sys.argv:
        selftest_football()
    elif "--record-football" in sys.argv:
        i = sys.argv.index("--record-football")
        seed = int(sys.argv[i + 2]) if len(sys.argv) > i + 2 else None
        record_football(sys.argv[i + 1], seed=seed)
    elif "--shots-football" in sys.argv:
        import shots
        shots.football(sys.argv[sys.argv.index("--shots-football") + 1])
    elif "--selftest-batdown" in sys.argv:
        selftest_batdown()
    elif "--selftest-basketball" in sys.argv:
        selftest_basketball()
    elif "--record-basketball" in sys.argv:
        i = sys.argv.index("--record-basketball")
        seed = int(sys.argv[i + 2]) if len(sys.argv) > i + 2 else None
        record_basketball(sys.argv[i + 1], seed=seed)
    elif "--shots-basketball" in sys.argv:
        import shots
        shots.basketball(sys.argv[sys.argv.index("--shots-basketball") + 1])
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
        fs = want_fullscreen()
        App(fullscreen=fs, display_size=display_size_arg() if fs else None).run()
