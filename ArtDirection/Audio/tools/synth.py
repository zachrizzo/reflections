"""Procedural stand-in sound effects (numpy only). python synth.py [Name ...] -> proc/synth/Name_NN.wav"""
import sys, os, json, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import audiolib as A

SR = 44100
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "proc", "synth")
FOLEY = os.path.join(ROOT, "foley")  # WAVs exported from /Game/Audio/Foley (GASP)


# ---------------------------------------------------------------- primitives
def n_(d):
    return int(round(d * SR))


def tt(d):
    return np.arange(n_(d)) / SR


def white(rng, n):
    return rng.standard_normal(n).astype(np.float32)


def colored(rng, n, slope_db_oct=-3.0, circular=False):
    """Noise with a spectral tilt via FFT (pink=-3, brown=-6). FFT synthesis is inherently loopable."""
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    f[0] = f[1]
    spec *= (f / 1000.0) ** (slope_db_oct / 6.0206)
    y = np.fft.irfft(spec, n).astype(np.float32)
    return y / (np.abs(y).max() + 1e-9)


def fft_filter(x, lo=None, hi=None, circular=False):
    """Static brickwall-ish band filter with soft (raised-cosine) skirts."""
    n = len(x)
    N = n if circular else int(2 ** np.ceil(np.log2(n * 2)))
    X = np.fft.rfft(x, N)
    f = np.fft.rfftfreq(N, 1 / SR)
    g = np.ones_like(f)
    if lo:
        g *= np.clip((f - lo * 0.7) / (lo * 0.3 + 1e-9), 0, 1)
    if hi:
        g *= np.clip((hi * 1.3 - f) / (hi * 0.3 + 1e-9), 0, 1)
    return np.fft.irfft(X * g, N)[:n].astype(np.float32)


def stft_sculpt(x, center_fn, width_oct_fn, gain_fn=None, nfft=1024, hop=256):
    """Time-varying band-pass: per STFT frame keep a Gaussian (in octaves) band around center_fn(t)."""
    n = len(x)
    win = np.hanning(nfft).astype(np.float32)
    pad = np.concatenate([np.zeros(nfft, np.float32), x, np.zeros(nfft, np.float32)])
    frames = 1 + (len(pad) - nfft) // hop
    out = np.zeros(len(pad), np.float32)
    norm = np.zeros(len(pad), np.float32)
    f = np.fft.rfftfreq(nfft, 1 / SR)
    lf = np.log2(np.maximum(f, 20))
    for i in range(frames):
        s = i * hop
        tsec = max(0.0, (s - nfft + nfft / 2) / SR)
        seg = pad[s : s + nfft] * win
        S = np.fft.rfft(seg)
        c = np.log2(max(30.0, center_fn(tsec)))
        w = max(0.05, width_oct_fn(tsec))
        g = np.exp(-0.5 * ((lf - c) / w) ** 2)
        if gain_fn is not None:
            g = g * gain_fn(tsec)
        out[s : s + nfft] += np.fft.irfft(S * g, nfft).astype(np.float32) * win
        norm[s : s + nfft] += win ** 2
    out = out / np.maximum(norm, 1e-3)
    return out[nfft : nfft + n]


def env_ad(n, attack_s, decay_s, curve=4.0):
    a = max(1, n_(attack_s))
    e = np.ones(n, np.float32)
    e[:a] = np.linspace(0, 1, a) ** 1.5
    rest = n - a
    if rest > 0:
        e[a:] = np.exp(-curve * np.arange(rest) / max(1, n_(decay_s)))
    return e


def bell_env(n, peak_frac=0.5, sharp=2.0):
    x = np.linspace(0, 1, n)
    p = peak_frac
    e = np.where(x < p, (x / p) ** sharp, ((1 - x) / (1 - p)) ** sharp)
    return e.astype(np.float32)


def partials(d, freqs, amps, decays, rng=None, detune_cents=0.0, voices=1, attack=0.002, phase_rand=True):
    t = tt(d)
    y = np.zeros(len(t), np.float32)
    rng = rng or np.random.default_rng(0)
    for f, a, dk in zip(freqs, amps, decays):
        for v in range(voices):
            cents = (v - (voices - 1) / 2) * detune_cents
            ff = f * 2 ** (cents / 1200)
            ph = rng.uniform(0, 2 * np.pi) if phase_rand else 0
            y += (a / voices) * np.sin(2 * np.pi * ff * t + ph).astype(np.float32) * np.exp(-t / dk).astype(np.float32)
    a = max(1, n_(attack))
    y[:a] *= np.linspace(0, 1, a)
    return y


def sweep_sine(d, f0, f1, curve="exp"):
    t = tt(d)
    if curve == "exp":
        f = f0 * (f1 / f0) ** (t / d)
    else:
        f = f0 + (f1 - f0) * t / d
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph).astype(np.float32)


