"""Football's extra sounds, synthesised (writes only these files):
    kick.wav         a boot on the ball (a firm leathery thump)
    post.wav         the ball off the goal frame (a hollow aluminium clang)
    net.wav          the ball hitting the back of the net (a soft rushing swish)
    board.wav        the ball off the side boards (a dull plastic thud)
    crowd_cheer.wav  the crowd going up for a goal
    crowd_groan.wav  the crowd's "ohhh" for a save, a near miss or the woodwork
    python tools/make_football_sounds.py
"""
import os
import wave

import numpy as np

SR = 22050
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "sounds")
rng = np.random.default_rng(23)


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
    """One-pole low-pass (vectorised enough for short sounds)."""
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += (v - acc) * k
        y[i] = acc
    return y


def bandnoise(n, lo, hi):
    x = rng.normal(0, 1, n)
    return lowpass(x, hi) - lowpass(x, lo)


def kick():
    """A boot on a football: a short punchy low thump, a leathery slap on top."""
    t = t_(0.22)
    f = 120 * np.exp(-t * 30) + 70
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 30)
    slap = lowpass(rng.normal(0, 1, len(t)), 0.45) * np.exp(-t * 140) * 0.9
    return body + slap


def post():
    """Off the woodwork (aluminium): a clang with inharmonic partials and a long ring."""
    t = t_(0.9)
    x = np.zeros_like(t)
    for f, a, d in ((523, 1.0, 5.0), (1187, 0.6, 7.0), (1960, 0.35, 9.0), (2870, 0.2, 12.0), (311, 0.5, 6.0)):
        x += a * np.sin(2 * np.pi * f * t) * np.exp(-t * d)
    hit = lowpass(rng.normal(0, 1, len(t)), 0.6) * np.exp(-t * 120)
    return x * 0.6 + hit * 0.8


def net():
    """The ball into the net: a soft rush of air and cord, swelling quickly then settling."""
    t = t_(0.6)
    n = bandnoise(len(t), 0.03, 0.35)
    env = (1 - np.exp(-t * 60)) * np.exp(-t * 5.5)
    flutter = 1 + 0.4 * np.sin(2 * np.pi * 17 * t) * np.exp(-t * 4)
    thud = np.sin(2 * np.pi * 90 * t) * np.exp(-t * 25) * 0.4
    return n * env * flutter + thud


def board():
    """A dull plastic board: a low knock with a short boxy resonance."""
    t = t_(0.25)
    body = np.sin(2 * np.pi * 160 * t) * np.exp(-t * 28) + 0.5 * np.sin(2 * np.pi * 240 * t) * np.exp(-t * 40)
    knock = lowpass(rng.normal(0, 1, len(t)), 0.25) * np.exp(-t * 90)
    return body + knock


def voices(dur, n, f_lo, f_hi, shape):
    """A crowd: many breathy voices, each a buzzy tone through two vowel formants, plus a bed of noise."""
    t = t_(dur)
    out = np.zeros_like(t)
    for i in range(n):
        f0 = rng.uniform(f_lo, f_hi)
        start = rng.uniform(0, 0.15)
        vib = 1 + 0.02 * np.sin(2 * np.pi * rng.uniform(4, 7) * t + rng.uniform(0, 6))
        glide = shape(t)
        f = f0 * vib * glide
        ph = 2 * np.pi * np.cumsum(f) / SR
        # a few harmonics, weighted like an open "ah"/"oh"
        v = sum((1 / k) * np.sin(k * ph) for k in range(1, 7))
        env = np.clip((t - start) / 0.12, 0, 1)
        out += v * env * rng.uniform(0.5, 1.0)
    out /= n
    bed = bandnoise(len(t), 0.02, 0.25) * 0.8
    return out + bed


def crowd_cheer():
    """Up goes the crowd: a rising roar, swelling and holding, then dying away."""
    dur = 2.4
    t = t_(dur)
    x = voices(dur, 36, 180, 420, lambda t: 1 + 0.25 * (1 - np.exp(-t * 4)))
    env = np.clip(t / 0.25, 0, 1) * np.clip((dur - t) / 1.2, 0, 1)
    # a few claps on top
    claps = np.zeros_like(t)
    for i in range(70):
        at = int(rng.uniform(0.2, dur - 0.4) * SR)
        L = int(0.02 * SR)
        claps[at:at + L] += rng.normal(0, 1, L) * np.exp(-np.arange(L) / (0.004 * SR)) * 0.6
    return lowpass(x, 0.35) * env + claps * env


def crowd_groan():
    """The crowd's "ohhh": a falling, round murmur."""
    dur = 1.5
    t = t_(dur)
    x = voices(dur, 30, 140, 300, lambda t: 1.15 - 0.3 * np.clip(t / 1.2, 0, 1))
    env = np.clip(t / 0.15, 0, 1) * np.clip((dur - t) / 0.8, 0, 1)
    return lowpass(x, 0.18) * env


if __name__ == "__main__":
    for name, fn in (("kick", kick), ("post", post), ("net", net), ("board", board),
                     ("crowd_cheer", crowd_cheer), ("crowd_groan", crowd_groan)):
        save(name, fn())
        print("wrote", name)
