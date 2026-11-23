import sys, os, pickle, json
from pathlib import Path
HERE = Path(r"C:/Users/zachc/Documents/Unreal Projects/reflections/Tools/ClothingFit/garmentprep")
ST = Path(r"C:/Users/zachc/Documents/Unreal Projects/reflections/Saved/ClothingFit/DirectImage3D/MarketJerkin/MeshRetargetPilot/ContactStudy/tools")
sys.path.insert(0, str(ST)); sys.path.insert(0, str(HERE)); os.chdir(ST)
import numpy as np
from check import *
import prep, meshops
np.set_printoptions(linewidth=220, suppress=True)
OUT = Path(sys.argv[1])
fr = load(PILOT / "AfterPreserved", "standing"); c0, cf = fr["cloth"], fr["cf"]
c1, _ = meshops.read_surface(OUT / "standing_jerkin.bin")
body, obst = pickle.load(open(HERE / "_field_barnaby.pkl", "rb"))
fr2 = dict(fr); fr2["cloth"] = c1; m = measure(fr2)
gt = m["garment_tris"]
T0 = c0[cf[gt]]; T1 = c1[cf[gt]]
def longest(T): return np.max([np.linalg.norm(T[:, i] - T[:, (i + 1) % 3], axis=1) for i in range(3)], axis=0)
print("crossing tris", len(gt), "longest edge before pct", np.percentile(longest(T0), [0, 50, 100]).round(2), "after", np.percentile(longest(T1), [0, 50, 100]).round(2))
cen = T1.mean(1); print("centroid phi pct", np.percentile(obst(cen), [0, 50, 100]).round(2))
o = np.argsort(-longest(T1))
for i in o[:14]:
    print("tri", gt[i], "before", T0[i].round(1).tolist(), "\n      after", T1[i].round(1).tolist(), "phi verts", obst(T1[i]).round(2), "cen", round(float(obst(cen[i:i+1])[0]), 2))
# all triangles: size distribution in yoke region
allL0 = longest(c0[cf]); print("all tris longest edge pct 50/95/99/100", np.percentile(allL0, [50, 95, 99, 100]).round(2))
big = np.flatnonzero(allL0 > 3); print("tris with edge > 3 cm:", len(big), "centroids z>140:", int((c0[cf[big]].mean(1)[:, 2] > 140).sum()))
