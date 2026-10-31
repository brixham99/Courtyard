"""Courtyard title music: "Saturday Kick-Off", an original tune in the spirit of
a 1970s British TV football show (brassy fanfare, horn stabs, driving bass,
marching snare). The melody and riffs are newly written for Courtyard.

126 bpm, B-flat major, 20 bars of 4/4 = 38.10 s, a seamless loop: note tails and
reverb wrap round from the end to the start.

    python3 tools/make_title_music.py      -> assets/sounds/title_theme.ogg
Needs numpy and ffmpeg (libvorbis). Loudness is matched to game_music.ogg.
"""
import os, re, subprocess, sys, tempfile, wave
import numpy as np

SR = 44100
BPM = 126.0
BEAT = 60.0 / BPM
BARS = 20
LOOP_BEATS = BARS * 4
N = int(round(LOOP_BEATS * BEAT * SR))
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets", "sounds")
TARGET_LUFS = -13.3          # measured integrated loudness of game_music.ogg
rng = np.random.default_rng(1974)

def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)

# ---------------------------------------------------------------- mix buffers
L = np.zeros(N + 5 * SR)
R = np.zeros(N + 5 * SR)

def put(beat, sig, pan=0.0, gain=1.0):
    i = int(round(beat * BEAT * SR))
    gl, gr = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    L[i:i + len(sig)] += sig * gain * gl * 1.414
    R[i:i + len(sig)] += sig * gain * gr * 1.414

# ---------------------------------------------------------------- instruments
def brass(m, dur, bright=1.0, vib=True, scoop=True):
    """Band-limited sawtooth (additive) through a lowpass whose cutoff follows
    a 'blat' envelope, two detuned voices, scoop into the note, late vibrato."""
    rel = 0.09
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    f0 = hz(m)
    att = 0.03
    a = np.clip(t / att, 0, 1) ** 1.5
    a *= np.where(t < dur, 0.75 + 0.25 * np.exp(-(t) / 0.12), 1.0)
    a *= np.where(t < dur, 1.0, np.exp(-(t - dur) / (rel / 4)))
    # cutoff envelope (in multiples of f0)
    fc = f0 * (2.2 + bright * (5.5 * np.exp(-t / 0.09) * np.clip(t / 0.02, 0, 1) + 2.0)) 
    fc *= np.where(t < dur, 1.0, np.exp(-(t - dur) / 0.05))
    out = np.zeros(n)
    for det in (-0.06, 0.06):            # semitones
        f = f0 * 2 ** (det / 12)
        pitch = np.ones(n)
        if scoop:
            pitch *= 2 ** ((-0.35 * np.exp(-t / 0.025)) / 12)
        if vib and dur > 0.45:
            pitch *= 2 ** ((0.12 * np.sin(2 * np.pi * 5.6 * t) * np.clip((t - 0.25) / 0.3, 0, 1)) / 12)
        ph = 2 * np.pi * np.cumsum(f * pitch) / SR + rng.uniform(0, 6.28)
        kmax = int(min(28, (SR / 2 - 500) / f))
        for k in range(1, kmax + 1):
            g = (1.0 / k) / np.sqrt(1 + (k * f / fc) ** 4)
            out += g * np.sin(k * ph)
    out *= a * 0.35
    return np.tanh(out * 1.6) / 1.6           # a little brass 'edge'

def bass(m, dur):
    """Plucked electric bass: saw-ish harmonics, upper partials decay fastest."""
    n = int((dur + 0.06) * SR)
    t = np.arange(n) / SR
    f = hz(m)
    out = np.zeros(n)
    for k in range(1, 12):
        out += (1.0 / k ** 1.2) * np.exp(-t * (2.0 + 9.0 * k)) * np.sin(2 * np.pi * k * f * t + 0.3 * k)
    out += 0.6 * np.sin(2 * np.pi * f * t) * np.exp(-t * 1.5)
    a = np.clip(t / 0.004, 0, 1) * np.where(t < dur, 1.0, np.exp(-(t - dur) / 0.015))
    return np.tanh(out * a * 1.2) * 0.55

def onepole_hp(x, fc):
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.zeros_like(x); prev_x = prev_y = 0.0
    # vectorised enough for short drum hits
    for i in range(len(x)):
        prev_y = a * (prev_y + x[i] - prev_x); prev_x = x[i]; y[i] = prev_y
    return y

