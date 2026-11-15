"""Procedural footsteps (no recorded or sampled audio): shoe/boot on wet cobblestone, 8 variations each.

    python footsteps.py           -> proc/foley/SW_Footstep_<Set>_<n>.wav + spectrogram-free summary
Sets: Stone (NPC shoes: lighter, a heel tock and a toe click) and Hero (boots: heavier heel, leather creak, a faint coat
brush). Leveled quietly: footsteps sit well under voices and spells.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synth as S, audiolib as A, level as Lv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "proc", "foley")
SR = S.SR
TARGET = {"Stone": -27.0, "Hero": -25.0}  # momentary-max LUFS


def burst(n, lo, hi, decay_s, rng, attack_s=0.0015):
    x = S.fft_filter(rng.standard_normal(n).astype(np.float32), lo, hi)
    return x * S.env_ad(n, attack_s, decay_s)


def thump(n, f0, decay_s, rng):
    t = np.arange(n) / SR
    f = f0 * (1.0 + 0.6 * np.exp(-t / 0.012))  # quick downward pitch: the heel landing
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * np.exp(-t / decay_s)).astype(np.float32)


def grit(n, rate_hz, decay_s, rng, lo=2500, hi=10000):
    """Sparse crackle of street grit crushed under a sole: random tiny impulses, filtered, with a decay."""
    x = np.zeros(n, np.float32)
    k = rng.poisson(rate_hz * n / SR)
    idx = rng.integers(0, n, k)
    x[idx] = rng.uniform(-1, 1, k).astype(np.float32) * np.exp(-idx / SR / decay_s).astype(np.float32)
    return S.fft_filter(x, lo, hi)


def step(kind, rng):
    n = int(SR * 0.5)
    y = np.zeros(n, np.float32)
    heavy = kind == "Hero"
    # heel: a hard, broadband slap (most energy 1-6 kHz) over a short low weight (noise, not a tone)
    y += (1.0 if heavy else 0.85) * burst(n, rng.uniform(700, 1100), rng.uniform(6000, 9000), rng.uniform(0.008, 0.014), rng, attack_s=0.0005)
    y += (0.55 if heavy else 0.45) * burst(n, 50, rng.uniform(220, 320), 0.035 if heavy else 0.03, rng, attack_s=0.001)
    y += (0.35 if heavy else 0.55) * grit(n, 900 if heavy else 1400, 0.03 if heavy else 0.045, rng)
    # toe or sole roll-off, 60-110 ms later
    d = int(SR * rng.uniform(0.06, 0.11))
    y[d:] += (0.4 if heavy else 0.5) * burst(n - d, rng.uniform(1200, 1800), 9000, rng.uniform(0.006, 0.01), rng, attack_s=0.0005)
    y[d:] += 0.25 * grit(n - d, 700, 0.025, rng)
    # occasional scuff as the foot lifts
    if not heavy or rng.random() < 0.5:
        sc = int(SR * rng.uniform(0.12, 0.2))
        y[sc:] += (0.08 if heavy else 0.14) * burst(n - sc, 1800, 8000, 0.06, rng, attack_s=0.02)
    if heavy:  # boot leather creak, kept small
        c = int(SR * rng.uniform(0.02, 0.05))
        t = np.arange(n - c) / SR
        y[c:] += 0.05 * burst(n - c, 700, 2000, 0.05, rng, attack_s=0.01) * (0.6 + 0.4 * np.sin(2 * np.pi * 32 * t))
    # outdoor space: two quick slap reflections off walls, then a very short tail
    for delay, gain in ((rng.uniform(0.018, 0.03), 0.22 if heavy else 0.3), (rng.uniform(0.04, 0.065), 0.12 if heavy else 0.2)):
        k = int(SR * delay)
        y[k:] += gain * S.fft_filter(y[:n - k].copy(), 300, 7000)
    S.SR = SR
    y = S.reverb(y.astype(np.float32), 0.08, 0.5, 0.35, 7000)
    return S.fade_out(y, 60)


def main():
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(4242)
    made = []
    for kind in ("Stone", "Hero"):
        for i in range(1, 9):
            y = step(kind, rng)
            y = A.trim_oneshot(y, SR, head_db=-60, tail_db=-66, pre_ms=2, post_ms=60, fade_out_ms=30)
            g = 10 ** ((TARGET[kind] - Lv.momentary_max(y, SR)) / 20)
            y = np.clip(y * g, -0.98, 0.98).astype(np.float32)
            p = os.path.join(OUT, f"SW_Footstep_{kind}_{i:02d}.wav")
            A.write_wav(p, y, SR)
            made.append((os.path.basename(p), round(len(y) / SR, 3), round(float(np.abs(y).max()), 3)))
    for m in made:
        print(m)


if __name__ == "__main__":
    main()
