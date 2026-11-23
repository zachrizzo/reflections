"""EMULATED 51-pose audit of a prepared standing shape (not an Unreal measurement).

usage: _emul.py <result.npz | baseline> <outdir> <binding: full | torso> [workers]
The garment is bound to the captured standing body (nearest surface point, like Unreal's
closest-point weight transfer) and carried into each captured pose. 'torso' binds to the body
with the free arms removed, to predict what a torso-only weight source would do.
"""
import sys, os, json, time
from pathlib import Path
HERE = Path(r"C:/Users/zachc/Documents/Unreal Projects/reflections/Tools/ClothingFit/garmentprep")
ST = Path(r"C:/Users/zachc/Documents/Unreal Projects/reflections/Saved/ClothingFit/DirectImage3D/MarketJerkin/MeshRetargetPilot/ContactStudy/tools")
sys.path.insert(0, str(ST)); sys.path.insert(0, str(HERE)); os.chdir(ST)
import numpy as np
from parts import *            # load, Wrap, arm_mask, pairs_by_part, intersections, tri_area ...
from check import stretch
SRC = PILOT / "AfterPreserved"


def labels():
    man = json.loads((SRC / "Manifest.json").read_text())
    return ["standing"] + [f["label"] for c in man["clips"].values() for f in c["frames"]]


def setup(shape, binding):
    b0, bf = surface(SRC / "standing_body.bin")
    if shape == "baseline":
        c, cf = surface(SRC / "standing_jerkin.bin")
    else:
        d = np.load(shape); c, cf = d["P"], d["F"]
    arm_v = arm_mask(b0)
    faces = bf if binding == "full" else bf[arm_v[bf].sum(1) == 0]
    W = Wrap(b0, faces, 2); W.N = adjacency(len(b0), bf, 2)   # motion fit always uses the whole body's neighbourhoods
    bd = W.bind(c)
    return b0, c, cf, arm_v, W, bd


def one(args):
    shape, out, binding, label = args
    out = Path(out)
    if (out / f"{label}.json").exists():
        return label
    b0, c, cf, arm_v, W, bd = setup(shape, binding)
    fr = load(SRC, label); b1 = fr["skin"][:len(b0)]
    fr["cloth"] = c if label == "standing" else W.pose(bd, b1); fr["cf"] = cf
    isk, icl, sub, is_arm = pairs_by_part(fr, arm_v)
    ga = np.unique(icl[is_arm[isk]]); gt = np.unique(icl[~is_arm[isk]])
    aa = tri_area(fr["skin"], sub[np.unique(isk[is_arm[isk]])]).sum(); at = tri_area(fr["skin"], sub[np.unique(isk[~is_arm[isk]])]).sum()
    depth = 0.
    if len(gt):
        pts = np.vstack((fr["cloth"][np.unique(cf[gt])], fr["cloth"][cf[gt]].mean(1))); osub = sub[~is_arm]
        cp, d, f = closest_on_tris(pts, fr["skin"], osub); _, fn = vnormals(fr["skin"], osub); s = skin_sign(fr["skin"], fr["sf"])
        ins = np.einsum("ij,ij->i", pts - cp, fn[f]) * s < 0; depth = float(d[ins].max() * 10) if ins.any() else 0.
    ib, ic2 = intersections(fr["bottom"], fr["tf"], fr["cloth"], cf)
    st = stretch(c, fr["cloth"], cf)
    row = dict(label=label, other_tris=int(len(gt)), other_area=round(float(at), 2), other_depth_mm=round(depth, 2), arm_tris=int(len(ga)),
               arm_area=round(float(aa), 2), trouser_tris=int(len(np.unique(ic2))), stretch_p95=round(float(np.percentile(st, 95)), 2))
    np.savez_compressed(out / f"{label}.npz", arm=ga, other=gt)
    (out / f"{label}.json").write_text(json.dumps(row))
    return label


def summary(out):
    rows = [json.loads((Path(out) / f"{l}.json").read_text()) for l in labels()]; S = {}
    for name in ("standing", "walk", "reach"):
        r = [x for x in rows if x["label"].startswith(name)]
        S[name] = dict(poses=len(r), poses_with_non_arm_contact=sum(x["other_tris"] > 0 for x in r),
                       non_arm_tris_median=int(np.median([x["other_tris"] for x in r])), non_arm_tris_peak=max(x["other_tris"] for x in r),
                       non_arm_area_peak=max(x["other_area"] for x in r), non_arm_depth_peak_mm=max(x["other_depth_mm"] for x in r),
                       poses_with_arm_contact=sum(x["arm_tris"] > 0 for x in r), arm_tris_median=int(np.median([x["arm_tris"] for x in r])),
                       arm_tris_peak=max(x["arm_tris"] for x in r), arm_area_peak=max(x["arm_area"] for x in r),
                       poses_with_trouser_contact=sum(x["trouser_tris"] > 0 for x in r), stretch_p95_worst=max(x["stretch_p95"] for x in r))
    return S, rows


if __name__ == "__main__":
    from multiprocessing import Pool
    shape, out, binding = sys.argv[1:4]
    workers = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    Path(out).mkdir(parents=True, exist_ok=True)
    t = time.time()
    with Pool(workers) as pool:
        for done in pool.imap_unordered(one, [(shape, out, binding, l) for l in labels()]):
            pass
    S, rows = summary(out)
    (Path(out) / "summary.json").write_text(json.dumps(dict(emulated=True, binding=binding, summary=S, poses=rows), indent=1))
    print("EMULATED", binding, round(time.time() - t), "s"); print(json.dumps(S, indent=1))