def impulses(rng, d, rate_fn, decay_ms=(0.5, 3.0), lo=1500, hi=8000):
    """Sparse crackle: random clicks with density rate_fn(t) per second, band-limited."""
    n = n_(d)
    y = np.zeros(n, np.float32)
    t = 0.0
    while t < d:
        r = max(1e-3, rate_fn(t))
        t += rng.exponential(1.0 / r)
        if t >= d:
            break
        i = n_(t)
        L = n_(rng.uniform(*decay_ms) / 1000 * 6)
        if L < 4:
            continue
        burst = rng.standard_normal(L) * np.exp(-np.arange(L) / (L / 6))
        amp = rng.uniform(0.3, 1.0)
        j = min(n, i + L)
        y[i:j] += (amp * burst[: j - i]).astype(np.float32)
    return fft_filter(y, lo, hi)


def blockwise_comb(x, D, g):
    y = x.copy()
    for k in range(D, len(y), D):
        e = min(len(y), k + D)
        y[k:e] += g * y[k - D : e - D]
    return y


def blockwise_allpass(x, D, g):
    y = np.zeros_like(x)
    xd = np.concatenate([np.zeros(D, x.dtype), x])[: len(x)]
    y[:D] = -g * x[:D] + xd[:D]
    for k in range(D, len(y), D):
        e = min(len(y), k + D)
        y[k:e] = -g * x[k:e] + xd[k:e] + g * y[k - D : e - D]
    return y


def reverb(x, wet=0.3, size=1.0, tail_s=1.5, damp_hz=6000):
    tail = np.concatenate([x, np.zeros(n_(tail_s), np.float32)])
    combs = [1557, 1617, 1491, 1422, 1277, 1356]
    fb = 0.80 + 0.12 * min(1.0, size)
    acc = np.zeros_like(tail)
    for c in combs:
        acc += blockwise_comb(tail, int(c * size), fb)
    acc /= len(combs)
    for a in (225, 556, 441, 341):
        acc = blockwise_allpass(acc, int(a * size), 0.5)
    acc = fft_filter(acc, None, damp_hz)
    acc *= np.abs(tail).max() / (np.abs(acc).max() + 1e-9)
    return (1 - wet) * tail + wet * acc


def fade_out(y, ms):
    n = min(len(y), n_(ms / 1000))
    if n > 0:
        y[-n:] *= np.cos(np.linspace(0, np.pi / 2, n)) ** 2
    return y


def mix(*parts):
    n = max(len(p) for p in parts)
    y = np.zeros(n, np.float32)
    for p in parts:
        y[: len(p)] += p
    return y


def at(x, offset_s, total_n=None):
    pad = np.zeros(n_(offset_s), np.float32)
    y = np.concatenate([pad, x])
    if total_n:
        y = np.concatenate([y, np.zeros(max(0, total_n - len(y)), np.float32)])[:total_n]
    return y


def norm(x, peak=0.89):
    return (x * (peak / (np.abs(x).max() + 1e-9))).astype(np.float32)


USE_FOLEY = False  # third-party (Game Animation Sample) layer disabled: keep /Game/Audio/Jam fully original


def load_foley(name):
    if not USE_FOLEY:
        return None
    p = os.path.join(FOLEY, name + ".wav")
    if not os.path.exists(p):
        return None
    d, sr = A.decode(p)
    m = A.to_mono(d)
    if sr != SR:
        idx = np.arange(0, len(m), sr / SR)
        m = np.interp(idx, np.arange(len(m)), m).astype(np.float32)
    return m


# ---------------------------------------------------------------- loop-safe (circular) helpers
def circ_noise(rng, d, lo, hi, slope=-3.0):
    n = n_(d)
    return fft_filter(colored(rng, n, slope), lo, hi, circular=True)


def lfo(d, rate_hz, phase=0.0):
    """Periodic LFO; rate snapped so an integer number of cycles fits d (loop-safe)."""
    cyc = max(1, round(rate_hz * d))
    return np.sin(2 * np.pi * cyc * tt(d) / d + phase).astype(np.float32)


def snap(f, d):
    return round(f * d) / d


# ---------------------------------------------------------------- sounds
def whoosh(rng, d, f_start, f_peak, f_end, peak_frac=0.5, width=0.6, ring=0.0):
    x = colored(rng, n_(d), -1.5)
    def c(t):
        u = t / d
        return f_start * (f_peak / f_start) ** (u / peak_frac) if u < peak_frac else f_peak * (f_end / f_peak) ** ((u - peak_frac) / (1 - peak_frac))
    y = stft_sculpt(x, c, lambda t: width)
    y *= bell_env(len(y), peak_frac, 2.2)
    if ring:
        f0 = rng.uniform(3500, 5200)
        r = partials(d, [f0, f0 * 1.51], [1, 0.5], [d * 0.6, d * 0.4], rng)
        y = y / (np.abs(y).max() + 1e-9) + ring * r * bell_env(len(r), peak_frac, 1.5)
    return y


