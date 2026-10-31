"""Basketball's extra sounds, synthesised (writes only these four files):
    bounce.wav     the ball bouncing on tarmac (a hollow, rubbery thump)
    swish.wav      nothing but net
    clank.wav      the ball off the steel rim
    backboard.wav  the ball off the backboard
    python tools/make_basketball_sounds.py
"""
import os
import wave

import numpy as np

SR = 22050
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "sounds")
rng = np.random.default_rng(11)


def save(name, x):
    x = x / max(1e-9, np.abs(x).max()) * 0.9
    with wave.open(os.path.join(OUT, name + ".wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def t_(dur):
    return np.arange(int(dur * SR)) / SR


def lowpass(x, k):
    y = np.zeros_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += (v - acc) * k
        y[i] = acc
    return y


def bounce():
    """A pumped-up ball on tarmac: a low pitch-dropping thump with a ringing
    air-cavity tone and a slap of rubber on top."""
    t = t_(0.28)
    f = 150 * np.exp(-t * 6) + 90
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 26)
    ring = 0.25 * np.sin(2 * np.pi * 410 * t) * np.exp(-t * 40)
    slap = lowpass(rng.normal(0, 1, len(t)), 0.35) * np.exp(-t * 180) * 0.8
    return body + ring + slap


def swish():
    """Net: a soft, quick burst of filtered noise that swells and dies."""
    t = t_(0.42)
    n = rng.normal(0, 1, len(t))
    hi = n - lowpass(n, 0.12)               # take out the rumble
    env = np.sin(np.clip(t / 0.42, 0, 1) * np.pi) ** 1.5 * np.exp(-t * 3)
    flutter = 1 + 0.35 * np.sin(2 * np.pi * 26 * t)
    return lowpass(hi, 0.5) * env * flutter


def clank():
    """Steel rim: bright, inharmonic partials ringing off."""
    t = t_(0.6)
    parts = ((620, 1.0, 9), (1430, 0.6, 12), (2390, 0.4, 16), (3310, 0.25, 22), (880, 0.35, 10))
    x = sum(a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * np.exp(-t * d) for f, a, d in parts)
    hit = rng.normal(0, 1, len(t)) * np.exp(-t * 300) * 0.8
    return x + hit


def backboard():
    """A wooden/perspex backboard: a dull thud with a short rattle."""
    t = t_(0.32)
    x = np.sin(2 * np.pi * 180 * t) * np.exp(-t * 30) + 0.5 * np.sin(2 * np.pi * 370 * t) * np.exp(-t * 36)
    rattle = lowpass(rng.normal(0, 1, len(t)), 0.25) * np.exp(-t * 22) * 0.35 * (1 + np.sin(2 * np.pi * 38 * t))
    return x + rattle


if __name__ == "__main__":
    save("bounce", bounce())
    save("swish", swish())
    save("clank", clank())
    save("backboard", backboard())
    print("wrote bounce, swish, clank, backboard")
