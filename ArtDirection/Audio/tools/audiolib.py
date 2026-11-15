"""Small audio toolkit: decode via the engine's bundled libsndfile, process with numpy, write 16-bit WAV."""
import ctypes, os, wave
import numpy as np

_DLL = r"C:\Program Files\Epic Games\UE_5.9\Engine\Binaries\ThirdParty\libsndfile\Win64\libsndfile-1.dll"
os.add_dll_directory(os.path.dirname(_DLL))
_lib = ctypes.CDLL(_DLL)


class SF_INFO(ctypes.Structure):
    _fields_ = [("frames", ctypes.c_int64), ("samplerate", ctypes.c_int), ("channels", ctypes.c_int),
                ("format", ctypes.c_int), ("sections", ctypes.c_int), ("seekable", ctypes.c_int)]


_lib.sf_open.restype = ctypes.c_void_p
_lib.sf_open.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(SF_INFO)]
_lib.sf_readf_float.restype = ctypes.c_int64
_lib.sf_readf_float.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.c_int64]
_lib.sf_close.argtypes = [ctypes.c_void_p]
_lib.sf_strerror.restype = ctypes.c_char_p
_lib.sf_strerror.argtypes = [ctypes.c_void_p]
SFM_READ = 0x10


def decode(path):
    info = SF_INFO()
    h = _lib.sf_open(path.encode("mbcs"), SFM_READ, ctypes.byref(info))
    if not h:
        raise RuntimeError(f"sf_open failed for {path}: {_lib.sf_strerror(None)}")
    try:
        chunks = []
        block = 1 << 16
        buf = np.empty((block, info.channels), dtype=np.float32)
        ptr = buf.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        while True:
            n = _lib.sf_readf_float(h, ptr, block)
            if n <= 0:
                break
            chunks.append(buf[:n].copy())
        data = np.concatenate(chunks, axis=0) if chunks else np.zeros((0, info.channels), np.float32)
    finally:
        _lib.sf_close(h)
    return data, info.samplerate


