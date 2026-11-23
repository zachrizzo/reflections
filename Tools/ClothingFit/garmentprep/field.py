"""Signed distance grid of a body (skin) mesh, for garment fit preparation.

Everything is in actor-local centimetres: x lateral, +y front, z up.
The sign comes from crossing parity along the three grid axes (majority vote),
so small open seams (body/face join, mouth) do not flip large regions.
"""
import numpy as np
from scipy.spatial import cKDTree
from scipy import ndimage


def surface_samples(P, F, spacing):
    a, b, c = P[F].transpose(1, 0, 2)
    area = .5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    k = np.clip(np.ceil(area / (spacing * spacing)).astype(int), 1, 4000)
    idx = np.repeat(np.arange(len(F)), k)
    r = np.random.default_rng(7).random((len(idx), 2))
    s = np.sqrt(r[:, 0])
    u, v, w = 1 - s, s * (1 - r[:, 1]), s * r[:, 1]
    pts = a[idx] * u[:, None] + b[idx] * v[:, None] + c[idx] * w[:, None]
    return np.vstack((pts, P[np.unique(F)]))


def _column_crossings(P, F, origin, cell, shape, axis):
    """Count, for every grid node, the surface crossings below it along `axis`. Returns parity (bool grid)."""
    o = [a for a in range(3) if a != axis]
    T = P[F]
    A, B, C = T[:, 0], T[:, 1], T[:, 2]
    lo = np.floor((T[:, :, o].min(1) - origin[o]) / cell).astype(int)
    hi = np.floor((T[:, :, o].max(1) - origin[o]) / cell).astype(int)
    n_u, n_v, n_w = shape[o[0]], shape[o[1]], shape[axis]
    counts = np.zeros((n_u, n_v, n_w + 1), np.int32)
    span = hi - lo
    for du in range(int(span[:, 0].max()) + 1):
        for dv in range(int(span[:, 1].max()) + 1):
            sel = np.flatnonzero((span[:, 0] >= du) & (span[:, 1] >= dv))
            if not len(sel):
                continue
            iu, iv = lo[sel, 0] + du, lo[sel, 1] + dv
            ok = (iu >= 0) & (iu < n_u) & (iv >= 0) & (iv < n_v)
            sel, iu, iv = sel[ok], iu[ok], iv[ok]
            # tiny irrational offset keeps columns off vertices and edges
            pu = origin[o[0]] + iu * cell + 1.37e-4
            pv = origin[o[1]] + iv * cell + 2.11e-4
            a, b, c = A[sel], B[sel], C[sel]
            d = (b[:, o[1]] - c[:, o[1]]) * (a[:, o[0]] - c[:, o[0]]) + (c[:, o[0]] - b[:, o[0]]) * (a[:, o[1]] - c[:, o[1]])
            good = np.abs(d) > 1e-12
            d = np.where(good, d, 1)
            l1 = ((b[:, o[1]] - c[:, o[1]]) * (pu - c[:, o[0]]) + (c[:, o[0]] - b[:, o[0]]) * (pv - c[:, o[1]])) / d
            l2 = ((c[:, o[1]] - a[:, o[1]]) * (pu - c[:, o[0]]) + (a[:, o[0]] - c[:, o[0]]) * (pv - c[:, o[1]])) / d
            l3 = 1 - l1 - l2
            inside = good & (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
            h = l1 * a[:, axis] + l2 * b[:, axis] + l3 * c[:, axis]
            k = np.ceil((h - origin[axis]) / cell).astype(int)  # first node above the crossing
            k = np.clip(k, 0, n_w)
            np.add.at(counts, (iu[inside], iv[inside], k[inside]), 1)
    par = (np.cumsum(counts, axis=2)[:, :, :n_w] % 2).astype(bool)
    # back to x,y,z order
    return np.moveaxis(par, [0, 1, 2], [o[0], o[1], axis])


class SignedField:
    def __init__(self, P, F, lo, hi, cell=.4, sample=.14):
        self.cell = cell
        self.origin = np.asarray(lo, float)
        self.shape = np.ceil((np.asarray(hi, float) - self.origin) / cell).astype(int) + 1
        box_lo, box_hi = self.origin - 30, np.asarray(hi, float) + 30
        near = F[np.all((P[F] >= box_lo) & (P[F] <= box_hi), axis=(1, 2))]
        self.P, self.F = P, near
        pts = surface_samples(P, near, sample)
        self.tree = cKDTree(pts)
        g = np.stack(np.meshgrid(*[self.origin[a] + np.arange(self.shape[a]) * cell for a in range(3)], indexing="ij"), -1)
        d, _ = self.tree.query(g.reshape(-1, 3), workers=-1)
        d = d.reshape(self.shape)
        votes = sum(_column_crossings(P, F, self.origin, cell, self.shape, ax).astype(np.int8) for ax in range(3))
        inside = votes >= 2
        # remove isolated sign noise
        inside = ndimage.binary_opening(inside, iterations=1) | (inside & (d > cell))
        self.inside = inside
        self.grid = np.where(inside, -d, d)

    def __call__(self, pts):
        return ndimage.map_coordinates(self.grid, ((np.asarray(pts) - self.origin) / self.cell).T, order=1, mode="nearest")

    def gradient(self, pts, h=.25):
        g = np.empty((len(pts), 3))
        for a in range(3):
            e = np.zeros(3); e[a] = h
            g[:, a] = (self(pts + e) - self(pts - e)) / (2 * h)
        n = np.linalg.norm(g, axis=1)
        return g / np.maximum(n, 1e-9)[:, None]

    def exit_distance(self, pts, direction, clearance=0., reach=45., step=.2):
        """Distance along `direction` to the first point with field >= clearance (inf when none within reach)."""
        d = np.broadcast_to(np.asarray(direction, float), pts.shape)
        need = np.broadcast_to(np.asarray(clearance, float), (len(pts),))
        out = np.full(len(pts), np.inf)
        prev = self(pts)
        out[prev >= need] = 0.
        live = np.flatnonzero(prev < need)
        t = 0.
        while len(live) and t < reach:
            t += step
            val = self(pts[live] + t * d[live])
            hit = val >= need[live]
            if hit.any():
                p0 = prev[live][hit]
                frac = (need[live][hit] - p0) / np.maximum(val[hit] - p0, 1e-9)
                out[live[hit]] = t - step + step * np.clip(frac, 0, 1)
            prev[live] = val
            live = live[~hit]
        return out
