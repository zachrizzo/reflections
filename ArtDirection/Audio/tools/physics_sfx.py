"""Procedural SFX for spell physics, reactions and the Giltside squads (numpy only: no recorded or sampled audio).

Registered into synth.py's SOUNDS/VARIANTS, so `python synth.py Fireball_Explode ...` renders proc/synth/<Name>_NN.wav,
then level.py and ue_build.py treat them like every other jam sound.
Loops (Shock_Loop, Burning_Loop, March_Loop) are rendered longer than the loop and equal-power crossfaded into a seamless
cycle.
"""
import numpy as np
import synth as S
import spells as SP

SR = S.SR
N = SP.N


def loopify(x, loop_s, xfade_s):
    """Seamless loop: the first xfade_s are crossfaded with the material just past the loop end."""
    n, m = S.n_(loop_s), S.n_(xfade_s)
    y = x[:n].copy()
    t = np.linspace(0, np.pi / 2, m)
    y[:m] = x[:m] * np.sin(t) + x[n:n + m] * np.cos(t)
    return y


def sat(y, drive=1.6):
    """Gentle tanh saturation for weight on big impacts."""
    y = y / (np.abs(y).max() + 1e-9)
    return (np.tanh(drive * y) / np.tanh(drive)).astype(np.float32)


def place(dst, src, t0):
    i = S.n_(max(0.0, t0))
    if i >= len(dst):
        return dst
    j = min(len(dst), i + len(src))
    dst[i:j] += src[: j - i]
    return dst


def rings(rng, d, count, spread_s, f_range=(3000, 10000), tau=(0.002, 0.008), peak_s=0.01):
    """Chain-mail jingle: many tiny metal rings shaken at once, densest just after the impact."""
    y = np.zeros(S.n_(d), np.float32)
    for _ in range(count):
        t0 = peak_s + abs(rng.normal(0, spread_s))
        f = np.exp(rng.uniform(np.log(f_range[0]), np.log(f_range[1])))
        tk = rng.uniform(*tau)
        r = S.mix(SP.damped(f, tk, tk * 6, rng.uniform(0, 6.28)), 0.5 * SP.damped(f * rng.uniform(1.9, 2.7), tk * 0.6, tk * 4))
        place(y, r * rng.uniform(0.2, 1.0) * np.exp(-t0 / (spread_s * 2.5 + 1e-3)), t0)
    return y


def stone_hits(rng, d, count, start, scale, f_range=(350, 2600), decay=1.4):
    """Debris: small stones and splinters landing, sparser and quieter over time."""
    y = np.zeros(S.n_(d), np.float32)
    for _ in range(count):
        t0 = start + min(d - start - 0.15, rng.exponential(scale))
        hit = S.mix(SP.damped(np.exp(rng.uniform(np.log(f_range[0]), np.log(f_range[1]))), rng.uniform(0.003, 0.016), 0.1),
                    0.35 * SP.click(rng, 2, 700, 9000))
        place(y, hit * rng.uniform(0.15, 1.0) * np.exp(-(t0 - start) * decay), t0)
    return y


# ---------------------------------------------------------------- spell physics
def Fireball_Explode(rng):
    d = 3.4
    n = S.n_(d)
    crack = S.mix(SP.click(rng, 3, 300, 16000), 0.9 * SP.burst(rng, 0.05, 1000, 5000, 0.0002, 0.016))
    boom = S.mix(SP.sub_drop(1.6, rng.uniform(52, 66), 22, 0.6),
                 0.8 * S.fft_filter(S.colored(rng, S.n_(1.4), -4), 22, 240) * S.env_ad(S.n_(1.4), 0.003, 0.5, 2.5))
    blast = S.stft_sculpt(S.colored(rng, S.n_(1.2), -1.2), lambda t: 9000 * (240 / 9000) ** min(1, t / 0.75),
                          lambda t: 1.5) * S.env_ad(S.n_(1.2), 0.002, 0.55, 3.0)
    m = S.n_(2.2)
    roar = S.fft_filter(S.colored(rng, m, -5), 40, 1000) * SP.turb(rng, m, 4, 16, 0.8) * S.env_ad(m, 0.04, 1.1, 2.6)
    debris = stone_hits(rng, d, 70, 0.12, 0.45, (900, 5000))
    clunks = stone_hits(rng, d, 10, 0.2, 0.5, (140, 420), 1.0)
    gravel = S.at(S.impulses(rng, 2.0, lambda t: 260 * np.exp(-2.2 * t), (0.2, 0.9), 1500, 7500), 0.18, n)
    embers = SP.pops(rng, d, lambda t: 90 * np.exp(-1.1 * t), (1500, 7000), (0.0008, 0.004))
    rumble = S.fft_filter(S.colored(rng, n, -6), 18, 170) * SP.turb(rng, n, 0.8, 3.5, 0.7) * S.env_ad(n, 0.12, 1.8, 2.0)
    y = S.mix(0.85 * N(crack), 1.15 * N(boom), 0.8 * N(blast), S.at(0.45 * N(roar), 0.02), 0.55 * N(debris), 0.35 * N(clunks),
              0.2 * N(gravel), 0.16 * N(embers), S.at(0.45 * N(rumble), 0.05))
    y = sat(y, 1.4)
    return S.fade_out(S.reverb(y, 0.22, 1.25, 1.3, 5000)[: S.n_(d + 0.6)], 600)


