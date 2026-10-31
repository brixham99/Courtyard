"""Screenshots for review: python game.py --shots DIR (headless is fine)."""
import os
import pygame
import tag
import game as G


def run_until(app, cond, limit=60 * 120, dt=1 / 60):
    for _ in range(limit):
        app.update(dt, auto=True)
        if cond(app):
            return True
    return False


def main(out):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.makedirs(out, exist_ok=True)
    app = G.App(sound=False)
    # title
    app.t = 0.4
    app.draw(); pygame.image.save(app.screen, os.path.join(out, "title.png"))
    app.sel_char = 1; app.t = 1.0
    app.draw(); pygame.image.save(app.screen, os.path.join(out, "title_holly.png"))
    # robot sprite sheet: the 4 facings x 8 walk frames, on grass, plus the painted sources
    ch = app.chars["robot"]
    W = 8 * 70 + 40
    sheet = pygame.Surface((W + 260, 4 * 130 + 60))
    sheet.fill((92, 140, 70))
    f = G.load_font(16, True)
    for r, key in enumerate(("se", "sw", "nw", "ne")):
        sheet.blit(f.render(key.upper(), True, (255, 255, 255)), (8, 40 + r * 130 + 50))
        for i, img in enumerate(ch.walk[key]):
            sheet.blit(img, (40 + i * 70, 30 + r * 130))
    big = pygame.image.load(os.path.join(G.CH_DIR, "robot_se.png")).convert_alpha()
    sheet.blit(big, (W + 30, 30))
    big = pygame.image.load(os.path.join(G.CH_DIR, "robot_ne.png")).convert_alpha()
    sheet.blit(big, (W + 140, 30))
    sheet.blit(f.render("Robot: 4 facings x 8 walk frames (in-game size); right: full size", True, (255, 255, 255)), (8, 6))
    pygame.image.save(sheet, os.path.join(out, "robot_sprite_sheet.png"))
    # gameplay with each character (human-controlled p1 standing in for a player)
    for idx, name in ((0, "archie"), (1, "holly")):
        app.sel_char = idx
        app.start_game(player_ai=True, seed=10 + idx)
        import iso
        def apart(a):
            g = a.game
            if not (g.state == "playing" and g.clock < g.round_s - 6):
                return False
            p, q = iso.P(g.p1.x, g.p1.y), iso.P(g.p2.x, g.p2.y)
            return abs(p[0] - q[0]) > 140 and 3 < g.p1.x + g.p1.y < 22
        run_until(app, apart)
        app.draw(); pygame.image.save(app.screen, os.path.join(out, f"play_{name}.png"))
    # a tag moment
    app.sel_char = 0
    app.start_game(player_ai=True, seed=4)
    seen = {"n": 0}

    def tagged(a):
        g = a.game
        if g.tag_fx and 0.12 < g.tag_fx[-1][2] < 0.2:
            seen["n"] += 1
            return seen["n"] >= 2
        return False
    run_until(app, tagged)
    app.draw(); pygame.image.save(app.screen, os.path.join(out, "tag_moment.png"))
    # the counting-to-3 freeze just after
    run_until(app, lambda a: any(0.6 < r.frozen < 0.8 for r in a.game.runners))
    app.draw(); pygame.image.save(app.screen, os.path.join(out, "counting.png"))
    # round over card
    run_until(app, lambda a: a.game.state in ("round_over", "match_over"), limit=60 * 90)
    app.game.state_t = 3.0
    app.draw(); pygame.image.save(app.screen, os.path.join(out, "round_over.png"))
    # match over: play the rest with a human-style p1 that just stands still (robot should win)
    app.sel_char = 1
    app.start_game(player_ai=False, seed=5, round_s=20)
    while app.game.state != "match_over":
        app.update(1 / 30)
        if app.game.state == "round_over":
            app.game.continue_()
    app.draw(); pygame.image.save(app.screen, os.path.join(out, "match_over.png"))
    print("shots in", out)
