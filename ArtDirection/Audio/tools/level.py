"""Loudness pass. Picks each sound's source (ElevenLabs take if present, else procedural stand-in), normalizes it to a
per-sound loudness target (BS.1770 K-weighted; momentary max for SFX, gated integrated for music), limits peaks to
-1 dBFS, and writes proc/final/{sfx,music}/ + final/sources.json. python level.py [names...]"""
import sys, os, glob, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import audiolib as A
import catalog

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, "proc", *a)

# Momentary-max loudness targets (LUFS) for SFX; integrated targets for music.
TARGET = {
    "Fire_Cast": -16, "Water_Cast": -16, "Ice_Cast": -16, "Lightning_Cast": -16, "Earth_Cast": -16, "Arcane_Cast": -16,
    "Fire_Impact": -12, "Water_Impact": -13, "Ice_Impact": -13, "Lightning_Impact": -12, "Earth_Impact": -12, "Arcane_Impact": -13,
    "Heal_Shimmer": -18, "Shield_Up": -17, "Shield_Block": -16, "Shield_Loop": -25, "Projectile_Loop": -22,
    "Levitation_Start": -18, "Levitation_Loop": -24,
    "Sword_Swing": -17, "Sword_Hit": -16, "Sword_Clash": -15,
    "WorldJump_Whoosh": -15, "WorldJump_Stinger": -14, "WorldJump_Refused": -19,
    "Coin_Pickup": -18, "Page_Pickup": -19, "Door_Unseal": -16,
    "UI_Click": -24, "UI_Hover": -30, "UI_Confirm": -22,
    "Infected_Growl": -16,
    "Villain_Manifest": -13, "Villain_Voice": -18, "Villain_Hop": -16, "Villain_Telegraph": -16, "Villain_Slam": -11,
    "Villain_Hurt": -14, "Villain_Death": -14, "FinalSpell_Cast": -12,
    "Fireball_Explode": -11, "Water_Shove": -13, "Shock_Loop": -20, "Shock_Collapse": -14, "Body_Knockback": -15,
    "Burning_Loop": -21, "March_Loop": -21, "March_Step": -22, "Sword_ShieldHit": -15, "Shield_BlockHeavy": -15,
    "MUS_Gray_Loop": -20, "MUS_Red_Loop": -20, "MUS_White_Loop": -20, "MUS_Combat_Layer": -21, "MUS_Victory_Sting": -17,
}
CEILING_DB = -1.0
MAX_LIMIT_DB = 3.0


def k_weight(x, sr):
    """Apply the BS.1770 K-weighting magnitude response in the frequency domain (power-equivalent)."""
    def shelf(f):
        G, Q, fc = 3.99984385397, 0.7071752369554193, 1681.9744509555319
        K = np.tan(np.pi * fc / sr); Vh = 10 ** (G / 20); Vb = Vh ** 0.4996667741545416
        a0 = 1 + K / Q + K * K
        b = [(Vh + Vb * K / Q + K * K) / a0, 2 * (K * K - Vh) / a0, (Vh - Vb * K / Q + K * K) / a0]
        a = [1, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0]
        return b, a
    def hp(f):
        Q, fc = 0.5003270373238773, 38.13547087602444
        K = np.tan(np.pi * fc / sr)
        a0 = 1 + K / Q + K * K
        return [1, -2, 1], [1, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0]
    n = len(x)
    N = int(2 ** np.ceil(np.log2(n + 1)))
    w = 2 * np.pi * np.fft.rfftfreq(N, 1 / sr) / sr
    z = np.exp(-1j * w)
    H = np.ones_like(w, dtype=complex)
    for b, a in (shelf(None), hp(None)):
        H *= (b[0] + b[1] * z + b[2] * z * z) / (a[0] + a[1] * z + a[2] * z * z)
    X = np.fft.rfft(x, N, axis=0)
    Y = X * (np.abs(H)[:, None] if x.ndim > 1 else np.abs(H))
    return np.fft.irfft(Y, N, axis=0)[:n]


def blocks_ms(x, sr, win=0.4, hop=0.1):
    y = k_weight(x, sr)
    if y.ndim == 1:
        y = y[:, None]
    W, Hh = int(win * sr), int(hop * sr)
    if len(y) < W:
        y = np.concatenate([y, np.zeros((W - len(y), y.shape[1]))])
    cs = np.concatenate([np.zeros((1, y.shape[1])), np.cumsum(y ** 2, axis=0)])
    starts = np.arange(0, len(y) - W + 1, Hh)
    ms = (cs[starts + W] - cs[starts]) / W
    return ms.sum(axis=1)  # channel weights 1.0 (L/R)


