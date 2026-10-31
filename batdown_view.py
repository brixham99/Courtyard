"""Drawing Batdown in the park: the players (posed from their own sprites),
the bat and ball (drawn in code), the chalk X, the aiming guide and the HUD.
Used by game.App; kept apart from the rules in batdown.py."""
import functools
import math
import os

import pygame
import aa

import batdown as B
import park
import poses
import scene
from iso import WIN_W, WIN_H, N, P, shade

WILLOW = (226, 200, 146)
HANDLE = (70, 52, 40)
GRIP = (40, 60, 120)
BALL = (214, 236, 70)          # a tennis ball
CHALK = (250, 250, 244)


def norm(a):
    a = (a + 180) % 360 - 180
    return a


def lerp(a, b, k):
    return a + (b - a) * k


class BatdownView:
    def __init__(self, app):
        self.app = app
        import game as G
        self.posers = {k: poses.Poser(k, os.path.join(G.CH_DIR, "{kind}_{key}.png"), G.CH_SCALE[k], app.chars[k].anchor)
                       for k in ("archie", "holly", "robot")}
        self.oak = park.OakArt()
        self.ball_shadow = pygame.Surface((14, 7), pygame.SRCALPHA)
        aa.ellipse(self.ball_shadow, (16, 24, 12, 110), self.ball_shadow.get_rect())
        self.fx = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)

    # ------------------------------------------------------------ the pose for this moment
    def pose_for(self, g, r):
        """(a_active, a_off, crouch, bat) — arm angles in degrees (0 down, + forwards, 180 up)."""
        t = r.anim_t
        a = r.anim
        if g is not None and g.state == "play" and r is g.batter:
            if a == "swing" and t < B.SWING_LEN:
                k = t / B.SWING_LEN
                # backlift, then through the line of the ball, then the follow-through
                if t < 0.08:
                    ang = lerp(25, -70, t / 0.08)
                elif t < 0.2:
                    ang = lerp(-70, 120, (t - 0.08) / 0.12)
                elif t < 0.3:
                    ang = lerp(120, 150, (t - 0.2) / 0.1)
                else:
                    ang = lerp(150, 25, (t - 0.3) / 0.12)
                return ang, ang * 0.8, False, "swing"
            return 28, 22, False, "stance"
        if a == "windup":
            return -125, 30, False, None
        if a == "throw" and t < 0.45:
            # overarm: from behind, up over the shoulder, through and down
            if t < 0.12:
                ang = lerp(-125, -180, t / 0.12)
            elif t < 0.25:
                ang = lerp(180, 70, (t - 0.12) / 0.13)
            else:
                ang = lerp(70, 20, (t - 0.25) / 0.2)
            return norm(ang), 25, False, None
        if a == "lob" and t < 0.45:
            ang = lerp(-60, 115, min(1, t / 0.22)) if t < 0.3 else lerp(115, 30, (t - 0.3) / 0.15)
            return ang, 10, False, None
        if a == "pickup" and t < 0.35:
            return 40, 10, True, None
        if a == "catch" and t < 1.6:
            return 165, -160, False, None
        if a == "cheer":
            w = math.sin(t * 12) * 12
            return 150 + w, -150 - w, False, None
        return None

    # ------------------------------------------------------------ people
    def draw_player(self, s, g, r, t):
        app = self.app
        ch = app.chars[r.kind]
        key = r.sprite_key
        gx, gy = P(r.x, r.y)
        pose = self.pose_for(g, r)
        s.blit(app.contact, (round(gx - 16), round(gy - 6)))
        moving = r.moved > 0
        img, (shd, (sx, sy)) = ch.frame(key, r.walk_phase, moving)
        s.blit(shd, (round(gx + sx), round(gy + sy)))
        fwd = poses.FORWARD[key]
        act = 1 if fwd > 0 else 0           # the arm on the forward side does the work
        hand = None
        bat_kind = None
        if pose is None or moving:
            bob = abs(math.sin(r.walk_phase / ch.cycle * 2 * math.pi)) * 2.0 if moving else 0
            ax, ay = ch.anchor[key]
            x0, y0 = round(gx - ax), round(gy - ay - bob)
            s.blit(img, (x0, y0))
            rect = pygame.Rect(x0, y0, img.get_width(), img.get_height())
            if g is not None and r is g.fielder and r.holding:
                p = self.posers[r.kind]
                shx, shy = p.shoulders[key][act]
                hand = p.arms[key][act].hand_at((gx + shx, gy + shy - bob), 0)
        else:
            a_ang, ao, crouch, bat_kind = pose
            p = self.posers[r.kind]
            angs = [0, 0]
            angs[act] = a_ang
            angs[1 - act] = ao
            hs = self._draw_posed(s, p, key, (gx, gy), ch.anchor[key], angs, crouch, g, r, bat_kind, act)
            hand = hs[act]
            ax, ay = ch.anchor[key]
            rect = pygame.Rect(round(gx - ax), round(gy - ay), img.get_width(), img.get_height())
        if hand is not None and g is not None and r is g.fielder and r.holding:
            aa.circle(s, shade(BALL, 0.7), (round(hand[0]), round(hand[1])), 4)
            aa.circle(s, BALL, (round(hand[0]) - 1, round(hand[1]) - 1), 3)
        return rect

    def _draw_posed(self, s, p, key, feet, anchor, angs, crouch, g, r, bat_kind, act):
        back = poses.BACK_VIEW[key]
        if bat_kind and back:
            # facing away: the bat is hidden behind them, so draw it first
            sh = p.shoulders[key][act]
            hand = p.arms[key][act].hand_at((feet[0] + sh[0], feet[1] + sh[1]), angs[act] * poses.FORWARD[key])
            self.draw_bat(s, g, hand, bat_kind, angs[act], key)
            return p.draw(s, key, feet, anchor, angs[0], angs[1], crouch)
        hands = p.draw(s, key, feet, anchor, angs[0], angs[1], crouch)
        if bat_kind:
            self.draw_bat(s, g, hands[act], bat_kind, angs[act], key)
        return hands

    def draw_bat(self, s, g, hand, kind, ang, key):
        hx, hy = hand
        if kind == "stance":
            # toe of the blade grounded at the bat's spot in front of the batter
            bx, by = g.bat_point()
            tx, ty = P(bx, by)
        else:
            # an extension of the arm, seen side-on
            fwd = poses.FORWARD[key]
            a = math.radians(ang)
            dx, dy = math.sin(a) * fwd, math.cos(a)
            L = 62
            tx, ty = hx + dx * L, hy + dy * L * 0.85
        self._bat_line(s, (hx, hy), (tx, ty))

    def _bat_line(self, s, a, b, width=8):
        ax, ay = a
        bx, by = b
        L = math.hypot(bx - ax, by - ay) or 1
        ux, uy = (bx - ax) / L, (by - ay) / L
        k = min(0.36, 20 / L)
        sx, sy = ax + (bx - ax) * k, ay + (by - ay) * k
        aa.line(s, HANDLE, (ax - ux * 4, ay - uy * 4), (sx, sy), 3)
        aa.line(s, GRIP, (ax - ux * 3, ay - uy * 3), (ax + (sx - ax) * 0.6, ay + (sy - ay) * 0.6), 4)
        nx, ny = -uy * width / 2, ux * width / 2
        poly = [(sx + nx * 0.7, sy + ny * 0.7), (bx + nx, by + ny), (bx - nx, by - ny), (sx - nx * 0.7, sy - ny * 0.7)]
        aa.polygon(s, shade(WILLOW, 0.72), [(x + 1, y + 1) for x, y in poly])
        aa.polygon(s, WILLOW, poly)
        aa.line(s, shade(WILLOW, 1.12), (sx + nx * 0.5, sy + ny * 0.5), (bx + nx * 0.7, by + ny * 0.7), 2)

    def draw_fallen_bat(self, s, g):
        bx, by, ux, uy = g.fallen
        lx, ly = -uy, ux
        a = P(bx - lx * 0.75 + ux * 0.2, by - ly * 0.75 + uy * 0.2)
        b = P(bx + lx * 0.55 + ux * 0.4, by + ly * 0.55 + uy * 0.4)
        self._bat_line(s, (a[0], a[1] - 2), (b[0], b[1] - 2), 9)

    # ------------------------------------------------------------ the ground marks
    def draw_chalk_x(self, s, x, y, t, pulse=True):
        gx, gy = P(x, y)
        k = 1.0 + (0.08 * math.sin(t * 5) if pulse else 0)
        # along the world axes, so it reads as an X on screen
        for (dx1, dy1, dx2, dy2) in ((-0.3, 0, 0.3, 0), (0, -0.3, 0, 0.3)):
            p1 = P(x + dx1 * k, y + dy1 * k)
            p2 = P(x + dx2 * k, y + dy2 * k)
            aa.line(s, (60, 90, 50), (p1[0], p1[1] + 1), (p2[0], p2[1] + 1), 6)
            aa.line(s, CHALK, p1, p2, 4)

    def draw_aim_guide(self, s, g, t):
        f = g.fielder
        lx, ly = g.predicted_landing()
        ca, sa = math.cos(g.aim_ang), math.sin(g.aim_ang)
        surf = self.fx
        surf.fill((0, 0, 0, 0))
        # a dotted line from the thrower out to the landing dot
        d = math.hypot(lx - f.x, ly - f.y)
        n = int(d / 0.4)
        for i in range(1, n + 1):
            px, py = P(f.x + ca * i * 0.4, f.y + sa * i * 0.4)
            aa.circle(surf, (255, 255, 255, 150), (round(px), round(py)), 2)
        # the arrow head a little way out
        tip = P(f.x + ca * 1.25, f.y + sa * 1.25)
        l1 = P(f.x + ca * 0.85 - sa * 0.25, f.y + sa * 0.85 + ca * 0.25)
        l2 = P(f.x + ca * 0.85 + sa * 0.25, f.y + sa * 0.85 - ca * 0.25)
        aa.polygon(surf, (255, 230, 90, 220), [tip, l1, l2])
        if g.charging or g.power > 0:
            gx, gy = P(lx, ly)
            aa.ellipse(surf, (255, 90, 70, 200), (gx - 12, gy - 6, 24, 12), 3)
            aa.circle(surf, (255, 90, 70, 230), (round(gx), round(gy)), 3)
        s.blit(surf, (0, 0))

    # ------------------------------------------------------------ the scene
    def draw_world(self, s, g, t, title=False):
        app = self.app
        sc = app.scene("park")
        s.blit(sc["bg"], (0, 0))
        if g is not None:
            if g.state in ("play", "swap") and g.x_mark is not None and g.phase in ("fetch", "aim"):
                self.draw_chalk_x(s, *g.x_mark, t, pulse=g.phase == "fetch")
            if g.state == "play" and g.phase == "aim" and not g.fielder.ai:
                self.draw_aim_guide(s, g, t)
            for x, y, age in g.dust:
                gx, gy = P(x, y)
                a = int(120 * (1 - age / 0.6))
                rr = 6 + age * 26
                aa.ellipse(s, shade((150, 190, 110), 1.15), (gx - rr, gy - rr * 0.45, rr * 2, rr * 0.9), 1)
            if g.state in ("swap", "match_over") and getattr(g, "fallen", None):
                self.draw_fallen_bat(s, g)
            ball = g.ball
            show_ball = not (g.fielder.holding and g.state in ("play",)) and g.state != "toss"
            if g.state == "swap" and g.fielder.holding:
                show_ball = False
            if show_ball:
                fl = g.geom.floor(ball.x, ball.y)
                bx, by = P(ball.x, ball.y, fl * B.ZPX)
                k = max(0.45, 1 - (ball.z - fl) / 6)
                sh = pygame.transform.smoothscale(self.ball_shadow, (round(14 * k), round(7 * k)))
                s.blit(sh, (round(bx - sh.get_width() / 2), round(by - sh.get_height() / 2)))
        items = [("ob", o) for o in sc["obstacles"]]
        if g is not None:
            items += [("run", r) for r in g.runners]
            if show_ball:
                items.append(("ball", g.ball))
        app_ = self.app

        def depth(it):
            k, o = it
            if k == "ob":
                return app_.ob_depth(o)
            return o.x + o.y

        def cmp(a, b):
            ka, oa = a
            kb, ob = b
            if ka != "ob" and kb == "ob":
                return 1 if app_.run_in_front(oa, ob) else -1
            if ka == "ob" and kb != "ob":
                return -1 if app_.run_in_front(ob, oa) else 1
            return 1 if depth(a) > depth(b) else -1
        items.sort(key=functools.cmp_to_key(cmp))
        rects = {}
        trees = []
        for k, o in items:
            if k == "run":
                rects[id(o)] = self.draw_player(s, g, o, t)
            elif k == "ball":
                self.draw_ball(s, o)
            elif o.kind == "tree":
                park.draw_oak_base(s, o)
                trees.append(o)
            elif o.kind == "bench":
                scene.draw_bench(s, o)
        for o in trees:
            s.blit(self.oak.canopy, park.oak_canopy_rect(o, self.oak))
        s.blit(sc["front"], (0, 0))
        return rects

    def draw_ball(self, s, b):
        x, y = P(b.x, b.y, b.z * B.ZPX)
        x, y = round(x), round(y)
        aa.circle(s, shade(BALL, 0.55), (x, y), 6)
        aa.circle(s, BALL, (x, y), 5)
        aa.circle(s, (250, 255, 200), (x + 1, y - 2), 1)
        aa.arc(s, (250, 250, 240), (x - 4, y - 4, 8, 8), 3.6, 5.6, 1)

    # ------------------------------------------------------------ the HUD
    def draw_hud(self, s, g, t):
        app = self.app
        bar = pygame.Rect(10, 8, WIN_W - 20, 66)
        app.panel(s, bar, alpha=228)
        for side, r in ((0, g.p1), (1, g.p2)):
            por = app.portrait(r.kind, 54)
            label = r.name + (" (you)" if not r.ai else "")
            batting = r is g.batter and g.state in ("play", "toss")
            role = "batting" if r is g.batter else "fielding"
            sub = (f"Turn {min(r.turns, g.turns)} of {g.turns} at bat" if r is g.batter else f"Fielding  ·  batted {r.turns} of {g.turns}")
            col = (255, 230, 120) if batting else (230, 236, 250)
            if side == 0:
                s.blit(por, (bar.x + 10, bar.y + 6))
                x = bar.x + 20 + por.get_width()
                self.app.text(s, app.f_hud, label, col, (x, bar.y + 6))
                app.text(s, app.f_small, sub, (210, 216, 230), (x, bar.y + 36))
                self.score_bar(s, r.score, g.target, x + 236, bar.y + 10, False)
            else:
                s.blit(por, (bar.right - 10 - por.get_width(), bar.y + 6))
                x = bar.right - 20 - por.get_width()
                app.text(s, app.f_hud, label, col, (x, bar.y + 6), "topright")
                app.text(s, app.f_small, sub, (210, 216, 230), (x, bar.y + 36), "topright")
                self.score_bar(s, r.score, g.target, x - 236, bar.y + 10, True)
        cx = WIN_W // 2
        app.text(s, app.f_small_b, f"BATDOWN  ·  first to {g.target}", (190, 200, 220), (cx, bar.y + 4), "midtop")
        f = g.fielder
        if g.state == "play" and f.holding and g.clock_running:
            tl = max(0.0, g.throw_clock)
            hot = tl < 2.5
            col = (255, 90, 80) if hot and int(tl * 4) % 2 == 0 else (255, 255, 255)
            app.text(s, app.f_big, f"{tl:0.1f}", col, (cx, bar.y + 20), "midtop")
            app.text(s, app.f_tiny, "throw!", (190, 200, 220), (cx + 60, bar.y + 44), "midleft", False)
        else:
            app.text(s, app.f_mid, f"{g.p1.score} – {g.p2.score}", (255, 255, 255), (cx, bar.y + 28), "midtop")
        if g.streak and g.state == "play":
            app.text(s, app.f_tiny, f"streak {g.streak}", (255, 230, 120), (cx - 60, bar.y + 44), "midright", False)
        self.draw_callouts(s, g)
        self.draw_banner(s, g)
        if g.state == "toss":
            b = g.batter
            app.centre_card(s, [(app.f_big, "Batdown", (255, 230, 120)),
                                (app.f_mid, f"{b.name} won the toss and bats first", (255, 255, 255)),
                                (app.f_small, "Hit it far for points. Bat down, or caught on the full, and you swap.", (210, 216, 230))])
        elif g.state == "match_over":
            w = g.winner
            sc = f"{max(g.p1.score, g.p2.score)}–{min(g.p1.score, g.p2.score)}"
            if w is None:
                head, sub = f"A draw, {sc}!", "Nothing in it. Have another go."
            elif not g.p1.ai and w is g.p1:
                head, sub = f"{w.name} wins {sc}!", "Well batted! The Robot wants a rematch."
            elif not g.p1.ai:
                head, sub = f"The {w.name} wins {sc}", "So close! Have another go."
            else:
                head, sub = f"{w.name} wins {sc}!", ""
            lines = [(app.f_big, head, (255, 230, 120))]
            for r in g.runners:
                lines.append((app.f_hud, f"{r.name}: {r.score} point{'s' if r.score != 1 else ''} in {r.turns} turn{'s' if r.turns != 1 else ''} at bat", (235, 240, 250)))
            if sub:
                lines.append((app.f_hud, sub, (235, 240, 250)))
            lines.append((app.f_small, "Press Enter for the title screen", (190, 200, 220)))
            app.centre_card(s, lines)

    def score_bar(self, s, score, target, x, y, right):
        w, h = 150, 16
        r = pygame.Rect(0, 0, w, h)
        if right:
            r.topright = (x, y)
        else:
            r.topleft = (x, y)
        pygame.draw.rect(s, (40, 46, 70), r, border_radius=8)
        k = min(1.0, score / target)
        if k > 0:
            fr = pygame.Rect(r.x, r.y, max(10, round(w * k)), h)
            if right:
                fr.right = r.right
            pygame.draw.rect(s, (90, 190, 90), fr, border_radius=8)
        pygame.draw.rect(s, (255, 255, 255), r, 1, border_radius=8)
        app = self.app
        txt = f"{score} / {target}"
        app.text(s, app.f_small_b, txt, (255, 255, 255), (r.centerx, r.bottom + 2), "midtop")

    def draw_callouts(self, s, g):
        app = self.app
        y = 84
        for text, col, age in g.callouts[-3:][::-1]:
            a = 255 if age < 1.6 else int(255 * max(0, 1 - (age - 1.6) / 0.6))
            k = 1.0 + max(0, 0.25 - age) * 1.2
            im = app.f_big.render(text, True, col)
            if k != 1.0:
                im = pygame.transform.smoothscale(im, (round(im.get_width() * k), round(im.get_height() * k)))
            out = app.f_big.render(text, True, (20, 24, 40))
            if k != 1.0:
                out = pygame.transform.smoothscale(out, im.get_size())
            r = im.get_rect(midtop=(WIN_W // 2, y - age * 10))
            out.set_alpha(a)
            im.set_alpha(a)
            for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2), (2, 3)):
                s.blit(out, r.move(ox, oy))
            s.blit(im, r)
            y += im.get_height() + 4

    def draw_banner(self, s, g):
        if g.state != "play":
            return
        app = self.app
        h = g.p1
        if h.ai:
            f = g.fielder
            if g.phase == "fetch":
                msg = f"{f.name} heads for the chalk X" if f.holding else f"{f.name} is fetching the ball"
            elif g.phase == "aim":
                msg = f"{f.name} lines up a throw at {g.batter.name}'s bat"
            else:
                msg = f"{g.batter.name} is batting"
            col = (40, 100, 190)
        elif h is g.batter:
            msg = f"You're batting: Space to swing  ·  hold Up for a lofted shot  ·  aim {('left', 'straight', 'right')[g.aim_i]}"
            col = (200, 110, 30)
        elif g.phase == "aim":
            msg = f"Throw: {B.THROW_TYPES[g.throw_type]} (Up/Down)  ·  Left/Right aim  ·  hold Space, let go to throw"
            col = (40, 120, 70)
        elif h.holding:
            msg = "Got it! Run to the chalk X to throw"
            col = (40, 120, 70)
        else:
            msg = "Fielding: fetch the ball!"
            col = (40, 120, 70)
        im = app.f_hud.render(msg, True, (255, 255, 255))
        r = pygame.Rect(0, 0, im.get_width() + 36, im.get_height() + 12)
        r.bottomleft = (16, WIN_H - 14)
        pygame.draw.rect(s, shade(col, 0.6), r.move(0, 3), border_radius=18)
        pygame.draw.rect(s, col, r, border_radius=18)
        s.blit(im, im.get_rect(center=r.center))
        if not h.ai and h is g.fielder and g.phase == "aim":
            # a power meter by the banner
            pr = pygame.Rect(r.right + 14, r.y + 6, 180, r.h - 12)
            pygame.draw.rect(s, (30, 34, 50), pr, border_radius=8)
            fill = pr.copy()
            fill.w = max(0, round(pr.w * g.power))
            if fill.w:
                pygame.draw.rect(s, (240, 120 + round(100 * (1 - g.power)), 60), fill, border_radius=8)
            pygame.draw.rect(s, (255, 255, 255), pr, 2, border_radius=8)
            app.text(s, app.f_tiny, f"power  {g.power * B.MAX_RANGE:0.0f} tiles" if g.power else "power", (255, 255, 255), pr.center, "center", False)