def arc(rng, d, f, snap=1.0, fall=None):
    """One electric arc: a loud snap, then pulse-modulated noise (the buzz of current) with a distorted hum and bursts
    of bright crackle, flickering on and off."""
    m = S.n_(d)
    ff = np.geomspace(f, fall, m) if fall else f * (1 + 0.2 * SP.smooth(rng, m, 25))
    ph = np.cumsum(ff) / SR
    pulse = ((ph % 1.0) < 0.3).astype(np.float32)
    buzz = S.fft_filter(S.colored(rng, m, -1) * pulse, 150, 10000)
    hum = S.fft_filter(np.tanh(3.0 * np.sin(2 * np.pi * ph)).astype(np.float32), 60, 2500)
    flick = np.clip(S.fft_filter((SP.smooth(rng, m, rng.uniform(30, 70)) > -0.2).astype(np.float32), None, 300), 0, 1)
    env = S.env_ad(m, 0.001, d * 0.9, 1.2)
    crk = S.impulses(rng, d, lambda t: 260.0, (1.0, 5.0), 2500, 16000)
    y = S.mix(0.75 * N(buzz) * flick * env, 0.35 * N(hum) * flick * env, 0.55 * N(crk) * env)
    sn = S.mix(SP.burst(rng, 0.012, 300, 18000, 0.0001, 0.003), 0.6 * SP.sub_drop(0.05, 160, 60, 0.015))
    return place(y, snap * N(sn), 0.0)


def Shock_Loop(rng):
    L, X = 2.5, 0.2
    d = L + X + 0.4
    n = S.n_(d)
    f = rng.uniform(70, 100)
    arcs = np.zeros(n, np.float32)
    t = 0.0
    while t < d - 0.35:  # arcs in bursts with short gaps: the current keeps jumping
        dur = rng.uniform(0.05, 0.25)
        place(arcs, arc(rng, dur, f * rng.uniform(0.7, 1.4), rng.uniform(0.5, 1.0)) * rng.uniform(0.5, 1.0), t)
        t += dur + rng.exponential(0.07)
    bed = S.impulses(rng, d, lambda t: 500.0, (1.0, 4.0), 4000, 16000) * SP.turb(rng, n, 8, 30, 0.95)
    sparks = S.impulses(rng, d, lambda t: 14.0, (2.0, 8.0), 1500, 18000)
    hiss = S.fft_filter(S.white(rng, n), 5000, 15000) * SP.turb(rng, n, 20, 60, 0.9)
    level = S.fft_filter(np.abs(arcs), None, 30)  # how hard it is arcing right now
    level = level / (level.max() + 1e-9)
    mains = S.fft_filter(np.tanh(2.5 * np.sin(2 * np.pi * f * S.tt(d))).astype(np.float32), 50, 450) * (0.3 + 0.7 * level)
    y = S.mix(0.65 * N(arcs), 0.35 * N(bed), 0.55 * N(sparks), 0.12 * N(hiss), 0.4 * N(mains))
    return loopify(y, L, X)


def Shock_Collapse(rng):
    d = 1.7
    n = S.n_(d)
    zap = arc(rng, 0.42, rng.uniform(170, 200), 1.0, fall=35)
    zap2 = arc(rng, 0.12, rng.uniform(140, 170), 0.8)
    sizzle = S.impulses(rng, 1.2, lambda t: 320 * np.exp(-4.5 * t), (0.1, 0.5), 2500, 14000)
    drop = Body_Knockback(rng, light=True)
    y = S.mix(N(zap), S.at(0.6 * N(zap2), rng.uniform(0.05, 0.1), n), S.at(0.25 * N(sizzle), 0.3, n),
              S.at(0.9 * N(drop), rng.uniform(0.36, 0.44), n))
    return S.fade_out(S.reverb(y, 0.12, 0.8, 0.5)[: S.n_(d)], 250)


