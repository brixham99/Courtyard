"""Gamepads for Courtyard, via SDL's GameController API.

Xbox and PlayStation pads share one layout: A/Cross confirms, B/Circle goes
back, Y/Triangle toggles the music, Start/Options pauses, and holding
Back/Share for about a second quits. The left stick and the D-pad both
stand in for the arrow keys. A resting stick inside the deadzone does nothing.

The first pad is player 1. A second pad is player 2 (the games here are all
against the robot, so player 2's pad is tracked but not applied).

There is no name-entry screen in the game today. NameEntry is the pad (and
keyboard) control for one, if a screen asks for a name: up and down cycle the
letter, left and right move, A accepts.
"""
import ctypes

import pygame

DEADZONE = 0.3
QUIT_HOLD = 1.0          # seconds Back/Share must be held to quit to the launcher
_AXIS_SCALE = 32767.0

_SDL = None


def norm_axis(value):
    """SDL axes arrive as -32768..32767, or already as -1..1. Either becomes -1..1.

    Controller.get_axis gives whole numbers (-32768..32767); Joystick.get_axis
    gives floats (-1..1). Tell them apart by type, not size: a resting stick can
    read a raw 1 or -1, which must not count as a full tilt."""
    if isinstance(value, int) and not isinstance(value, bool):
        v = value / 32767.0
    else:
        v = float(value)
        if abs(v) > 1.5:
            v /= 32767.0
    if v > 1.0:
        return 1.0
    if v < -1.0:
        return -1.0
    return v


def family_of(name):
    """'xbox' or 'playstation' from the controller's name. Generic pads use Xbox labels,
    which matches the GameController buttons (A/B/X/Y)."""
    n = (name or "").lower()
    if any(s in n for s in ("xbox", "x-box", "xinput", "microsoft")):
        return "xbox"
    if any(s in n for s in ("playstation", "dualshock", "dualsense", "dual shock", "ps4", "ps5", "sony",
                            "wireless controller")):
        return "playstation"
    return "xbox"


class Hints:
    """Button words for the on-screen prompts. No pad: the keyboard words, unchanged."""

    def __init__(self, family):
        self.family = family    # "xbox", "playstation", or None

    @property
    def pad(self):
        return self.family in ("xbox", "playstation")

    @property
    def action(self):
        if self.family == "playstation":
            return "Cross"
        if self.family == "xbox":
            return "A"
        return "Space"

    @property
    def back(self):
        if self.family == "playstation":
            return "Circle"
        if self.family == "xbox":
            return "B"
        return "Esc"

    @property
    def extra(self):
        """The west button: a lofted swing in Batdown."""
        if self.family == "playstation":
            return "Square"
        if self.family == "xbox":
            return "X"
        return ""

    @property
    def music(self):
        if self.family == "playstation":
            return "Triangle"
        if self.family == "xbox":
            return "Y"
        return "M"

    @property
    def pause(self):
        if self.family == "playstation":
            return "Options"
        if self.family == "xbox":
            return "Start"
        return ""

    @property
    def quit(self):
        """Back on Xbox (View on newer pads), Share on PlayStation."""
        if self.family == "playstation":
            return "Share"
        if self.family == "xbox":
            return "Back"
        return ""


class PadInput:
    def __init__(self, connected=False, family=None, turn=0, move=0, down=(), up=(), held=(), forward=False):
        self.connected = connected
        self.forward = forward    # right trigger pulled: forwards in play (A is the action)
        self.family = family
        self.turn = turn          # -1, 0, +1 like Left/Right
        self.move = move          # +1 forwards (up), -1 back
        self.down = set(down)     # action buttons pressed this frame
        self.up = set(up)
        self.held = set(held)


