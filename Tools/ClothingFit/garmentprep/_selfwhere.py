import sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contact, meshops
from contact import candidate_pairs, tri_tri
d = np.load(sys.argv[1])
P0, P1, F = d["P0"], d["P"], d["F"]
W0, Fw, inv = meshops.weld(P0, F)
W1 = np.zeros_like(W0); W1[inv] = P1
def pairs(P, F):
    F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]
    ia, ib = candidate_pairs(P, F, P, F)
    keep = ia < ib
    ia, ib = ia[keep], ib[keep]
    share = (F[ia][:, :, None] == F[ib][:, None, :]).any((1, 2))
    ia, ib = ia[~share], ib[~share]
    hit = tri_tri(P[F[ia]], P[F[ib]])
    return F, ia[hit], ib[hit]
for name, W in (("before", W0), ("after", W1)):
    Fv, ia, ib = pairs(W, Fw)
    print(name, "pairs", len(ia))
    if not len(ia): continue
    c = W[Fv[ia]].mean(1)
    # cluster coarsely on a 6 cm grid
    key = np.round(c / 6).astype(int)
    u, cnt = np.unique(key, axis=0, return_counts=True)
    o = np.argsort(-cnt)[:14]
    for k, n in zip(u[o], cnt[o]):
        print("   around", (k * 6).tolist(), "pairs", int(n))
    disp = np.linalg.norm(W1 - W0, axis=1)
    print("   displacement at crossing triangles cm p50/p95", np.percentile(disp[Fv[ia]].mean(1), [50, 95]).round(2))
    area = contact.tri_area(W, Fv)
    print("   triangle area at crossings p50", np.percentile(area[ia], 50).round(3), "overall p50", np.percentile(area, 50).round(3))
Fv, ia, ib = pairs(W1, Fw)
rest = np.linalg.norm(W0[Fv[ia]].mean(1) - W0[Fv[ib]].mean(1), axis=1)
print("rest distance between the two triangles of a crossing pair, cm: p5 p50 p95 max", np.percentile(rest, [5, 50, 95, 100]).round(2))
da = (W1 - W0)[Fv[ia]].mean(1); db = (W1 - W0)[Fv[ib]].mean(1)
print("difference of their displacement cm p50 p95", np.percentile(np.linalg.norm(da - db, axis=1), [50, 95]).round(2))
