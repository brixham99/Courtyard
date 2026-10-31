"""Drawing Football in the mini stadium: the goals (frames and rippling nets),
the players posed from their own sprites (slides and dives tip the sprite over),
the ball with its height shadow, the live scoreboard and the HUD. Used by
game.App; the rules are in football.py and the scenery in stadium.py."""
import math

import pygame

import football as FB
import poses
import scene  # noqa: F401  (scene registers the stadium; import it first)
import stadium as ST
from iso import WIN_W, WIN_H, N, P, shade, poly

Z = FB.ZPX
BAR = FB.BAR_Z * Z
WHITE = (250, 250, 250)
PATCH = (28, 30, 38)
NET = (245, 248, 252)
FRAME = (196, 202, 212)


def lerp(a, b, k):
    return a + (b - a) * k


class FootballView:
    def __init__(self, app):
        self.app = app
        self.posers = app.bd_view.posers
        self.fx = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        self.shadow = pygame.Surface((30, 15), pygame.SRCALPHA)
        pygame.draw.ellipse(self.shadow, (12, 22, 14, 150), self.shadow.get_rect())
        self.rot = {}
        self.sb_font = pygame.font.SysFont("dejavusansmono,dejavusans", 20, bold=True)
        self.sb_small = pygame.font.SysFont("dejavusans", 9, bold=True)

    # ------------------------------------------------------------ poses
    def pose_for(self, g, r):
        """(a_active, a_off, crouch) for the poser, 'tip' for a tipped-over sprite, or None."""
        a, t = r.anim, r.anim_t
        if r.slide_t is not None or r.dive_t is not None or (r.down_t > 0 and a == "down"):
            return "tip"
        if r.charging:
            w = min(1.0, r.power_t / 0.25)
            return lerp(10, -40, w), lerp(-10, 40, w), True
        if a == "kick" and t < 0.4:
            return 75, -80, False
        if a == "cheer":
            w = math.sin(t * 12) * 14
            return 160 + w, -160 - w, False
        if g.state == "play" and g.holder is not None and g.holder is not r and r.moved <= 0 \
                and abs(r.x - r.home.x) < 2.6:
            return 55, -55, True                # the keeper's ready stance
        return None

    def tip_angle(self, r):
        """(degrees, lift px, sideways px) for a slide, a dive or lying on the grass."""
        key = r.sprite_key
        fwd = poses.FORWARD.get(key, 1)
        if r.dive_t is not None:
            k = min(1.0, r.dive_t / 0.18)
            # +y runs down-left on screen: tipping that way is anticlockwise
            ang = 72 * k * (1 if r.dive_dir > 0 else -1)
            lift = 16 * math.sin(math.pi * min(1.0, r.dive_t / FB.DIVE_S))
            return ang, lift
        if r.slide_t is not None:
            k = min(1.0, r.slide_t / 0.08)
            return 58 * k * fwd, 0.0
        return 78 * fwd, 0.0

    def tipped(self, kind, key, ang):
        ang = round(ang / 3) * 3
        k = (kind, key, ang)
        if k not in self.rot:
            ch = self.app.chars[kind]
            img = ch.still[key]
            ax, ay = ch.anchor[key]
            w, h = img.get_size()
            im = pygame.transform.rotate(img, ang)
            vx, vy = ax - w / 2, ay - h / 2
            a = math.radians(ang)
            # pygame turns anticlockwise on screen
            rx = vx * math.cos(a) + vy * math.sin(a)
            ry = -vx * math.sin(a) + vy * math.cos(a)
            self.rot[k] = (im, (im.get_width() / 2 + rx, im.get_height() / 2 + ry))
        return self.rot[k]

    def draw_player(self, s, g, r):
        app = self.app
        ch = app.chars[r.kind]
        key = r.sprite_key
        gx, gy = P(r.x, r.y)
        pose = self.pose_for(g, r) if g is not None else None
        s.blit(app.contact, (round(gx - 16), round(gy - 6)))
        moving = r.moved > 0
        if pose == "tip":
            ang, lift = self.tip_angle(r)
            im, (ax, ay) = self.tipped(r.kind, key, ang)
            # a squashed shadow under the body
            sh = pygame.transform.smoothscale(self.shadow, (56, 18))
            s.blit(sh, (round(gx - 28 - math.sin(math.radians(ang)) * 20), round(gy - 9)))
            # sit the body on the grass: lying, its middle (not its feet) is at ground height
            down = abs(math.sin(math.radians(ang))) * 14
            x0, y0 = round(gx - ax), round(gy - ay - lift - down)
            s.blit(im, (x0, y0))
            return pygame.Rect(x0, y0, im.get_width(), im.get_height())
        img, (shd, (sx, sy)) = ch.frame(key, r.walk_phase, moving)
        s.blit(shd, (round(gx + sx), round(gy + sy)))
        if pose is None or (moving and not r.charging):
            bob = abs(math.sin(r.walk_phase / ch.cycle * 2 * math.pi)) * 2.0 if moving else 0
            ax, ay = ch.anchor[key]
            x0, y0 = round(gx - ax), round(gy - ay - bob)
            s.blit(img, (x0, y0))
            return pygame.Rect(x0, y0, img.get_width(), img.get_height())
        aa, ao, crouch = pose
        p = self.posers[r.kind]
        act = 1 if poses.FORWARD[key] > 0 else 0
        angs = [0, 0]
        angs[act] = aa
        angs[1 - act] = ao
        p.draw(s, key, (gx, gy), ch.anchor[key], angs[0], angs[1], crouch)
        ax, ay = ch.anchor[key]
        return pygame.Rect(round(gx - ax), round(gy - ay), img.get_width(), img.get_height())

    # ------------------------------------------------------------ the ball
    def draw_ball_at(self, s, x, y, spin, r=8):
        x, y = round(x), round(y)
        d = 2 * r + 2
        b = pygame.Surface((d, d), pygame.SRCALPHA)
        c = (r + 1, r + 1)
        pygame.draw.circle(b, WHITE, c, r)
        pygame.draw.circle(b, (214, 218, 226), (c[0] + 2, c[1] + 2), r - 1)
        pygame.draw.circle(b, WHITE, (c[0] - 1, c[1] - 1), r - 2)
        # the panels: one roughly facing us (drifting with the spin), five round the rim
        ox, oy = math.cos(spin) * r * 0.32, math.sin(spin * 0.8) * r * 0.25
        def pent(px, py, rad, rot):
            return [(px + rad * math.cos(rot + i * 2 * math.pi / 5), py + rad * math.sin(rot + i * 2 * math.pi / 5)) for i in range(5)]
        pygame.draw.polygon(b, PATCH, pent(c[0] + ox, c[1] + oy, r * 0.36, spin))
        for i in range(5):
            a = spin + i * 2 * math.pi / 5
            pygame.draw.polygon(b, PATCH, pent(c[0] + ox + math.cos(a) * r * 0.95, c[1] + oy + math.sin(a) * r * 0.95, r * 0.3, a))
        mask = pygame.Surface((d, d), pygame.SRCALPHA)
        pygame.draw.circle(mask, (255, 255, 255, 255), c, r)
        b.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        pygame.draw.circle(b, (90, 96, 110), c, r, 1)
        pygame.draw.circle(b, (255, 255, 255), (c[0] - 3, c[1] - 3), 2)
        s.blit(b, (x - r - 1, y - r - 1))

    def draw_ball(self, s, g):
        b = g.ball
        x, y = P(b.x, b.y, b.z * Z)
        self.draw_ball_at(s, x, y, b.spin)

    def draw_ball_shadow(self, s, g):
        b = g.ball
        k = max(0.35, 1.0 - (b.z - FB.BALL_R) / 7.0)
        w, h = round(22 * k), round(11 * k)
        sh = pygame.transform.smoothscale(self.shadow, (w, h))
        sh.set_alpha(round(255 * (0.4 + 0.6 * k)))
        gx, gy = P(b.x, b.y)
        s.blit(sh, (round(gx - w / 2), round(gy - h / 2)))

    # ------------------------------------------------------------ the goals
    def ripple(self, gl, y, z):
        """How far the back of the net bellies out (tiles) at (y, z px) after the ball hits it."""
        t = gl.net_t
        if t > 1.6:
            return 0.0
        hy, hz = gl.net_hit
        amp = 0.42 * math.exp(-t * 3.2) * (0.6 + 0.4 * math.cos(t * 16))
        return amp * math.exp(-((y - hy) ** 2) / 0.9 - ((z - hz * Z) / Z) ** 2 / 1.4)

    def mesh(self, f, fn, nu, nv, col, w=1):
        for i in range(nu + 1):
            u = i / nu
            pts = [fn(u, j / 8) for j in range(9)]
            pygame.draw.lines(f, col, False, pts, w)
        for j in range(nv + 1):
            v = j / nv
            pts = [fn(i / 10, v) for i in range(11)]
            pygame.draw.lines(f, col, False, pts, w)

    def net_part(self, s, gl, part):
        f = self.fx
        f.fill((0, 0, 0, 0))
        sd = gl.side
        x0, xb = gl.x, gl.back
        y0, y1 = FB.GOAL_Y0, FB.GOAL_Y1
        col = (*NET, 150)
        if part == "back":
            def fn(u, v):
                y, z = lerp(y0, y1, u), BAR * (1 - v)
                return P(xb - sd * self.ripple(gl, y, z), y, z)
            # a darker wash behind the cords so the net reads against the scenery
            poly(f, (20, 30, 24, 40), [P(xb, y0, 0), P(xb, y1, 0), P(xb, y1, BAR), P(xb, y0, BAR)])
            self.mesh(f, fn, 20, 13, col)
        elif part in ("side0", "side1"):
            y = y0 if part == "side0" else y1
            def fn(u, v):
                return P(lerp(x0, xb, u), y, BAR * (1 - v))
            self.mesh(f, fn, 4, 13, col)
        elif part == "roof":
            def fn(u, v):
                return P(lerp(x0, xb, v), lerp(y0, y1, u), BAR)
            self.mesh(f, fn, 20, 4, (*NET, 120))
        s.blit(f, (0, 0))
        # the back frame: thin grey tubes
        if part == "back":
            for y in (y0, y1):
                pygame.draw.line(s, FRAME, P(xb, y, 0), P(xb, y, BAR), 2)
            pygame.draw.line(s, FRAME, P(xb, y0, BAR), P(xb, y1, BAR), 2)
            pygame.draw.line(s, shade(FRAME, 0.8), P(xb, y0, 0), P(xb, y1, 0), 2)
        elif part in ("side0", "side1"):
            y = y0 if part == "side0" else y1
            pygame.draw.line(s, FRAME, P(x0, y, BAR), P(xb, y, BAR), 2)
            pygame.draw.line(s, shade(FRAME, 0.8), P(x0, y, 0), P(xb, y, 0), 2)

    def frame(self, s, gl):
        """The posts and crossbar on the goal line: white, round, with a shaded side."""
        dx = math.sin(gl.shake * 60) * gl.shake * 5
        y0, y1 = FB.GOAL_Y0, FB.GOAL_Y1

        def Q(y, z):
            x, yy = P(gl.x, y, z)
            return (x + dx, yy)
        for y in (y0, y1):
            pygame.draw.line(s, (150, 156, 166), Q(y, 0), Q(y, BAR), 7)
            pygame.draw.line(s, WHITE, (Q(y, 0)[0] - 1, Q(y, 0)[1]), (Q(y, BAR)[0] - 1, Q(y, BAR)[1]), 5)
        pygame.draw.line(s, (150, 156, 166), Q(y0, BAR + 1), Q(y1, BAR + 1), 7)
        pygame.draw.line(s, WHITE, Q(y0, BAR + 2), Q(y1, BAR + 2), 4)

    def draw_goal(self, s, g, gl, ball_inside):
        if gl.side > 0:
            # the far goal, seen from the pitch: back, left side, (ball), right side, roof, frame
            self.net_part(s, gl, "back")
            self.net_part(s, gl, "side0")
            if ball_inside:
                self.draw_ball(s, g)
            self.net_part(s, gl, "side1")
            self.net_part(s, gl, "roof")
            self.frame(s, gl)
        else:
            # the near goal, seen from behind: far side, frame, (ball), roof, near side, back
            self.net_part(s, gl, "side0")
            self.frame(s, gl)
            if ball_inside:
                self.draw_ball(s, g)
            self.net_part(s, gl, "roof")
            self.net_part(s, gl, "side1")
            self.net_part(s, gl, "back")

    # ------------------------------------------------------------ the scoreboard
    def draw_scoreboard(self, s, g, t):
        """The live score on the stand's scoreboard (drawn flat, then sheared onto the panel)."""
        w = round((ST.SB_X1 - ST.SB_X0) * 32) - 8
        hgt = round(ST.SB_Z1 - ST.SB_Z0) - 8
        im = pygame.Surface((w, hgt))
        im.fill((16, 18, 22))
        if g is None:
            a, b, na, nb = 0, 0, "HOME", "AWAY"
        else:
            a, b = g.p1.score, g.p2.score
            na, nb = g.p1.name.upper()[:6], g.p2.name.upper()[:6]
        amber = (255, 186, 60)
        flash = g is not None and g.state == "goal" and int(t * 6) % 2 == 0
        for txt, x in ((na, 4), (nb, w - 4)):
            ti = self.sb_small.render(txt, True, (240, 240, 240))
            r = ti.get_rect(topleft=(x, 2)) if x < w / 2 else ti.get_rect(topright=(x, 2))
            im.blit(ti, r)
        sc = self.sb_font.render(f"{a}", True, (255, 255, 255) if flash else amber)
        im.blit(sc, sc.get_rect(midtop=(w * 0.25, 12)))
        sc = self.sb_font.render(f"{b}", True, (255, 255, 255) if flash else amber)
        im.blit(sc, sc.get_rect(midtop=(w * 0.75, 12)))
        pygame.draw.rect(im, amber, (w / 2 - 4, 22, 8, 3))
        # shear: along the board (+x) the screen drops half a pixel per pixel
        out = pygame.Surface((w, hgt + w // 2 + 2), pygame.SRCALPHA)
        for x in range(w):
            out.blit(im, (x, x // 2), (x, 0, 1, hgt))
        X, Y = P(ST.SB_X0, ST.SB_Y, ST.SB_Z1)
        s.blit(out, (round(X + 4), round(Y + 4)))

    # ------------------------------------------------------------ the scene
    def draw_world(self, s, g, t, title=False):
        app = self.app
        sc = app.scene("stadium")
        s.blit(sc["bg"], (0, 0))
        self.draw_scoreboard(s, g, t)
        far, near = g.goals if g is not None else FB.make_goals()
        inside = g.ball.in_goal if g is not None else None
        held = g is not None and g.holder is not None
        if g is not None:
            b = g.ball
            if inside is None and b.x < 0:
                inside = far
            elif inside is None and b.x > N:
                inside = near
            self.draw_ball_shadow(s, g)
        self.draw_goal(s, g, far, g is not None and inside is far)
        rects = {}
        if g is not None:
            items = [(r.x + r.y, 0, r) for r in g.runners]
            if inside is None:
                items.append((g.ball.x + g.ball.y + (0.01 if held else 0), 1, g.ball))
            for _, k, o in sorted(items, key=lambda i: (i[0], i[1])):
                if k == 0:
                    rects[id(o)] = self.draw_player(s, g, o)
                else:
                    self.draw_ball(s, g)
        s.blit(sc["front"], (0, 0))
        self.draw_goal(s, g, near, g is not None and inside is near)
        if g is not None and g.state != "match_over":
            self.draw_goal_labels(s, g)
            if g.state == "play":
                self.draw_you(s, g, rects, t)
        return rects

    def draw_goal_labels(self, s, g):
        app = self.app
        for gl in g.goals:
            owner = g.p1 if g.p1.home is gl else g.p2
            if owner is g.p1 and not owner.ai:
                txt = "Your goal: keep it out"
            elif not g.p1.ai:
                txt = f"{owner.name}'s goal: shoot here"
            else:
                txt = f"{owner.name}'s goal"
            x, y = P(gl.x - gl.side * 0.5, gl.cy, BAR + 26)
            im = app.f_tiny.render(txt, True, (255, 255, 255))
            rr = pygame.Rect(0, 0, im.get_width() + 16, im.get_height() + 4)
            rr.center = (round(x), round(y))
            col = (200, 110, 30) if owner is g.p1 else (60, 90, 150)
            pygame.draw.rect(s, col, rr, border_radius=9)
            pygame.draw.rect(s, (255, 255, 255), rr, 1, border_radius=9)
            s.blit(im, im.get_rect(center=rr.center))

    def draw_you(self, s, g, rects, t):
        r = g.p1
        if r.ai or id(r) not in rects:
            return
        rc = rects[id(r)]
        x = rc.centerx
        y = max(rc.top - 10, 90) + math.sin(t * 5) * 2
        pygame.draw.polygon(s, (20, 24, 40), [(x - 9, y - 11), (x + 9, y - 11), (x, y + 1)])
        pygame.draw.polygon(s, (255, 220, 80), [(x - 7, y - 10), (x + 7, y - 10), (x, y - 1)])

    # ------------------------------------------------------------ the HUD
    def draw_hud(self, s, g, t):
        app = self.app
        bd = app.bd_view
        bar = pygame.Rect(10, 8, WIN_W - 20, 66)
        app.panel(s, bar, alpha=190)
        for side, r in ((0, g.p1), (1, g.p2)):
            por = app.portrait(r.kind, 54)
            label = r.name + (" (you)" if not r.ai else "")
            has = g.holder is r and g.state == "play"
            col = (255, 230, 120) if has else (230, 236, 250)
            sub = f"Goals {r.score}  ·  shots {r.shots}  ·  saves {r.saves}"
            if side == 0:
                s.blit(por, (bar.x + 10, bar.y + 6))
                x = bar.x + 20 + por.get_width()
                app.text(s, app.f_hud, label, col, (x, bar.y + 6))
                app.text(s, app.f_small, sub, (210, 216, 230), (x, bar.y + 36))
                bd.score_bar(s, r.score, g.target, x + 250, bar.y + 10, False)
            else:
                s.blit(por, (bar.right - 10 - por.get_width(), bar.y + 6))
                x = bar.right - 20 - por.get_width()
                app.text(s, app.f_hud, label, col, (x, bar.y + 6), "topright")
                app.text(s, app.f_small, sub, (210, 216, 230), (x, bar.y + 36), "topright")
                bd.score_bar(s, r.score, g.target, x - 250, bar.y + 10, True)
        cx = WIN_W // 2
        app.text(s, app.f_small_b, f"FOOTBALL  ·  first to {g.target}", (190, 200, 220), (cx, bar.y + 4), "midtop")
        app.text(s, app.f_mid, f"{g.p1.score} – {g.p2.score}", (255, 255, 255), (cx, bar.y + 28), "midtop")
        if g.state != "match_over":
            bd.draw_callouts(s, g)
        self.draw_banner(s, g)
        if g.state == "kickoff" and g.p1.score + g.p2.score == 0:
            b = g.holder
            who = "You kick off" if (b is g.p1 and not b.ai) else f"{b.name} kicks off"
            app.centre_card(s, [(app.f_big, "Football", (255, 230, 120)),
                                (app.f_mid, who, (255, 255, 255)),
                                (app.f_small, f"Score in the far goal, keep them out of yours. First to {g.target} wins.",
                                 (210, 216, 230))])
        elif g.state == "match_over":
            w = g.winner
            sc = f"{max(g.p1.score, g.p2.score)}–{min(g.p1.score, g.p2.score)}"
            if w is None:
                head, sub = f"A draw, {sc}!", "Nothing in it. Have another go."
            elif not g.p1.ai and w is g.p1:
                head, sub = f"{w.name} wins {sc}!", "What a finish! The robot wants a rematch."
            elif not g.p1.ai:
                head, sub = f"The {w.name} wins {sc}", "So close! Have another go."
            else:
                head, sub = f"{w.name} wins {sc}!", ""
            lines = [(app.f_big, head, (255, 230, 120))]
            for r in g.runners:
                lines.append((app.f_hud, f"{r.name}: {r.score} goal{'s' if r.score != 1 else ''} from {r.shots} "
                              f"shot{'s' if r.shots != 1 else ''}, {r.saves} save{'s' if r.saves != 1 else ''}",
                              (235, 240, 250)))
            if sub:
                lines.append((app.f_hud, sub, (235, 240, 250)))
            lines.append((app.f_small, "Press Enter for the title screen", (190, 200, 220)))
            app.centre_card(s, lines)

    def draw_banner(self, s, g):
        if g.state not in ("play", "goal", "kickoff"):
            return
        if g.state == "kickoff" and g.p1.score + g.p2.score == 0:
            return
        app = self.app
        h, o = g.p1, g.p2
        meter = False
        if g.state in ("goal", "kickoff"):
            nb = g.next_ball if g.state == "goal" else g.holder
            sc = g.last_goal[0] if g.last_goal else None
            head = ("You scored!" if (sc is h and not h.ai) else f"Goal for {sc.name}!") if sc else ""
            nxt = "you kick off" if (nb is h and not h.ai) else f"{nb.name} kicks off" if nb else ""
            msg = f"{head}  {nxt[0].upper() + nxt[1:]}" if g.state == "goal" else (nxt[0].upper() + nxt[1:])
            col = (90, 90, 110)
        elif h.ai:
            if g.holder is not None:
                msg = f"{g.holder.name} on the ball"
            elif g.ball.shot_by is not None:
                msg = f"{g.ball.shot_by.name} shoots…"
            else:
                msg = "Loose ball!"
            col = (40, 100, 190)
        elif g.holder is h:
            msg = "Your ball: hold Space and let go in the green to shoot"
            col = (200, 110, 30)
            meter = True
        elif g.ball.shot_by is h:
            msg = "Shot's away…"
            col = (200, 110, 30)
        elif g.ball.shot_by is o and abs(h.x - h.home.x) < 3.0:
            msg = "Shot! Space to dive"
            col = (170, 50, 60)
        elif g.holder is o:
            msg = "Defend! Space to slide-tackle – or get back in goal"
            col = (40, 120, 70)
        else:
            msg = "Loose ball – get to it!"
            col = (40, 120, 70)
        im = app.f_hud.render(msg, True, (255, 255, 255))
        r = pygame.Rect(0, 0, im.get_width() + 36, im.get_height() + 12)
        r.bottomleft = (16, WIN_H - 14)
        pygame.draw.rect(s, shade(col, 0.6), r.move(0, 3), border_radius=18)
        pygame.draw.rect(s, col, r, border_radius=18)
        s.blit(im, im.get_rect(center=r.center))
        if meter:
            self.draw_meter(s, g, pygame.Rect(r.right + 14, r.y + 4, 200, r.h - 8))

    def draw_meter(self, s, g, pr):
        h = g.p1
        d = math.hypot(h.x - h.goal.x, h.y - h.goal.cy)
        ideal = FB.ideal_power(d)
        sw = FB.sweet(d)
        pygame.draw.rect(s, (30, 34, 50), pr, border_radius=8)
        gz = pygame.Rect(pr.x + round(pr.w * max(0, ideal - sw)), pr.y + 2, max(4, round(pr.w * 2 * sw)), pr.h - 4)
        pygame.draw.rect(s, (70, 190, 90), gz, border_radius=5)
        # past the green the ball balloons over: a red end
        hi = pygame.Rect(pr.x + round(pr.w * min(1, ideal + sw + 0.12)), pr.y + 2, 0, pr.h - 4)
        hi.w = max(0, pr.right - 2 - hi.x)
        if hi.w:
            pygame.draw.rect(s, (170, 60, 50), hi, border_radius=5)
        if h.charging:
            x = pr.x + round(pr.w * h.power)
            inside = abs(h.power - ideal) <= sw
            pygame.draw.rect(s, (255, 255, 255) if inside else (255, 200, 80), (x - 3, pr.y - 4, 6, pr.h + 8), border_radius=3)
            pygame.draw.rect(s, (20, 24, 40), (x - 3, pr.y - 4, 6, pr.h + 8), 1, border_radius=3)
        pygame.draw.rect(s, (255, 255, 255), pr, 2, border_radius=8)
        if not h.charging:
            app = self.app
            app.text(s, app.f_tiny, "power", (255, 255, 255), (pr.x + 10, pr.centery), "midleft", False)
