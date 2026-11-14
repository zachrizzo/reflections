"""Raw SFX takes -> mono, trimmed, peak-normalized 16-bit WAVs in proc/sfx/NAME_NN.wav. Prints QA stats."""
import sys, os, json, glob, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import audiolib as A
import catalog

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW, OUT = os.path.join(ROOT, "raw"), os.path.join(ROOT, "proc", "sfx")
CAT = {s["name"]: s for s in catalog.as_dicts()["sfx"]}
SKIP = set()  # e.g. {"Fire_Cast_t2"} for takes rejected in QA
SKIP_FILE = os.path.join(ROOT, "rejected.json")
if os.path.exists(SKIP_FILE):
    SKIP = set(json.load(open(SKIP_FILE)))


def slice_on_silence(m, sr, gap_db=-38.0, min_gap_s=0.06, min_len_s=0.08):
    """Split a clip of several separate sounds at gaps quieter than gap_db (re peak) lasting min_gap_s."""
    e = A.env_db(m, sr, 5.0)  # 5 ms frames
    quiet = e < (e.max() + gap_db)
    hop = int(sr * 0.005)
    segs, start, run = [], None, 0
    for i, q in enumerate(quiet):
        if not q:
            if start is None:
                start = i
            run = 0
        elif start is not None:
            run += 1
            if run * 0.005 >= min_gap_s:
                segs.append((start, i - run + 1))
                start, run = None, 0
    if start is not None:
        segs.append((start, len(quiet)))
    out = []
    for a, b in segs:
        a0 = max(0, a * hop - int(0.01 * sr))
        b0 = min(len(m), b * hop + int(0.05 * sr))
        if (b0 - a0) / sr >= min_len_s:
            out.append(m[a0:b0])
    return out


def process(name, take_files):
    spec = CAT[name]
    results = []
    n = 0
    for f in take_files:
        stem = os.path.splitext(os.path.basename(f))[0]
        if stem in SKIP:
            continue
        x, sr = A.decode(f)
        m = A.to_mono(x)
        if spec.get("multi"):
            for k, piece in enumerate(slice_on_silence(m, sr)):
                if f"{stem}_s{k + 1}" in SKIP:
                    continue
                y = A.trim_oneshot(piece, sr)
                y, g = A.normalize_peak(y, -1.0)
                n += 1
                out = os.path.join(OUT, f"{name}_{n:02d}.wav")
                A.write_wav(out, y, sr)
                d = A.describe(y, sr)
                d.update({"src": f"{stem}_s{k + 1}", "out": os.path.basename(out), "gain_db": round(g, 1)})
                results.append(d)
            continue
        if spec["loop"]:
            a = np.abs(m)
            thr = a.max() * 10 ** (-60 / 20)
            nz = np.nonzero(a > thr)[0]
            m = m[nz[0] : nz[-1] + 1]
            y = A.loop_from_points(m, sr, 0, len(m) - int(0.15 * sr), 0.15)
        else:
            y = A.trim_oneshot(m, sr)
        y, g = A.normalize_peak(y, -1.0)
        n += 1
        out = os.path.join(OUT, f"{name}_{n:02d}.wav")
        A.write_wav(out, y, sr)
        d = A.describe(y, sr)
        d.update({"src": stem, "out": os.path.basename(out), "gain_db": round(g, 1), "raw_dur": round(len(x) / sr, 2),
                  "raw_peak_db": round(A.db(np.abs(x).max()), 1)})
        if spec["loop"]:
            d["seam"] = [round(v, 4) for v in A.seam_jump(y)]
        results.append(d)
    return results


def main(names):
    os.makedirs(OUT, exist_ok=True)
    allres = {}
    for name in names:
        files = sorted(glob.glob(os.path.join(RAW, f"{name}_t*.mp3")), key=lambda p: int(re.search(r"_t(\d+)\.mp3$", p).group(1)))
        if not files:
            print("no takes", name)
            continue
        for old in glob.glob(os.path.join(OUT, f"{name}_[0-9][0-9].wav")):
            os.remove(old)
        res = process(name, files)
        allres[name] = res
        for r in res:
            flag = ""
            if r["dur"] < 0.08 or r.get("raw_peak_db", 0) < -30:
                flag = "  <-- CHECK (too short/quiet)"
            print(name, r, flag)
    rep = os.path.join(ROOT, "sfx_report.json")
    old = json.load(open(rep)) if os.path.exists(rep) else {}
    old.update(allres)
    json.dump(old, open(rep, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1:] or list(CAT))