def Water_Shove(rng):
    d = 2.1
    n = S.n_(d)
    ti = rng.uniform(0.24, 0.3)  # the wave reaches the body
    m = S.n_(ti + 0.05)
    surge = SP.sweep_noise(rng, ti + 0.05, 280, 2400, 0.9, -1.8, 1.4) * SP.env_rise(m, 1.6)
    surge[-S.n_(0.04):] *= np.linspace(1, 0, S.n_(0.04))
    k = S.n_(0.7)
    hit = S.stft_sculpt(S.white(rng, k), lambda t: 3200 * (650 / 3200) ** min(1, t / 0.3), lambda t: 1.3) * S.env_ad(k, 0.002, 0.22)
    slap = SP.burst(rng, 0.05, 500, 5000, 0.0004, 0.012)
    thump = SP.sub_drop(0.35, 150, 60, 0.1)
    k2 = S.n_(1.1)
    body = S.fft_filter(S.colored(rng, k2, -2), 300, 6500) * SP.turb(rng, k2, 14, 40, 0.8) * S.env_ad(k2, 0.004, 0.5, 2.8)
    bub = SP.bubbles(rng, 1.3, 75, 280, 1500, 0.22, 0.2)
    spray = S.fft_filter(S.white(rng, S.n_(0.6)), 4000, 12000) * S.env_ad(S.n_(0.6), 0.003, 0.28)
    patter = SP.bubbles(rng, 1.6, 60, 900, 3200, 0.25, 0.3)  # droplets falling back onto stone: rising plips
    impact = S.mix(0.9 * N(hit), 0.55 * N(slap), 0.55 * N(thump), 0.6 * N(body), 0.35 * N(bub), 0.25 * N(spray))
    y = S.mix(0.5 * N(surge), S.at(impact, ti, n), S.at(0.2 * N(patter), ti + 0.25, n))
    return S.fade_out(S.reverb(y, 0.13, 0.85, 0.6)[: S.n_(d + 0.2)], 300)


def body_part(rng, f0, weight=1.0):
    """One part of a body meeting stone: low thud, a hard stone slap and a short dry cloth/leather smack."""
    thud = SP.sub_drop(0.25, f0, 40, 0.07)
    knock = SP.burst(rng, 0.08, 90, 700, 0.0005, 0.02, -2)
    slap = SP.burst(rng, 0.03, 1500, 6500, 0.0002, 0.005)
    smack = SP.burst(rng, 0.05, 500, 3000, 0.0004, 0.01)
    return weight * S.mix(1.0 * N(thud), 0.7 * N(knock), 0.55 * N(slap), 0.35 * N(smack))


def Body_Knockback(rng, light=False):
    d = 0.9
    n = S.n_(d)
    f0 = rng.uniform(85, 110)
    y = np.zeros(n, np.float32)
    place(y, body_part(rng, f0, 1.0), 0.0)  # torso
    place(y, body_part(rng, f0 * 1.5, 0.45), rng.uniform(0.035, 0.07))  # an arm or shoulder
    place(y, body_part(rng, f0 * 1.8, 0.3), rng.uniform(0.08, 0.13))  # legs
    gear = rings(rng, 0.4, 10, 0.03, (1500, 6000), (0.002, 0.006))
    pebbles = stone_hits(rng, d, 9, 0.03, 0.12, (1500, 5000), 3.0)
    k = S.n_(0.35)
    scrape = S.fft_filter(S.white(rng, k), 600, 5000) * SP.turb(rng, k, 40, 120, 0.9) * S.env_ad(k, 0.01, 0.12, 2.5)
    y = S.mix(y, 0.12 * N(gear), 0.25 * N(pebbles), S.at(0.16 * N(scrape), 0.06, n))
    if not light and rng.random() < 0.6:  # a small bounce
        place(y, body_part(rng, f0 * 1.2, 0.35), rng.uniform(0.18, 0.26))
    return S.fade_out(S.reverb(sat(y, 1.3), 0.1, 0.6, 0.35)[: S.n_(d)], 160)


