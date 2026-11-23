"""Is the surface rougher after preparation? Relief = distance of each vertex from the locally smoothed surface."""
import sys, os
from pathlib import Path
HERE = Path(r"C:/Users/zachc/Documents/Unreal Projects/reflections/Tools/ClothingFit/garmentprep")
sys.path.insert(0, str(HERE))
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as spla
import prep, meshops
d = np.load(sys.argv[1]); P0, F, P1 = d["P0"], d["F"], d["P"]
g = prep.Garment(P0, F)
solve = spla.factorized((sp.identity(g.n) + 6. * g.L_mesh).tocsc())
x1 = np.zeros_like(g.P0); x1[g.inv] = P1
def relief(x):
    base = np.column_stack([solve(x[:, a]) for a in range(3)])
    n = g.normals(x)
    return np.einsum("ij,ij->i", x - base, n)
h0, h1 = relief(g.P0), relief(x1)
zones = {"front lower (y>8, z<125)": (g.P0[:, 1] > 8) & (g.P0[:, 2] < 125), "front upper (y>5, z>=125)": (g.P0[:, 1] > 5) & (g.P0[:, 2] >= 125),
         "back (y<-5)": g.P0[:, 1] < -5, "sides (|x|>17, z<125)": (np.abs(g.P0[:, 0]) > 17) & (g.P0[:, 2] < 125)}
for name, m in zones.items():
    print(f"{name:28s} relief rms before {np.sqrt((h0[m] ** 2).mean()):.3f} cm  after {np.sqrt((h1[m] ** 2).mean()):.3f} cm  | p95 abs before {np.percentile(np.abs(h0[m]), 95):.3f} after {np.percentile(np.abs(h1[m]), 95):.3f}")
