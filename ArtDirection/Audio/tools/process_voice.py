"""Raw TTS wavs -> mono, trimmed, character FX, loudness-leveled voice wavs in <work>/voice/final/<id>.wav."""
import sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import audiolib as A
import level as Lv
import voice_script as V
import synth as S

WORK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "voice")
RAW, OUT = os.path.join(WORK, "raw"), os.path.join(WORK, "final")
TARGET = {"tarnish": -15, "narrator": -18, "bark": -16, "tarnished": -19}  # momentary-max LUFS


MAX_GAP = {"tarnish": 0.6, "tarnished": 0.5, "narrator": 0.35, "bark": 0.3}


def tighten(x, sr, max_gap, thresh_db=-38.0, frame_ms=20, xf_ms=15):
    """Shorten internal pauses longer than max_gap (dialogue edit), with short crossfades at each cut."""
    hop = int(sr * frame_ms / 1000)
    e = A.env_db(x, sr, frame_ms)
    quiet = e < e.max() + thresh_db
    keep = np.ones(len(x), bool)
    i = 0
    n = len(quiet)
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]:
                j += 1
            if i > 0 and j < n and (j - i) * frame_ms / 1000 > max_gap:
                cut = (j - i) * hop - int(max_gap * sr)
                a = i * hop + int(max_gap * sr / 2)
                keep[a:a + cut] = False
            i = j
        else:
            i += 1
    if keep.all():
        return x
    y = x[keep].copy()
    # soften each cut point
    xf = int(sr * xf_ms / 1000)
    cuts = np.nonzero(np.diff(keep.astype(int)) == -1)[0]
    pos = np.cumsum(keep)[cuts] if len(cuts) else []
    for c in pos:
        a, b = max(0, c - xf), min(len(y), c + xf)
        y[a:b] *= np.concatenate([np.linspace(1, 0.3, c - a), np.linspace(0.3, 1, b - c)])
    return y


def fx(x, sr, kind):
    S.SR = sr  # synth helpers use the module rate
    t = np.arange(len(x)) / sr
    if kind == "tarnish":
        dry = S.fft_filter(x, 60, 7000)
        ring = dry * np.sin(2 * np.pi * 31 * t)
        y = 0.9 * dry + 0.12 * ring
        y = np.tanh(1.2 * y / (np.abs(y).max() + 1e-9))
        y = S.reverb(y.astype(np.float32), 0.16, 1.2, 0.9)
    elif kind == "tarnished":
        bp = S.fft_filter(x, 180, 5000)
        y = 0.85 * bp + 0.2 * bp * np.sin(2 * np.pi * 47 * t)
        y = S.reverb(y.astype(np.float32), 0.15, 0.8, 0.5)
    elif kind == "narrator":
        y = S.fft_filter(x, 70, None)
    else:  # bark
        y = S.fft_filter(x, 90, None)
    return y.astype(np.float32)


def main(ids):
    os.makedirs(OUT, exist_ok=True)
    rep = {}
    for lid, grp, spk, text in V.LINES:
        if ids and lid not in ids:
            continue
        src = os.path.join(RAW, lid + ".wav")
        if not os.path.exists(src):
            continue
        x, sr = A.decode(src)
        m = A.to_mono(x)
        m = A.trim_oneshot(m, sr, head_db=-45, tail_db=-55, pre_ms=10, post_ms=80, fade_out_ms=40)
        kind = V.SPEAKERS[spk][2]
        m = tighten(m, sr, MAX_GAP[kind])
        y = fx(m, sr, kind)
        y = S.fade_out(y, 120)
        meas = Lv.momentary_max(y, sr)
        g = 10 ** ((TARGET[kind] - meas) / 20)
        pk = float(np.abs(y).max()) * g
        cap = 10 ** ((Lv.CEILING_DB + Lv.MAX_LIMIT_DB) / 20)
        if pk > cap:
            g *= cap / pk
        y, nlim = Lv.limit((y * g).astype(np.float32), sr)
        A.write_wav(os.path.join(OUT, lid + ".wav"), y, sr)
        rep[lid] = {"dur": round(len(y) / sr, 2), "lufs": round(Lv.momentary_max(y, sr), 1), "sr": sr}
        print(lid, rep[lid])
    p = os.path.join(WORK, "final_report.json")
    old = json.load(open(p)) if os.path.exists(p) else {}
    old.update(rep)
    json.dump(old, open(p, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