def Burning_Loop(rng):
    L, X = 4.0, 0.4
    d = L + X + 0.05
    n = S.n_(d)
    roar = S.fft_filter(S.colored(rng, n, -4), 90, 1800) * SP.turb(rng, n, 5, 18, 0.8)
    whump = S.fft_filter(S.colored(rng, n, -6), 40, 220) * SP.turb(rng, n, 1.5, 5, 0.9)  # the flame breathing
    cloth = S.fft_filter(S.colored(rng, n, -2), 300, 1600) * SP.turb(rng, n, 12, 28, 0.95)  # fabric flapping in the flame
    wob = SP.smooth(rng, n, 2.5)
    flutter = S.stft_sculpt(S.colored(rng, n, -2), lambda t: 620 * 1.5 ** wob[min(n - 1, int(t * SR))], lambda t: 1.0)
    flutter *= SP.turb(rng, n, 8, 20, 0.85)
    crk = SP.pops(rng, d, lambda t: 50 + 25 * np.sin(2 * np.pi * 0.7 * t), (1200, 6500), (0.0006, 0.003))
    lowpop = SP.pops(rng, d, lambda t: 6.0, (180, 600), (0.004, 0.012))
    hiss = S.fft_filter(S.white(rng, n), 3000, 9000) * SP.turb(rng, n, 10, 40, 0.9)
    sizzle = S.impulses(rng, d, lambda t: 160.0, (0.1, 0.4), 3500, 12000)
    y = S.mix(0.7 * N(roar), 0.35 * N(whump), 0.4 * N(flutter), 0.3 * N(cloth), 0.35 * N(crk), 0.18 * N(lowpop),
              0.1 * N(hiss), 0.1 * N(sizzle))
    return loopify(y, L, X)


# ---------------------------------------------------------------- squads
STEP_RATE = 1.8  # steps per second at march speed (squads session to confirm)
SQUAD = 8


def boot_step(rng, d=0.45, dist=0.0):
    """One soldier's boot on stone with mail and kit; dist 0 (close) .. 1 (far side of the squad)."""
    n = S.n_(d)
    heel = S.mix(SP.sub_drop(0.12, rng.uniform(110, 140), 60, 0.04),
                 0.9 * SP.burst(rng, 0.08, 80, 600, 0.0005, 0.028, -2),
                 0.7 * SP.burst(rng, 0.05, 700, 5000, 0.0003, rng.uniform(0.008, 0.013)))
    grit = S.impulses(rng, 0.1, lambda t: 900 * np.exp(-25 * t), (0.2, 0.7), 2000, 7000)
    toe = S.mix(SP.burst(rng, 0.05, 200, 1500, 0.0004, 0.012), 0.5 * SP.burst(rng, 0.03, 1200, 6000, 0.0003, 0.005))
    mail = rings(rng, d, int(rng.integers(14, 24)), 0.04, (1800, 6500), (0.003, 0.009), peak_s=0.012)
    kit = S.mix(SP.damped(rng.uniform(420, 900), rng.uniform(0.015, 0.03), 0.2),
                0.5 * SP.damped(rng.uniform(900, 1600), rng.uniform(0.008, 0.02), 0.15))
    y = S.mix(N(heel), 0.2 * N(grit), S.at(0.45 * N(toe), rng.uniform(0.07, 0.11), n), 0.24 * N(mail))
    y = place(y, 0.18 * N(kit), rng.uniform(0.015, 0.05))
    if dist > 0:
        y = S.fft_filter(y, None, 9000 - 4500 * dist) * (1.0 - 0.45 * dist)
    return y[:n]


def March_Loop(rng):
    period = 8 / STEP_RATE  # eight steps per loop
    X = 0.12
    d = 3 * period + 1.0
    y = np.zeros(S.n_(d), np.float32)
    dists = np.linspace(0, 1, SQUAD)
    for s in range(SQUAD):
        lag = rng.normal(0, 0.028)  # each soldier's own small lag behind the beat
        for k in range(int(3 * 8)):
            t0 = (k + 0.5) / STEP_RATE + lag + rng.normal(0, 0.012)
            place(y, boot_step(rng, 0.45, dists[s]) * rng.uniform(0.7, 1.0), t0)
    y = S.reverb(y, 0.22, 0.9, 0.8, 6000)
    mid = y[S.n_(period):]
    return loopify(mid, period, X)


def March_Step(rng):
    return S.fade_out(S.reverb(boot_step(rng, 0.5), 0.12, 0.6, 0.3)[: S.n_(0.6)], 80)