def kick():
    t = np.arange(int(0.35 * SR)) / SR
    f = 48 + 90 * np.exp(-t / 0.03)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.13)
    s += 0.3 * rng.standard_normal(len(t)) * np.exp(-t / 0.004)
    return s * 0.9

def snare(level=1.0):
    t = np.arange(int(0.25 * SR)) / SR
    nz = onepole_hp(rng.standard_normal(len(t)), 1200) * np.exp(-t / 0.07)
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.04)
    return (0.55 * nz + 0.45 * tone) * 0.6 * level

def hat(open_=False):
    d = 0.22 if open_ else 0.05
    t = np.arange(int((d * 2) * SR)) / SR
    nz = onepole_hp(onepole_hp(rng.standard_normal(len(t)), 7000), 7000)
    return nz * np.exp(-t / (d / 2.5)) * 0.35

def crash():
    t = np.arange(int(1.6 * SR)) / SR
    nz = onepole_hp(rng.standard_normal(len(t)), 4500)
    return nz * np.exp(-t / 0.55) * 0.28

def glock(m, dur=0.5):
    t = np.arange(int(0.9 * SR)) / SR
    f = hz(m)
    s = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.35) + 0.4 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t / 0.12)
    return s * 0.18

KICK, HATC, HATO, CRASH = kick(), hat(), hat(True), crash()

# ---------------------------------------------------------------- the score
# MIDI: F4 65 G4 67 A4 69 Bb4 70 C5 72 D5 74 Eb5 75 F5 77 G5 79 A5 81 Bb5 82 C6 84
# Lead trumpet melody, (start beat within bar, length, midi); one list per bar.
LEAD = {
 # --- fanfare
 0: [(0, 1/3, 70), (1/3, 1/3, 70), (2/3, 1/3, 70), (1, 1.5, 74), (2.5, .5, 77), (3, 1, 82)],
 1: [(0, 2.5, 82), (3, 1/3, 77), (10/3, 1/3, 79), (11/3, 1/3, 81)],
 # --- A (Bb Gm Eb F Bb Gm Cm-F Bb)
 2: [(0, .5, 65), (.5, .5, 70), (1, 1, 74), (2, .5, 72), (2.5, .5, 74), (3, 1, 77)],
 3: [(0, 1.5, 79), (1.5, .5, 77), (2, 1, 74), (3, 1, 70)],
 4: [(0, .5, 75), (.5, .5, 77), (1, 1, 79), (2, 1, 82), (3, 1, 79)],
 5: [(0, 3, 77)],
 6: [(0, .5, 65), (.5, .5, 70), (1, 1, 74), (2, .5, 72), (2.5, .5, 74), (3, 1, 77)],
 7: [(0, .5, 79), (.5, .5, 81), (1, 1.5, 82), (2.5, .5, 79), (3, 1, 77)],
 8: [(0, 1, 75), (1, 1, 79), (2, 1, 77), (3, 1, 69)],
 9: [(0, 2, 70)],
 # --- B (Eb F Dm Gm Cm F Bb F7)
 10: [(0, 1, 82), (1, .5, 79), (1.5, .5, 75), (2, 1, 79), (3, 1, 82)],
 11: [(0, 1.5, 81), (1.5, .5, 77), (2, 2, 72)],
 12: [(0, .5, 74), (.5, .5, 77), (1, 1, 81), (2, .5, 77), (2.5, .5, 74), (3, 1, 69)],
 13: [(0, 1, 70), (1, 1, 74), (2, 2, 79)],
 14: [(0, .5, 79), (.5, .5, 77), (1, 1, 75), (2, .5, 72), (2.5, .5, 75), (3, 1, 79)],
 15: [(0, 1, 77), (1, 1, 81), (2, 2, 84)],
 16: [(0, 1.5, 82), (1.5, .5, 81), (2, .5, 79), (2.5, .5, 77), (3, 1, 74)],
 17: [(0, 1, 75), (1, 1, 72), (2, 1, 69), (3, 1, 65)],
 # --- turnaround (Gm | F) into the fanfare
 18: [],
 19: [(0, .25, 65), (.25, .25, 67), (.5, .25, 69), (.75, .25, 70), (1, .25, 72), (1.25, .25, 74),
      (1.5, .25, 75), (1.75, .25, 76), (2, 1.5, 77)],
}
# chord per bar (root midi for bass, chord tones for stabs)
CH = {0: "Bb", 1: "Bb", 2: "Bb", 3: "Gm", 4: "Eb", 5: "F", 6: "Bb", 7: "Gm", 8: "Cm/F", 9: "Bb",
      10: "Eb", 11: "F", 12: "Dm", 13: "Gm", 14: "Cm", 15: "F", 16: "Bb", 17: "F7", 18: "Gm", 19: "F"}
