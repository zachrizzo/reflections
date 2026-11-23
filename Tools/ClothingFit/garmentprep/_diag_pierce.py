import sys, json, pickle
from pathlib import Path
import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import prep, contact
import prepare_generated_garment as pg
garment, capture = Path(sys.argv[1]), Path(sys.argv[2])
d = np.load(garment); P, F = d["P"], d["F"]
joints = pg.load_joints(capture)
bones = prep.bone_segments(joints, pg.PARENTS)
spine = prep.bone_segments({k: joints[k] for k in pg.TRUNK + ("neck_02", "head") if k in joints}, pg.PARENTS)
print("spine segments"); print(np.round(spine, 1))
under = sys.argv[3:] or ["bottom"]
skin, sf, layers, full = pg.body_fields(capture, under, P.min(0) - 8, P.max(0) + np.array([8., 8., 14.]))
g = prep.Garment(P, F)
phi = full(g.P0)
T = g.P0[g.F]
for i, (a, b) in enumerate(spine):
    lo, hi = np.minimum(a, b) - .01, np.maximum(a, b) + .01
    near = np.flatnonzero(np.all((T.max(1) >= lo) & (T.min(1) <= hi), axis=1))
    if not len(near): continue
    p = np.tile(a, (len(near), 1)); q = np.tile(b, (len(near), 1))
    hit = near[contact._seg_tri(p, q, T[near, 0], T[near, 1], T[near, 2])]
    for t in hit:
        cen = T[t].mean(0)
        print("segment", i, "pierces triangle", t, "centre", cen.round(1), "phi at verts", phi[g.F[t]].round(2))
edges = g.links
inside = phi < 0
keep = inside[edges[:, 0]] & inside[edges[:, 1]]
graph = sp.coo_matrix((np.ones(keep.sum()), (edges[keep, 0], edges[keep, 1])), shape=(g.n, g.n))
_, comp = connected_components(graph, directed=False)
deep = phi < -1
for label in np.unique(comp[deep]):
    m = np.flatnonzero(inside & (comp == label))
    if deep[m].sum() < 3: continue
    q = g.P0[m]
    print("component", label, "verts", len(m), "deep", int(deep[m].sum()), "bbox", q.min(0).round(1), q.max(0).round(1), "centre", q.mean(0).round(1))