def wood_thock(rng, f0, d=0.5, decay=0.04):
    ratios = [1, 1.58, 2.13, 2.94, 3.71, 4.6, 5.8]
    return S.partials(d, [f0 * r * rng.uniform(0.98, 1.02) for r in ratios], [1, 0.8, 0.6, 0.45, 0.35, 0.25, 0.18],
                      [decay, decay * 0.8, decay * 0.6, decay * 0.45, decay * 0.35, decay * 0.25, decay * 0.2], rng)


def wood_crack(rng, d=0.06):
    """Dry timber crack: a broadband snap shaped by a few wooden resonances in 0.8-3 kHz."""
    snap = SP.burst(rng, d, 800, 7000, 0.0002, 0.006)
    res = S.partials(d, [rng.uniform(800, 1100), rng.uniform(1500, 1900), rng.uniform(2400, 3000)], [1, 0.7, 0.4],
                     [0.012, 0.009, 0.006], rng)
    return S.mix(N(snap), 0.6 * N(res))


def Sword_ShieldHit(rng):
    d = 1.1
    n = S.n_(d)
    tr = S.mix(SP.click(rng, 1, 3000, 16000), 0.7 * SP.burst(rng, 0.02, 4000, 12000, 0.0001, 0.003))
    wood = S.mix(wood_thock(rng, rng.uniform(160, 240), 0.4, 0.035), 0.7 * wood_crack(rng))
    f1 = rng.uniform(2000, 3000)
    blade = S.partials(d, [f1 * r for r in (1, 1.47, 2.09, 2.56, 3.11)], [1, 0.7, 0.5, 0.35, 0.2],
                       [0.3, 0.22, 0.16, 0.11, 0.08], rng, detune_cents=5, voices=2)
    y = S.mix(0.8 * N(tr), 1.0 * N(wood), 0.32 * N(blade))
    if rng.random() < 0.6:  # the steel rim takes part of the blow
        f2 = rng.uniform(600, 900)
        y = S.mix(y, 0.3 * N(S.partials(0.6, [f2, f2 * 2.32, f2 * 4.25], [1, 0.5, 0.3], [0.16, 0.1, 0.07], rng)))
    return S.fade_out(S.reverb(y, 0.14, 0.7, 0.45)[: S.n_(d)], 200)


def Shield_BlockHeavy(rng):
    d = 1.0
    n = S.n_(d)
    strike = S.mix(SP.click(rng, 1, 2000, 14000), 0.8 * SP.burst(rng, 0.02, 2000, 9000, 0.0001, 0.004),
                   0.5 * S.partials(0.12, [rng.uniform(900, 1400), rng.uniform(2100, 2700)], [1, 0.6], [0.04, 0.025], rng))
    wood = S.mix(wood_thock(rng, rng.uniform(110, 160), 0.5, 0.05), 0.9 * wood_crack(rng, 0.08))
    thump = SP.sub_drop(0.25, rng.uniform(95, 120), 50, 0.07)
    f2 = rng.uniform(420, 650)
    boss = S.partials(0.6, [f2, f2 * 2.32, f2 * 4.25], [1, 0.5, 0.25], [0.18, 0.12, 0.08], rng)
    mail = rings(rng, 0.5, 22, 0.05, (1800, 6500), (0.003, 0.008), peak_s=0.015)
    y = S.mix(0.8 * N(strike), 1.0 * N(wood), 0.6 * N(thump), 0.25 * N(boss), 0.22 * N(mail))
    return S.fade_out(S.reverb(sat(y, 1.3), 0.14, 0.7, 0.45)[: S.n_(d)], 200)


SOUNDS = {"Fireball_Explode": Fireball_Explode, "Shock_Loop": Shock_Loop, "Shock_Collapse": Shock_Collapse,
          "Water_Shove": Water_Shove, "Body_Knockback": Body_Knockback, "Burning_Loop": Burning_Loop,
          "March_Loop": March_Loop, "March_Step": March_Step, "Sword_ShieldHit": Sword_ShieldHit,
          "Shield_BlockHeavy": Shield_BlockHeavy}
VARIANTS = {"Fireball_Explode": 3, "Shock_Loop": 1, "Shock_Collapse": 3, "Water_Shove": 3, "Body_Knockback": 4,
            "Burning_Loop": 1, "March_Loop": 1, "March_Step": 6, "Sword_ShieldHit": 4, "Shield_BlockHeavy": 4}