def write_wav(path, data, sr):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if data.ndim == 1:
        data = data[:, None]
    pcm = np.clip(data, -1.0, 1.0)
    pcm = (pcm * 32767.0).round().astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(pcm.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def db(x):
    return 20 * np.log10(max(float(x), 1e-9))


def rms(x):
    return float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0


def to_mono(data):
    if data.ndim == 1 or data.shape[1] == 1:
        return data.reshape(-1)
    mono = data.mean(axis=1)
    side_rms = max(rms(data[:, 0]), rms(data[:, 1]))
    # Guard against phase cancellation: fall back to the louder channel.
    if side_rms > 0 and rms(mono) < 0.5 * side_rms:
        mono = data[:, int(np.argmax([rms(data[:, 0]), rms(data[:, 1])]))]
    return mono.astype(np.float32)


def env_db(x, sr, win_ms=10.0):
    """Peak-ish envelope in dB per window (mono or multi-channel)."""
    m = np.abs(x) if x.ndim == 1 else np.abs(x).max(axis=1)
    hop = max(1, int(sr * win_ms / 1000))
    n = len(m) // hop
    if n == 0:
        return np.array([db(m.max() if len(m) else 0)])
    frames = m[: n * hop].reshape(n, hop).max(axis=1)
    return 20 * np.log10(np.maximum(frames, 1e-9))


def trim_oneshot(x, sr, head_db=-42.0, tail_db=-55.0, pre_ms=4.0, post_ms=40.0, fade_out_ms=None):
    """Trim leading/trailing silence relative to the clip's peak, with short fades."""
    a = np.abs(x) if x.ndim == 1 else np.abs(x).max(axis=1)
    peak = a.max()
    if peak <= 0:
        return x
    head_thr = peak * 10 ** (head_db / 20)
    tail_thr = peak * 10 ** (tail_db / 20)
    above = np.nonzero(a > head_thr)[0]
    start = max(0, above[0] - int(sr * pre_ms / 1000))
    above_t = np.nonzero(a > tail_thr)[0]
    end = min(len(a), above_t[-1] + int(sr * post_ms / 1000))
    y = x[start:end].copy()
    fi = min(len(y), int(sr * 0.002))
    if start > 0 and fi > 0:
        ramp = np.linspace(0, 1, fi, dtype=np.float32)
        y[:fi] = (y[:fi].T * ramp).T
    fo_ms = fade_out_ms if fade_out_ms is not None else min(120.0, 0.25 * len(y) / sr * 1000)
    fo = min(len(y), int(sr * fo_ms / 1000))
    if fo > 0:
        ramp = np.cos(np.linspace(0, np.pi / 2, fo, dtype=np.float32)) ** 2
        y[-fo:] = (y[-fo:].T * ramp).T
    return y


def normalize_peak(x, target_db=-1.0):
    p = float(np.abs(x).max())
    if p <= 0:
        return x, 0.0
    g = 10 ** (target_db / 20) / p
    return (x * g).astype(np.float32), db(g)


def normalize_rms(x, target_db=-18.0, peak_ceiling_db=-1.0):
    r = rms(x)
    if r <= 0:
        return x, 0.0
    g = 10 ** (target_db / 20) / r
    p = float(np.abs(x).max()) * g
    ceiling = 10 ** (peak_ceiling_db / 20)
    if p > ceiling:
        g *= ceiling / p
    return (x * g).astype(np.float32), db(g)


def onset_env(x, sr, hop_ms=10.0):
    m = x if x.ndim == 1 else x.mean(axis=1)
    hop = int(sr * hop_ms / 1000)
    n = len(m) // hop
    fr = m[: n * hop].reshape(n, hop)
    e = np.log(np.sqrt(np.mean(fr ** 2, axis=1)) + 1e-6)
    on = np.maximum(0, np.diff(e, prepend=e[0]))
    return on, hop


def loop_crossfade(x, sr, xfade_s, end_search=(None, None), match_s=6.0, start=0):
    """Make a seamless loop: y = x[start:E] with its head crossfaded with x[E:E+X].

    E is searched in end_search=(lo_s, hi_s) seconds (relative to x) for the best rhythmic match between
    x[E:E+match] and x[start:start+match] (normalized correlation of onset envelopes).
    """
    X = int(sr * xfade_s)
    on, hop = onset_env(x, sr)
    W = int(match_s * 1000 / 10)
    s0 = start // hop
    ref = on[s0 : s0 + W]
    ref = (ref - ref.mean()) / (ref.std() + 1e-9)
    lo_s, hi_s = end_search
    L = len(x)
    lo = int((lo_s if lo_s is not None else (L - X) / sr - 20) * sr) // hop
    hi = int((hi_s if hi_s is not None else (L - X) / sr - 1) * sr) // hop
    hi = min(hi, (L - X) // hop - W if (L - X) // hop - W > lo else hi)
    best, bestk = -9, lo
    for k in range(lo, max(lo + 1, hi)):
        seg = on[k : k + W]
        if len(seg) < W:
            break
        seg = (seg - seg.mean()) / (seg.std() + 1e-9)
        c = float(np.dot(seg, ref) / W)
        if c > best:
            best, bestk = c, k
    E = bestk * hop
    E = min(E, L - X)
    head = x[start : start + X]
    tail = x[E : E + X]
    t = np.linspace(0, np.pi / 2, X, dtype=np.float32)
    fin, fout = np.sin(t), np.cos(t)
    if x.ndim > 1:
        fin, fout = fin[:, None], fout[:, None]
    y = x[start:E].copy()
    y[:X] = head * fin + tail * fout
    return y.astype(np.float32), {"E_s": E / sr, "start_s": start / sr, "match": best, "len_s": len(y) / sr}


def band_features(x, sr, hop=512, nfft=2048, nbands=24):
    m = x if x.ndim == 1 else x.mean(axis=1)
    n = 1 + (len(m) - nfft) // hop
    idx = np.arange(nfft)[None, :] + hop * np.arange(n)[:, None]
    win = np.hanning(nfft).astype(np.float32)
    spec = np.abs(np.fft.rfft(m[idx] * win, axis=1)) ** 2
    freqs = np.fft.rfftfreq(nfft, 1 / sr)
    edges = np.geomspace(40, min(16000, sr / 2 - 1), nbands + 1)
    bands = np.stack([spec[:, (freqs >= lo) & (freqs < hi)].sum(axis=1) for lo, hi in zip(edges[:-1], edges[1:])], axis=1)
    logb = np.log(bands + 1e-9)
    flux = np.maximum(0, np.diff(logb, axis=0, prepend=logb[:1]))
    def z(a):
        return (a - a.mean(axis=0)) / (a.std(axis=0) + 1e-9)
    return z(logb), z(flux), hop


def _ncc_scan(F, s, W, lo, hi):
    """NCC of template F[s:s+W] against F[k:k+W] for k in [lo, hi)."""
    T = F[s : s + W]
    T = T - T.mean()
    tn = np.sqrt((T ** 2).sum()) + 1e-9
    out = np.full(hi - lo, -9.0)
    for i, k in enumerate(range(lo, hi)):
        seg = F[k : k + W]
        if len(seg) < W:
            break
        seg = seg - seg.mean()
        out[i] = float((seg * T).sum() / (tn * (np.sqrt((seg ** 2).sum()) + 1e-9)))
    return out


def find_loop(x, sr, start_range_s, end_range_s, match_s=6.0, w_flux=1.0, w_spec=0.5, step=2):
    spec, flux, hop = band_features(x, sr)
    W = int(match_s * sr / hop)
    lo = int(end_range_s[0] * sr / hop)
    hi = int(end_range_s[1] * sr / hop)
    best = (-9, 0, 0)
    for s_s in np.arange(start_range_s[0], start_range_s[1] + 1e-6, 0.5):
        s = int(s_s * sr / hop)
        score = w_flux * _ncc_scan(flux, s, W, lo, hi)[::1] if w_flux else 0
        if w_spec:
            score = score + w_spec * _ncc_scan(spec, s, W, lo, hi)
        score = score / (w_flux + w_spec)
        k = int(np.argmax(score))
        if score[k] > best[0]:
            best = (float(score[k]), s * hop, (lo + k) * hop)
    return best  # (score, start_sample, end_sample)


def refine_transient(x, sr, s, e, radius_ms=12):
    """Nudge e by up to radius so its fine-grained envelope lines up with s."""
    m = x if x.ndim == 1 else x.mean(axis=1)
    hp = np.diff(m, prepend=m[0])
    env = np.abs(hp)
    W = int(0.3 * sr)
    r = int(radius_ms * sr / 1000)
    ref = env[s : s + W]
    best, bk = -1e9, 0
    for k in range(-r, r + 1, 4):
        seg = env[e + k : e + k + W]
        if len(seg) < W:
            continue
        c = float(np.dot(seg, ref))
        if c > best:
            best, bk = c, k
    return e + bk


def loop_from_points(x, sr, s, e, xfade_s):
    X = int(sr * xfade_s)
    e = min(e, len(x) - X)
    head = x[s : s + X]
    tail = x[e : e + X]
    t = np.linspace(0, np.pi / 2, X, dtype=np.float32)
    fin, fout = np.sin(t), np.cos(t)
    if x.ndim > 1:
        fin, fout = fin[:, None], fout[:, None]
    y = x[s:e].copy()
    y[:X] = head * fin + tail * fout
    return y.astype(np.float32)


def seam_jump(y):
    """Sample discontinuity at the loop seam vs typical sample-to-sample step."""
    a = y if y.ndim == 1 else y.mean(axis=1)
    step = np.abs(np.diff(a))
    return float(abs(a[0] - a[-1])), float(np.percentile(step, 99))


def describe(x, sr):
    a = x if x.ndim == 1 else x.mean(axis=1)
    spec = np.abs(np.fft.rfft(a * np.hanning(len(a)))) if len(a) > 16 else np.zeros(1)
    freqs = np.fft.rfftfreq(len(a), 1 / sr) if len(a) > 16 else np.zeros(1)
    centroid = float((spec * freqs).sum() / (spec.sum() + 1e-9))
    e = env_db(a, sr, 10)
    return {
        "dur": round(len(a) / sr, 3),
        "peak_db": round(db(np.abs(a).max() if len(a) else 0), 1),
        "rms_db": round(db(rms(a)), 1),
        "centroid_hz": round(centroid),
        "attack_ms": int(np.argmax(e) * 10),
    }
