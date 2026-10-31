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


def batdown(out):
    """Batdown screenshots: python game.py --shots-batdown DIR"""
    import batdown as B
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.makedirs(out, exist_ok=True)
    app = G.App(sound=False)
    bd = [n for n, _ in G.GAMES].index("Batdown")
    app.sel_game = bd
    app.t = 0.4
    app.draw(); pygame.image.save(app.screen, os.path.join(out, "batdown_title.png"))

    def save(name, as_human=True):
        g = app.game
        was = g.p1.ai
        if as_human:
            g.p1.ai = False          # draw it as the player sees it (the frame itself was played by the AI)
        app.draw()
        g.p1.ai = was
        pygame.image.save(app.screen, os.path.join(out, name))

    def game_where(p1_bats, seed0=200):
        for sd in range(seed0, seed0 + 50):
            app.sel_char = 0
            app.start_game(player_ai=True, seed=sd)
            if (app.game.batter is app.game.p1) == p1_bats:
                return sd

    # batting: Archie at the crease, the robot's throw on its way in
    game_where(True)
    g = app.game
    run_until(app, lambda a: g.state == "play" and g.phase == "flight" and g.flight_t > 0.42 and g.batter is g.p1, limit=60 * 60)
    save("batdown_batting.png")
    # the hit: just after bat meets ball
    run_until(app, lambda a: g.phase == "hit" and g.ball.age > 0.15 or g.state != "play", limit=60 * 10)
    save("batdown_hit.png")
    # fielding: Archie chasing the ball, the chalk X down
    game_where(False, 300)
    g = app.game
    run_until(app, lambda a: g.state == "play" and g.phase == "fetch" and not g.fielder.holding and g.ball.age > 0.6
              and g.fielder is g.p1, limit=60 * 120)
    save("batdown_fielding.png")
    # throw: Archie (really human-controlled) on the bowling mark, aiming with the power up
    sd = game_where(False, 400)
    app.start_game(player_ai=False, seed=sd)
    g = app.game
    run_until(app, lambda a: g.state == "play", limit=60 * 5)
    app.held_turn = [pygame.K_RIGHT]
    for _ in range(12):
        app.update(1 / 60)
    app.held_turn = []
    g.press("space")
    for _ in range(int(60 * 1.0)):
        app.update(1 / 60)
    app.draw(); pygame.image.save(app.screen, os.path.join(out, "batdown_throw.png"))
    # the robot's throw in the air
    game_where(True, 500)
    g = app.game
    run_until(app, lambda a: g.state == "play" and g.phase == "flight" and 0.1 < g.flight_t < 0.2, limit=60 * 60)
    save("batdown_throw_flight.png")
    # a swap: bat down (or caught)
    for sd in range(600, 640):
        app.start_game(player_ai=True, seed=sd)
        g = app.game
        ok = run_until(app, lambda a: g.state == "swap" and g.swap_reason == "bat" and 3.95 < g.state_t < 4.05 or g.state == "match_over",
                       limit=60 * 200)
        if ok and g.state == "swap":
            break
    save("batdown_swap.png")
    run_until(app, lambda a: g.state == "swap" and g.state_t < 2.8 or g.state == "play", limit=60 * 10)
    save("batdown_swap_walk.png")
    # the end
    run_until(app, lambda a: g.state == "match_over", limit=60 * 600)
    save("batdown_match_over.png", as_human=False)
    print("batdown shots in", out)