def S_Sword_Swing(rng):
    d = rng.uniform(0.28, 0.42)
    y = whoosh(rng, d, rng.uniform(500, 900), rng.uniform(2800, 4200), rng.uniform(900, 1500), rng.uniform(0.4, 0.6), 0.45, ring=0.08)
    return fade_out(np.concatenate([y, np.zeros(n_(0.05), np.float32)]), 30)


def S_Sword_Hit(rng):
    d = 0.5
    slice_ = fft_filter(white(rng, n_(0.06)), 2500, 9000) * env_ad(n_(0.06), 0.001, 0.02)
    f0 = rng.uniform(1800, 2600)
    ring = partials(0.4, [f0, f0 * 1.37, f0 * 2.1], [0.4, 0.25, 0.15], [0.08, 0.06, 0.04], rng)
    punch = load_foley(f"foley_punch_0{rng.integers(1, 4)}")
    if punch is None:
        thud = sweep_sine(0.3, rng.uniform(120, 150), 48) * env_ad(n_(0.3), 0.004, 0.12, 1.5)
        body = fft_filter(colored(rng, n_(0.25), -3), 60, 700) * env_ad(n_(0.25), 0.003, 0.09, 1.5)
        meat = fft_filter(white(rng, n_(0.2)), 250, 1600) * env_ad(n_(0.2), 0.003, 0.06, 2.0) * (0.6 + 0.4 * np.sign(rng.standard_normal(n_(0.2))))
        cloth = fft_filter(white(rng, n_(0.12)), 1500, 6000) * env_ad(n_(0.12), 0.004, 0.04)
        punch = mix(norm(thud), 0.8 * norm(body), 0.55 * norm(meat), 0.2 * norm(cloth))
    punch = A.trim_oneshot(punch, SR, head_db=-24.0, tail_db=-60.0, pre_ms=2.0, post_ms=40.0, fade_out_ms=60.0)
    punch = norm(punch[: n_(d)])
    y = mix(0.95 * punch, at(0.4 * norm(slice_), 0.004), at(0.25 * ring, 0.004))
    return fade_out(y[: n_(d)], 60)


def S_Sword_Clash(rng):
    d = 1.3
    f0 = rng.uniform(650, 1100)
    ratios = [1, 1.47, 2.09, 2.56, 3.11, 4.18, 5.33]
    fr = [f0 * r * rng.uniform(0.99, 1.01) for r in ratios]
    am = [1, 0.8, 0.6, 0.5, 0.35, 0.25, 0.18]
    dk = [0.55, 0.42, 0.33, 0.25, 0.18, 0.12, 0.09]
    tone = partials(d, fr, am, dk, rng, detune_cents=6, voices=2)
    hit = fft_filter(white(rng, n_(0.03)), 2000, 12000) * env_ad(n_(0.03), 0.0005, 0.008)
    y = mix(norm(tone) * 0.8, 0.6 * norm(hit))
    return fade_out(reverb(y, 0.18, 0.7, 0.6)[: n_(d + 0.3)], 120)


def S_WorldJump_Whoosh(rng):
    d = 2.4
    x = colored(rng, n_(d), -2.0)
    y = stft_sculpt(x, lambda t: 180 * (5200 / 180) ** ((t / d) ** 1.6), lambda t: 0.9 - 0.4 * t / d)
    y *= (np.linspace(0, 1, len(y)) ** 2.2)
    sub = sweep_sine(d, 38, 70) * np.linspace(0, 1, n_(d)) ** 1.5
    notes = [440, 554.4, 659.3, 880, 1108.7, 1318.5]
    sh = partials(d, notes, [0.5, 0.4, 0.4, 0.3, 0.25, 0.2], [0.9] * 6, rng, detune_cents=10, voices=3)
    sh = sh[::-1] * np.linspace(0, 1, len(sh)) ** 3  # reversed shimmer swelling into the jump
    y = mix(norm(y) * 0.8, 0.35 * norm(sub), 0.35 * norm(sh))
    return fade_out(reverb(y, 0.2, 1.0, 0.4)[: n_(d + 0.15)], 140)


def S_WorldJump_Stinger(rng):
    d = 3.2
    boom = sweep_sine(1.6, 75, 32) * env_ad(n_(1.6), 0.004, 0.55, 3.0)
    burst = stft_sculpt(colored(rng, n_(1.0), -3), lambda t: 4000 * (250 / 4000) ** min(1, t / 0.5), lambda t: 1.2) * env_ad(n_(1.0), 0.001, 0.35)
    chord = [880, 1108.7, 1318.5, 1760, 2217.5, 2637]
    ring = partials(d, chord, [0.6, 0.45, 0.45, 0.35, 0.25, 0.2], [1.6, 1.4, 1.3, 1.1, 0.9, 0.8], rng, detune_cents=12, voices=3, attack=0.02)
    air = fft_filter(colored(rng, n_(d), 0), 5000, 14000) * env_ad(n_(d), 0.05, 1.2) * 0.15
    y = mix(0.9 * norm(boom), 0.4 * norm(burst), at(0.45 * norm(ring), 0.03), air)
    return fade_out(reverb(y, 0.3, 1.2, 1.5)[: n_(d + 1.0)], 400)