class NameEntry:
    """A short name, edited with a pad or the arrow keys. A accepts, B cancels."""

    LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ "

    def __init__(self, length=10):
        self.length = length
        self.slots = ["A"] + [" "] * (length - 1)
        self.i = 0
        self.done = False
        self.cancelled = False

    def move(self, d):
        if self.done or self.cancelled or not d:
            return
        self.i = max(0, min(self.length - 1, self.i + d))

    def cycle(self, d):
        """d > 0 (up) moves forward through the letters; down moves back."""
        if self.done or self.cancelled or not d:
            return
        letters = self.LETTERS
        cur = self.slots[self.i]
        k = letters.index(cur) if cur in letters else 0
        self.slots[self.i] = letters[(k + d) % len(letters)]

    def accept(self):
        if self.done or self.cancelled:
            return True
        self.done = True
        return True

    def back(self):
        if self.done or self.cancelled:
            return True
        self.cancelled = True
        return True

    @property
    def text(self):
        return "".join(self.slots).rstrip()


def _sdl():
    """The SDL pygame-ce is actually linked against, so a virtual pad is the same one the game sees."""
    global _SDL
    if _SDL is not None:
        return _SDL
    path = None
    with open("/proc/self/maps") as f:
        for line in f:
            if "libSDL2-2" in line and ".so" in line:
                path = line.split()[-1]
                break
    if not path:
        raise RuntimeError("SDL2 is not loaded")
    lib = ctypes.CDLL(path)
    lib.SDL_JoystickAttachVirtual.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    lib.SDL_JoystickAttachVirtual.restype = ctypes.c_int
    lib.SDL_JoystickDetachVirtual.argtypes = [ctypes.c_int]
    lib.SDL_JoystickDetachVirtual.restype = ctypes.c_int
    lib.SDL_JoystickOpen.argtypes = [ctypes.c_int]
    lib.SDL_JoystickOpen.restype = ctypes.c_void_p
    lib.SDL_JoystickSetVirtualAxis.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int16]
    lib.SDL_JoystickSetVirtualAxis.restype = ctypes.c_int
    lib.SDL_JoystickSetVirtualButton.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint8]
    lib.SDL_JoystickSetVirtualButton.restype = ctypes.c_int
    lib.SDL_GameControllerAddMapping.argtypes = [ctypes.c_char_p]
    lib.SDL_GameControllerAddMapping.restype = ctypes.c_int
    lib.SDL_JoystickGetGUID.argtypes = [ctypes.c_void_p]
    lib.SDL_JoystickGetGUID.restype = ctypes.c_uint8 * 16
    lib.SDL_JoystickGetGUIDString.argtypes = [ctypes.c_uint8 * 16, ctypes.c_char_p, ctypes.c_int]
    _SDL = lib
    return lib


# SDL_JOYSTICK_TYPE_GAMECONTROLLER
_GC_TYPE = 1
_MAPPINGS = {
    "xbox": "Xbox 360 Controller",
    "playstation": "Sony DualShock 4",
}
# Standard GameController layout on a simple virtual device: buttons 0..14, axes 0..5.
_MAP_BODY = ("a:b0,b:b1,x:b2,y:b3,back:b4,guide:b5,start:b6,leftstick:b7,rightstick:b8,"
             "leftshoulder:b9,rightshoulder:b10,dpup:b11,dpdown:b12,dpleft:b13,dpright:b14,"
             "leftx:a0,lefty:a1,rightx:a2,righty:a3,lefttrigger:a4,righttrigger:a5,")