TONES = {"Bb": (46, [62, 65, 70]), "Gm": (43, [62, 67, 70]), "Eb": (39, [63, 67, 70]),
         "F": (41, [60, 65, 69]), "Cm": (36, [60, 63, 67]), "Dm": (38, [62, 65, 69]),
         "F7": (41, [60, 63, 69])}
SCALE = sorted(  # B-flat major pitch classes (Bb C D Eb F G A)
    ((p + 10) % 12) for p in [0, 2, 4, 5, 7, 9, 11])

def third_below(m):
    """Diatonic third below in B-flat major (second trumpet)."""
    pcs = SCALE
    x = m - 1
    steps = 0
    while steps < 2:
        if x % 12 in pcs:
            steps += 1
            if steps == 2:
                return x
        x -= 1
    return x

def chord_of(bar, beat):
    c = CH[bar]
    if c == "Cm/F":
        c = "Cm" if beat < 2 else "F"
    return TONES[c]

# lead trumpet (+ second trumpet in thirds on the A/B tunes)
for bar, notes in LEAD.items():
    for (b, d, m) in notes:
        beat = bar * 4 + b
        put(beat, brass(m, d * BEAT * 0.97, bright=1.1), pan=0.25, gain=0.55)
        if 2 <= bar <= 17 or bar == 1:
            put(beat, brass(third_below(m), d * BEAT * 0.97, bright=0.9), pan=-0.1, gain=0.33)

# fanfare: full brass chords under the lead
for (b, d) in [(0, 1/3), (1/3, 1/3), (2/3, 1/3), (1, 1.5), (2.5, .5), (3, 1), (4, 2.5)]:
    for m in [58, 62, 65]:
        put(b, brass(m, d * BEAT * 0.95, bright=1.0, vib=False), pan=-0.35, gain=0.30)

# horn/trombone stabs: on the 'and' of 2 and on 4 in the tunes; answering
# figures in the bars where the tune holds; punchy pushes in the turnaround
STAB_PAT = {"tune": [(1.5, .3), (3, .3)], "answer": [(2.5, .25), (3, .25), (3.5, .45)],
            "turn": [(0, .4), (1.5, .3), (2.5, .3), (3, .6)]}
for bar in range(2, 20):
    pat = "answer" if bar in (5, 9) else "turn" if bar == 18 else "tune"
    if bar == 19:
        pat = None
    if pat is None:
        continue
    for (b, d) in STAB_PAT[pat]:
        _, tones = chord_of(bar, b)
        for m in tones:
            put(bar * 4 + b, brass(m - 12, d * BEAT, bright=1.4, vib=False, scoop=False), pan=-0.4, gain=0.27)
# bar 20 (index 19): rising chord pushes under the run, then a hit on 3
for b, tones in [(2, [60, 65, 69]), (3, [62, 65, 70])]:
    for m in tones:
        put(19 * 4 + b, brass(m - 12, .45 * BEAT, bright=1.5, vib=False, scoop=False), pan=-0.4, gain=0.3)

# bass: driving 8ths walk (root, root, fifth, root, octave, fifth, approach)
for bar in range(BARS):
    for half in range(2):
        root, _ = chord_of(bar, half * 2)
        nxt, _ = chord_of((bar + 1) % BARS, 0)
        if half == 0:
            line = [(0, .5, root), (.5, .5, root), (1, .5, root + 7), (1.5, .5, root + 12)]
        else:
            appr = nxt + (1 if nxt < root else -1) if nxt != root else root + 7
            line = [(2, .5, root), (2.5, .5, root + 7), (3, .5, root + 12), (3.5, .5, appr)]
        if bar == 0 or bar == 1:     # fanfare: bass on the hits only
            line = [(0, 1, 46)] if half == 0 else ([(3, 1, 46)] if bar == 0 else [])
        for (b, d, m) in line:
            put(bar * 4 + b, bass(m, d * BEAT * 0.85), gain=0.75)

