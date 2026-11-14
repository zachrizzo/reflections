"""Procedural villain / finale sounds (stand-ins until ElevenLabs takes arrive)."""
import numpy as np
import synth as S
import spells as P

SR = S.SR
N = P.N


def saw(f, d):
    ph = np.cumsum(np.broadcast_to(f, (S.n_(d),)) if np.ndim(f) == 0 else f) / SR
    return (2 * (ph % 1.0) - 1).astype(np.float32)


def cluster(rng, d, freqs, lp=900, detune=8):
    y = np.zeros(S.n_(d), np.float32)
    for f in freqs:
        for c in (-detune, 0, detune):
            y += saw(f * 2 ** (c / 1200), d)
    return S.fft_filter(y, 30, lp)


def reverse_swell(rng, d, lo=1500, hi=12000):
    n = S.n_(d)
    x = S.fft_filter(S.colored(rng, n, -1), lo, hi) * (np.linspace(0, 1, n) ** 3)
    return x


def voice(rng, d, f0_fn, formants, breath=0.05, rattle_hz=None, dbl=0.55, jitter=0.05):
    """Pulse-train voice through moving formants (same model as the growl). f0_fn(u) -> Hz for u in 0..1."""
    n = S.n_(d)
    u = np.linspace(0, 1, n)
    f0 = np.array([f0_fn(x) for x in u[:: max(1, n // 2000)]])
    f0 = np.interp(np.arange(n), np.linspace(0, n - 1, len(f0)), f0) * (1 + jitter * P.smooth(rng, n, 20))
    k = np.floor(np.cumsum(f0) / SR).astype(int)
    starts = np.nonzero(np.diff(k, prepend=k[0]))[0]
    src = np.zeros(n, np.float32)
    kern = np.diff((np.sin(np.linspace(0, np.pi, S.n_(0.002))) ** 2).astype(np.float32), prepend=0.0) * 8
    for j, s0 in enumerate(starts):
        e = min(n, s0 + len(kern))
        src[s0:e] += rng.uniform(0.6, 1.0) * (dbl if j % 2 else 1.0) * kern[: e - s0]
    if rattle_hz:
        src *= 1 - 0.45 * (0.5 + 0.5 * np.sin(2 * np.pi * rattle_hz * S.tt(d)))
    src = src + breath * S.fft_filter(S.white(rng, n), 300, 6000)

    def g(t, f):
        uu = min(1.0, t / d)
        lf = np.log2(np.maximum(f, 20))
        out = np.zeros_like(lf)
        for (fa, fb), w, a in formants:
            c = np.log2(fa + (fb - fa) * uu)
            out = out + a * np.exp(-0.5 * ((lf - c) / w) ** 2)
        return out
    return P.stft_gain(src, g)


def whisper(rng, d, formants, sss=0.0):
    """Unvoiced (whispered) formant noise gesture."""
    n = S.n_(d)
    src = S.white(rng, n)

    def g(t, f):
        uu = min(1.0, t / d)
        lf = np.log2(np.maximum(f, 20))
        out = np.zeros_like(lf)
        for (fa, fb), w, a in formants:
            c = np.log2(fa + (fb - fa) * uu)
            out = out + a * np.exp(-0.5 * ((lf - c) / w) ** 2)
        return out + sss * np.exp(-0.5 * ((lf - np.log2(6500)) / 0.35) ** 2) * (uu > 0.6)
    return P.stft_gain(src, g)


VOWELS = {"a": (750, 1200, 2600), "o": (500, 900, 2500), "e": (500, 1800, 2500), "u": (350, 800, 2300), "i": (300, 2200, 2900)}


def whisper_phrase(rng, d):
    """Articulated whisper: syllables with vowel formants, gaps, and occasional sibilants."""
    n = S.n_(d)
    y = np.zeros(n, np.float32)
    t = 0.05
    while t < d - 0.15:
        if rng.random() < 0.3:  # sibilant "s"/"sh"
            L = rng.uniform(0.08, 0.18)
            lo = rng.choice([3500, 5000])
            seg = S.fft_filter(S.white(rng, S.n_(L)), lo, lo * 2.2) * S.bell_env(S.n_(L), 0.4, 1.5) * 0.5
        else:
            L = rng.uniform(0.12, 0.28)
            v1 = VOWELS[rng.choice(list(VOWELS))]
            v2 = VOWELS[rng.choice(list(VOWELS))]
            seg = whisper(rng, L, [((v1[0], v2[0]), 0.16, 1.0), ((v1[1], v2[1]), 0.15, 0.6), ((v1[2], v2[2]), 0.14, 0.3)])
            seg = seg * S.bell_env(len(seg), rng.uniform(0.25, 0.5), 1.3)
        y += S.at(seg.astype(np.float32), t, n)
        t += L + rng.uniform(0.02, 0.09)
    return y


# ---------------------------------------------------------------- sounds
def Villain_Manifest(rng):
    d = 3.2
    total = S.n_(d)
    sw = reverse_swell(rng, 0.8)
    hit_t = 0.8
    sub = P.sub_drop(1.6, 60, 24, 0.6)
    blast = P.burst(rng, 0.6, 40, 2500, 0.002, 0.2, -3)
    cl = cluster(rng, 2.3, [73.4, 77.8, 103.8], 900) * S.env_ad(S.n_(2.3), 0.02, 1.1, 2.5)
    air = S.fft_filter(S.colored(rng, S.n_(2.3), 0), 3000, 9000) * S.env_ad(S.n_(2.3), 0.3, 1.0, 2.5) * 0.15
    y = S.mix(0.5 * N(sw), S.at(1.0 * N(sub), hit_t, total), S.at(0.5 * N(blast), hit_t, total), S.at(0.55 * N(cl), hit_t, total), S.at(air, hit_t, total))
    return S.fade_out(S.reverb(y, 0.3, 1.4, 1.5)[: S.n_(d + 0.8)], 600)


def Villain_Voice(rng):
    kind = rng.integers(0, 3)
    if kind == 0:  # whispered hiss-phrase
        d = rng.uniform(1.0, 1.4)
        y = whisper_phrase(rng, d)
    elif kind == 1:  # breathy low laugh "heh heh heh"
        d = 1.4
        n = S.n_(d)
        y = np.zeros(n, np.float32)
        for k in range(rng.integers(3, 5)):
            L = rng.uniform(0.12, 0.18)
            syl = voice(rng, L, lambda u, k=k: 95 - 6 * k - 15 * u, [((550, 500), 0.2, 1.0), ((1000, 900), 0.2, 0.5), ((2500, 2500), 0.18, 0.2)], breath=0.25)
            syl *= S.bell_env(len(syl), 0.3, 1.5)
            y += S.at(syl, 0.05 + k * rng.uniform(0.2, 0.26), n)
    else:  # sigh-whisper with low demonic undertone
        d = rng.uniform(1.2, 1.6)
        wh = whisper_phrase(rng, d)
        und = voice(rng, d, lambda u: 48 + 6 * np.sin(3 * u), [((400, 450), 0.25, 1.0), ((900, 950), 0.2, 0.4)], breath=0.1, rattle_hz=27)
        y = S.mix(0.8 * N(wh), 0.3 * N(und) * S.bell_env(S.n_(d), 0.4, 1.0))
    y = S.reverb(y, 0.25, 1.2, 0.8)
    return S.fade_out(y, 200)


def Villain_Hop(rng):
    d = 1.3
    wh = S.whoosh(rng, d, 300, 1800, 500, 0.55, 1.0)
    n = S.n_(d)
    gloop = np.zeros(n, np.float32)
    for _ in range(18):
        t0 = abs(rng.normal(d * 0.55, d * 0.15))
        L = rng.uniform(0.04, 0.1)
        f0 = rng.uniform(150, 450)
        b = S.sweep_sine(L, f0, f0 * rng.uniform(0.6, 1.6)) * S.env_ad(S.n_(L), 0.003, L / 3)
        gloop += S.at(b * rng.uniform(0.3, 1.0), min(t0, d * 0.9), n)
    smoke = S.fft_filter(S.colored(rng, n, -3), 100, 2500) * P.turb(rng, n, 4, 15, 0.8) * S.bell_env(n, 0.5, 1.2)
    y = S.mix(0.75 * N(wh), 0.45 * N(gloop), 0.5 * N(smoke))
    return S.fade_out(S.reverb(y, 0.2, 1.0, 0.6)[: S.n_(d + 0.3)], 250)


def Villain_Telegraph(rng):
    d = 1.0
    n = S.n_(d)
    t = S.tt(d)
    f = 70 * 2.2 ** (t / d)
    cl = S.mix(*[saw(f * r, d) for r in (1.0, 1.06, 1.5)])
    cl = S.fft_filter(cl, 40, 2500) * (1 + 0.6 * np.sin(2 * np.pi * np.cumsum(4 + 22 * t / d) / SR))
    riser = S.stft_sculpt(S.colored(rng, n, 0), lambda tt_: 600 * (9000 / 600) ** (tt_ / d), lambda tt_: 0.7)
    y = S.mix(0.55 * N(cl), 0.5 * N(riser)) * (np.linspace(0, 1, n) ** 1.8)
    y[-S.n_(0.01):] *= np.linspace(1, 0, S.n_(0.01))
    return y


def Villain_Slam(rng):
    d = 2.2
    tr = P.click(rng, 5, 200, 12000)
    sub = P.sub_drop(1.2, rng.uniform(52, 60), 24, 0.45)
    blast = S.stft_sculpt(S.colored(rng, S.n_(1.2), -2), lambda t: 3000 * (120 / 3000) ** min(1, t / 0.6), lambda t: 1.5) * S.env_ad(S.n_(1.2), 0.002, 0.45)
    shock = S.whoosh(rng, 0.9, 1500, 600, 150, 0.15, 1.0)
    debris = P.pops(rng, 1.5, lambda t: 50 * np.exp(-2.0 * t), (250, 1800), (0.004, 0.02))
    y = S.mix(0.7 * N(tr), 1.0 * N(sub), 0.75 * N(blast), S.at(0.45 * N(shock), 0.02), S.at(0.4 * N(debris), 0.05))
    return S.fade_out(S.reverb(y, 0.22, 1.3, 1.0)[: S.n_(d + 0.5)], 400)


def Villain_Hurt(rng):
    d = 1.2
    sizzle = S.impulses(rng, 0.9, lambda t: 500 * np.exp(-3 * t), (0.1, 0.5), 2500, 12000)
    roar = voice(rng, 0.9, lambda u: rng.uniform(55, 70) * (1 + 0.6 * np.sin(np.pi * u)), [((600, 750), 0.22, 1.0), ((1100, 1300), 0.2, 0.6), ((2500, 2700), 0.18, 0.3)], breath=0.2, rattle_hz=31)
    roar = np.tanh(2.5 * N(roar)) * S.bell_env(len(roar), 0.25, 1.2)
    hit = P.sub_drop(0.4, 120, 50, 0.12)
    y = S.mix(0.55 * N(sizzle), S.at(0.8 * N(roar), 0.03), 0.6 * N(hit))
    return S.fade_out(S.reverb(y, 0.18, 1.0, 0.6)[: S.n_(d + 0.3)], 250)


def Villain_Death(rng):
    d = 3.6
    total = S.n_(d)
    scream = voice(rng, 2.4, lambda u: 90 + 260 * np.sin(np.pi * min(1, u * 1.3)) ** 1.5, [((700, 500), 0.2, 1.0), ((1200, 900), 0.2, 0.6), ((2700, 2400), 0.18, 0.35)], breath=0.3, rattle_hz=29, dbl=0.7)
    scream = np.tanh(2.0 * N(scream)) * S.bell_env(len(scream), 0.3, 1.0)
    dissolve = S.impulses(rng, 3.2, lambda t: 600 * np.exp(-0.9 * t), (0.1, 0.6), 1500, 12000)
    shimmer = S.partials(3.0, [880, 1318.5, 1760, 2637], [0.4, 0.35, 0.3, 0.2], [1.6, 1.4, 1.2, 1.0], rng, detune_cents=20, voices=3, attack=0.4)
    sub = P.sub_drop(2.5, 70, 28, 0.9)
    tail = whisper(rng, 1.2, [((500, 350), 0.25, 1.0), ((1000, 800), 0.22, 0.5)])
    y = S.mix(S.at(0.85 * N(scream), 0.0, total), 0.45 * N(dissolve), S.at(0.25 * N(shimmer), 0.6, total), 0.6 * N(sub), S.at(0.3 * N(tail) * S.bell_env(S.n_(1.2), 0.3, 1.0), 2.3, total))
    return S.fade_out(S.reverb(y, 0.3, 1.4, 1.5)[: S.n_(d + 1.0)], 700)


def FinalSpell_Cast(rng):
    d = 3.2
    n = S.n_(d)
    chord = [146.83, 220.0, 293.66, 369.99, 440.0, 587.33]  # D major, open voicing
    choir = np.zeros(n, np.float32)
    for f in chord:
        for c in (-9, -3, 3, 9):
            choir += saw(f * 2 ** (c / 1200) * (1 + 0.004 * np.sin(2 * np.pi * 5.2 * S.tt(d) + c)), d)
    form = [((700, 750), 0.25, 1.0), ((1150, 1200), 0.22, 0.6), ((2800, 2900), 0.2, 0.25)]  # "aah"
    choir = P.stft_gain(choir, lambda t, f: sum(a * np.exp(-0.5 * ((np.log2(np.maximum(f, 20)) - np.log2(fa)) / w) ** 2) for (fa, fb), w, a in form) + 0.15)
    choir *= S.env_ad(n, 0.35, d * 0.7, 1.5)
    bells = S.partials(d, [1174.66, 1479.98, 1760, 2349.3, 2959.96], [0.5, 0.4, 0.4, 0.3, 0.2], [1.6, 1.4, 1.3, 1.1, 0.9], rng, detune_cents=8, voices=3, attack=0.01)
    swell = S.fft_filter(S.colored(rng, n, 0.5), 3000, 14000) * S.bell_env(n, 0.25, 1.0) * 0.25
    whoosh = S.whoosh(rng, 1.2, 400, 4000, 2000, 0.6, 0.8)
    sub = P.sub_drop(1.6, 73.4, 55, 0.7)
    y = S.mix(0.6 * N(choir), S.at(0.35 * N(bells), 0.25, n), swell, S.at(0.4 * N(whoosh), 0.0, n), S.at(0.6 * N(sub), 0.3, n))
    return S.fade_out(S.reverb(y, 0.35, 1.4, 2.0)[: S.n_(d + 1.2)], 800)


SOUNDS = {k: v for k, v in globals().items() if (k.startswith("Villain_") or k == "FinalSpell_Cast") and callable(v)}
VARIANTS = {"Villain_Voice": 6, "Villain_Hurt": 3, "Villain_Slam": 2, "Villain_Hop": 2}
