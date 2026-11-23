import sys, os, pickle, json
from pathlib import Path
HERE = Path(r"C:/Users/zachc/Documents/Unreal Projects/reflections/Tools/ClothingFit/garmentprep")
ST = Path(r"C:/Users/zachc/Documents/Unreal Projects/reflections/Saved/ClothingFit/DirectImage3D/MarketJerkin/MeshRetargetPilot/ContactStudy/tools")
sys.path.insert(0, str(ST)); sys.path.insert(0, str(HERE)); os.chdir(ST)
import numpy as np
from check import *
import prep, meshops
np.set_printoptions(linewidth=200, suppress=True)
OUT = Path(sys.argv[1])
fr = load(PILOT / "AfterPreserved", "standing"); c0, cf = fr["cloth"], fr["cf"]
c1, _ = meshops.read_surface(OUT / "standing_jerkin.bin")
info = np.load(OUT / "info.npz")
body, obst = pickle.load(open(HERE / "_field_barnaby.pkl", "rb"))
fr2 = dict(fr); fr2["cloth"] = c1; m = measure(fr2)
gt = m["garment_tris"]
P0, Fw, inv = meshops.weld(c0, cf)
planned = info["planned"][inv]
print("crossing tris", len(gt))
v = np.unique(cf[gt])
print("verts in crossing tris", len(v), "planned among them", int(planned[v].sum()))
rows = np.column_stack((c0[v], c1[v], obst(c0[v]), obst(c1[v]), planned[v]))
o = np.argsort(rows[:, 0])
print("   x0     y0     z0  |   x1     y1     z1  | phi0  phi1 planned")
for r in rows[o][::max(1, len(o) // 70)]:
    print(np.round(r, 1))
# where did unplanned buried vertices of the yoke region go: front or back
front = (c1[:, 1] > 2) & (c0[:, 2] > 146) & (np.abs(c0[:, 0]) < 9) & (c0[:, 1] < 4)
print("upper-centre verts ending in front (y>2):", int(front.sum()), "of which planned", int((front & planned).sum()))
e = np.sort(cf[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2), axis=1); e = np.unique(e, axis=0)
l0 = np.linalg.norm(c0[e[:, 0]] - c0[e[:, 1]], axis=1); l1 = np.linalg.norm(c1[e[:, 0]] - c1[e[:, 1]], axis=1)
big = np.flatnonzero((l1 > 3 * l0) & (l0 > .05))
print("edges stretched >3x:", len(big))
for i in big[:25]:
    a, b = e[i]
    print(np.round(c0[a], 1), "->", np.round(c1[a], 1), "|", np.round(c0[b], 1), "->", np.round(c1[b], 1), "pl", planned[a], planned[b], round(l0[i], 2), round(l1[i], 2))