def S_WorldJump_Refused(rng):
    d = 0.9
    fz = impulses(rng, 0.6, lambda t: 300 * np.exp(-t * 4), (0.3, 2.0), 1500, 7000) * env_ad(n_(0.6), 0.002, 0.3)
    tone = sweep_sine(0.5, 420, 140) * (1 + 0.5 * np.sin(2 * np.pi * 23 * tt(0.5))) * env_ad(n_(0.5), 0.01, 0.25)
    thud = sweep_sine(0.25, 110, 55) * env_ad(n_(0.25), 0.002, 0.08)
    thud = mix(thud, 0.5 * fft_filter(white(rng, n_(0.2)), 60, 500) * env_ad(n_(0.2), 0.001, 0.06))
    y = mix(0.5 * norm(fz), 0.45 * norm(fft_filter(tone, 100, 2500)), at(0.9 * norm(thud), 0.42))
    return fade_out(y[: n_(d)], 80)


def S_Coin_Pickup(rng):
    d = 0.9
    f0 = rng.uniform(2300, 3100)
    clink = partials(d, [f0, f0 * 2.76, f0 * 5.40, f0 * 1.52], [1, 0.5, 0.25, 0.35], [0.22, 0.12, 0.06, 0.15], rng)
    tick = fft_filter(white(rng, n_(0.008)), 4000, 15000) * env_ad(n_(0.008), 0.0003, 0.002)
    base = rng.choice([1046.5, 1174.7, 1318.5])
    magic = partials(0.8, [base * 2, base * 3], [0.5, 0.3], [0.35, 0.25], rng, detune_cents=8, voices=3, attack=0.01)
    magic *= 1 + 0.15 * np.sin(2 * np.pi * 7 * tt(0.8))
    y = mix(0.9 * norm(clink), 0.5 * norm(tick), at(0.3 * norm(magic), 0.03))
    return fade_out(reverb(y, 0.15, 0.6, 0.4)[: n_(d)], 150)


def S_Page_Pickup(rng):
    d = 1.0
    n = n_(0.6)
    noise = fft_filter(white(rng, n), 900, 7000)
    am = np.zeros(n, np.float32)
    t = 0.0
    while t < 0.55:
        i = n_(t)
        L = n_(rng.uniform(0.015, 0.05))
        seg = np.hanning(L) * rng.uniform(0.4, 1.0)
        am[i : i + L] += seg[: max(0, min(L, n - i))]
        t += rng.uniform(0.02, 0.06)
    rustle = noise * am * env_ad(n, 0.02, 0.35, 2.0)
    chime = partials(0.9, [1568, 2349.3, 3136], [0.5, 0.35, 0.2], [0.4, 0.3, 0.25], rng, detune_cents=8, voices=3, attack=0.02)
    y = mix(0.85 * norm(rustle), at(0.28 * norm(chime), 0.12))
    return fade_out(reverb(y, 0.15, 0.6, 0.4)[: n_(d)], 150)


def S_Heal_Shimmer(rng):
    d = 2.4
    y = np.zeros(n_(d + 1), np.float32)
    notes = [523.25, 659.25, 783.99, 880.0, 1046.5, 1318.5, 1568.0]
    for k, f in enumerate(notes):
        nt = partials(1.4, [f, 2 * f, 3 * f], [0.6, 0.18, 0.07], [0.7, 0.4, 0.25], rng, detune_cents=9, voices=3, attack=0.03)
        y += at(nt * (0.6 + 0.4 * k / len(notes)), 0.06 + k * 0.17, len(y))
    air = fft_filter(colored(rng, len(y), 0), 4000, 12000) * bell_env(len(y), 0.55, 1.5) * 0.12
    y = norm(y) * 0.85 + air
    return fade_out(reverb(y, 0.35, 1.1, 1.2)[: n_(d + 0.8)], 400)


def S_Shield_Up(rng):
    d = 1.6
    whoomp = mix(sweep_sine(0.5, 120, 55) * env_ad(n_(0.5), 0.01, 0.2),
                 0.6 * fft_filter(colored(rng, n_(0.4), -3), 40, 600) * env_ad(n_(0.4), 0.005, 0.12))
    hum = partials(d, [220, 329.6, 440, 659.3, 880], [0.5, 0.35, 0.4, 0.2, 0.15], [5, 5, 5, 5, 5], rng, detune_cents=14, voices=3)
    hum *= np.linspace(0, 1, len(hum)) ** 0.5 * (1 + 0.2 * np.sin(2 * np.pi * 5 * tt(d)))
    glass = partials(d, [1760, 2637, 3520], [0.3, 0.2, 0.15], [0.8, 0.6, 0.5], rng, detune_cents=10, voices=2, attack=0.05)
    y = mix(0.9 * norm(whoomp), at(0.45 * norm(hum) * bell_env(n_(d), 0.45, 1.2), 0.05), at(0.25 * norm(glass), 0.08))
    return fade_out(reverb(y, 0.25, 0.9, 0.8)[: n_(d + 0.4)], 350)


