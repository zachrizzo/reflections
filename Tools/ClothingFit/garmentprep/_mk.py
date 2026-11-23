import sys, re
st = sys.argv[1]
fit = open(st + "/fitlib.py", encoding="utf-8").read()
# keep the geometric kernels only
start = fit.index("def tri_aabb")
body = fit[start:]
head = '''"""Exact triangle-level contact tests between a garment and the surfaces it must clear.

Ported from the contact study tools (same numbers as Tools/ClothingFit/audit_wardrobe_layers.py).
"""
import numpy as np
from scipy.spatial import cKDTree


'''
tail = '''

def crossing_triangles(skin, skin_faces, cloth, cloth_faces, pad=2.):
    """Indices of garment triangles that cross the skin, and of the skin triangles they cross."""
    lo, hi = cloth.min(0) - pad, cloth.max(0) + pad
    near = np.all((skin >= lo) & (skin <= hi), axis=1)
    sub = skin_faces[near[skin_faces].any(1)]
    i_skin, i_cloth = intersections(skin, sub, cloth, cloth_faces)
    return np.unique(i_cloth), sub[np.unique(i_skin)]


def self_crossing_pairs(P, F):
    """Number of non-adjacent triangle pairs of one mesh that cross each other."""
    F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]
    ia, ib = candidate_pairs(P, F, P, F)
    keep = ia < ib
    ia, ib = ia[keep], ib[keep]
    share = (F[ia][:, :, None] == F[ib][:, None, :]).any((1, 2))
    ia, ib = ia[~share], ib[~share]
    return int(tri_tri(P[F[ia]], P[F[ib]]).sum())
'''
open("contact.py", "w", encoding="utf-8").write(head + body.rstrip() + "\n" + tail)
print("contact.py written", len((head + body + tail).splitlines()))
