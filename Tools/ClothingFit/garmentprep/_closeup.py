"""Close-up renders and self-intersection count (welded) for a result folder."""
import sys, os, json
from pathlib import Path
HERE = Path(r"C:/Users/zachc/Documents/Unreal Projects/reflections/Tools/ClothingFit/garmentprep")
ST = Path(r"C:/Users/zachc/Documents/Unreal Projects/reflections/Saved/ClothingFit/DirectImage3D/MarketJerkin/MeshRetargetPilot/ContactStudy/tools")
sys.path.insert(0, str(ST)); sys.path.insert(0, str(HERE)); os.chdir(ST)
import numpy as np
from check import *
from render import render, scene, strip, LEATHER
import meshops, contact
OUT = Path(sys.argv[1])
d = np.load(OUT / "result.npz"); P0, F, P1 = d["P0"], d["F"], d["P"]
fr = load(PILOT / "AfterPreserved", "standing")
W0, Fw, inv = meshops.weld(P0, F)
W1 = np.zeros_like(W0); W1[inv] = P1
print("self pairs (welded) before", contact.self_crossing_pairs(W0, Fw), "after", contact.self_crossing_pairs(W1, Fw))
c0, cf0 = fr["cloth"], fr["cf"]
print("self pairs original 60k capture (welded)", self_pairs(c0, cf0))
# where are the crossing pairs after
Fv = Fw[(Fw[:, 0] != Fw[:, 1]) & (Fw[:, 1] != Fw[:, 2]) & (Fw[:, 0] != Fw[:, 2])]
ia, ib = contact.candidate_pairs(W1, Fv, W1, Fv); k = ia < ib; ia, ib = ia[k], ib[k]
share = (Fv[ia][:, :, None] == Fv[ib][:, None, :]).any((1, 2)); ia, ib = ia[~share], ib[~share]
h = contact.tri_tri(W1[Fv[ia]], W1[Fv[ib]]); cen = W0[Fv[ia[h]]].mean(1)
z = cen[:, 2]; x = np.abs(cen[:, 0])
print("crossing pairs by original zone: z>140:", int((z > 140).sum()), " 116<z<=140:", int(((z > 116) & (z <= 140)).sum()), " z<=116:", int((z <= 116).sum()), " of which |x|<12 & z>140 (yoke):", int(((z > 140) & (x < 12)).sum()))
st = stretch(P0, P1, F); e = edges(F); mid0 = .5 * (P0[e[:, 0]] + P0[e[:, 1]]); l0 = np.linalg.norm(P0[e[:, 0]] - P0[e[:, 1]], axis=1); ok = l0 > .05
rim = ok & (mid0[:, 2] > 149.5) & (np.abs(mid0[:, 0]) < 11) & (mid0[:, 1] < 3)
yoke = ok & (mid0[:, 2] > 143) & (mid0[:, 2] <= 149.5) & (np.abs(mid0[:, 0]) < 9) & (mid0[:, 1] < 0)
l1 = np.linalg.norm(P1[e[:, 0]] - P1[e[:, 1]], axis=1); s_all = (l1 / np.maximum(l0, 1e-9) - 1) * 100
print("back binding (rim) edges", int(rim.sum()), "stretch % p5/p50/p95/max", np.percentile(s_all[rim], [5, 50, 95, 100]).round(1))
print("upper-back yoke edges", int(yoke.sum()), "stretch % p5/p50/p95", np.percentile(s_all[yoke], [5, 50, 95]).round(1))
fr2 = dict(fr); fr2["cloth"] = P1; fr2["cf"] = F
ims = []
for az, el, label, ctr, half in ((180, 12, "back close", (0, 0, 143), (22, 16)), (180, 60, "back from above", (0, -4, 146), (22, 18)), (135, 15, "back three-quarter", (0, 0, 138), (26, 22)), (90, 8, "side close", (0, 0, 132), (22, 24))):
    ims.append(render(scene(fr2), az, el, np.array(ctr, float), half=half, px=.05))
strip(ims, ["back close", "back from above", "back three-quarter", "side close"], f"{OUT.name} close-ups").save(OUT / "closeup.png")
