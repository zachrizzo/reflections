"""Layered procedural element spells (cast + impact). Each design = transient + body + texture + tail layers."""
import numpy as np
import synth as S

SR = S.SR


# ---------------------------------------------------------------- layer helpers
def smooth(rng, n, cutoff_hz):
    """Band-limited random LFO in [-1, 1]."""
    x = S.fft_filter(rng.standard_normal(n).astype(np.float32), None, cutoff_hz)
    return x / (np.abs(x).max() + 1e-9)


def turb(rng, n, lo_hz, hi_hz, depth=0.7):
    x = S.fft_filter(rng.standard_normal(n).astype(np.float32), lo_hz, hi_hz)
    x = x / (np.abs(x).max() + 1e-9)
    return (1 - depth) + depth * np.abs(x)


def damped(f, tau, d, phase=0.0):
    t = S.tt(d)
    return (np.exp(-t / tau) * np.sin(2 * np.pi * f * t + phase)).astype(np.float32)


def pops(rng, d, rate_fn, f_range, tau_range, amp_range=(0.3, 1.0), total=None):
    """Scattered resonant pops (damped sinusoids) with time-varying density."""
    n = total or S.n_(d)
    y = np.zeros(n, np.float32)
    t = 0.0
    while True:
        r = max(1e-3, rate_fn(t))
        t += rng.exponential(1.0 / r)
        if t >= d:
            break
        f = np.exp(rng.uniform(np.log(f_range[0]), np.log(f_range[1])))
        tau = rng.uniform(*tau_range)
        L = min(S.n_(tau * 7), n)
        p = damped(f, tau, L / SR, rng.uniform(0, 6.28)) * rng.uniform(*amp_range)
        i = S.n_(t)
        j = min(n, i + len(p))
        y[i:j] += p[: j - i]
    return y


def burst(rng, d, lo, hi, attack, decay, slope=0.0):
    x = S.colored(rng, S.n_(d), slope) if slope else S.white(rng, S.n_(d))
    return S.fft_filter(x, lo, hi) * S.env_ad(S.n_(d), attack, decay)


def sweep_noise(rng, d, f0, f1, width, slope=-1.5, shape=1.0):
    x = S.colored(rng, S.n_(d), slope)
    return S.stft_sculpt(x, lambda t: f0 * (f1 / f0) ** min(1.0, (t / d) ** shape), lambda t: width)


def click(rng, ms=4, lo=800, hi=16000):
    return burst(rng, ms / 1000, lo, hi, 0.0002, ms / 4000)


def sub_drop(d, f0, f1, decay):
    return S.sweep_sine(d, f0, f1) * S.env_ad(S.n_(d), 0.002, decay, 4.0)


def env_rise(n, p=1.5):
    return (np.linspace(0, 1, n) ** p).astype(np.float32)


def N(x):
    return S.norm(x, 1.0)


# ---------------------------------------------------------------- FIRE
def Fire_Cast(rng):
    d = rng.uniform(0.9, 1.1)
    n = S.n_(d)
    ignite = S.stft_sculpt(S.colored(rng, S.n_(0.35), -2), lambda t: 250 * (1800 / 250) ** min(1, t / 0.12), lambda t: 0.9) * S.env_ad(S.n_(0.35), 0.005, 0.12)
    whoosh = S.whoosh(rng, d, rng.uniform(450, 600), rng.uniform(1200, 1600), rng.uniform(700, 900), 0.3, 1.0)
    roar = S.fft_filter(S.colored(rng, n, -5), 50, 900) * turb(rng, n, 6, 25) * S.env_ad(n, 0.04, d * 0.45, 3.0)
    crk = pops(rng, d, lambda t: 70 * np.exp(-1.5 * t), (1500, 6500), (0.0008, 0.003))
    lowpop = pops(rng, d, lambda t: 12 * np.exp(-2 * t), (250, 700), (0.004, 0.01))
    y = S.mix(0.85 * N(ignite), 0.55 * N(whoosh), 0.6 * N(roar), 0.3 * N(crk), 0.2 * N(lowpop))
    return S.fade_out(y, 140)