def momentary_max(x, sr):
    ms = blocks_ms(x, sr)
    return -0.691 + 10 * np.log10(ms.max() + 1e-12)


def integrated(x, sr):
    ms = blocks_ms(x, sr)
    l = -0.691 + 10 * np.log10(ms + 1e-12)
    g = ms[l > -70]
    rel = -0.691 + 10 * np.log10(g.mean() + 1e-12) - 10
    g2 = ms[(l > -70) & (l > rel)]
    return -0.691 + 10 * np.log10(g2.mean() + 1e-12)


def limit(x, sr, ceiling_db=CEILING_DB, look_ms=2.0, release_ms=60.0):
    """Look-ahead peak limiter (sample peak). Only touches samples that would exceed the ceiling."""
    c = 10 ** (ceiling_db / 20)
    a = np.abs(x) if x.ndim == 1 else np.abs(x).max(axis=1)
    if a.max() <= c:
        return x, 0
    need = np.minimum(1.0, c / np.maximum(a, 1e-12))
    L = max(1, int(sr * look_ms / 1000))
    pad = np.concatenate([need, np.ones(L)])
    win = np.lib.stride_tricks.sliding_window_view(pad, L + 1).min(axis=1)[: len(need)]
    rel = np.exp(-1.0 / (sr * release_ms / 1000))
    g = np.empty_like(win)
    cur = 1.0
    for i, v in enumerate(win):  # instant attack (look-ahead), smooth release
        cur = v if v < cur else v + (cur - v) * rel
        g[i] = cur
    y = x * (g if x.ndim == 1 else g[:, None])
    return np.clip(y, -c, c).astype(np.float32), int((g < 0.999).sum())


def pick(name, is_music):
    if is_music:
        for src, p in (("elevenlabs", P("music", f"{name}.wav")), ("procedural", P("synth_music", f"{name}.wav"))):
            if os.path.exists(p):
                return src, [p]
        return None, []
    el = sorted(glob.glob(P("sfx", f"{name}_[0-9][0-9].wav")))
    if el:
        return "elevenlabs", el
    return "procedural", sorted(glob.glob(P("synth", f"{name}_[0-9][0-9].wav")))


def main(names):
    cat = catalog.as_dicts()
    music = {m["name"] for m in cat["music"]}
    allnames = [s["name"] for s in cat["sfx"]] + [m["name"] for m in cat["music"]]
    srcp = P("final", "sources.json")
    sources = json.load(open(srcp)) if os.path.exists(srcp) else {}
    for name in names or allnames:
        is_m = name in music
        src, files = pick(name, is_m)
        if not files:
            print("no source", name)
            continue
        outdir = P("final", "music" if is_m else "sfx")
        os.makedirs(outdir, exist_ok=True)
        for old in glob.glob(os.path.join(outdir, f"{name}.wav" if is_m else f"{name}_[0-9][0-9].wav")):
            os.remove(old)
        rep = []
        for f in files:
            x, sr = A.decode(f)
            if not is_m:
                x = A.to_mono(x)
            meas = integrated(x, sr) if is_m else momentary_max(x, sr)
            g = 10 ** ((TARGET[name] - meas) / 20)
            pk = float(np.abs(x).max()) * g
            cap = 10 ** ((CEILING_DB + MAX_LIMIT_DB) / 20)
            if pk > cap:  # never squash more than MAX_LIMIT_DB: land under target instead
                g *= cap / pk
            y, nlim = limit((x * g).astype(np.float32), sr)
            after = integrated(y, sr) if is_m else momentary_max(y, sr)
            A.write_wav(os.path.join(outdir, os.path.basename(f)), y, sr)
            rep.append({"file": os.path.basename(f), "in_lufs": round(meas, 1), "out_lufs": round(after, 1),
                        "gain_db": round(20 * np.log10(g), 1), "limited_samples": nlim,
                        "peak_db": round(A.db(np.abs(y).max()), 2)})
        sources[name] = {"source": src, "target_lufs": TARGET[name], "measure": "integrated" if is_m else "momentary_max", "files": rep}
        worst = max(r["peak_db"] for r in rep)
        print(f"{name:20s} {src:10s} target {TARGET[name]:4d}  out {[r['out_lufs'] for r in rep]}  peak<= {worst} dB  limited {[r['limited_samples'] for r in rep]}")
    json.dump(sources, open(srcp, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
