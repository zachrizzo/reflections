"""Mesh helpers for garment fit preparation (numpy/scipy only)."""
import numpy as np
import scipy.sparse as sp
from scipy.spatial import cKDTree


def read_surface(path):
    """Unreal capture: uint32 vertex count, uint32 index count, float32 xyz, uint32 triangles (actor-local cm)."""
    with open(path, "rb") as stream:
        nv, ni = np.fromfile(stream, dtype="<u4", count=2)
        xyz = np.fromfile(stream, dtype="<f4", count=int(nv) * 3).reshape(-1, 3).astype(np.float64)
        tri = np.fromfile(stream, dtype="<u4", count=int(ni)).reshape(-1, 3).astype(np.int64)
    return xyz, tri


def write_surface(path, xyz, tri):
    with open(path, "wb") as stream:
        np.array([len(xyz), tri.size], dtype="<u4").tofile(stream)
        xyz.astype("<f4").tofile(stream)
        tri.astype("<u4").tofile(stream)


def weld(P, F, decimals=4):
    """Merge position duplicates (UV seams). Returns welded points, welded faces, map full->welded."""
    Pu, inv = np.unique(P.round(decimals), axis=0, return_inverse=True)
    inv = inv.ravel()
    return Pu, inv[F], inv


def edges_of(F):
    e = np.sort(F[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2), axis=1)
    e = e[e[:, 0] != e[:, 1]]
    return np.unique(e, axis=0)


def vertex_normals(P, F):
    a, b, c = P[F].transpose(1, 0, 2)
    fn = np.cross(b - a, c - a)
    n = np.zeros_like(P)
    for i in range(3):
        np.add.at(n, F[:, i], fn)
    return n / np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]


def tri_area(P, F):
    a, b, c = P[F].transpose(1, 0, 2)
    return .5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)


def shell_partners(P, N, reach=2.6, lateral=.7):
    """For a thin double-walled shell: index of the vertex on the opposite wall (or -1)."""
    tree = cKDTree(P)
    dist, idx = tree.query(P, k=48, distance_upper_bound=reach)
    ok = np.isfinite(dist)
    idx = np.where(ok, idx, 0)
    d = P[idx] - P[:, None, :]
    along = -np.einsum("nkj,nj->nk", d, N)            # distance into the cloth
    perp = np.linalg.norm(d + along[:, :, None] * N[:, None, :], axis=2)
    facing = np.einsum("nkj,nj->nk", N[idx], N)
    good = ok & (along > .12) & (facing < -.25) & (perp < lateral + .25 * along)
    score = np.where(good, perp + .25 * along, np.inf)
    best = score.argmin(1)
    rows = np.arange(len(P))
    partner = idx[rows, best]
    partner[~np.isfinite(score[rows, best])] = -1
    return partner


def graph_laplacian(n, edges, weights):
    i, j = edges[:, 0], edges[:, 1]
    W = sp.coo_matrix((np.r_[weights, weights], (np.r_[i, j], np.r_[j, i])), shape=(n, n)).tocsr()
    return (sp.diags(np.asarray(W.sum(1)).ravel()) - W).tocsr()


def geodesic_from(n, edges, lengths, sources, limit=np.inf):
    from scipy.sparse.csgraph import dijkstra
    G = sp.coo_matrix((np.r_[lengths, lengths], (np.r_[edges[:, 0], edges[:, 1]], np.r_[edges[:, 1], edges[:, 0]])),
                      shape=(n, n)).tocsr()
    return dijkstra(G, directed=False, indices=np.asarray(sources), min_only=True, limit=limit)


def smoothstep(x, lo, hi):
    t = np.clip((np.asarray(x, float) - lo) / (hi - lo), 0, 1)
    return t * t * (3 - 2 * t)