def Fire_Impact(rng):
    d = rng.uniform(1.5, 1.9)
    n = S.n_(d)
    tr = click(rng, 4)
    thump = sub_drop(0.8, rng.uniform(75, 90), 34, 0.3)
    blast = S.stft_sculpt(S.colored(rng, S.n_(1.0), -1.5), lambda t: 7000 * (300 / 7000) ** min(1, t / 0.5), lambda t: 1.4) * S.env_ad(S.n_(1.0), 0.002, 0.42)
    roar = S.fft_filter(S.colored(rng, n, -5), 40, 750) * turb(rng, n, 5, 20) * S.env_ad(n, 0.02, d * 0.5, 3.0)
    crk = pops(rng, d, lambda t: 110 * np.exp(-2.2 * t), (1200, 7000), (0.0008, 0.004))
    y = S.mix(0.7 * N(tr), 1.0 * N(thump), 0.75 * N(blast), S.at(0.55 * N(roar), 0.01), 0.28 * N(crk))
    return S.fade_out(S.reverb(y, 0.15, 1.0, 0.7)[: S.n_(d + 0.4)], 350)


# ---------------------------------------------------------------- WATER
def bubbles(rng, d, count, f_lo, f_hi, center=0.5, spread=0.3, total=None):
    n = total or S.n_(d)
    y = np.zeros(n, np.float32)
    for _ in range(count):
        t0 = float(np.clip(rng.normal(center * d, spread * d), 0, d * 0.95))
        L = rng.uniform(0.015, 0.06)
        f0 = np.exp(rng.uniform(np.log(f_lo), np.log(f_hi)))
        b = S.sweep_sine(L, f0, f0 * rng.uniform(1.4, 2.4)) * S.env_ad(S.n_(L), 0.001, L / 3)
        i = S.n_(t0)
        j = min(n, i + len(b))
        y[i:j] += rng.uniform(0.3, 1) * b[: j - i]
    return y


def Water_Cast(rng):
    d = rng.uniform(1.0, 1.2)
    n = S.n_(d)
    wob = smooth(rng, n, 7.0)
    slosh = S.stft_sculpt(S.colored(rng, n, -2), lambda t: 750 * 1.45 ** wob[min(n - 1, int(t * SR))], lambda t: 0.9)
    slosh *= S.bell_env(n, 0.45, 1.3)
    bub = bubbles(rng, d, 45, 350, 1500, 0.45, 0.25)
    launch = S.whoosh(rng, d, 600, 2600, 1500, 0.75, 0.8)
    spray = S.fft_filter(S.white(rng, n), 4000, 11000) * turb(rng, n, 20, 45, 0.9) * S.bell_env(n, 0.78, 3.0)
    y = S.mix(0.75 * N(slosh), 0.45 * N(bub), 0.55 * N(launch), 0.18 * N(spray))
    return S.fade_out(y, 150)


def Water_Impact(rng):
    d = 1.4
    n = S.n_(d)
    hit = S.stft_sculpt(S.white(rng, S.n_(0.6)), lambda t: 2500 * (700 / 2500) ** min(1, t / 0.25), lambda t: 1.2) * S.env_ad(S.n_(0.6), 0.002, 0.18)
    bub = bubbles(rng, d, 80, 250, 1300, 0.25, 0.2)
    drops = pops(rng, d, lambda t: 90 * np.exp(-2.5 * t), (2500, 8000), (0.001, 0.004))
    thump = sub_drop(0.35, 130, 60, 0.1)
    y = S.mix(0.9 * N(hit), 0.45 * N(bub), 0.25 * N(drops), 0.6 * N(thump))
    return S.fade_out(S.reverb(y, 0.12, 0.8, 0.5)[: S.n_(d + 0.2)], 250)


# ---------------------------------------------------------------- ICE
def ice_ping(rng, d, f0, tau, partials=(1, 2.32, 4.25, 6.63)):
    return S.partials(d, [f0 * r for r in partials], [1, 0.55, 0.3, 0.18], [tau, tau * 0.7, tau * 0.45, tau * 0.3], rng, detune_cents=4, voices=2, attack=0.0008)


def Ice_Cast(rng):
    d = rng.uniform(1.0, 1.2)
    n = S.n_(d)
    hiss = S.fft_filter(S.colored(rng, n, 1.0), 3000, 13000) * env_rise(n, 1.2) * S.bell_env(n, 0.85, 0.6)
    crys = pops(rng, d, lambda t: 25 + 320 * (t / d) ** 1.5, (3000, 11000), (0.0004, 0.0015))
    pings = np.zeros(n, np.float32)
    for k in range(rng.integers(5, 8)):
        t0 = d * (0.15 + 0.75 * k / 7) + rng.uniform(-0.03, 0.03)
        p = ice_ping(rng, 0.5, rng.uniform(2200, 3200) * (1 + 0.5 * t0 / d), rng.uniform(0.06, 0.15))
        pings += S.at(p * rng.uniform(0.4, 1.0), max(0, t0), n)
    y = S.mix(0.35 * N(hiss), 0.5 * N(crys), 0.6 * N(pings))
    return S.fade_out(S.reverb(y, 0.2, 0.8, 0.5)[: S.n_(d + 0.25)], 220)


