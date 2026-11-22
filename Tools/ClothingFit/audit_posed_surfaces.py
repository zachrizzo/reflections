"""Audit Unreal's sampled LOD 0 skinned surfaces. Run in Blender background mode."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def surface(path):
    with path.open("rb") as stream:
        nv, ni = np.fromfile(stream, dtype="<u4", count=2)
        xyz = np.fromfile(stream, dtype="<f4", count=int(nv) * 3).reshape(-1, 3)
        tri = np.fromfile(stream, dtype="<u4", count=int(ni)).reshape(-1, 3)
        if len(tri) * 3 != ni or stream.read(1) or tri.max() >= nv or not np.isfinite(xyz).all():
            raise ValueError(f"Invalid surface {path}")
    return xyz, tri


def tree(points, faces):
    return BVHTree.FromPolygons(points.tolist(), faces.tolist(), all_triangles=True)


def summarize(values):
    return {key: round(float(v), 2) for key, v in zip(("min", "p05", "median", "p95", "max"), np.percentile(values, [0, 5, 50, 95, 100]))}


def fit_to_skin(skin, points, cloth_tree):
    # Intersect triangles directly. The separate MetaHuman head and body meshes
    # are open at their join, which makes nearest-normal inside tests unreliable.
    crossing = {cloth_tri for _, cloth_tri in skin.overlap(cloth_tree)}
    nearest = [skin.find_nearest(Vector(p)) for p in points]
    gaps = np.array([distance * 10 for _, _, _, distance in nearest])
    return crossing, gaps, nearest


def bind_skin_points(skin_xyz, triangles, nearest, gap):
    visible = np.flatnonzero(gap <= 40)
    ids = triangles[[nearest[i][2] for i in visible]]
    a, b, c = skin_xyz[ids].astype(np.float64).transpose(1, 0, 2)
    v0, v1 = b - a, c - a
    v2 = np.array([list(nearest[i][0]) for i in visible]) - a
    def dot(x, y):
        return np.einsum("ij,ij->i", x, y)
    aa, bb, ab = dot(v0, v0), dot(v1, v1), dot(v0, v1)
    den = aa * bb - ab * ab
    valid = den > 1e-10
    wb = (bb * dot(v2, v0) - ab * dot(v2, v1))[valid] / den[valid]
    wc = (aa * dot(v2, v1) - ab * dot(v2, v0))[valid] / den[valid]
    return visible[valid], ids[valid], np.stack([1 - wb - wc, wb, wc], axis=1)


def measure_rest(body, cloth, bones):
    chest, waist, shoulder = bones["spine_05"], bones["spine_03"], bones["upperarm_l"]
    half = abs(bones["upperarm_r"][0] - shoulder[0]) / 2
    result = {}
    for feature, center in (("chest", chest), ("waist", waist)):
        for side, direction in (("front", -1), ("back", 1)):
            gaps = []
            for x in np.linspace(-0.6, 0.6, 9) * half:
                for dz in (-1, 0, 1):
                    start = Vector((center[0] + x, -direction * 150, center[2] + dz))
                    ray = Vector((0, direction, 0))
                    skin, skin_normal, _, _ = body.ray_cast(start, ray, 350)
                    textile, fabric_normal, _, _ = cloth.ray_cast(start, ray, 350)
                    # Unreal render indices use clockwise front faces. Exclude
                    # hits on the opposite panel when rays pass through an opening.
                    if (skin is not None and textile is not None and
                            skin_normal.dot(ray) > 0 and fabric_normal.dot(ray) > 0):
                        gaps.append(10 * (skin - textile).dot(ray))
            result[feature + "_" + side] = {"n": len(gaps), **(summarize(gaps) if gaps else {})}
    return result


def audit_character(folder):
    frames = json.loads((folder / "frames.json").read_text())
    result = {}
    for frame, data in frames.items():
        body, body_tri = surface(folder / (frame + "_body.bin"))
        garment, garment_tri = surface(folder / (frame + "_tunic.bin"))
        face, face_tri = surface(folder / (frame + "_face.bin"))
        # Restrict to the vicinity of the garment. Ignore distant face and leg detail.
        lower = garment.min(axis=0) - 16
        upper = garment.max(axis=0) + 16
        pieces = []
        for xyz, tri, offset in [(body, body_tri, 0), (face, face_tri, len(body))]:
            near = np.all((xyz >= lower) & (xyz <= upper), axis=1)
            pieces.append(tri[near[tri].any(axis=1)] + offset)
        skin_xyz = np.vstack((body, face))
        triangles = np.vstack(pieces)
        skin = tree(skin_xyz, triangles)
        textile = tree(garment, garment_tri)
        crossed, gap, nearest = fit_to_skin(skin, garment, textile)
        report = {"vertices": len(garment), "triangles": len(garment_tri),
                  "garment_faces_crossing_skin": len(crossed),
                  "crossing_percent": round(100 * len(crossed) / len(garment_tri), 3),
                  "nearest_surface_mm": summarize(gap)}
        if crossed:
            centers = garment[garment_tri[sorted(crossed)]].mean(axis=1)
            report["crossing_bounds_cm"] = [centers.min(axis=0).round(1).tolist(), centers.max(axis=0).round(1).tolist()]
        if frame == "rest":
            rest = garment
            rest_tri = garment_tri
            tracked, bound_tri, weights = bind_skin_points(skin_xyz, triangles, nearest, gap)
            starting_gap = gap[tracked]
            report["tracked_vertices_within_40mm"] = len(tracked)
            edges = np.unique(np.sort(np.concatenate([garment_tri[:, [0, 1]], garment_tri[:, [1, 2]], garment_tri[:, [2, 0]]]), axis=1), axis=0)
            lengths = np.linalg.norm(rest[edges[:, 0]] - rest[edges[:, 1]], axis=1)
            edges = edges[lengths > 0.25]
            lengths = lengths[lengths > 0.25]
            report["directional_mm"] = measure_rest(skin, textile, data["bones_cm"])
        else:
            if not np.array_equal(garment_tri, rest_tri):
                raise ValueError("Topology changed across poses")
            current = np.linalg.norm(garment[edges[:, 0]] - garment[edges[:, 1]], axis=1)
            report["edge_length_ratio"] = summarize(current / lengths)
            report["vertex_travel_cm"] = summarize(np.linalg.norm(garment - rest, axis=1))
            skin_points = np.einsum("ijk,ij->ik", skin_xyz[bound_tri], weights)
            gap_to_same_skin_point = 10 * np.linalg.norm(garment[tracked] - skin_points, axis=1)
            report["change_in_gap_to_tracked_skin_mm"] = summarize(abs(gap_to_same_skin_point - starting_gap))
        result[frame] = report
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("surfaces", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    manifest = args.surfaces / "capture.json"
    if manifest.exists():
        run = json.loads(manifest.read_text())
        if not run["complete"]:
            parser.error("The lineup capture did not finish")
        folders = [args.surfaces / name for name in run["characters"]]
    else:
        folders = sorted(f.parent for f in args.surfaces.glob("*/frames.json"))
    if not folders:
        parser.error("No completed captures")
    result = {folder.name: audit_character(folder) for folder in folders}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
