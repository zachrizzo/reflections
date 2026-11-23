"""MetaHuman body UV0 layout, matched to the triangles of the body capture files (standing_body.bin etc.).

  python body_uv.py check <dump folder> [capture standing_body.bin ...]

The layout is read once in the editor by editor/dump_body_uvs.py (GeometryScript copy of the body mesh, LOD0 render
data) and stored in Saved/ClothingFit/BodyUV/<Character>/body_uv_render_data.bin:
uint32 vertex count, uint32 triangle count, float32 xyz per vertex, uint32 triangles, float32 (u, v) x 3 per triangle.
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from meshops import read_surface

DEFAULT = ROOT / "Saved/ClothingFit/BodyUV/Holdout/body_uv_render_data.bin"


def read_dump(path=DEFAULT):
    with open(path, "rb") as stream:
        nv, nt = np.fromfile(stream, "<u4", 2)
        xyz = np.fromfile(stream, "<f4", int(nv) * 3).reshape(-1, 3).astype(np.float64)
        tri = np.fromfile(stream, "<u4", int(nt) * 3).reshape(-1, 3).astype(np.int64)
        uv = np.fromfile(stream, "<f4", int(nt) * 6).reshape(-1, 3, 2).astype(np.float64)
    return xyz, tri, uv


def corner_uvs(faces, path=DEFAULT):
    """UV of each corner of each capture triangle (T x 3 x 2). Asserts the capture uses the dumped triangle order."""
    _, tri, uv = read_dump(path)
    assert faces.shape == tri.shape and (faces == tri).all(), "body capture triangles do not match the UV dump (other mesh build?)"
    return uv


def main():
    folder = Path(sys.argv[2])
    xyz, tri, uv = read_dump(folder / "body_uv_render_data.bin")
    print("uv range", uv.reshape(-1, 2).min(0).round(4), uv.reshape(-1, 2).max(0).round(4), "unset", int((uv < -.5).all(2).any(1).sum()))
    per_vertex = {}
    bad = 0
    for t in range(len(tri)):
        for k in range(3):
            key = tri[t, k]
            if key in per_vertex and np.abs(per_vertex[key] - uv[t, k]).max() > 1e-6:
                bad += 1
            per_vertex.setdefault(key, uv[t, k])
    print("render vertices whose UV differs between triangles:", bad)
    crossing = (np.ptp(np.floor(uv[:, :, 0]), 1) > 0) | (np.ptp(np.floor(uv[:, :, 1]), 1) > 0)
    print("triangles crossing an integer UV line:", int(crossing.sum()))
    for capture in [folder / "standing_body.bin"] + [Path(p) for p in sys.argv[3:]]:
        P, F = read_surface(capture)
        same = F.shape == tri.shape and bool((F == tri).all())
        print(capture, "triangles identical:", same, "vertices", len(P), "vs", len(xyz))


if __name__ == "__main__":
    main()