def Ice_Impact(rng):
    d = 1.3
    n = S.n_(d)
    crack = S.mix(click(rng, 3, 1500), 0.8 * damped(rng.uniform(2200, 3000), 0.015, 0.1))
    ping = ice_ping(rng, 1.0, rng.uniform(1800, 2500), rng.uniform(0.3, 0.45))
    shards = np.zeros(n, np.float32)
    for _ in range(55):
        t0 = min(d * 0.9, rng.exponential(0.16))
        p = ice_ping(rng, 0.25, rng.uniform(3000, 9500), rng.uniform(0.015, 0.09), (1, 2.76))
        shards += S.at(p * rng.uniform(0.2, 1.0), t0, n)
    thunk = sub_drop(0.2, 170, 95, 0.05)
    y = S.mix(0.9 * N(crack), 0.6 * N(ping), 0.65 * N(shards), 0.45 * N(thunk))
    return S.fade_out(S.reverb(y, 0.22, 0.9, 0.6)[: S.n_(d + 0.3)], 250)


# ---------------------------------------------------------------- LIGHTNING
def arc_buzz(rng, d, f=110, jitter=0.08, gate_hz=(20, 70)):
    n = S.n_(d)
    t = S.tt(d)
    ff = f * (1 + jitter * smooth(rng, n, 30))
    saw = (2 * ((np.cumsum(ff) / SR) % 1.0) - 1).astype(np.float32)
    gate = (smooth(rng, n, rng.uniform(*gate_hz)) > -0.2).astype(np.float32)
    gate = S.fft_filter(gate, None, 400)
    return S.fft_filter(saw, 300, 7000) * np.clip(gate, 0, 1)


def Lightning_Cast(rng):
    d = rng.uniform(0.8, 1.0)
    n = S.n_(d)
    whine = S.sweep_sine(d, rng.uniform(350, 450), rng.uniform(2200, 2800)) * env_rise(n, 1.8)
    buzz = arc_buzz(rng, d, rng.uniform(100, 140)) * S.bell_env(n, 0.7, 0.8)
    crk = S.impulses(rng, d, lambda t: 150 + 300 * t / d, (0.1, 0.5), 2000, 12000)
    snap = S.at(click(rng, 3, 1000), d * 0.82, n)
    whine = S.fft_filter(whine * turb(rng, n, 15, 60, 0.9), 300, 6000)
    hiss = S.fft_filter(S.white(rng, n), 2500, 12000) * env_rise(n, 1.5) * turb(rng, n, 30, 90, 0.9)
    y = S.mix(0.1 * N(whine), 0.55 * N(buzz), 0.6 * N(crk), 0.25 * N(hiss), 0.9 * N(snap))
    return S.fade_out(y, 100)


def Lightning_Impact(rng):
    d = 2.2
    n = S.n_(d)
    crack = S.mix(click(rng, 1, 300, 18000), 0.8 * burst(rng, 0.03, 1500, 16000, 0.0002, 0.008))
    crack2 = S.at(0.6 * N(click(rng, 2, 800)), rng.uniform(0.012, 0.025))
    buzz = arc_buzz(rng, 0.35, 60, 0.05, (30, 90)) * S.env_ad(S.n_(0.35), 0.002, 0.12)
    thunder = S.fft_filter(S.colored(rng, n, -6), 20, 260) * turb(rng, n, 1.5, 6, 0.8) * S.env_ad(n, 0.04, 0.9, 2.5)
    sizzle = S.impulses(rng, 0.8, lambda t: 300 * np.exp(-4 * t), (0.1, 0.4), 3000, 14000)
    y = S.mix(1.0 * N(crack), crack2, 0.45 * N(buzz), S.at(0.85 * N(thunder), 0.03), 0.25 * N(sizzle))
    return S.fade_out(S.reverb(y, 0.2, 1.2, 1.0)[: S.n_(d + 0.5)], 450)


# ---------------------------------------------------------------- EARTH
def grind(rng, n, lo=250, hi=1100):
    return S.fft_filter(S.colored(rng, n, -3), lo, hi) * turb(rng, n, 20, 60, 0.9)


