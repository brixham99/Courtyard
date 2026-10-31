"""Synthesise Courtyard's sound effects and title music (numpy, 22,050 Hz mono).

Writes assets/sounds/*.wav and title_theme.ogg (via ffmpeg if available, else wav).
"""
import os
import subprocess
import wave
import numpy as np

SR = 22050
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "assets", "sounds")


def save(name, x, vol=0.9):
    x = np.asarray(x, np.float64)
    x = x / max(1e-9, np.abs(x).max()) * vol
    d = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    p = os.path.join(OUT, name + ".wav")
    with wave.open(p, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(d.tobytes())
    return p


def t_(dur):
    return np.arange(int(SR * dur)) / SR


def env(n, a=0.005, r=0.05, total=None):
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    if na: e[:na] = np.linspace(0, 1, na)
    if nr: e[-nr:] *= np.linspace(1, 0, nr)
    return e


def whistle(dur=0.55, trills=2):
    """A pea whistle: a bright tone with a fast warble from the pea."""
    t = t_(dur)
    warble = 1 + 0.035 * np.sign(np.sin(2 * np.pi * 28 * t)) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))
    ph = np.cumsum(2 * np.pi * 2900 * warble / SR)
    x = np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.08 * np.random.default_rng(1).normal(size=len(t))
    return x * env(len(t), 0.01, 0.08)


def slap():
    """A hand tag: a short noisy clap with a little body."""
    rng = np.random.default_rng(2)
    t = t_(0.18)
    n = rng.normal(size=len(t)) * np.exp(-t * 45)
    body = np.sin(2 * np.pi * 180 * t) * np.exp(-t * 30) * 0.6
    # crude band-pass on the noise
    k = np.ones(6) / 6
    n = n - np.convolve(n, k, "same")
    return n + body


def boing():
    t = t_(0.45)
    f = 220 + 380 * np.exp(-t * 6) + 25 * np.sin(2 * np.pi * 14 * t) * np.exp(-t * 3)
    ph = np.cumsum(2 * np.pi * f / SR)
    return (np.sin(ph) + 0.3 * np.sin(2 * ph)) * np.exp(-t * 5) * env(len(t), 0.003, 0.05)


def beep(f=880, dur=0.12):
    t = t_(dur)
    return (np.sign(np.sin(2 * np.pi * f * t)) * 0.4 + np.sin(2 * np.pi * f * t)) * env(len(t), 0.003, 0.03)


def step(seed):
    rng = np.random.default_rng(seed)
    t = t_(0.07)
    n = rng.normal(size=len(t)) * np.exp(-t * 90)
    return np.convolve(n, np.ones(4) / 4, "same") + 0.4 * np.sin(2 * np.pi * 110 * t) * np.exp(-t * 60)


def robot_step(seed):
    t = t_(0.09)
    rng = np.random.default_rng(seed + 10)
    clank = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * d) for f, d in ((620, 40), (1310, 55), (2210, 70)))
    return clank * 0.5 + rng.normal(size=len(t)) * np.exp(-t * 120) * 0.5


def robot_chirp(up=True):
    """The robot's happy beep-boop when it tags or gets away."""
    out = []
    notes = (660, 990, 1320) if up else (990, 740, 520)
    for f in notes:
        t = t_(0.07)
        out.append(np.sign(np.sin(2 * np.pi * f * t)) * 0.5 * env(len(t), 0.002, 0.02))
    return np.concatenate(out)


def cheer():
    """A small playground cheer (layered noisy 'yay' formants)."""
    rng = np.random.default_rng(5)
    t = t_(1.3)
    x = np.zeros(len(t))
    for i in range(7):
        f0 = rng.uniform(260, 420)
        vib = 1 + 0.04 * np.sin(2 * np.pi * rng.uniform(4, 7) * t)
        ph = np.cumsum(2 * np.pi * f0 * vib * (1 + 0.15 * t) / SR)
        v = sum(np.sin(k * ph) / k for k in range(1, 8))
        start = rng.uniform(0, 0.15)
        e = np.clip((t - start) / 0.08, 0, 1) * np.exp(-np.clip(t - start, 0, None) * 2.2)
        x += v * e
    return x + rng.normal(size=len(t)) * 0.3 * np.exp(-t * 2)


# ---------------------------------------------------------------- music
NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}


def hz(name):
    n, o = name[:-1], int(name[-1])
    return 440 * 2 ** ((NOTE[n] + 12 * (o - 4) - 9) / 12)