def S_Shield_Block(rng):
    d = 0.9
    f0 = rng.uniform(820, 1050)
    ping = partials(d, [f0, f0 * 2.32, f0 * 4.25, f0 * 6.63], [1, 0.6, 0.35, 0.2], [0.35, 0.22, 0.14, 0.1], rng, detune_cents=5, voices=2)
    buzz = fft_filter(colored(rng, n_(0.5), -1), 300, 3000) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * rng.uniform(38, 48) * tt(0.5)))) * env_ad(n_(0.5), 0.005, 0.18)
    hit = fft_filter(white(rng, n_(0.02)), 1500, 10000) * env_ad(n_(0.02), 0.0005, 0.005)
    y = mix(0.8 * norm(ping), 0.35 * norm(buzz), 0.5 * norm(hit))
    return fade_out(reverb(y, 0.2, 0.7, 0.5)[: n_(d)], 150)


def S_Shield_Loop(rng):
    d = 4.0
    fr = [snap(f, d) for f in (110, 220.25, 330, 440.5, 660)]
    t = tt(d)
    y = np.zeros(len(t), np.float32)
    for f, a in zip(fr, (0.5, 0.6, 0.3, 0.3, 0.12)):
        for dc in (-0.25, 0, 0.25):
            y += a * np.sin(2 * np.pi * (f + dc) * t + rng.uniform(0, 6.28)).astype(np.float32)
    y *= 1 + 0.18 * lfo(d, 0.5)
    shimmer = circ_noise(rng, d, 3000, 9000, 0) * (0.5 + 0.5 * lfo(d, 1.0)) * 0.12
    return norm(y) * 0.8 + shimmer


def S_Projectile_Loop(rng):
    d = 3.0
    w = circ_noise(rng, d, 500, 4000, -2)
    w *= 0.7 + 0.3 * lfo(d, 2.0) * lfo(d, 0.667, 1.0)
    t = tt(d)
    f = snap(196, d)
    hum = np.sin(2 * np.pi * f * t + 0.8 * lfo(d, 6.0)) + 0.4 * np.sin(2 * np.pi * 2 * f * t)
    crack = np.roll(impulses(rng, d, lambda _t: 25, (0.3, 1.5), 2500, 9000), 0)
    return norm(0.8 * norm(w) + 0.35 * norm(hum.astype(np.float32)) + 0.3 * norm(crack))


def S_Levitation_Start(rng):
    d = 1.5
    y = whoosh(rng, d, 250, 2600, 1400, 0.6, 0.8)
    chime = partials(1.2, [1318.5, 1975.5, 2637], [0.4, 0.3, 0.2], [0.5, 0.4, 0.3], rng, detune_cents=10, voices=3, attack=0.05)
    y = mix(norm(y) * 0.85, at(0.22 * norm(chime), 0.35))
    return fade_out(reverb(y, 0.2, 0.9, 0.6)[: n_(d + 0.3)], 300)


def S_Levitation_Loop(rng):
    d = 4.0
    w = circ_noise(rng, d, 200, 5000, -3)
    X = np.fft.rfft(w)
    y = np.fft.irfft(X, len(w)).astype(np.float32)
    y *= 0.65 + 0.25 * lfo(d, 0.5) + 0.1 * lfo(d, 1.25, 2.0)
    t = tt(d)
    hum = sum(a * np.sin(2 * np.pi * snap(f, d) * t) for f, a in ((392, 0.4), (587.3, 0.25), (784, 0.15))).astype(np.float32)
    return norm(0.85 * norm(y) + 0.18 * norm(hum) * (0.8 + 0.2 * lfo(d, 0.25)))


def S_UI_Click(rng):
    f = rng.uniform(1800, 2800)
    body = rng.uniform(550, 850)
    y = mix(partials(0.06, [f], [1], [0.004], rng), 0.6 * partials(0.06, [body], [1], [0.012], rng),
            0.3 * fft_filter(white(rng, n_(0.004)), 3000, 12000))
    return fade_out(y, 15)


def S_UI_Hover(rng):
    f = rng.uniform(1100, 1400)
    y = partials(0.08, [f, 2 * f], [1, 0.2], [0.02, 0.012], rng, attack=0.006)
    return fade_out(y, 20)


