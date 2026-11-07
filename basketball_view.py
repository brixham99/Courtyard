"""Drawing Basketball on the city court: the hoops (posts, backboards, rims
and nets), the players posed from their own sprites, the ball with its height
shadow, and the HUD. Used by game.App; the rules are in basketball.py."""
import functools
import math

import pygame
import aa

import basketball as BB
import poses
import traffic
from iso import WIN_W, WIN_H, N, P, shade, mix, poly, quad_x, quad_y, quad_z, box

Z = BB.ZPX
ORANGE = (232, 112, 36)
SEAM = (50, 26, 14)
RIM = (236, 84, 40)
POST = (54, 70, 104)
NET = (250, 250, 250)


def lerp(a, b, k):
    return a + (b - a) * k


class BasketballView:
    def __init__(self, app):
        self.app = app
        self.posers = app.bd_view.posers
        self.fx = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        self.shadow = pygame.Surface((30, 15), pygame.SRCALPHA)
        aa.ellipse(self.shadow, (12, 12, 18, 140), self.shadow.get_rect())

    # ------------------------------------------------------------ poses
    def pose_for(self, g, r):
        """(a_active, a_off, crouch, lift px) or None for the plain sprite."""
        t, a = r.anim_t, r.anim
        lift = 0.0
        if r.jump_t is not None:
            lift = BB.JUMP_H * Z * math.sin(math.pi * min(1.0, r.jump_t / BB.JUMP_S))
        if r.charging or (a == "set" and g.holder is r):
            return 172, -168, False, 0.0
        if a == "release" and t < 0.45:
            k = min(1.0, t / 0.12)
            return lerp(172, 140, k), lerp(-168, -150, k), False, lift
        if a == "jump" and r.jump_t is not None:
            if g.holder is not None and g.holder is not r and not g.holder.charging and g.ball.shot_by is None:
                return 85, -160, False, lift * 0.6     # a swipe at the ball
            return 168, -165, False, lift
        if a == "cheer":
            w = math.sin(t * 12) * 12
            return 150 + w, -150 - w, False, 0.0
        if g is not None and g.holder is r and r.moved <= 0:
            return 28, 6, False, 0.0
        return None

    def draw_player(self, s, g, r):
        app = self.app
        ch = app.chars[r.kind]
        key = r.sprite_key
        gx, gy = P(r.x, r.y)
        pose = self.pose_for(g, r) if g is not None else None
        s.blit(app.contact, (round(gx - 16), round(gy - 6)))
        moving = r.moved > 0
        img, (shd, (sx, sy)) = ch.frame(key, r.walk_phase, moving)
        s.blit(shd, (round(gx + sx), round(gy + sy)))
        hands = None
        if pose is None or (moving and pose[3] == 0 and not r.charging):
            bob = abs(math.sin(r.walk_phase / ch.cycle * 2 * math.pi)) * 2.0 if moving else 0
            ax, ay = ch.anchor[key]
            x0, y0 = round(gx - ax), round(gy - ay - bob)
            s.blit(img, (x0, y0))
            rect = pygame.Rect(x0, y0, img.get_width(), img.get_height())
        else:
            a_ang, ao, crouch, lift = pose
            p = self.posers[r.kind]
            act = 1 if poses.FORWARD[key] > 0 else 0
            angs = [0, 0]
            angs[act] = a_ang
            angs[1 - act] = ao
            hands = p.draw(s, key, (gx, gy - lift), ch.anchor[key], angs[0], angs[1], crouch)
            ax, ay = ch.anchor[key]
            rect = pygame.Rect(round(gx - ax), round(gy - ay - lift), img.get_width(), img.get_height())
        # the ball held up for a shot, in both hands over the head
        if g is not None and g.holder is r and r.charging and hands:
            hx = (hands[0][0] + hands[1][0]) / 2
            hy = min(hands[0][1], hands[1][1]) - 7
            self.draw_ball_at(s, hx, hy, g.ball.spin)
        return rect

    # ------------------------------------------------------------ the ball
    def draw_ball_at(self, s, x, y, spin, r=9):
        x, y = round(x), round(y)
        aa.circle(s, shade(ORANGE, 0.55), (x + 1, y + 1), r)
        aa.circle(s, ORANGE, (x, y), r)
        aa.circle(s, shade(ORANGE, 0.8), (x + 2, y + 2), r - 2, 0)
        aa.circle(s, ORANGE, (x - 1, y - 1), r - 3)
        # seams: one round the middle (turning with the spin) and a curved one
        a = spin
        ca, sa = math.cos(a), math.sin(a)
        aa.line(s, SEAM, (x - ca * r, y - sa * r), (x + ca * r, y + sa * r), 1)
        aa.line(s, SEAM, (x + sa * r, y - ca * r), (x - sa * r, y + ca * r), 1)
        k = 0.55
        aa.arc(s, SEAM, (x - r - r * k * ca, y - r - r * k * sa, 2 * r, 2 * r), a - 1.0, a + 1.0, 1)
        aa.circle(s, (255, 196, 140), (x - 3, y - 4), 2)
        aa.circle(s, SEAM, (x, y), r, 1)

    def draw_ball(self, s, g):
        b = g.ball
        x, y = P(b.x, b.y, b.z * Z)
        self.draw_ball_at(s, x, y, b.spin)

    def draw_ball_shadow(self, s, g):
        b = g.ball
        k = max(0.35, 1.0 - b.z / 9.0)
        w, h = round(26 * k), round(13 * k)
        sh = pygame.transform.smoothscale(self.shadow, (w, h))
        sh.set_alpha(round(255 * (0.45 + 0.55 * k)))
        gx, gy = P(b.x, b.y)
        s.blit(sh, (round(gx - w / 2), round(gy - h / 2)))

    # ------------------------------------------------------------ the hoops
    def draw_post(self, s, hp):
        from scene import _cyl, _disc
        top = (hp.z0 + 0.35) * Z
        # its shadow on the tarmac (west)
        d = top * 0.55 / 32 / 2
        sh = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        w = 0.1
        aa.polygon(sh, (12, 12, 18, 60), [P(hp.post_x + w, hp.cy - w), P(hp.post_x + w - d, hp.cy - w + d),
                                                    P(hp.post_x - w - d, hp.cy + w + d), P(hp.post_x - w, hp.cy + w)])
        s.blit(sh, (0, 0))
        # padding round the bottom, then the steel post
        _cyl(s, hp.post_x, hp.cy, 0.2, 0, 52, (40, 80, 160))
        _disc(s, hp.post_x, hp.cy, 0.2, 52, (60, 104, 190))
        _cyl(s, hp.post_x, hp.cy, 0.12, 52, top, POST)
        # the arm out to the board (a box along x)
        za = top - 26
        x0, x1 = sorted((hp.post_x, hp.bx))
        box(s, x0, hp.cy - 0.07, x1, hp.cy + 0.07, 9, POST, z0=za)
        # a diagonal brace
        aa.line(s, shade(POST, 0.9), P(hp.post_x, hp.cy, za - 50), P((hp.post_x + hp.bx) / 2, hp.cy, za), 4)

    def draw_board(self, s, hp, title=False):
        z0, z1 = hp.z0 * Z, hp.z1 * Z
        q = quad_x(hp.bx, hp.y0, hp.y1, z0, z1)
        if hp.side > 0:
            # the front of the far board: white, with the target square and a thick frame
            poly(s, (246, 246, 242), q)
            poly(s, (210, 214, 220), quad_x(hp.bx, hp.y0, hp.y1, z0, z0 + 4))
            sq = quad_x(hp.bx, hp.cy - 0.38, hp.cy + 0.38, (BB.RIM_Z + 0.03) * Z, (BB.RIM_Z + 0.03) * Z + 36)
            poly(s, RIM, sq, 3)
            poly(s, (40, 46, 60), q, 3)
            # the edge (thickness) seen from the side
            poly(s, (170, 176, 186), quad_y(hp.y1, hp.bx - 0.06, hp.bx, z0, z1))
        else:
            # the back of the near board: perspex, so you can see the rim and the ball through it
            glass = self.fx
            glass.fill((0, 0, 0, 0))
            poly(glass, (220, 236, 248, 70), q)
            poly(glass, (255, 255, 255, 120), [P(hp.bx, hp.y0 + 0.15, z1 - 6), P(hp.bx, hp.y0 + 0.55, z1 - 6),
                                                P(hp.bx, hp.y0 + 0.15, z1 - 30)])
            s.blit(glass, (0, 0))
            poly(s, (40, 46, 60), q, 4)
            poly(s, (200, 204, 212), quad_y(hp.y1, hp.bx, hp.bx + 0.06, z0, z1))
            # the bracket where the arm meets the board
            aa.line(s, POST, P(hp.bx, hp.cy - 0.4, z0 + 20), P(hp.bx, hp.cy + 0.4, z0 + 20), 4)
            aa.line(s, POST, P(hp.bx, hp.cy - 0.4, z1 - 20), P(hp.bx, hp.cy + 0.4, z1 - 20), 4)

    def rim_points(self, hp, half, n=24):
        """Points round the rim; half='back' (away from us) or 'front'."""
        shake = math.sin(hp.shake * 60) * hp.shake * 6
        pts = []
        for i in range(n + 1):
            # the back half runs through angles where x + y decreases (screen up)
            a = (math.pi * 0.75 + math.pi * i / n) if half == "back" else (-math.pi * 0.25 + math.pi * i / n)
            pts.append(P(hp.cx + BB.RIM_R * math.cos(a), hp.cy + BB.RIM_R * math.sin(a), BB.RIM_Z * Z + shake))
        return pts

    def draw_rim(self, s, hp, half):
        pts = self.rim_points(hp, half)
        if half == "back":
            # the bracket from the board to the rim
            aa.line(s, shade(RIM, 0.7), P(hp.bx, hp.cy, BB.RIM_Z * Z - 2),
                             P(hp.cx - hp.side * BB.RIM_R, hp.cy, BB.RIM_Z * Z), 4)
            aa.lines(s, shade(RIM, 0.75), False, pts, 4)
        else:
            self.draw_net(s, hp)
            aa.lines(s, RIM, False, pts, 4)
            aa.lines(s, shade(RIM, 1.25), False, [(x, y - 1) for x, y in pts[3:-3]], 1)

    def draw_net(self, s, hp):
        """A white cord net hanging from the rim, flicking when the ball goes through."""
        t = hp.net_t
        swing = math.sin(t * 22) * math.exp(-t * 4) if t < 2 else 0.0
        L = 0.62 + 0.12 * max(0.0, 1 - t / 0.5) * (1 if t < 0.5 else 0)
        n = 16
        rz = BB.RIM_Z
        top = []
        mid = []
        bot = []
        for i in range(n):
            a = 2 * math.pi * i / n
            top.append(P(hp.cx + BB.RIM_R * math.cos(a), hp.cy + BB.RIM_R * math.sin(a), rz * Z))
            mid.append(P(hp.cx + BB.RIM_R * 0.8 * math.cos(a + 0.2) + swing * 0.06, hp.cy + BB.RIM_R * 0.8 * math.sin(a + 0.2),
                         (rz - L * 0.5) * Z))
            bot.append(P(hp.cx + BB.RIM_R * 0.55 * math.cos(a) + swing * 0.12, hp.cy + BB.RIM_R * 0.55 * math.sin(a),
                         (rz - L) * Z))
        net = self.fx
        net.fill((0, 0, 0, 0))
        col = (*NET, 190)
        for i in range(n):
            j = (i + 1) % n
            pygame.draw.aaline(net, col, top[i], mid[j])
            pygame.draw.aaline(net, col, top[j], mid[i])
            pygame.draw.aaline(net, col, mid[i], bot[j])
            pygame.draw.aaline(net, col, mid[j], bot[i])
        pygame.draw.aalines(net, col, True, mid)
        pygame.draw.aalines(net, col, True, bot)
        s.blit(net, (0, 0))

    # ------------------------------------------------------------ the scene
    def draw_world(self, s, g, t, title=False):
        app = self.app
        sc = app.scene("city")
        s.blit(sc["bg"], (0, 0))
        traffic.draw_shadows(s, app.t)
        hoops = g.hoops if g is not None else BB.make_hoops()
        if g is not None and not (g.holder is not None and g.holder.charging):
            self.draw_ball_shadow(s, g)
        if g is not None and g.state == "play" and not g.p1.ai and g.holder is g.p1:
            self.draw_arc_hint(s, g)
        items = []
        for hi, hp in enumerate(hoops):
            for part in ("post", "board", "rimback", "rimfront"):
                items.append((part, hp, hi))
        if g is not None:
            for r in g.runners:
                items.append(("run", r, None))
            if not (g.holder is not None and g.holder.charging):
                items.append(("ball", g.ball, None))
        order = {"post": 0, "board": 1, "rimback": 2, "rimfront": 3}
        near_order = {"rimback": 0, "rimfront": 1, "board": 2, "post": 3}

        def fixed_rank(it):
            k, hp, hi = it
            return hi * 10 + (order if hp.side > 0 else near_order)[k]

        def mover_in_front(m, it, is_ball):
            k, hp, hi = it
            if k in ("post", "board"):
                plane = hp.post_x if k == "post" else hp.bx
                y0, y1 = (hp.cy - 0.15, hp.cy + 0.15) if k == "post" else (hp.y0, hp.y1)
                if m.y > y1:
                    return True
                if m.y < y0:
                    return False
                return m.x > plane
            # the rim
            if is_ball:
                dh = math.hypot(m.x - hp.cx, m.y - hp.cy)
                if dh < BB.RIM_R + BB.BALL_R and abs(m.z - BB.RIM_Z) < 1.0:
                    return k == "rimback"
            return (m.x + m.y) > (hp.cx + hp.cy) if k == "rimfront" else (m.x + m.y) > (hp.cx + hp.cy) - 0.4

        def cmp(a, b):
            ka, kb = a[0], b[0]
            ma, mb = ka in ("run", "ball"), kb in ("run", "ball")
            if ma and mb:
                return 1 if a[1].x + a[1].y > b[1].x + b[1].y else -1
            if ma:
                return 1 if mover_in_front(a[1], b, ka == "ball") else -1
            if mb:
                return -1 if mover_in_front(b[1], a, kb == "ball") else 1
            return 1 if fixed_rank(a) > fixed_rank(b) else -1

        # insertion by comparison (a handful of items; robust to the odd cycle)
        ordered = []
        for it in sorted(items, key=lambda i: fixed_rank(i) if i[0] not in ("run", "ball") else 100):
            if it[0] not in ("run", "ball"):
                ordered.append(it)
        for it in items:
            if it[0] in ("run", "ball"):
                pos = len(ordered)
                # just after the last thing it must be in front of
                for i in range(len(ordered) - 1, -1, -1):
                    if cmp(it, ordered[i]) > 0:
                        pos = i + 1
                        break
                else:
                    pos = 0
                # but before anything after that it must be behind
                ordered.insert(pos, it)
        rects = {}
        for k, o, hi in ordered:
            if k == "run":
                rects[id(o)] = self.draw_player(s, g, o)
            elif k == "ball":
                self.draw_ball(s, g)
            elif k == "post":
                self.draw_post(s, o)
            elif k == "board":
                self.draw_board(s, o, title)
            elif k == "rimback":
                self.draw_rim(s, o, "back")
            elif k == "rimfront":
                self.draw_rim(s, o, "front")
        s.blit(sc["front"], (0, 0))
        # the odd black cab or red bus on the roads beyond, then the far pavements' lamps and bins
        traffic.draw(s, app.t)
        if "street" not in sc:
            import city
            sc["street"] = city.build_city_street()
        s.blit(sc["street"], (0, 0))
        if g is not None and g.state != "match_over":
            self.draw_hoop_labels(s, g)
            if g.state == "play":
                self.draw_you(s, g, rects, t)
        return rects

    def draw_arc_hint(self, s, g):
        """While you have the ball: the three-point line you're behind lights up."""
        r = g.p1
        hp = r.goal
        d = math.hypot(r.x - hp.cx, r.y - hp.cy)
        if d < BB.ARC_R:
            return
        f = self.fx
        f.fill((0, 0, 0, 0))
        ang = math.asin(3.7 / BB.ARC_R)
        pts = [P(hp.cx + hp.side * BB.ARC_R * math.cos(a), 7 + BB.ARC_R * math.sin(a)) for a in [-ang + 2 * ang * i / 40 for i in range(41)]]
        aa.lines(f, (255, 230, 90, 200), False, pts, 5)
        s.blit(f, (0, 0))

    def draw_hoop_labels(self, s, g):
        app = self.app
        for hp in g.hoops:
            if hp.side > 0 and g.callouts:
                continue            # the far label sits where the callouts go
            owner = g.p1 if g.p1.goal is hp else g.p2
            # Say who shoots where, so it can't be mixed up with football,
            # where "Your goal" is the one you defend.
            if owner is g.p1 and not owner.ai:
                txt = "You shoot here"
            else:
                txt = f"{owner.name} shoots here"
            x, y = P(hp.bx, hp.cy, hp.z1 * Z + 18)
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
        top = rc.top - (34 if r.charging or r.jump_t is not None else 10)
        y = max(top, 90) + math.sin(t * 5) * 2
        aa.polygon(s, (20, 24, 40), [(x - 9, y - 11), (x + 9, y - 11), (x, y + 1)])
        aa.polygon(s, (255, 220, 80), [(x - 7, y - 10), (x + 7, y - 10), (x, y - 1)])

    # ------------------------------------------------------------ the HUD
    def draw_hud(self, s, g, t):
        app = self.app
        bd = app.bd_view
        bar = pygame.Rect(10, 8, WIN_W - 20, 66)
        app.panel(s, bar, alpha=228)
        for side, r in ((0, g.p1), (1, g.p2)):
            por = app.portrait(r.kind, 54)
            label = r.name + (" (you)" if not r.ai else "")
            has = g.holder is r and g.state == "play"
            col = (255, 230, 120) if has else (230, 236, 250)
            sub = f"Baskets {r.made2 + r.made3}  ·  threes {r.made3}"
            if side == 0:
                s.blit(por, (bar.x + 10, bar.y + 6))
                x = bar.x + 20 + por.get_width()
                app.text(s, app.f_hud, label, col, (x, bar.y + 6))
                app.text(s, app.f_small, sub, (210, 216, 230), (x, bar.y + 36))
                bd.score_bar(s, r.score, g.target, x + 190, bar.y + 10, False)
            else:
                s.blit(por, (bar.right - 10 - por.get_width(), bar.y + 6))
                x = bar.right - 20 - por.get_width()
                app.text(s, app.f_hud, label, col, (x, bar.y + 6), "topright")
                app.text(s, app.f_small, sub, (210, 216, 230), (x, bar.y + 36), "topright")
                bd.score_bar(s, r.score, g.target, x - 190, bar.y + 10, True)
        cx = WIN_W // 2
        app.text(s, app.f_small_b, f"BASKETBALL  ·  first to {g.target}", (190, 200, 220), (cx, bar.y + 4), "midtop")
        app.text(s, app.f_mid, f"{g.p1.score} – {g.p2.score}", (255, 255, 255), (cx, bar.y + 28), "midtop")
        # the shot clock
        if g.holder is not None and g.state == "play":
            sc = max(0.0, g.shot_clock)
            hot = sc < 4
            br = pygame.Rect(0, 0, 44, 30)
            br.midleft = (cx + 62, bar.y + 44)
            pygame.draw.rect(s, (30, 20, 20), br, border_radius=6)
            col = (255, 80, 70) if hot and int(sc * 4) % 2 == 0 else (255, 196, 80)
            pygame.draw.rect(s, col, br, 2, border_radius=6)
            app.text(s, app.f_hud, f"{math.ceil(sc - 1e-6)}", col, br.center, "center", False)
            app.text(s, app.f_tiny, "shot clock", (190, 200, 220), (br.right + 6, br.centery), "midleft", False)
        if g.state != "match_over":
            bd.draw_callouts(s, g)
        self.draw_banner(s, g)
        if g.state == "tipoff":
            b = g.holder
            who = "You have" if (b is g.p1 and not b.ai) else f"{b.name} has"
            app.centre_card(s, [(app.f_big, "Basketball", (255, 230, 120)),
                                (app.f_mid, f"{who} the first ball", (255, 255, 255)),
                                (app.f_small, "2 points a basket, 3 from beyond the arc. First to 21 wins.", (210, 216, 230))])
        elif g.state == "match_over":
            w = g.winner
            sc = f"{max(g.p1.score, g.p2.score)}–{min(g.p1.score, g.p2.score)}"
            if w is None:
                head, sub = f"A draw, {sc}!", "Nothing in it. Have another go."
            elif not g.p1.ai and w is g.p1:
                head, sub = f"{w.name} wins {sc}!", "Brilliant shooting! The Robot wants a rematch."
            elif not g.p1.ai:
                head, sub = f"The {w.name} wins {sc}", "So close! Have another go."
            else:
                head, sub = f"{w.name} wins {sc}!", ""
            lines = [(app.f_big, head, (255, 230, 120))]
            for r in g.runners:
                n = r.made2 + r.made3
                lines.append((app.f_hud, f"{r.name}: {n} basket{'s' if n != 1 else ''} ({r.made3} three{'s' if r.made3 != 1 else ''}) from {r.shots} shot{'s' if r.shots != 1 else ''}",
                              (235, 240, 250)))
            if sub:
                lines.append((app.f_hud, sub, (235, 240, 250)))
            lines.append((app.f_small, app.enter_title_line(), (190, 200, 220)))
            app.centre_card(s, lines)

    def draw_banner(self, s, g):
        if g.state not in ("play", "scored"):
            return
        app = self.app
        h = g.p1
        o = g.p2
        meter = False
        if g.state == "scored":
            nb = g.next_ball
            if nb is None:
                msg = "Change of possession"
            elif nb is h and not h.ai:
                msg = "Your ball next, under the far hoop"
            else:
                msg = f"{nb.name}'s ball next"
            col = (90, 90, 110)
        elif h.ai:
            if g.holder is not None:
                msg = f"{g.holder.name} has the ball"
            elif g.ball.shot_by is not None:
                msg = f"{g.ball.shot_by.name} shoots…"
            else:
                msg = "Loose ball!"
            col = (40, 100, 190)
        elif g.holder is h:
            d = math.hypot(h.x - h.goal.cx, h.y - h.goal.cy)
            pts = 3 if d >= BB.ARC_R else 2
            act = app.pads.hints.action
            msg = f"Your ball: hold {act} and let go in the green to shoot  ·  {pts} points from here"
            col = (200, 110, 30)
            meter = True
        elif g.holder is o:
            msg = f"Defend! {app.pads.hints.action} to swipe for a steal, or jump as {o.name} shoots"
            col = (40, 120, 70)
        elif g.ball.shot_by is not None:
            msg = "Shot's up! Get ready for the rebound"
            col = (40, 120, 70)
        else:
            msg = "Loose ball – grab it!"
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
        d = math.hypot(h.x - h.goal.cx, h.y - h.goal.cy)
        ideal = BB.ideal_power(d)
        sw = BB.sweet(d)
        pygame.draw.rect(s, (30, 34, 50), pr, border_radius=8)
        # the green zone
        gz = pygame.Rect(pr.x + round(pr.w * max(0, ideal - sw)), pr.y + 2, max(4, round(pr.w * 2 * sw)), pr.h - 4)
        pygame.draw.rect(s, (70, 190, 90), gz, border_radius=5)
        if h.charging:
            x = pr.x + round(pr.w * h.power)
            inside = abs(h.power - ideal) <= sw
            pygame.draw.rect(s, (255, 255, 255) if inside else (255, 200, 80), (x - 3, pr.y - 4, 6, pr.h + 8), border_radius=3)
            pygame.draw.rect(s, (20, 24, 40), (x - 3, pr.y - 4, 6, pr.h + 8), 1, border_radius=3)
        pygame.draw.rect(s, (255, 255, 255), pr, 2, border_radius=8)
        if not h.charging:
            app = self.app
            app.text(s, app.f_tiny, "power", (255, 255, 255), (pr.x + 10, pr.centery), "midleft", False)