def tone(f, dur, kind="sq", vol=1.0):
    t = t_(dur)
    if kind == "sq":
        x = np.sign(np.sin(2 * np.pi * f * t)) * 0.5 + 0.5 * np.sin(2 * np.pi * f * t)
    elif kind == "tri":
        x = 2 / np.pi * np.arcsin(np.sin(2 * np.pi * f * t))
    else:
        x = np.sin(2 * np.pi * f * t)
    return x * env(len(t), 0.004, min(0.06, dur * 0.4)) * np.exp(-t * 2.5) * vol


def music():
    """A jaunty playground tune in G major, 132 bpm, 16 bars, loops cleanly."""
    bpm = 132
    beat = 60 / bpm
    bars = 16
    total = int(SR * beat * 4 * bars)
    x = np.zeros(total + SR)

    def put(start_beats, sig):
        i = int(start_beats * beat * SR)
        x[i:i + len(sig)] += sig[: max(0, len(x) - i)]

    # melody: (note, beats); a skipping rhythm
    A = [("G4", .5), ("B4", .5), ("D5", .5), ("B4", .5), ("C5", .5), ("E5", .5), ("D5", 1),
         ("B4", .5), ("G4", .5), ("A4", .5), ("B4", .5), ("A4", 1), ("D4", 1),
         ("G4", .5), ("B4", .5), ("D5", .5), ("G5", .5), ("F#5", .5), ("E5", .5), ("D5", 1),
         ("C5", .5), ("A4", .5), ("F#4", .5), ("A4", .5), ("G4", 2)]
    B = [("E5", .5), ("E5", .5), ("D5", .5), ("C5", .5), ("D5", 1), ("B4", 1),
         ("C5", .5), ("C5", .5), ("B4", .5), ("A4", .5), ("B4", 1), ("G4", 1),
         ("A4", .5), ("B4", .5), ("C5", .5), ("D5", .5), ("E5", .5), ("F#5", .5), ("G5", 1),
         ("D5", .5), ("B4", .5), ("A4", .5), ("F#4", .5), ("G4", 2)]
    pos = 0
    for part in (A, B, A, B):
        for n, d in part:
            put(pos, tone(hz(n), d * beat * 0.95, "sq", 0.32))
            pos += d
    # bass + chords: I-IV-V-I patterns per bar
    prog = ["G", "C", "D", "G", "G", "C", "D", "G", "C", "G", "D", "G", "C", "G", "D", "G"]
    roots = {"G": ("G2", ["G3", "B3", "D4"]), "C": ("C3", ["C4", "E4", "G4"]), "D": ("D3", ["D4", "F#4", "A4"])}
    for b, c in enumerate(prog):
        r, ch = roots[c]
        for k in range(4):
            bn = r if k % 2 == 0 else r[:-1] + str(int(r[-1]) + 1)
            put(b * 4 + k, tone(hz(bn), beat * 0.8, "tri", 0.55))
            if k % 2 == 1:
                for cn in ch:
                    put(b * 4 + k + 0.0, tone(hz(cn), beat * 0.35, "sin", 0.12))
    # light percussion: tick on every off-beat, thump on beats 1 and 3
    rng = np.random.default_rng(9)
    for b in range(bars * 4):
        if b % 2 == 0:
            t = t_(0.12)
            put(b, np.sin(2 * np.pi * (60 + 80 * np.exp(-t * 40)) * t) * np.exp(-t * 25) * 0.6)
        t = t_(0.04)
        put(b + 0.5, rng.normal(size=len(t)) * np.exp(-t * 120) * 0.15)
    # wrap the tail round to the start so the loop is seamless
    tail = x[total:]
    x = x[:total]
    x[: len(tail)] += tail
    return x


def main():
    os.makedirs(OUT, exist_ok=True)
    save("whistle", whistle(), 0.8)
    save("whistle_long", np.concatenate([whistle(0.35), np.zeros(int(SR * 0.08)), whistle(0.9)]), 0.8)
    save("slap", slap(), 0.9)
    save("boing", boing(), 0.7)
    save("beep", beep(880), 0.5)
    save("beep_hi", beep(1320, 0.25), 0.5)
    for i in range(3):
        save(f"step{i + 1}", step(i), 0.35)
        save(f"rstep{i + 1}", robot_step(i), 0.35)
    save("robot_happy", robot_chirp(True), 0.45)
    save("robot_sad", robot_chirp(False), 0.45)
    save("cheer", cheer(), 0.7)
    p = save("title_theme", music(), 0.7)
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", p, "-c:a", "libvorbis", "-q:a", "4",
                        os.path.join(OUT, "title_theme.ogg")], check=True)
        os.remove(p)
    except Exception as e:
        print("kept wav:", e)
    print("sounds written to", OUT)


if __name__ == "__main__":
    main()