def S_UI_Confirm(rng):
    a, b = (659.25, 987.77)
    n1 = partials(0.6, [a, 2 * a, 3 * a], [0.7, 0.2, 0.08], [0.25, 0.15, 0.08], rng, detune_cents=6, voices=2, attack=0.004)
    n2 = partials(0.7, [b, 2 * b, 3 * b], [0.7, 0.2, 0.08], [0.3, 0.18, 0.1], rng, detune_cents=6, voices=2, attack=0.004)
    y = mix(n1, at(n2, 0.085))
    return fade_out(reverb(y, 0.15, 0.5, 0.3)[: n_(0.85)], 120)


def S_Door_Unseal(rng):
    d = 4.6
    total = n_(d)
    crack = fft_filter(white(rng, n_(0.08)), 800, 9000) * env_ad(n_(0.08), 0.001, 0.025)
    seal = partials(1.8, [392, 587.3, 784, 1174.7, 1568], [0.6, 0.45, 0.4, 0.25, 0.2], [1.0, 0.9, 0.8, 0.6, 0.5], rng, detune_cents=10, voices=3, attack=0.01)
    gd = 3.0
    grind = fft_filter(colored(rng, n_(gd), -5), 40, 1200)
    rough = np.abs(fft_filter(white(rng, n_(gd)), 15, 60))
    grind = grind * (0.5 + rough / (rough.max() + 1e-9)) * bell_env(n_(gd), 0.3, 0.8)
    grit = impulses(rng, gd, lambda t: 60, (0.5, 3), 800, 4000) * bell_env(n_(gd), 0.3, 0.8)
    thud = sweep_sine(0.4, 90, 40) * env_ad(n_(0.4), 0.003, 0.15)
    y = mix(at(0.6 * norm(crack), 0.0, total), at(0.5 * norm(seal), 0.02, total), at(0.75 * norm(grind), 1.2, total),
            at(0.3 * norm(grit), 1.2, total), at(0.8 * norm(thud), 4.15, total))
    return fade_out(reverb(y, 0.2, 1.1, 0.8)[: n_(d + 0.6)], 400)


# --- spell stand-ins (ElevenLabs takes replace these when they arrive)
def S_Fire_Cast(rng):
    d = 1.0
    wh = whoosh(rng, d, 300, 1800, 700, 0.35, 0.9)
    roar = fft_filter(colored(rng, n_(d), -4), 60, 1500) * (0.6 + 0.4 * np.abs(fft_filter(white(rng, n_(d)), 6, 18)) * 3) * env_ad(n_(d), 0.04, 0.45)
    crk = impulses(rng, d, lambda t: 80 * np.exp(-t * 2), (0.2, 1.2), 2000, 9000)
    return fade_out(mix(0.7 * norm(wh), 0.6 * norm(roar), 0.35 * norm(crk)), 150)


def S_Fire_Impact(rng):
    d = 1.6
    boom = sweep_sine(0.9, 85, 38) * env_ad(n_(0.9), 0.003, 0.3)
    blast = stft_sculpt(colored(rng, n_(1.2), -2), lambda t: 5000 * (300 / 5000) ** min(1, t / 0.6), lambda t: 1.3) * env_ad(n_(1.2), 0.002, 0.4)
    crk = impulses(rng, d, lambda t: 120 * np.exp(-t * 2.5), (0.2, 1.5), 1500, 9000)
    y = mix(0.9 * norm(boom), 0.7 * norm(blast), 0.3 * norm(crk))
    return fade_out(reverb(y, 0.2, 1.0, 0.8)[: n_(d + 0.4)], 300)


def bubbles(rng, d, count, f_lo=400, f_hi=1600):
    y = np.zeros(n_(d), np.float32)
    for _ in range(count):
        t0 = rng.uniform(0, d * 0.85)
        L = rng.uniform(0.02, 0.07)
        f0 = rng.uniform(f_lo, f_hi)
        b = sweep_sine(L, f0, f0 * rng.uniform(1.3, 2.2)) * env_ad(n_(L), 0.002, L / 3)
        i = n_(t0)
        y[i : i + len(b)] += rng.uniform(0.3, 1) * b[: max(0, min(len(b), len(y) - i))]
    return y


def S_Water_Cast(rng):
    d = 1.1
    rush = whoosh(rng, d, 400, 2200, 900, 0.4, 1.0)
    y = mix(0.7 * norm(rush), 0.5 * norm(bubbles(rng, d, 45)))
    return fade_out(y, 150)


def S_Water_Impact(rng):
    d = 1.3
    splash = stft_sculpt(white(rng, n_(d)), lambda t: 3000 * (1200 / 3000) ** min(1, t / 0.5), lambda t: 1.5) * env_ad(n_(d), 0.003, 0.35)
    y = mix(0.8 * norm(splash), 0.4 * norm(bubbles(rng, d, 60, 300, 1200)), 0.5 * norm(sweep_sine(0.3, 120, 60) * env_ad(n_(0.3), 0.002, 0.1)))
    return fade_out(y, 200)


