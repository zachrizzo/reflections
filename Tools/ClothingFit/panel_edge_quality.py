"""Measure bends across adjacent render triangles, including UV and material seams."""
import numpy as np


def edge_pairs(points, triangles):
    # Position-weld only for adjacency in the neutral pose. Keep the original
    # face indices when evaluating later poses so coincident UV splits stay paired.
    _, ids = np.unique(np.round(points, 4), axis=0, return_inverse=True)
    t = ids.ravel()[triangles]
    edges = np.sort(np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]]), axis=1)
    face = np.tile(np.arange(len(t)), 3)
    order = np.lexsort((edges[:, 1], edges[:, 0]))
    sorted_edges = edges[order]
    boundary = np.r_[0, 1 + np.flatnonzero(np.any(np.diff(sorted_edges, axis=0), axis=1)), len(edges)]
    starts = boundary[:-1][np.diff(boundary) == 2]
    return np.stack((face[order[starts]], face[order[starts + 1]]), axis=1)


def crease_metrics(points, triangles, pairs):
    a, b, c = points[triangles].transpose(1, 0, 2)
    normals = np.cross(b - a, c - a)
    length = np.linalg.norm(normals, axis=1)
    valid = pairs[np.all(length[pairs] > 1e-8, axis=1)]
    normals /= np.maximum(length[:, None], 1e-12)
    cosine = np.einsum('ij,ij->i', normals[valid[:, 0]], normals[valid[:, 1]])
    degrees = np.rad2deg(np.arccos(np.clip(cosine, -1, 1)))
    return {'triangles': len(triangles), 'adjacent_edges': len(degrees),
            'over_45_deg': int(np.count_nonzero(degrees > 45)),
            'over_90_deg': int(np.count_nonzero(degrees > 90)),
            'p95_deg': round(float(np.percentile(degrees, 95)), 2)}
