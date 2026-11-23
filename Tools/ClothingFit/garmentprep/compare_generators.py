"""Compare garment meshes made by different image-to-3D generators from the same reference image.

  python compare_generators.py <out folder> <label>=<textured.obj>[::<colour.png>] ...

Per mesh (each scaled to unit height first, so numbers compare across generators):
  triangles, vertices, pieces (connected parts after welding equal positions) and the largest piece's share,
  open edge length (hems, cuffs, neck, and every gap between loose panels), non-manifold edges,
  double-wall share (surface that has a second, opposite-facing wall within 1.5 % of the height),
  texture size, share of the texture atlas that the UVs use, and texels per unit of surface.
Writes <out>/GeneratorCompare.json and .md; the pictures come from render_compare.py (Blender).
"""
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree


def load(obj):
    mesh = trimesh.load(obj, force="mesh", process=False)
    return mesh


def weld(V, F, tol):
    key = np.round(V / tol).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    return V[first], inv.reshape(-1)[F]


def edges_stats(F):
    e = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1)
    uniq, counts = np.unique(e, axis=0, return_counts=True)
    return uniq, counts


def pieces(F, nv):
    e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]]])
    g = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(nv, nv))
    n, label = connected_components(g, directed=False)
    face_label = label[F[:, 0]]
    sizes = np.bincount(face_label, minlength=n)
    sizes = sizes[sizes > 0]
    return len(sizes), float(sizes.max() / len(F))


def double_wall_share(mesh, height, n=30000, reach=.015):
    pts, fi = trimesh.sample.sample_surface_even(mesh, n, seed=1) if len(mesh.faces) else (np.zeros((0, 3)), [])
    nrm = mesh.face_normals[fi]
    tree = cKDTree(pts)
    hits = 0
    for i, nb in enumerate(tree.query_ball_point(pts, reach * height)):
        nb = [j for j in nb if j != i]
        if not nb:
            continue
        d = pts[nb] - pts[i]
        along = np.abs(d @ nrm[i])
        side = np.linalg.norm(d - np.outer(d @ nrm[i], nrm[i]), axis=1)
        opposite = (nrm[nb] @ nrm[i] < -.6) & (along > .002 * height) & (side < along * 1.5)
        hits += bool(opposite.any())
    return hits / max(len(pts), 1)


def atlas_use(uv, F, size=1024):
    img = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(img)
    t = (uv[F] % 1.0) * (size - 1)
    for tri in t:
        draw.polygon([(float(x), float((size - 1) - y)) for x, y in tri], fill=255)
    return float((np.asarray(img) > 0).mean())


def stats(label, obj, texture=None):
    mesh = load(obj)
    V = np.asarray(mesh.vertices, float); F = np.asarray(mesh.faces, np.int64)
    height = float(np.ptp(V[:, 1])) or 1.0
    Vw, Fw = weld(V, F, 1e-5 * height)
    uniq, counts = edges_stats(Fw)
    open_edges = uniq[counts == 1]
    open_len = float(np.linalg.norm(Vw[open_edges[:, 0]] - Vw[open_edges[:, 1]], axis=1).sum() / height)
    n_pieces, largest = pieces(Fw, len(Vw))
    scaled = trimesh.Trimesh(Vw / height, Fw, process=False)
    out = dict(label=label, obj=str(obj), triangles=int(len(F)), vertices=int(len(V)), pieces=n_pieces, largest_piece_share=round(largest, 3),
               open_edge_length_in_heights=round(open_len, 1), non_manifold_edges=int((counts > 2).sum()),
               double_wall_share=round(double_wall_share(scaled, 1.0), 3), surface_area_in_heights2=round(float(scaled.area), 3))
    uv = getattr(mesh.visual, "uv", None)
    tex = Path(texture) if texture else None
    if tex is None:
        mtl = Path(obj).with_suffix(".mtl")
        if mtl.exists():
            for line in mtl.read_text().splitlines():
                if line.strip().startswith("map_Kd"):
                    tex = Path(obj).parent / line.split(None, 1)[1].strip()
    if uv is not None and tex is not None and tex.exists():
        w, h = Image.open(tex).size
        use = atlas_use(np.asarray(uv), F)
        out.update(texture=str(tex), texture_size=f"{w}x{h}", atlas_used_share=round(use, 3),
                   texels_per_surface=int(use * w * h / max(scaled.area, 1e-9)))
    return out


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    rows = []
    for arg in sys.argv[2:]:
        label, rest = arg.split("=", 1)
        obj, _, tex = rest.partition("::")
        rows.append(stats(label, Path(obj), tex or None))
        print(json.dumps(rows[-1]), flush=True)
    (out / "GeneratorCompare.json").write_text(json.dumps(rows, indent=1))
    keys = ["triangles", "pieces", "largest_piece_share", "open_edge_length_in_heights", "non_manifold_edges", "double_wall_share", "texture_size", "atlas_used_share", "texels_per_surface"]
    lines = ["| | " + " | ".join(r["label"] for r in rows) + " |", "|---|" + "---|" * len(rows)]
    for k in keys:
        lines.append(f"| {k} | " + " | ".join(str(r.get(k, "")) for r in rows) + " |")
    (out / "GeneratorCompare.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