def S_Ice_Cast(rng):
    d = 1.1
    crk = impulses(rng, d, lambda t: 40 + 400 * (t / d), (0.2, 0.8), 2500, 12000) * np.linspace(0.3, 1, n_(d))
    glass = partials(d, [3135.96, 4186, 5274, 6271.9], [0.5, 0.4, 0.3, 0.2], [0.6, 0.5, 0.4, 0.3], rng, detune_cents=15, voices=3, attack=0.3)
    y = mix(0.7 * norm(crk), 0.3 * norm(glass))
    return fade_out(reverb(y, 0.2, 0.8, 0.5)[: n_(d + 0.3)], 200)


def S_Ice_Impact(rng):
    d = 1.2
    crack = fft_filter(white(rng, n_(0.03)), 1000, 14000) * env_ad(n_(0.03), 0.0003, 0.006)
    y = np.zeros(n_(d), np.float32)
    for _ in range(40):
        t0 = abs(rng.normal(0, 0.18))
        f = rng.uniform(2500, 9000)
        tk = partials(0.3, [f, f * 1.7], [1, 0.4], [rng.uniform(0.03, 0.15)] * 2, rng)
        i = n_(t0)
        y[i : i + len(tk)] += rng.uniform(0.2, 1) * tk[: max(0, min(len(tk), len(y) - i))]
    y = mix(0.8 * norm(crack), 0.7 * norm(y))
    return fade_out(reverb(y, 0.2, 0.8, 0.5)[: n_(d + 0.3)], 200)


def S_Lightning_Cast(rng):
    d = 0.9
    t = tt(d)
    f0 = 90 + 30 * np.sin(2 * np.pi * 7 * t) + 20 * rng.standard_normal(len(t)).cumsum() / np.sqrt(len(t))
    saw = 2 * ((np.cumsum(f0) / SR) % 1.0) - 1
    arc = fft_filter(saw.astype(np.float32), 400, 9000) * env_ad(len(t), 0.02, 0.4)
    crk = impulses(rng, d, lambda _t: 250, (0.1, 0.6), 2000, 12000)
    zap = fft_filter(sweep_sine(0.25, 3500, 300), 200, 8000) * env_ad(n_(0.25), 0.002, 0.08)
    return fade_out(mix(0.6 * norm(arc), 0.5 * norm(crk), 0.6 * norm(zap)), 120)


def S_Lightning_Impact(rng):
    d = 2.0
    crack = fft_filter(white(rng, n_(0.05)), 500, 16000) * env_ad(n_(0.05), 0.0002, 0.01)
    snap_ = impulses(rng, 0.15, lambda _t: 900, (0.1, 0.5), 2000, 14000)
    rumble = fft_filter(colored(rng, n_(d), -5), 25, 300) * env_ad(n_(d), 0.05, 0.9, 2.5) * (1 + 0.4 * np.sin(2 * np.pi * 3 * tt(d)))
    y = mix(1.0 * norm(crack), 0.6 * norm(snap_), at(0.8 * norm(rumble), 0.02))
    return fade_out(reverb(y, 0.25, 1.2, 1.0)[: n_(d + 0.5)], 400)


def S_Earth_Cast(rng):
    d = 1.3
    grind = fft_filter(colored(rng, n_(d), -5), 40, 600)
    rough = np.abs(fft_filter(white(rng, n_(d)), 10, 40))
    grind = grind * (0.4 + rough / (rough.max() + 1e-9)) * bell_env(n_(d), 0.4, 1.0)
    gravel = impulses(rng, d, lambda t: 50 + 150 * t, (0.5, 3), 700, 4000) * np.linspace(0.3, 1, n_(d))
    return fade_out(mix(0.8 * norm(grind), 0.4 * norm(gravel)), 200)


def S_Earth_Impact(rng):
    d = 1.5
    thud = sweep_sine(0.6, 70, 32) * env_ad(n_(0.6), 0.003, 0.22)
    crunch = fft_filter(white(rng, n_(0.3)), 200, 4000) * env_ad(n_(0.3), 0.001, 0.08) * (0.6 + 0.4 * np.sign(rng.standard_normal(n_(0.3))))
    debris = impulses(rng, d, lambda t: 120 * np.exp(-t * 2.5), (1, 5), 300, 3500)
    y = mix(1.0 * norm(thud), 0.6 * norm(crunch), 0.4 * norm(debris))
    return fade_out(reverb(y, 0.18, 1.0, 0.7)[: n_(d + 0.3)], 300)


