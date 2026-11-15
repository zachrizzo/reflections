"""Turn raw music generations into loop-ready (or one-shot) WAVs."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import audiolib as A

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW, OUT = os.path.join(ROOT, "raw"), os.path.join(ROOT, "proc", "music")

# name: (raw file, mode, params)
TRACKS = {
    "MUS_Gray_Loop": ("MUS_Gray_Loop_t1.mp3", "loop", dict(xfade=5.0, search=(126, 146), match=8.0, rms=-19.0, w_flux=0.5, w_spec=1.0)),
    "MUS_Red_Loop": ("MUS_Red_Loop_t1.mp3", "loop", dict(xfade=1.5, search=(126, 147.5), match=6.0, rms=-18.0)),
    "MUS_White_Loop": ("MUS_White_Loop_t1.mp3", "loop", dict(xfade=4.0, search=(124, 145), match=8.0, rms=-20.0)),
    "MUS_Combat_Layer": ("MUS_Combat_Layer_t1.mp3", "loop", dict(xfade=1.0, search=(70, 95), match=6.0, rms=-19.0)),
    "MUS_Victory_Sting": ("MUS_Victory_Sting_t1.mp3", "oneshot", dict(rms=-16.0)),
}


def fade_tail_end(x, sr, thresh_db=-12.0):
    """Find where the generated outro starts: first second (from 60% on) whose RMS drops thresh below median."""
    m = x.mean(axis=1)
    sec = len(m) // sr
    r = np.array([A.db(A.rms(m[i * sr:(i + 1) * sr])) for i in range(sec)])
    med = np.median(r)
    for i in range(int(sec * 0.6), sec):
        if r[i] < med + thresh_db:
            return i
    return sec


def main(names):
    report = {}
    for name in names:
        raw, mode, p = TRACKS[name]
        path = os.path.join(RAW, raw)
        if not os.path.exists(path):
            print("missing", name)
            continue
        x, sr = A.decode(path)
        if mode == "loop":
            body_end = fade_tail_end(x, sr)
            lo, hi = p["search"]
            hi = min(hi, body_end - max(p["xfade"], p["match"]) - 0.5)
            lo = min(lo, hi - 5)
            score, s0, e0 = A.find_loop(x, sr, p.get("start", (0, 6)), (lo, hi), match_s=p["match"],
                                        w_flux=p.get("w_flux", 1.0), w_spec=p.get("w_spec", 0.5))
            e1 = A.refine_transient(x, sr, s0, e0)
            y = A.loop_from_points(x, sr, s0, e1, p["xfade"])
            info = {"start_s": s0 / sr, "E_s": e1 / sr, "match": score, "body_end_s": body_end}
        else:
            y = A.trim_oneshot(x, sr, head_db=-40, tail_db=-60, post_ms=60, fade_out_ms=250)
            info = {}
        y, g = A.normalize_rms(y, p["rms"], -1.0)
        info.update(A.describe(y, sr))
        info["gain_db"] = round(g, 1)
        info["seam"] = A.seam_jump(y) if mode == "loop" else None
        out = os.path.join(OUT, name + ".wav")
        A.write_wav(out, y, sr)
        info["file"] = out
        info["bytes"] = os.path.getsize(out)
        report[name] = info
        print(name, json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in info.items()}, default=str))
    rp = os.path.join(ROOT, "music_report.json")
    old = json.load(open(rp)) if os.path.exists(rp) else {}
    old.update({k: {kk: (float(vv) if isinstance(vv, (float, np.floating)) else vv) for kk, vv in v.items() if kk != "seam"} for k, v in report.items()})
    json.dump(old, open(rp, "w"), indent=1, default=str)
    return report


if __name__ == "__main__":
    main(sys.argv[1:] or list(TRACKS))
