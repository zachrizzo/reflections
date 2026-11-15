"""Create small, review-only North Market shells from the checked survey plans.

This does not run Blender, read the large source GLB, alter Unreal, or produce
the detailed FBXs. The output has no doors, windows, collision, or gameplay use.
"""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
import math
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
SURVEY = PROJECT / "ArtDirection/CityPCG/MedievalOpening/FollowOn20261115"
OUTPUT = PROJECT / "Saved/CityPCG/NorthMarketMassing_20261115_codex"
SOURCE_HASH = "411a895aedeb642f0250cdd4c3e4725a1d04b73035ea4a75335f60193ca7102c"


def cross2(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def area(points):
    return sum(a[0] * b[1] - a[1] * b[0] for a, b in zip(points, points[1:] + points[:1])) / 2


def clip_y(points, level, above):
    """Clip a CCW polygon to a horizontal line, retaining winding."""
    output = []
    for a, b in zip(points, points[1:] + points[:1]):
        keep_a = a[1] >= level if above else a[1] <= level
        keep_b = b[1] >= level if above else b[1] <= level
        if keep_a:
            output.append(a)
        if keep_a != keep_b:
            t = (level - a[1]) / (b[1] - a[1])
            output.append((a[0] + t * (b[0] - a[0]), level))
    cleaned = []
    for point in output:
        point = tuple(round(value, 6) for value in point)
        if not cleaned or point != cleaned[-1]:
            cleaned.append(point)
    if len(cleaned) > 1 and cleaned[0] == cleaned[-1]:
        cleaned.pop()
    return cleaned


def roof_at(y, profile):
    for (low, z_low), (high, z_high) in zip(profile, profile[1:]):
        if y <= high + 1e-6:
            t = max(0., min(1., (y - low) / (high - low)))
            return z_low + t * (z_high - z_low)
    return profile[-1][1]


class Mesh:
    def __init__(self):
        self.vertices = []
        self.buckets = {}
        self.faces = []

    def face(self, material, points):
        points = [tuple(round(value, 6) for value in point) for point in points]
        indices = []
        for point in points:
            bucket = tuple(math.floor(value / .00001) for value in point)
            index = next((item for delta in product((-1, 0, 1), repeat=3)
                          for item in self.buckets.get(tuple(bucket[i] + delta[i] for i in range(3)), ())
                          if math.dist(point, self.vertices[item]) <= .00001), None)
            if index is None:
                index = len(self.vertices)
                self.vertices.append(point)
                self.buckets.setdefault(bucket, []).append(index)
            indices.append(index)
        if len(set(indices)) != 3:
            return
        a, b, c = (self.vertices[index] for index in indices)
        ab = tuple(b[i] - a[i] for i in range(3))
        ac = tuple(c[i] - a[i] for i in range(3))
        n = (ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2],
             ab[0] * ac[1] - ab[1] * ac[0])
        length = math.sqrt(sum(value * value for value in n))
        if length < 1e-8:
            return
        self.faces.append((material, tuple(indices), tuple(value / length for value in n)))

    def audit(self):
        edges = Counter()
        directed = Counter()
        volume = 0.
        for _, indices, _ in self.faces:
            for a, b in zip(indices, indices[1:] + indices[:1]):
                edges[tuple(sorted((a, b)))] += 1
                directed[(a, b)] += 1
            a, b, c = (self.vertices[index] for index in indices)
            volume += (a[0] * (b[1] * c[2] - b[2] * c[1]) +
                       a[1] * (b[2] * c[0] - b[0] * c[2]) +
                       a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
        if not self.faces or any(count != 2 or directed[(a, b)] != directed[(b, a)]
                                 for (a, b), count in edges.items()) or volume <= 0:
            raise ValueError("Massing mesh is not a closed, consistently wound positive-volume shell")
        return {"vertices": len(self.vertices), "triangles": len(self.faces),
                "closed_edges": len(edges), "volume_m3": round(volume, 4)}


def make_mesh(building):
    footprint = [tuple(point) for point in building["footprint_local_m"]]
    surface = building["surface_triangulation"]
    vertices = [tuple(point) for point in surface["vertices_local_m"]]
    triangles = surface["ccw_faces"]
    profile = [tuple(point) for point in building["roof_profile_local_y_z_m"]]
    if (footprint != vertices or len(footprint) < 3 or area(footprint) <= 0 or
            len(profile) < 3 or any(a[0] >= b[0] for a, b in zip(profile, profile[1:])) or
            abs(profile[0][0] - min(point[1] for point in footprint)) > .00001 or
            abs(profile[-1][0] - max(point[1] for point in footprint)) > .00001 or
            max(z for _, z in profile) > building["source_max_height_m"]):
        raise ValueError(f'{building["id"]}: invalid surveyed footprint or roof profile')
    if (any(len(face) != 3 or any(type(i) is not int or not 0 <= i < len(vertices) for i in face) or
            cross2(*(vertices[i] for i in face)) <= 0 for face in triangles) or
            not math.isclose(sum(cross2(*(vertices[i] for i in face)) / 2 for face in triangles),
                             area(footprint), abs_tol=1e-4)):
        raise ValueError(f'{building["id"]}: triangulation does not cover the surveyed footprint')

    mesh = Mesh()
    for face in triangles:
        triangle = [vertices[index] for index in face]
        for (low, _), (high, _) in zip(profile, profile[1:]):
            poly = clip_y(clip_y(triangle, low, True), high, False)
            for index in range(1, len(poly) - 1):
                piece = [poly[0], poly[index], poly[index + 1]]
                mesh.face("ClayRoof", [(x, y, roof_at(y, profile)) for x, y in piece])
                mesh.face("StoneBase", [(x, y, 0.) for x, y in reversed(piece)])

    stations = [point[0] for point in profile[1:-1]]
    for a, b in zip(footprint, footprint[1:] + footprint[:1]):
        times = [0., 1.]
        if abs(b[1] - a[1]) > 1e-9:
            times += [(y - a[1]) / (b[1] - a[1]) for y in stations
                      if 0 < (y - a[1]) / (b[1] - a[1]) < 1]
        points = [(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                  for t in sorted(times)]
        for p, q in zip(points, points[1:]):
            p0, q0 = (p[0], p[1], 0.), (q[0], q[1], 0.)
            p1, q1 = (p[0], p[1], roof_at(p[1], profile)), (q[0], q[1], roof_at(q[1], profile))
            mesh.face("LimeWall", (p0, q0, q1))
            mesh.face("LimeWall", (p0, q1, p1))
    return mesh


def write_obj(path, mesh):
    with path.open("x", encoding="utf-8", newline="\n") as out:
        out.write("# Review-only massing; local metres, Z up; no collision or openings.\n")
        out.write("mtllib NorthMarketMassing.mtl\n")
        for point in mesh.vertices:
            out.write("v %.6f %.6f %.6f\n" % point)
        for material, indices, normal in mesh.faces:
            for index in indices:
                x, y, z = mesh.vertices[index]
                uv = (x, y) if material != "LimeWall" else ((x + y), z)
                out.write("vt %.6f %.6f\n" % uv)
            out.write("vn %.6f %.6f %.6f\n" % normal)
        previous = None
        for number, (material, indices, _) in enumerate(mesh.faces, 1):
            if material != previous:
                out.write(f"usemtl {material}\n")
                previous = material
            out.write("f " + " ".join(f"{vertex + 1}/{3 * (number - 1) + corner + 1}/{number}"
                                      for corner, vertex in enumerate(indices)) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_record(candidate, planned):
    """Prove the plan uses this candidate's surveyed origin, entry and footprint."""
    origin = candidate["origin_m"]
    footprint = candidate["footprint"]
    edge = candidate["entry"]["edge"]
    if (len(origin) != 3 or not 0 <= edge < len(footprint) or
            edge != planned["entry"]["edge"] or math.dist(origin, planned["origin_m"]) > .00002 or
            abs(candidate["source_roof_m"] - candidate["base_m"] - planned["source_max_height_m"]) > .00002):
        raise ValueError(f'{planned["id"]}: plan origin, height or entry does not match the candidate')
    a, b = footprint[edge], footprint[(edge + 1) % len(footprint)]
    length = math.dist(a, b)
    if length < .00001:
        raise ValueError(f'{planned["id"]}: candidate entry has no width')
    y_axis = ((b[0] - a[0]) / length, (b[1] - a[1]) / length)
    x_axis = (y_axis[1], -y_axis[0])
    outward = candidate["entry"]["outward"]
    if sum(a * b for a, b in zip(x_axis, outward)) < .9999:
        raise ValueError(f'{planned["id"]}: candidate entry direction disagrees with the footprint')
    expected = [((x - origin[0]) * x_axis[0] + (y - origin[1]) * x_axis[1],
                 (x - origin[0]) * y_axis[0] + (y - origin[1]) * y_axis[1]) for x, y in footprint]
    local = planned["footprint_local_m"]
    yaw = math.degrees(math.atan2(x_axis[1], x_axis[0]))
    if (len(local) != len(expected) or any(math.dist(a, b) > .00002 for a, b in zip(local, expected)) or
            abs(math.remainder(yaw - planned["rotation_yaw_deg"], 360)) > .00001):
        raise ValueError(f'{planned["id"]}: local footprint or yaw does not match the candidate')


def build(output=OUTPUT):
    if not output.resolve().is_relative_to((PROJECT / "Saved").resolve()):
        raise ValueError("Review output must be under Saved")
    blocks = []
    for side in ("east", "west"):
        candidate_path = SURVEY / f"north_market_{side}_candidate_20261115.json"
        plan_path = SURVEY / f"north_market_{side}_plan_20261115.json"
        candidate = json.loads(candidate_path.read_text(encoding="utf-8-sig"))
        plan = json.loads(plan_path.read_text(encoding="utf-8-sig"))
        ids = [row["id"] for row in candidate["buildings"]]
        if (candidate["status"] != "offline_candidate" or plan["status"] != "offline_generation_input" or
                candidate["source_export_sha256"] != SOURCE_HASH or plan["source_export_sha256"] != SOURCE_HASH or
                candidate["source_tile"] != "Tile_p03_p01" or plan["source_tile"] != "Tile_p03_p01" or
                plan["reviewed_candidate"] != candidate_path.name or len(ids) != 2 or len(set(ids)) != 2 or
                set(ids) != {row["id"] for row in plan["buildings"]}):
            raise ValueError(f"{side}: reviewed candidates and surveyed plans do not match")
        records = {row["id"]: row for row in candidate["buildings"]}
        for row in plan["buildings"]:
            verify_record(records[row["id"]], row)
        blocks.append((side, candidate_path, plan_path, plan))

    output.mkdir(parents=True, exist_ok=False)
    (output / "NorthMarketMassing.mtl").write_text(
        "newmtl LimeWall\nKd 0.68 0.61 0.49\n\nnewmtl ClayRoof\nKd 0.36 0.19 0.15\n\n"
        "newmtl StoneBase\nKd 0.42 0.39 0.34\n", encoding="utf-8")
    report = {"status": "review_only_massing", "runtime_activation_eligible": False,
              "source_ue_section_mapping": "unverified", "source_tile_sha256": SOURCE_HASH,
              "source_glb_reverified_in_this_run": False, "units": "local metres, Z up",
              "warning": "Simple silhouettes only: no doors, windows, textures, collision, or gameplay approval.",
              "buildings": {}}
    for side, candidate_path, plan_path, plan in blocks:
        for row in plan["buildings"]:
            mesh = make_mesh(row)
            facts = mesh.audit()
            name = f'SM_GLMedieval_NorthMarketMassing_{side}_{row["id"].rsplit("_", 1)[-1][:8]}.obj'
            path = output / name
            write_obj(path, mesh)
            report["buildings"][row["id"]] = {"side": side, "file": name, "sha256": sha(path),
                "candidate_sha256": sha(candidate_path), "plan_sha256": sha(plan_path),
                "world_pivot_m": row["origin_m"], "yaw_deg": row["rotation_yaw_deg"],
                "entry_edge": row["entry"]["edge"], **facts}
    (output / "massing_manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT,
                        help="Fresh output folder inside this project's Saved directory")
    args = parser.parse_args()
    manifest = build(args.output)
    print(f'Built {len(manifest["buildings"])} review-only North Market shells in {args.output}')