def S_Arcane_Cast(rng):
    d = 1.1
    t = tt(d)
    f = 180 * (2.3) ** (t / d)
    mod = np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR) * 2.0
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR + mod).astype(np.float32)
    tone2 = np.sin(2 * np.pi * np.cumsum(f * 1.004) / SR + mod).astype(np.float32)
    hum = (tone + tone2) * np.linspace(0.2, 1, len(t)) ** 1.5
    wh = whoosh(rng, d, 600, 3000, 1500, 0.75, 0.7)
    y = mix(0.6 * norm(fft_filter(hum, 80, 6000)), 0.45 * norm(wh))
    return fade_out(reverb(y, 0.25, 0.9, 0.5)[: n_(d + 0.3)], 200)


def S_Arcane_Impact(rng):
    d = 1.3
    chord = partials(d, [523.25, 784, 1046.5, 1568, 2093], [0.6, 0.5, 0.4, 0.3, 0.2], [0.6, 0.5, 0.45, 0.35, 0.3], rng, detune_cents=12, voices=3, attack=0.004)
    boom = sweep_sine(0.6, 80, 45) * env_ad(n_(0.6), 0.003, 0.2)
    burst = fft_filter(colored(rng, n_(0.3), -2), 300, 6000) * env_ad(n_(0.3), 0.001, 0.08)
    y = mix(0.6 * norm(chord), 0.8 * norm(boom), 0.4 * norm(burst))
    return fade_out(reverb(y, 0.3, 1.0, 0.9)[: n_(d + 0.5)], 300)


def S_Infected_Growl(rng):
    d = rng.uniform(1.1, 1.6)
    t = tt(d)
    f0 = rng.uniform(70, 105) * (1 + 0.08 * np.sin(2 * np.pi * rng.uniform(3, 6) * t)) * (1 + 0.04 * rng.standard_normal(len(t)).cumsum() / np.sqrt(len(t)) * 20)
    ph = np.cumsum(f0) / SR
    pulse = (np.maximum(0, np.sin(2 * np.pi * ph)) ** 8).astype(np.float32)
    pulse *= 1 + 0.5 * rng.standard_normal(len(t)).astype(np.float32) * 0.3  # roughness
    src = pulse + 0.15 * white(rng, len(t))
    fmts = [(rng.uniform(550, 750), 0.35), (rng.uniform(1000, 1250), 0.3), (rng.uniform(2300, 2700), 0.25)]
    y = sum(a * stft_sculpt(src, lambda _t, f=f: f, lambda _t: 0.25) for f, a in fmts)
    breath = fft_filter(white(rng, len(t)), 500, 5000) * 0.08
    y = (y + breath) * bell_env(len(t), rng.uniform(0.3, 0.5), 1.0)
    return fade_out(y, 120)


SOUNDS = {k[2:]: v for k, v in globals().items() if k.startswith("S_")}
VARIANTS = {"Sword_Swing": 4, "Sword_Hit": 3, "Sword_Clash": 3, "Coin_Pickup": 3, "UI_Click": 4, "UI_Hover": 2,
            "Infected_Growl": 3, "Shield_Block": 2, "Fire_Cast": 2, "Fire_Impact": 2, "Water_Cast": 2, "Water_Impact": 2,
            "Ice_Cast": 2, "Ice_Impact": 2, "Lightning_Cast": 2, "Lightning_Impact": 2, "Earth_Cast": 2, "Earth_Impact": 2,
            "Arcane_Cast": 2, "Arcane_Impact": 2}


def main(names):
    import spells, villain, physics_sfx
    SOUNDS.update(spells.SOUNDS)
    SOUNDS.update(villain.SOUNDS)
    VARIANTS.update(villain.VARIANTS)
    SOUNDS.update(physics_sfx.SOUNDS)
    VARIANTS.update(physics_sfx.VARIANTS)
    for k in spells.SOUNDS:
        VARIANTS[k] = 3
    os.makedirs(OUT, exist_ok=True)
    rep = {}
    for name in names:
        fn = SOUNDS[name]
        k = VARIANTS.get(name, 1)
        for f in os.listdir(OUT):
            if f.startswith(name + "_") and f[len(name) + 1 : -4].isdigit():
                os.remove(os.path.join(OUT, f))
        outs = []
        for i in range(k):
            rng = np.random.default_rng(zlib.crc32(name.encode()) % 10000 + 97 * i)
            y = fn(rng).astype(np.float32)
            y = np.nan_to_num(y)
            y = y / (np.abs(y).max() + 1e-9) * 0.89
            p = os.path.join(OUT, f"{name}_{i + 1:02d}.wav")
            A.write_wav(p, y, SR)
            outs.append(A.describe(y, SR))
        rep[name] = outs
        print(name, [(o["dur"], o["rms_db"], o["centroid_hz"]) for o in outs])
    rp = os.path.join(ROOT, "synth_report.json")
    old = json.load(open(rp)) if os.path.exists(rp) else {}
    old.update(rep)
    json.dump(old, open(rp, "w"), indent=1, default=float)


if __name__ == "__main__":
    main(sys.argv[1:] or list(SOUNDS))