def Earth_Cast(rng):
    d = rng.uniform(1.2, 1.4)
    n = S.n_(d)
    rumble = S.fft_filter(S.colored(rng, n, -6), 25, 160) * env_rise(n, 0.8) * S.bell_env(n, 0.75, 0.7)
    sub = np.sin(2 * np.pi * 42 * S.tt(d)).astype(np.float32) * env_rise(n, 1.2) * S.bell_env(n, 0.8, 0.6)
    gr = grind(rng, n) * S.bell_env(n, 0.55, 1.0)
    grit = pops(rng, d, lambda t: 60 + 160 * t / d, (900, 3500), (0.0005, 0.002))
    crack_t = d * rng.uniform(0.72, 0.82)
    crack = S.at(S.mix(click(rng, 4, 300, 6000), 0.7 * damped(rng.uniform(450, 700), 0.02, 0.12)), crack_t, n)
    y = S.mix(0.7 * N(rumble), 0.35 * N(sub), 0.6 * N(gr), 0.3 * N(grit), 0.8 * N(crack))
    return S.fade_out(y, 180)


def Earth_Impact(rng):
    d = rng.uniform(1.5, 1.8)
    n = S.n_(d)
    thud = S.mix(sub_drop(0.6, rng.uniform(60, 72), 30, 0.25), 0.6 * burst(rng, 0.3, 30, 400, 0.002, 0.08, -3))
    crunch = burst(rng, 0.3, 300, 3500, 0.001, 0.07) * turb(rng, S.n_(0.3), 40, 120, 0.9)
    debris = np.zeros(n, np.float32)
    for _ in range(28):
        t0 = 0.05 + min(d * 0.85, rng.exponential(0.3))
        hit = S.mix(damped(rng.uniform(300, 1800), rng.uniform(0.004, 0.02), 0.12), 0.3 * click(rng, 2, 600, 6000))
        debris += S.at(hit * rng.uniform(0.15, 0.8) * np.exp(-t0 * 1.5), t0, n)
    dust = S.fft_filter(S.white(rng, n), 2500, 9000) * S.env_ad(n, 0.05, 0.5) * 0.15
    y = S.mix(1.0 * N(thud), 0.6 * N(crunch), 0.55 * N(debris), dust)
    return S.fade_out(S.reverb(y, 0.15, 1.0, 0.6)[: S.n_(d + 0.3)], 300)


# ---------------------------------------------------------------- ARCANE
def chord_bells(rng, d, freqs, tau, attack=0.003, gliss=0.0, voices=3, detune=12):
    t = S.tt(d)
    y = np.zeros(len(t), np.float32)
    for k, f in enumerate(freqs):
        for v in range(voices):
            c = (v - (voices - 1) / 2) * detune
            ff = f * 2 ** (c / 1200) * (1 + gliss * t / d)
            ph = 2 * np.pi * np.cumsum(ff) / SR + rng.uniform(0, 6.28)
            y += (np.sin(ph) * np.exp(-t / (tau * (1 - 0.08 * k)))).astype(np.float32) / voices
    a = S.n_(attack)
    y[:a] *= np.linspace(0, 1, a)
    return y


def Arcane_Cast(rng):
    d = rng.uniform(1.0, 1.2)
    n = S.n_(d)
    chord = [587.3, 880, 1174.7, 1480, 1760][: rng.integers(4, 6)]
    shimmer = chord_bells(rng, d, chord, 2.0, 0.3, gliss=0.06) * env_rise(n, 1.6)
    t = S.tt(d)
    fc = 220 * (1.5) ** (t / d)
    idx = 0.5 + 2.5 * (t / d)
    fm = np.sin(2 * np.pi * np.cumsum(fc) / SR + idx * np.sin(2 * np.pi * np.cumsum(fc * 2) / SR)).astype(np.float32)
    fm *= env_rise(n, 1.3)
    rev = S.reverb(chord_bells(rng, 0.6, [f * 2 for f in chord[:3]], 0.25), 1.0, 1.0, 0.6)[::-1]
    rev = S.at(N(rev) * 0.8, max(0.0, d * 0.85 - len(rev) / SR), n)
    wh = S.whoosh(rng, d, 700, 3200, 1600, 0.82, 0.7)
    y = S.mix(0.45 * N(shimmer), 0.4 * N(S.fft_filter(fm, 80, 6000)), 0.35 * rev[:n], 0.4 * N(wh))
    return S.fade_out(S.reverb(y, 0.25, 0.9, 0.5)[: S.n_(d + 0.3)], 220)


