"""Audit Unreal's sampled LOD 0 skinned surfaces. Run in Blender background mode."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree


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
    pairs = skin.overlap(cloth_tree)
    nearest = [skin.find_nearest(Vector(p)) for p in points]
    gaps = np.array([distance * 10 for _, _, _, distance in nearest])
    return pairs, gaps, nearest


def mask_image(path):
    import bpy
    image = bpy.data.images.load(str(path.resolve()), check_existing=True)
    image.colorspace_settings.name = "Non-Color"
    width, height = image.size
    rgba = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(rgba)
    # UE V=0 is the top of the image. Blender returns rows starting at the bottom.
    return rgba.reshape(height, width, 4)[::-1, :, 0].copy()


def classify_body_triangles(folder, body, tri, mask, texture_name="T_WayfarersTunic_BodyMask"):
    """0 = entirely culled, 1 = wholly unmasked, 2 = mixed or unverified."""
    state_file = folder / "body_mask.json"
    if not state_file.is_file() or mask is None:
        return np.full(len(tri), 2, dtype=np.uint8)
    state = json.loads(state_file.read_text())
    if not str(state["texture"]).endswith("." + texture_name):
        return np.full(len(tri), 2, dtype=np.uint8)
    uv = np.fromfile(folder / "body_uv.bin", dtype="<f4").reshape(-1, 2)
    if len(uv) != len(body):
        raise ValueError(f"UV vertex count differs in {folder.name}")
    coords = uv[tri]
    # Use the whole UV bounding box with a bilinear filter margin. This is
    # conservative for triangles straddling a mask edge or texture wrap.
    width, height = mask.shape[1], mask.shape[0]
    coords = coords - np.floor(coords.mean(axis=1))[:, None, :]
    lo = np.floor(coords.min(axis=1) * [width, height]).astype(int) - 1
    hi = np.ceil(coords.max(axis=1) * [width, height]).astype(int) + 2
    valid = (lo >= 0).all(axis=1) & (hi <= [width, height]).all(axis=1)
    x0, y0 = np.clip(lo, [0, 0], [width, height]).T
    x1, y1 = np.clip(hi, [0, 0], [width, height]).T
    def any_in_box(bitmap):
        summed = np.pad(bitmap.astype(np.int32), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
        return (summed[y1, x1] - summed[y0, x1] - summed[y1, x0] + summed[y0, x0]) > 0
    classes = np.full(len(tri), 2, dtype=np.uint8)
    classes[valid & ~any_in_box(mask < 0.999)] = 1
    if state["declared_by_material"]:
        classes[valid & ~any_in_box(mask >= state["max_cull"])] = 0
    return classes


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


def bare_body_contact(body, tris, neutral, garment, garment_tri, exposed):
    """Find self-intersections of body patches originally separated by at least 4 cm."""
    body_tree = tree(body, tris)
    pairs = np.array(body_tree.overlap(body_tree), dtype=np.int32).reshape(-1, 2)
    pairs = pairs[pairs[:, 0] < pairs[:, 1]]
    rest_centers = neutral[tris].mean(axis=1)
    pairs = pairs[np.linalg.norm(rest_centers[pairs[:, 0]] - rest_centers[pairs[:, 1]], axis=1) >= 4]
    # Discard shared vertices as well as neighbouring rest patches.
    a, b = tris[pairs[:, 0]], tris[pairs[:, 1]]
    pairs = pairs[~(a[:, :, None] == b[:, None, :]).any(axis=(1, 2))]
    close = 0
    if len(pairs) and exposed:
        contacts = body[tris[np.unique(pairs)]].mean(axis=1)
        search = KDTree(len(contacts))
        for i, point in enumerate(contacts):
            search.insert(Vector(point), i)
        search.balance()
        textile = garment[garment_tri[sorted(exposed)]].mean(axis=1)
        close = sum(search.find(Vector(point))[2] <= 2.0 for point in textile)
    return {"bare_body_intersecting_pairs_separated_in_rest": len(pairs),
            "unmasked_cloth_contacts_within_20mm_of_bare_self_contact": close}


def measure_rest(body, cloth, bones):
    chest, waist, shoulder = bones["spine_05"], bones["spine_03"], bones["upperarm_l"]
    half = abs(bones["upperarm_r"][0] - shoulder[0]) / 2
    result = {}
    hem = np.array(bones["pelvis"]) + [0, 0, 6.5]
    for feature, center in (("chest", chest), ("waist", waist), ("above_hem", hem)):
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
                            direction * (textile.y - center[1]) < 0 and direction * (skin.y - center[1]) < 0 and
                            skin_normal.dot(ray) > 0 and fabric_normal.dot(ray) > 0):
                        gaps.append(10 * (skin - textile).dot(ray))
            result[feature + "_" + side] = {"n": len(gaps), **(summarize(gaps) if gaps else {})}
    for side in ("l", "r"):
        arm = bones["upperarm_" + side]
        ray = Vector((0, 0, -1))
        gaps = []
        for fraction in (0.78, 0.88, 0.98):
            for depth in (-2.5, 0, 2.5):
                start = Vector((waist[0] + (arm[0] - waist[0]) * fraction, arm[1] + depth, arm[2] + 75))
                skin, skin_normal, _, _ = body.ray_cast(start, ray, 150)
                fabric, fabric_normal, _, _ = cloth.ray_cast(start, ray, 150)
                if (skin is not None and fabric is not None and abs(skin.z - arm[2]) <= 13 and
                        skin_normal.dot(ray) > 0 and fabric_normal.dot(ray) > 0):
                    gaps.append(10 * (skin - fabric).dot(ray))
        result["shoulder_" + side] = {"n": len(gaps), **(summarize(gaps) if gaps else {})}
    return result


def measure_girth(body, cloth, bones):
    """Approximate closed horizontal torso rings. Omit open or sleeve-spanning sections."""
    half = abs(bones["upperarm_l"][0] - bones["upperarm_r"][0]) / 2
    result = {}
    for region, joint in (("chest", "spine_05"), ("waist", "spine_03")):
        center = Vector(bones[joint])
        rings = [[], []]
        for angle in np.linspace(0, 2 * np.pi, 128, endpoint=False):
            ray = Vector((np.cos(angle), np.sin(angle), 0))
            for samples, mesh in zip(rings, (body, cloth)):
                point, normal, _, _ = mesh.ray_cast(center, ray, 100)
                if point is not None and normal.dot(ray) < 0 and abs(point.x - center.x) < 1.4 * half:
                    samples.append(tuple(point))
        entry = {"rays": 128, "body_hits": len(rings[0]), "garment_hits": len(rings[1])}
        if all(len(ring) == 128 for ring in rings):
            segments = [np.linalg.norm(np.array(r) - np.roll(r, 1, axis=0), axis=1) for r in rings]
            if all(edges.max() < half * 0.35 for edges in segments):
                skin_mm, cloth_mm = [10 * edges.sum() for edges in segments]
                entry.update(body_mm=round(skin_mm, 1), garment_mm=round(cloth_mm, 1),
                             ease_mm=round(cloth_mm - skin_mm, 1))
        result[region] = entry
    return result


def audit_character(folder, mask):
    frames = json.loads((folder / "frames.json").read_text())
    result = {}
    for frame, data in frames.items():
        body, body_tri = surface(folder / (frame + "_body.bin"))
        garment, garment_tri = surface(folder / (frame + "_tunic.bin"))
        face, face_tri = surface(folder / (frame + "_face.bin"))
        # Restrict to the vicinity of the garment. Ignore distant face and leg detail.
        lower = garment.min(axis=0) - 16
        upper = garment.max(axis=0) + 16
        if frame == "rest":
            body_coverage = classify_body_triangles(folder, body, body_tri, mask)
            neutral_body = body
        pieces, coverage = [], []
        for xyz, tri, offset in [(body, body_tri, 0), (face, face_tri, len(body))]:
            near = np.all((xyz >= lower) & (xyz <= upper), axis=1)
            chosen = near[tri].any(axis=1)
            pieces.append(tri[chosen] + offset)
            coverage.append(body_coverage[chosen] if offset == 0 else np.full(chosen.sum(), 2, dtype=np.uint8))
        skin_xyz = np.vstack((body, face))
        triangles = np.vstack(pieces)
        skin = tree(skin_xyz, triangles)
        textile = tree(garment, garment_tri)
        pairs, gap, nearest = fit_to_skin(skin, garment, textile)
        crossed = {cloth_tri for _, cloth_tri in pairs}
        classes = np.concatenate(coverage)
        exposed = {j for i, j in pairs if classes[i] == 1}
        uncertain = {j for i, j in pairs if classes[i] == 2} - exposed
        hidden = crossed - exposed - uncertain
        report = {"vertices": len(garment), "triangles": len(garment_tri),
                  "garment_faces_crossing_skin": len(crossed),
                  "crossing_percent": round(100 * len(crossed) / len(garment_tri), 3),
                  "crossing_wholly_unmasked_body": len(exposed),
                  "crossing_mask_edge_or_unverified_skin": len(uncertain),
                  "crossing_only_fully_masked_skin": len(hidden),
                  "nearest_surface_mm": summarize(gap)}
        report.update(bare_body_contact(body, pieces[0], neutral_body, garment, garment_tri, exposed))
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
            report["circumference_mm"] = measure_girth(skin, textile, data["bones_cm"])
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
    parser.add_argument("--body-mask", type=Path, help="Wayfarer's body mask PNG used by this capture")
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
    mask = mask_image(args.body_mask) if args.body_mask else None
    result = {folder.name: audit_character(folder, mask) for folder in folders}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
