"""Which skin do the emulated underarm contacts hit, and how is that garment part bound?"""
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
label = sys.argv[2] if len(sys.argv) > 2 else "walk_11"
b0, bf = surface(SRC / "standing_body.bin"); arm_v = arm_mask(b0)
W = Wrap(b0, bf, 2); bd = W.bind(c)
bound_arm = arm_v[bf[bd["f"]]].sum(1) >= 2
print("prepared shape: vertices bound to arm-mask skin", int(bound_arm.sum()), "| bind distance cm p50/p95", np.percentile(bd["d"], [50, 95]).round(2))
fr = load(SRC, label); b1 = fr["skin"][:len(b0)]
posed = W.pose(bd, b1); fr["cloth"] = posed; fr["cf"] = cf
isk, icl, sub, is_arm = pairs_by_part(fr, arm_v)
other = ~is_arm[isk]
gt = np.unique(icl[other]); st = np.unique(isk[other])
skin_tri_standing = np.vstack((b0, surface(SRC / "standing_face.bin")[0]))[sub[st]].mean(1)
g_stand = c[cf[gt]].mean(1)
print(label, "garment tris crossing non-arm skin:", len(gt))
print(" garment tris (prepared standing position): |x| pct 5/50/95", np.percentile(np.abs(g_stand[:, 0]), [5, 50, 95]).round(1), " y", np.percentile(g_stand[:, 1], [5, 50, 95]).round(1), " z", np.percentile(g_stand[:, 2], [5, 50, 95]).round(1))
print(" skin tris hit (standing position):         |x| pct 5/50/95", np.percentile(np.abs(skin_tri_standing[:, 0]), [5, 50, 95]).round(1), " y", np.percentile(skin_tri_standing[:, 1], [5, 50, 95]).round(1), " z", np.percentile(skin_tri_standing[:, 2], [5, 50, 95]).round(1))
# how far did those skin triangles and garment triangles move from standing to this pose
skin_now = fr["skin"][sub[st]].mean(1)
print(" skin tris moved cm p50/p95", np.percentile(np.linalg.norm(skin_now - skin_tri_standing, axis=1), [50, 95]).round(1), "| garment tris moved", np.percentile(np.linalg.norm(posed[cf[gt]].mean(1) - g_stand, axis=1), [50, 95]).round(1))
gv = np.unique(cf[gt])
print(" garment verts in those tris:", len(gv), "bound to arm-mask skin:", int(bound_arm[gv].sum()), "| their bind points (standing) |x| p50", np.median(np.abs(bd["cp"][gv][:, 0])).round(1), "z p50", np.median(bd["cp"][gv][:, 2]).round(1))
# upper arm root: skin within 7.5 cm of the arm axis but inside x<17.5 or z>=150 counts as non-arm in arm_mask
for s in (1, -1):
    sel = b0[(s * b0[:, 0] > 27) & (b0[:, 2] > 95)]; cen = sel.mean(0); u = np.linalg.svd(sel - cen)[2][0]
    r = np.linalg.norm(np.cross(skin_tri_standing - cen, u), axis=1)
    side = s * skin_tri_standing[:, 0] > 0
    print(f" side {s:+d}: hit skin tris {int(side.sum())}, of which within 7.5 cm of the arm axis (arm root, counted as non-arm): {int((side & (r < 7.5)).sum())}")