# drums
for bar in range(BARS):
    base = bar * 4
    if bar == 0:
        put(base, CRASH, pan=0.3); put(base, KICK, gain=0.9)
        for b in (1, 3):
            put(base + b, KICK, gain=0.8)
        continue
    if bar == 1:      # snare roll building into the tune
        for i in range(16):
            put(base + i * 0.25, snare(0.35 + 0.6 * i / 15), pan=0.1)
        put(base, KICK)
        continue
    if bar in (2, 10):
        put(base, CRASH, pan=0.3)
    for b in (0, 2):
        put(base + b, KICK)
    if bar % 2 == 1:
        put(base + 2.5, KICK, gain=0.7)
    for b in (1, 3):
        put(base + b, snare(), pan=0.1)
    put(base + 3.75, snare(0.35), pan=0.1)          # marching ghost note
    for i in range(8):
        o = (i == 7)
        put(base + i * 0.5, HATO if o else HATC, pan=0.45, gain=0.9 if i % 2 == 0 else 0.6)
    if bar == 19:                                    # fill back to the fanfare
        for i in range(8):
            put(base + 2 + i * 0.25, snare(0.5 + 0.5 * i / 7), pan=0.1)

# glockenspiel sparkle doubling the lead an octave up in the B tune
for bar in range(10, 18):
    for (b, d, m) in LEAD[bar]:
        put(bar * 4 + b, glock(m + 12), pan=0.5, gain=0.8)

# ---------------------------------------------------------------- wrap + reverb
def wrap(x):
    y = x[:N].copy()
    tail = x[N:]
    y[:len(tail)] += tail                            # tails land in bar 1 of the next pass
    return y

l, r = wrap(L), wrap(R)
# reverb: circular convolution with a decaying noise impulse (seamless by construction)
ir_n = int(1.3 * SR)
ti = np.arange(ir_n) / SR
irl = rng.standard_normal(ir_n) * np.exp(-ti / 0.32); irl[:int(0.012 * SR)] = 0
irr = rng.standard_normal(ir_n) * np.exp(-ti / 0.32); irr[:int(0.017 * SR)] = 0
for ir in (irl, irr):
    ir /= np.sqrt(np.sum(ir ** 2))
def circ_conv(x, h):
    H = np.fft.rfft(np.concatenate([h, np.zeros(N - len(h))]))
    return np.fft.irfft(np.fft.rfft(x) * H, N)
mono = 0.5 * (l + r)
wl, wr = circ_conv(mono, irl), circ_conv(mono, irr)
l, r = l + 0.22 * wl, r + 0.22 * wr

st = np.stack([l, r], 1)
st /= np.max(np.abs(st))

# ---------------------------------------------------------------- loudness
def write_wav(path, x):
    x = np.clip(x, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())

def lufs(path):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=framelog=quiet",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", out)[-1])

def limit(x, ceil=0.93):
    # smooth soft-knee limiter (memoryless, so the loop stays seamless)
    k = 0.75
    y = x.copy()
    a = np.abs(x)
    over = a > k
    y[over] = np.sign(x[over]) * (k + (ceil - k) * np.tanh((a[over] - k) / (ceil - k)))
    return y

tmp = tempfile.mkdtemp()
wav = os.path.join(tmp, "title.wav")
g = 0.5
for _ in range(4):
    write_wav(wav, limit(st * g))
    cur = lufs(wav)
    if abs(cur - TARGET_LUFS) < 0.2:
        break
    g *= 10 ** ((TARGET_LUFS - cur) / 20)
print(f"loudness {cur:.1f} LUFS (target {TARGET_LUFS}), length {N / SR:.2f} s, {BPM:g} bpm, B-flat major")
dst = os.path.join(OUT, "title_theme.ogg")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "libvorbis", "-q:a", "6", dst], check=True)
if "--wav" in sys.argv:
    import shutil; shutil.copy(wav, "/tmp/title_theme_master.wav")
print("wrote", os.path.normpath(dst))
