"""EMULATED: if this garment were glued to the skin it binds to (at a given offset), how much would still be crossed?"""
import sys, os, json
from pathlib import Path
HERE = Path(r"C:/Users/zachc/Documents/Unreal Projects/reflections/Tools/ClothingFit/garmentprep")
ST = Path(r"C:/Users/zachc/Documents/Unreal Projects/reflections/Saved/ClothingFit/DirectImage3D/MarketJerkin/MeshRetargetPilot/ContactStudy/tools")
sys.path.insert(0, str(ST)); sys.path.insert(0, str(HERE)); os.chdir(ST)
import numpy as np
from parts import *
np.set_printoptions(linewidth=220, suppress=True)
SRC = PILOT / "AfterPreserved"
d = np.load(sys.argv[1]); c, cf = d["P"], d["F"]
b0, bf = surface(SRC / "standing_body.bin"); arm_v = arm_mask(b0)
W = Wrap(b0, bf, 2); bd = W.bind(c)
vn, fn = vnormals(b0, bf); s = skin_sign(b0, bf)
normal = fn[bd["f"]] * s
shapes = {"as prepared": c}
for T in (.6, 1.35):
    shapes[f"glued at {T} cm"] = bd["cp"] + normal * T
z = c[:, 2]; ax = np.abs(c[:, 0])
for name, shape in shapes.items():
    b = W.bind(shape)
    print(name, "| distance from bound skin p50/p95", np.percentile(b["d"], [50, 95]).round(2))
    for label in ("walk_03", "walk_11", "walk_19", "reach_10"):
        fr = load(SRC, label); b1 = fr["skin"][:len(b0)]
        fr["cloth"] = W.pose(b, b1); fr["cf"] = cf
        isk, icl, sub, is_arm = pairs_by_part(fr, arm_v)
        gt = np.unique(icl[~is_arm[isk]]); ga = np.unique(icl[is_arm[isk]])
        cen = c[cf[gt]].mean(1) if len(gt) else np.zeros((0, 3))
        under = int(((cen[:, 2] > 116) & (cen[:, 2] < 137) & (np.abs(cen[:, 0]) > 15)).sum())
        print(f"   {label}: non-arm {len(gt):4d} (underarm zone {under:4d})  arm {len(ga):4d}")
