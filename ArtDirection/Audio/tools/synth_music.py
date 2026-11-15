"""Procedural stand-ins for the combat percussion layer and victory sting (stereo 48 kHz)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import audiolib as A
import synth as S

SR = 48000
S.SR = SR  # synth helpers read the module-level rate
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "proc", "synth_music")


def drum(rng, f_hi, f_lo, decay, noise_amt=0.3, noise_band=(80, 2500), length=None):
    d = length or decay * 4
    n = S.n_(d)
    body = S.sweep_sine(d, f_hi, f_lo) * S.env_ad(n, 0.001, decay, 4.0)
    skin = S.fft_filter(S.white(rng, n), *noise_band) * S.env_ad(n, 0.0005, decay * 0.25, 4.0)
    return body + noise_amt * skin / (np.abs(skin).max() + 1e-9)


def snare(rng, decay=0.12):
    n = S.n_(decay * 4)
    nz = S.fft_filter(S.white(rng, n), 1200, 7000) * S.env_ad(n, 0.0005, decay, 4.0)
    body = S.sweep_sine(decay * 4, 260, 180) * S.env_ad(n, 0.001, decay * 0.5, 4.0)
    return 0.7 * nz / (np.abs(nz).max() + 1e-9) + 0.4 * body


def place(buf, x, t, gain=1.0, pan=0.0):
    i = int(t * SR) % len(buf)
    L, R = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    for k in range(0, len(x), len(buf) - i if i else len(x)):
        pass
    idx = (np.arange(len(x)) + i) % len(buf)  # wrap tails to the start: loop-safe
    np.add.at(buf[:, 0], idx, gain * L * x)
    np.add.at(buf[:, 1], idx, gain * R * x)


def combat_layer(seed=7, bpm=100, bars=16):
    rng = np.random.default_rng(seed)
    beat = 60 / bpm
    total = bars * 4 * beat
    buf = np.zeros((int(total * SR), 2), np.float32)
    taiko = [drum(rng, 95, 48, 0.28, 0.35) for _ in range(3)]
    frame = [drum(rng, 210, 150, 0.12, 0.5, (300, 5000)) for _ in range(3)]
    toms = [drum(rng, f, f * 0.7, 0.18, 0.3) for f in (150, 120, 100)]
    sn = [snare(rng) for _ in range(4)]
    sub = S.sweep_sine(0.25, 52, 45) * S.env_ad(S.n_(0.25), 0.003, 0.08)
    for bar in range(bars):
        t0 = bar * 4 * beat
        fill = bar % 4 == 3
        for b in range(4):
            tb = t0 + b * beat
            if b in (0, 2) or (b == 3 and bar % 2 == 1):
                place(buf, taiko[rng.integers(3)], tb, 1.0 * rng.uniform(0.9, 1.0), rng.uniform(-0.2, 0.2))
            for e in range(2):
                place(buf, sub, tb + e * beat / 2, 0.35)
            for s in range(4):
                if rng.random() < (0.85 if s % 2 == 0 else 0.55):
                    place(buf, frame[rng.integers(3)], tb + s * beat / 4, 0.35 * rng.uniform(0.7, 1.0), rng.uniform(-0.6, 0.6))
            if b in (1, 3):
                place(buf, sn[rng.integers(4)], tb, 0.45, 0.15)
        if fill:
            for s in range(8):
                place(buf, toms[s % 3], t0 + 3 * beat + s * beat / 8, 0.55 + 0.05 * s, -0.4 + 0.1 * s)
            for s in range(8):
                place(buf, sn[s % 4], t0 + 2 * beat + s * beat / 8, 0.15 + 0.04 * s, 0.1)
    mono = buf.mean(axis=1)
    wet = S.reverb(mono, 1.0, 1.0, 0.0)[: len(buf)]
    buf[:, 0] += 0.18 * wet
    buf[:, 1] += 0.18 * np.roll(wet, 331)
    return buf


def brass_chord(rng, d, freqs, attack=0.12):
    t = S.tt(d)
    y = np.zeros(len(t), np.float32)
    for f in freqs:
        for det in (-6, 0, 6):
            ff = f * 2 ** (det / 1200) * (1 + 0.003 * np.sin(2 * np.pi * 5.5 * t))
            ph = np.cumsum(ff) / SR
            y += (2 * (ph % 1.0) - 1).astype(np.float32)
    env = S.env_ad(len(t), attack, d * 0.5, 1.5)
    cutoff = lambda tt_: 700 + 3800 * min(1.0, tt_ / 0.25) * np.exp(-tt_ / 2.0)
    y = S.stft_sculpt(y * env, lambda tt_: cutoff(tt_) * 0.6, lambda tt_: 1.6)
    return y


def victory_sting(seed=3):
    rng = np.random.default_rng(seed)
    d = 5.0
    total = S.n_(d)
    roll = np.zeros(total, np.float32)
    for k in range(14):
        tk = k * 0.055
        hit = drum(rng, 110, 98, 0.35, 0.2)
        i = S.n_(tk)
        roll[i : i + len(hit)] += (0.25 + 0.05 * k) * hit[: max(0, min(len(hit), total - i))]
    boom = drum(rng, 98, 70, 0.9, 0.3, length=2.5)
    c1 = brass_chord(rng, 0.42, [261.6, 329.6, 392.0])
    c2 = brass_chord(rng, 3.6, [349.2 / 2 * 2, 523.3, 659.3, 784.0], attack=0.05)
    bells = S.partials(3.5, [1046.5, 1318.5, 1568, 2093], [0.5, 0.4, 0.35, 0.25], [1.5, 1.3, 1.1, 0.9], rng, detune_cents=8, voices=3)
    y = S.mix(roll * 0.6, S.at(0.5 * S.norm(c1), 0.78, total), S.at(0.9 * S.norm(boom), 1.2, total),
              S.at(0.75 * S.norm(c2), 1.2, total), S.at(0.25 * S.norm(bells), 1.22, total))
    y = S.reverb(y, 0.3, 1.2, 1.5)
    y = S.fade_out(y[: S.n_(d + 1.0)], 600)
    st = np.stack([y, y], axis=1)
    return st


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    c = combat_layer()
    c, _ = A.normalize_rms(c, -19.0, -1.0)
    A.write_wav(os.path.join(OUT, "MUS_Combat_Layer.wav"), c, SR)
    print("combat", A.describe(c, SR), "seam", A.seam_jump(c))
    v = victory_sting()
    v, _ = A.normalize_rms(v, -16.0, -1.0)
    A.write_wav(os.path.join(OUT, "MUS_Victory_Sting.wav"), v, SR)
    print("victory", A.describe(v, SR))