def Arcane_Impact(rng):
    d = 1.5
    n = S.n_(d)
    chord = [523.25, 784, 1046.5, 1318.5, 1568]
    pulse = chord_bells(rng, d, chord, 0.6, 0.002)
    pulse *= 1 + 0.35 * np.sin(2 * np.pi * rng.uniform(28, 40) * S.tt(d))  # ring-mod tint
    boom = sub_drop(0.6, rng.uniform(85, 95), 45, 0.22)
    zing = S.sweep_sine(0.3, rng.uniform(2600, 3400), 600) * S.env_ad(S.n_(0.3), 0.002, 0.1)
    air = S.fft_filter(S.colored(rng, n, 0.5), 4000, 13000) * S.env_ad(n, 0.01, 0.6) * 0.2
    y = S.mix(0.6 * N(pulse), 0.85 * N(boom), 0.3 * N(zing), air)
    return S.fade_out(S.reverb(y, 0.3, 1.0, 1.0)[: S.n_(d + 0.5)], 350)


SOUNDS = {k: v for k, v in globals().items() if k.split("_")[0] in ("Fire", "Water", "Ice", "Lightning", "Earth", "Arcane") and callable(v)}


# ---------------------------------------------------------------- VOICE (infected growl)
def stft_gain(x, gain_fn, nfft=1024, hop=256):
    """Time-varying spectral gain: gain_fn(t, freqs) -> gain array per frame."""
    n = len(x)
    win = np.hanning(nfft).astype(np.float32)
    pad = np.concatenate([np.zeros(nfft, np.float32), x, np.zeros(nfft, np.float32)])
    frames = 1 + (len(pad) - nfft) // hop
    out = np.zeros(len(pad), np.float32)
    nrm = np.zeros(len(pad), np.float32)
    f = np.fft.rfftfreq(nfft, 1 / SR)
    for i in range(frames):
        s = i * hop
        t = max(0.0, (s - nfft / 2) / SR)
        Sx = np.fft.rfft(pad[s : s + nfft] * win)
        out[s : s + nfft] += np.fft.irfft(Sx * gain_fn(t, f), nfft).astype(np.float32) * win
        nrm[s : s + nfft] += win ** 2
    return (out / np.maximum(nrm, 1e-3))[nfft : nfft + n]


def Infected_Growl(rng):
    d = rng.uniform(1.1, 1.6)
    n = S.n_(d)
    base = rng.uniform(62, 92)
    f0 = base * (1 + 0.12 * smooth(rng, n, 2.0)) * (1 + 0.05 * smooth(rng, n, 25.0))
    ph = np.cumsum(f0) / SR
    k = np.floor(ph).astype(int)
    starts = np.nonzero(np.diff(k, prepend=k[0]))[0]
    src = np.zeros(n, np.float32)
    kern = (np.sin(np.linspace(0, np.pi, S.n_(0.0025))) ** 2).astype(np.float32)
    kern = np.diff(kern, prepend=0.0) * 8  # glottal-flow-derivative-like pulse
    for j, s0 in enumerate(starts):
        amp = rng.uniform(0.6, 1.0) * (0.55 if j % 2 else 1.0)  # shimmer + period doubling (growl)
        s1 = min(n, s0 + int(rng.normal(0, 6)) + 0) if s0 > 10 else s0
        e = min(n, s1 + len(kern))
        src[s1:e] += amp * kern[: e - s1]
    rattle = 1 - 0.45 * (0.5 + 0.5 * np.sin(2 * np.pi * rng.uniform(24, 34) * S.tt(d)))
    breath = S.fft_filter(S.white(rng, n), 400, 3500) * 0.035
    v = (src * rattle + breath).astype(np.float32)
    F = [(rng.uniform(520, 640), 0.20, 1.0), (rng.uniform(880, 1080), 0.18, 0.55), (rng.uniform(2300, 2650), 0.15, 0.22)]
    morph = rng.uniform(-0.25, -0.1)

    def g(t, f):
        u = min(1.0, t / d)
        lf = np.log2(np.maximum(f, 20))
        out = 0.35 * np.exp(-0.5 * ((lf - np.log2(260)) / 0.8) ** 2)
        for fc, w, a in F:
            c = np.log2(fc) + morph * u  # vowel closes slightly ("aah" -> "ohh")
            out = out + a * np.exp(-0.5 * ((lf - c) / w) ** 2)
        return out

    y = stft_gain(v, g)
    env = S.bell_env(n, rng.uniform(0.25, 0.4), 0.9) * (0.75 + 0.25 * turb(rng, n, 2, 8, 1.0))
    y = S.fade_out(y * env, 120)
    return S.reverb(y, 0.08, 0.5, 0.3)[: S.n_(d + 0.15)]


SOUNDS["Infected_Growl"] = Infected_Growl
