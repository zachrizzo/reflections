import sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contact, meshops, prep
from contact import candidate_pairs, tri_tri
d = np.load(sys.argv[1])
P0, P1, F = d["P0"], d["P"], d["F"]
g = prep.Garment(P0, F)
W1 = np.zeros_like(g.P0); W1[g.inv] = P1
has = g.partner >= 0
print("welded vertices", g.n, "with a partner on the other wall", round(float(has.mean()) * 100, 1), "%", "thickness median", round(g.thickness, 2))
gaps = np.linalg.norm(g.P0[has] - g.P0[g.partner[has]], axis=1)
print("wall gap cm p5 p50 p95", np.percentile(gaps, [5, 50, 95]).round(2))
Fv = g.F
ia, ib = candidate_pairs(W1, Fv, W1, Fv)
keep = ia < ib; ia, ib = ia[keep], ib[keep]
share = (Fv[ia][:, :, None] == Fv[ib][:, None, :]).any((1, 2)); ia, ib = ia[~share], ib[~share]
hit = tri_tri(W1[Fv[ia]], W1[Fv[ib]]); ia, ib = ia[hit], ib[hit]
print("pairs", len(ia))
tn = np.cross(g.P0[Fv[:, 1]] - g.P0[Fv[:, 0]], g.P0[Fv[:, 2]] - g.P0[Fv[:, 0]]); tn /= np.maximum(np.linalg.norm(tn, axis=1), 1e-12)[:, None]
facing = np.einsum("ij,ij->i", tn[ia], tn[ib])
print("pairs on opposite walls (rest normals opposed)", int((facing < -.3).sum()), "same-facing", int((facing > .3).sum()), "other", int((np.abs(facing) <= .3).sum()))
vs = np.unique(np.r_[Fv[ia].ravel(), Fv[ib].ravel()])
print("vertices at crossings", len(vs), "with partner", round(float(has[vs].mean()) * 100, 1), "%")
# displacement along rest normal for the two triangles
u = W1 - g.P0
print("gap between partners after, cm p1 p5 p50", np.percentile(np.linalg.norm(W1[has] - W1[g.partner[has]], axis=1), [1, 5, 50]).round(2))
# order check: outer partner should stay outside inner