class VirtualPad:
    """A synthetic SDL game controller, for headless tests. kind is 'xbox' or 'playstation'."""

    def __init__(self, kind):
        lib = _sdl()
        self.kind = kind
        self.index = lib.SDL_JoystickAttachVirtual(_GC_TYPE, 6, 15, 0)
        if self.index < 0:
            raise RuntimeError("could not attach a virtual game controller")
        pygame.event.pump()
        self._js = lib.SDL_JoystickOpen(self.index)
        if not self._js:
            raise RuntimeError("could not open the virtual game controller")
        joy = pygame.joystick.Joystick(self.index)
        if not joy.get_init():
            joy.init()
        self.instance_id = joy.get_instance_id()
        name = _MAPPINGS.get(kind, _MAPPINGS["xbox"])
        # Virtual joysticks often share one GUID, so the mapping name cannot tell two
        # of them apart. Pads records `kind` against this instance id as well.
        mapping = f"{joy.get_guid()},{name},{_MAP_BODY}"
        if lib.SDL_GameControllerAddMapping(mapping.encode()) < 0:
            raise RuntimeError("could not map the virtual game controller")
        pygame.event.pump()

    def set_axis(self, axis, value):
        """value is -1..1, or already a Sint16."""
        v = float(value)
        if abs(v) <= 1.5:
            sint = int(round(max(-1.0, min(1.0, v)) * _AXIS_SCALE))
        else:
            sint = int(value)
        sint = max(-32768, min(32767, sint))
        rc = _sdl().SDL_JoystickSetVirtualAxis(self._js, int(axis), sint)
        pygame.event.pump()
        return rc

    def set_button(self, button, down):
        rc = _sdl().SDL_JoystickSetVirtualButton(self._js, int(button), 1 if down else 0)
        pygame.event.pump()
        return rc

    def detach(self):
        if self.instance_id is None and self.index is None:
            return
        idx = None
        # The device index passed to DetachVirtual is the current one, which shifts
        # when an earlier pad is unplugged. Match our instance id.
        try:
            n = pygame.joystick.get_count()
        except Exception:
            n = 0
        for i in range(n):
            try:
                joy = pygame.joystick.Joystick(i)
                if not joy.get_init():
                    joy.init()
                if joy.get_instance_id() == self.instance_id:
                    idx = i
                    break
            except Exception:
                continue
        if idx is None:
            idx = self.index
        if idx is not None and idx >= 0:
            _sdl().SDL_JoystickDetachVirtual(idx)
        self.index = None
        self.instance_id = None
        pygame.event.pump()


