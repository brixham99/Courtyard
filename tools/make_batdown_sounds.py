"""Batdown's extra sounds, synthesised (writes only these three files):
    thock.wav    bat on ball (a woody knock)
    clatter.wav  the bat knocked flat (wood rattling on the grass)
    pock.wav     the ball bouncing on grass
    python tools/make_batdown_sounds.py
"""
import os
import wave

import numpy as np

SR = 22050
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "sounds")
rng = np.random.default_rng(7)


def save(name, x):
    x = x / max(1e-9, np.abs(x).max()) * 0.9
    with wave.open(os.path.join(OUT, name + ".wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def t_(dur):
    return np.arange(int(dur * SR)) / SR


def knock(f0, dur, decay, partials=((1, 1.0), (2.3, 0.5), (3.9, 0.25)), noise=0.3):
    t = t_(dur)
    x = sum(a * np.sin(2 * np.pi * f0 * k * t) * np.exp(-t * decay * (1 + 0.4 * k)) for k, a in partials)
    click = rng.normal(0, 1, len(t)) * np.exp(-t * 400) * noise
    return x + click


def thock():
    return knock(520, 0.25, 34) + 0.4 * knock(240, 0.25, 22, noise=0)


def pock():
    return knock(300, 0.12, 60, partials=((1, 1.0), (1.8, 0.3)), noise=0.5)


def clatter():
    out = np.zeros(int(0.7 * SR))
    for i, (when, f, a) in enumerate(((0.0, 430, 1.0), (0.11, 380, 0.7), (0.2, 470, 0.5), (0.27, 350, 0.35), (0.33, 410, 0.22))):
        k = knock(f, 0.25, 30, noise=0.6) * a
        j = int(when * SR)
        out[j:j + len(k)] += k[: len(out) - j]
    return out


if __name__ == "__main__":
    save("thock", thock())
    save("pock", pock())
    save("clatter", clatter())
    print("wrote thock, pock, clatter")
