"""Put the 1280×720 game on a television without a mode switch.

The drawing code all uses the internal resolution (iso.WIN_W × WIN_H). In a
window that surface is the window. Full-screen (Zen Station, or --fullscreen)
opens a borderless window at the display's native size and scales the internal
frame into it, keeping the aspect ratio. 16:9 televisions (1080p is 1.5×,
4K is exactly 3×) get no bars. Anything else is letterboxed or pillarboxed
in black.

Scaling stays off the Python pixel loops. An exact integer multiple (4K) uses
nearest-neighbour, which is pixel-perfect at 3× and the cheaper blit. Other
factors use smoothscale. The destination surface is reused, so a frame does
not allocate.
"""
import pygame

from iso import WIN_H, WIN_W


def fit_rect(src_w, src_h, dst_w, dst_h):
    """Where the internal frame sits inside the display. (x, y, w, h), centred."""
    if src_w <= 0 or src_h <= 0 or dst_w <= 0 or dst_h <= 0:
        return (0, 0, max(1, dst_w), max(1, dst_h))
    scale = min(dst_w / src_w, dst_h / src_h)
    dw = min(dst_w, max(1, int(round(src_w * scale))))
    dh = min(dst_h, max(1, int(round(src_h * scale))))
    x = (dst_w - dw) // 2
    y = (dst_h - dh) // 2
    return (x, y, dw, dh)


def scaler_name(src_size, dst_size):
    """'none', 'nearest' (integer multiple) or 'smooth'."""
    sw, sh = src_size
    dw, dh = dst_size
    if (dw, dh) == (sw, sh):
        return "none"
    if sw and sh and dw % sw == 0 and dh % sh == 0 and (dw // sw) == (dh // sh):
        return "nearest"
    return "smooth"


def desktop_size():
    """The display's current size, before we open our own window."""
    try:
        sizes = pygame.display.get_desktop_sizes()
    except Exception:
        sizes = []
    if sizes and sizes[0][0] > 1 and sizes[0][1] > 1:
        return sizes[0]
    info = pygame.display.Info()
    if info.current_w > 1 and info.current_h > 1:
        return (info.current_w, info.current_h)
    return (1920, 1080)


class Display:
    """The window. canvas is always WIN_W × WIN_H; present() copies it to the screen."""

    def __init__(self, fullscreen=False, display_size=None):
        self.fullscreen = bool(fullscreen)
        self.fit = (0, 0, WIN_W, WIN_H)
        self.size = (WIN_W, WIN_H)
        self.scaler = "none"
        self.flags = 0
        self._scaled = None
        self._bars = False
        self.last_present_s = 0.0
        if not self.fullscreen:
            # The ordinary window: exactly as the game has always opened.
            self.flags = 0
            self.out = pygame.display.set_mode((WIN_W, WIN_H))
            self.canvas = self.out
            self.size = self.out.get_size()
            pygame.mouse.set_visible(True)
            return
        if display_size:
            dw, dh = display_size
            # An explicit size (headless checks, or COURTYARD_DISPLAY) must come out
            # at those pixels. NOFRAME keeps the border off without asking the dummy
            # driver to clamp to its pretend desktop.
            self.flags = pygame.NOFRAME
        else:
            dw, dh = desktop_size()
            # Native television: borderless full-screen at the desktop size, so Wayland
            # (labwc) does not switch modes and there is no window chrome.
            self.flags = pygame.FULLSCREEN | pygame.NOFRAME
        self.out = pygame.display.set_mode((int(dw), int(dh)), self.flags)
        self.canvas = pygame.Surface((WIN_W, WIN_H)).convert()
        pygame.mouse.set_visible(False)
        self._configure()

    def _configure(self):
        self.size = self.out.get_size()
        self.fit = fit_rect(WIN_W, WIN_H, self.size[0], self.size[1])
        self.scaler = scaler_name((WIN_W, WIN_H), (self.fit[2], self.fit[3]))
        x, y, dw, dh = self.fit
        self._bars = (x, y, dw, dh) != (0, 0, self.size[0], self.size[1])
        if self.scaler == "none" or not self._bars:
            self._scaled = None
        else:
            self._scaled = pygame.Surface((dw, dh)).convert()
        if self._bars:
            self.out.fill((0, 0, 0))

    def present(self):
        import time
        if not self.fullscreen:
            pygame.display.flip()
            self.last_present_s = 0.0
            return 0.0
        t0 = time.perf_counter()
        x, y, dw, dh = self.fit
        if self._bars:
            W, H = self.size
            if y:
                pygame.draw.rect(self.out, (0, 0, 0), (0, 0, W, y))
                pygame.draw.rect(self.out, (0, 0, 0), (0, y + dh, W, H - (y + dh)))
            if x:
                pygame.draw.rect(self.out, (0, 0, 0), (0, 0, x, H))
                pygame.draw.rect(self.out, (0, 0, 0), (x + dw, 0, W - (x + dw), H))
        if self.scaler == "none":
            if self.canvas is not self.out:
                self.out.blit(self.canvas, (x, y))
        else:
            fn = pygame.transform.scale if self.scaler == "nearest" else pygame.transform.smoothscale
            if self._scaled is None:
                fn(self.canvas, (dw, dh), self.out)
            else:
                fn(self.canvas, (dw, dh), self._scaled)
                self.out.blit(self._scaled, (x, y))
        pygame.display.flip()
        self.last_present_s = time.perf_counter() - t0
        return self.last_present_s
