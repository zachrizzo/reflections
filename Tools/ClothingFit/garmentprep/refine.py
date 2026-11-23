"""Split long triangle edges without changing the surface or its texture mapping.

Each triangle keeps its own corner UVs, so UV seams stay seams: a new midpoint corner gets
the average of the two corner UVs of the triangle it belongs to. Positions of original
vertices are untouched; new vertices lie exactly on the old edges.
"""
import numpy as np


def split_long_edges(P, F, UV, limit, rounds=10):
    """P (n,3) welded positions, F (m,3), UV (m,3,2) per corner, limit (n,) max edge length at each vertex.

    Returns P, F, UV, limit, parent (index of the original triangle for every output triangle).
    """
    P, F, UV, limit = P.copy(), F.copy(), UV.copy(), np.asarray(limit, float).copy()
    parent = np.arange(len(F))
    for _ in range(rounds):
        a, b = F, F[:, [1, 2, 0]]                        # edge k runs from corner k to corner k+1
        length = np.linalg.norm(P[a] - P[b], axis=2)
        cap = np.minimum(limit[a], limit[b])
        marked = length > cap
        if not marked.any():
            break
        lo, hi = np.minimum(a, b), np.maximum(a, b)
        key = lo.astype(np.int64) * (len(P) + 1) + hi
        uniq, inverse = np.unique(key[marked], return_inverse=True)
        mid_index = np.full(F.shape, -1, dtype=np.int64)
        mid_index[marked] = len(P) + inverse
        # an edge marked from one triangle must be split in its neighbour too
        lookup = dict(zip(uniq.tolist(), (len(P) + np.arange(len(uniq))).tolist()))
        other = ~marked & np.isin(key, uniq)
        if other.any():
            mid_index[other] = [lookup[k] for k in key[other].tolist()]
            marked = mid_index >= 0
        first = np.zeros(len(uniq), dtype=np.int64)
        flat_rows = np.flatnonzero(marked.ravel())
        first[mid_index.ravel()[flat_rows] - len(P)] = flat_rows
        ea, eb = a.ravel()[first], b.ravel()[first]
        P = np.vstack((P, .5 * (P[ea] + P[eb])))
        limit = np.r_[limit, np.minimum(limit[ea], limit[eb])]
        mid_uv = .5 * (UV + UV[:, [1, 2, 0]])               # per triangle, per edge
        count = marked.sum(1)
        newF, newUV, newParent = [F[count == 0]], [UV[count == 0]], [parent[count == 0]]

        def emit(rows, corners):
            """corners: list of 3 selectors, each ('v', k) original corner k or ('m', k) midpoint of edge k."""
            tri = np.empty((len(rows), 3), dtype=np.int64)
            uv = np.empty((len(rows), 3, 2))
            for slot, (kind, k) in enumerate(corners):
                if kind == "v":
                    tri[:, slot] = F[rows, k]
                    uv[:, slot] = UV[rows, k]
                else:
                    tri[:, slot] = mid_index[rows, k]
                    uv[:, slot] = mid_uv[rows, k]
            newF.append(tri); newUV.append(uv); newParent.append(parent[rows])

        for rot in range(3):                                # rotate so the pattern is described once
            r = [(rot + i) % 3 for i in range(3)]
            one = np.flatnonzero((count == 1) & marked[:, r[0]])
            emit(one, [("v", r[0]), ("m", r[0]), ("v", r[2])])
            emit(one, [("m", r[0]), ("v", r[1]), ("v", r[2])])
            two = np.flatnonzero((count == 2) & ~marked[:, r[2]])   # edges r0 and r1 marked
            emit(two, [("v", r[0]), ("m", r[0]), ("v", r[2])])
            emit(two, [("m", r[0]), ("m", r[1]), ("v", r[2])])
            emit(two, [("m", r[0]), ("v", r[1]), ("m", r[1])])
        three = np.flatnonzero(count == 3)
        emit(three, [("v", 0), ("m", 0), ("m", 2)])
        emit(three, [("m", 0), ("v", 1), ("m", 1)])
        emit(three, [("m", 2), ("m", 1), ("v", 2)])
        emit(three, [("m", 0), ("m", 1), ("m", 2)])
        F, UV, parent = np.vstack(newF), np.vstack(newUV), np.concatenate(newParent)
    return P, F, UV, limit, parent


def mapping_check(P0, F0, UV0, P1, F1, UV1, parent):
    """Largest error of the refined mesh against the original surface and texture mapping."""
    A, B, C = P0[F0[parent]].transpose(1, 0, 2)
    ua, ub, uc = UV0[parent].transpose(1, 0, 2)
    worst_pos = worst_uv = 0.
    for corner in range(3):
        p = P1[F1[:, corner]]
        v0, v1, v2 = B - A, C - A, p - A
        d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
        d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
        den = np.where(np.abs(d00 * d11 - d01 * d01) < 1e-18, 1e-18, d00 * d11 - d01 * d01)
        v = (d11 * d20 - d01 * d21) / den
        w = (d00 * d21 - d01 * d20) / den
        on_surface = A + v[:, None] * v0 + w[:, None] * v1
        ok = d00 * d11 - d01 * d01 > 1e-12
        worst_pos = max(worst_pos, float(np.linalg.norm(on_surface - p, axis=1)[ok].max()))
        uv = ua + v[:, None] * (ub - ua) + w[:, None] * (uc - ua)
        worst_uv = max(worst_uv, float(np.abs(uv - UV1[:, corner])[ok].max()))
    return dict(max_position_error_cm=worst_pos, max_uv_error=worst_uv,
                triangles_before=int(len(F0)), triangles_after=int(len(F1)))