class Pads:
    """Hot-plugged GameControllers. Poll each frame; the edges are which actions changed."""

    SLOTS = 2

    def __init__(self):
        self._C = None
        self.devices = {}          # instance id -> Controller
        self.names = {}
        self.slots = [None, None]  # instance id per player
        self.prev_held = [set(), set()]
        self.players = [PadInput(), PadInput()]
        self.back_t = 0.0
        self._quit_latched = False
        self.quit_requested = False
        self.hints = Hints(None)
        self.virtuals = []
        self.kind_of = {}          # instance id -> "xbox" / "playstation" for synthetic pads
        try:
            import pygame._sdl2.controller as controller
            controller.init()
            pygame.joystick.init()
            self._C = controller
        except Exception:
            self._C = None
        self._sync()

    @property
    def connected(self):
        return any(p.connected for p in self.players)

    def player(self, slot):
        return self.players[slot]

    def attach_virtual(self, kind="xbox"):
        v = VirtualPad(kind)
        self.virtuals.append(v)
        if v.instance_id is not None:
            self.kind_of[v.instance_id] = "playstation" if kind == "playstation" else "xbox"
        self._sync()
        return v

    def detach_virtual(self, virtual=None):
        gone = list(self.virtuals) if virtual is None else [virtual]
        for v in gone:
            self.kind_of.pop(getattr(v, "instance_id", None), None)
            v.detach()
        self.virtuals = [v for v in self.virtuals if v not in gone]
        self._sync()

    def poll(self, dt):
        self.quit_requested = False
        if self._C is None:
            return self.players
        self._sync()
        any_back = False
        out = []
        for slot in range(self.SLOTS):
            iid = self.slots[slot]
            dev = self.devices.get(iid) if iid is not None else None
            if dev is None or not self._alive(dev):
                turn, move, held, forward = 0, 0, set(), False
                family = None
                connected = False
            else:
                turn, move = self._axes(dev)
                held = self._actions(dev)
                try:
                    rt = norm_axis(dev.get_axis(pygame.CONTROLLER_AXIS_TRIGGERRIGHT))
                except Exception:
                    rt = 0.0
                forward = rt >= DEADZONE
                family = self.kind_of.get(iid) or family_of(self.names.get(iid, ""))
                connected = True
                if dev.get_button(pygame.CONTROLLER_BUTTON_BACK):
                    any_back = True
            prev = self.prev_held[slot]
            down = held - prev
            up = prev - held
            self.prev_held[slot] = set(held)
            out.append(PadInput(connected, family, turn, move, down, up, held, forward))
        self.players = out
        if any_back:
            self.back_t += dt
            if self.back_t >= QUIT_HOLD and not self._quit_latched:
                self.quit_requested = True
                self._quit_latched = True
        else:
            self.back_t = 0.0
            self._quit_latched = False
        fam = None
        for p in out:
            if p.connected:
                fam = p.family
                break
        self.hints = Hints(fam)
        return out

    def _alive(self, dev):
        try:
            return bool(dev.attached())
        except Exception:
            return False

    def _actions(self, dev):
        held = set()
        for bit, name in ((pygame.CONTROLLER_BUTTON_A, "a"),
                          (pygame.CONTROLLER_BUTTON_B, "b"),
                          (pygame.CONTROLLER_BUTTON_X, "x"),
                          (pygame.CONTROLLER_BUTTON_Y, "y"),
                          (pygame.CONTROLLER_BUTTON_START, "start"),
                          (pygame.CONTROLLER_BUTTON_BACK, "back")):
            try:
                if dev.get_button(bit):
                    held.add(name)
            except Exception:
                pass
        return held

    def _axes(self, dev):
        try:
            lx = norm_axis(dev.get_axis(pygame.CONTROLLER_AXIS_LEFTX))
            ly = norm_axis(dev.get_axis(pygame.CONTROLLER_AXIS_LEFTY))
            left = dev.get_button(pygame.CONTROLLER_BUTTON_DPAD_LEFT)
            right = dev.get_button(pygame.CONTROLLER_BUTTON_DPAD_RIGHT)
            up = dev.get_button(pygame.CONTROLLER_BUTTON_DPAD_UP)
            down = dev.get_button(pygame.CONTROLLER_BUTTON_DPAD_DOWN)
        except Exception:
            return 0, 0
        # The D-pad wins while it is held, so a tap still answers if the stick is leaning.
        if right and not left:
            turn = 1
        elif left and not right:
            turn = -1
        elif abs(lx) >= DEADZONE:
            turn = 1 if lx > 0 else -1
        else:
            turn = 0
        if up and not down:
            move = 1
        elif down and not up:
            move = -1
        elif abs(ly) >= DEADZONE:
            move = -1 if ly > 0 else 1     # SDL's Y axis points down
        else:
            move = 0
        return turn, move

    def _sync(self):
        if self._C is None:
            return
        seen = []
        try:
            n = self._C.get_count()
        except Exception:
            n = 0
        for i in range(n):
            try:
                if not self._C.is_controller(i):
                    continue
                js = pygame.joystick.Joystick(i)
                if not js.get_init():
                    js.init()
                iid = js.get_instance_id()
            except Exception:
                continue
            seen.append(iid)
            if iid not in self.devices:
                try:
                    dev = self._C.Controller(i)
                except Exception:
                    continue
                self.devices[iid] = dev
                try:
                    self.names[iid] = dev.name if isinstance(dev.name, str) else dev.name()
                except Exception:
                    self.names[iid] = ""
        for iid in list(self.devices):
            if iid not in seen:
                dev = self.devices.pop(iid)
                self.names.pop(iid, None)
                try:
                    dev.quit()
                except Exception:
                    pass
        used = set()
        for slot, iid in enumerate(self.slots):
            if iid not in self.devices:
                self.slots[slot] = None
                # prev_held stays, so this frame's poll reports the buttons that came up
            else:
                used.add(iid)
        for iid in seen:
            if iid in used:
                continue
            for slot in range(self.SLOTS):
                if self.slots[slot] is None:
                    self.slots[slot] = iid
                    used.add(iid)
                    break
        # One pad left, and it was in the player-2 slot: it becomes player 1.
        if self.slots[0] is None and self.slots[1] is not None:
            self.slots[0] = self.slots[1]
            self.slots[1] = None
            self.prev_held[0] = self.prev_held[1]
            self.prev_held[1] = set()
