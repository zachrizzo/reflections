"""Exercise North Market's actual procedural detail generator without Blender.

This is a low-memory input/geometry preflight only. A small vector and ear
clipper shim allow the real generation functions to construct their Bay data;
they do not substitute for Blender's tessellation, FBX export or round trips.
"""

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[2]
SURVEY = ROOT / "ArtDirection/CityPCG/MedievalOpening/FollowOn20261115"
TILE = ROOT / "Saved/CityPCG/MedievalSurvey/Tile_p03_p01.glb"
REPORT = ROOT / "Saved/CityPCG/MedievalSurvey/NorthMarketDetailedPreflight_20261115_codex.json"


class Vector:
    """The 2D operations the generator uses before it constructs Blender meshes."""

    def __init__(self, value):
        self.x, self.y = value

    def __iter__(self):
        return iter((self.x, self.y))

    def __getitem__(self, index):
        return (self.x, self.y)[index]

    def __add__(self, other):
        return Vector((self.x + other.x, self.y + other.y))

    def __sub__(self, other):
        return Vector((self.x - other.x, self.y - other.y))

    def __mul__(self, value):
        return Vector((self.x * value, self.y * value))

    def __truediv__(self, value):
        return self * (1 / value)

    def normalized(self):
        length = math.hypot(self.x, self.y)
        if length <= 1e-12:
            raise ValueError("Cannot normalize a zero-length surveyed edge")
        return self / length

    def dot(self, other):
        return self.x * other.x + self.y * other.y


def cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def tessellate_polygon(rings):
    """Simple ear clipping for a single CCW ring; fail on ambiguous input."""
    if len(rings) != 1:
        raise ValueError("Preflight supports only single-ring surveyed roofs")
    points = [tuple(point) for point in rings[0]]
    if len(points) < 3 or len(set(points)) != len(points):
        raise ValueError("Invalid roof perimeter")
    area = sum(a[0] * b[1] - a[1] * b[0] for a, b in zip(points, points[1:] + points[:1]))
    if area <= 0:
        raise ValueError("Expected a CCW roof perimeter")
    remaining = list(range(len(points)))
    result = []
    while len(remaining) > 3:
        for pos, middle in enumerate(remaining):
            a, b, c = remaining[pos - 1], middle, remaining[(pos + 1) % len(remaining)]
            if cross(points[a], points[b], points[c]) <= 1e-10:
                continue
            if any(cross(points[a], points[b], points[index]) >= -1e-10 and
                   cross(points[b], points[c], points[index]) >= -1e-10 and
                   cross(points[c], points[a], points[index]) >= -1e-10
                   for index in remaining if index not in (a, b, c)):
                continue
            result.append((a, b, c))
            del remaining[pos]
            break
        else:
            raise ValueError("Roof perimeter could not be triangulated without ambiguity")
    if cross(*(points[index] for index in remaining)) <= 1e-10:
        raise ValueError("Degenerate final roof triangle")
    return result + [tuple(remaining)]


def load_generator():
    """Import its real functions with unavailable Blender APIs as inert stubs."""
    for name in ("bpy", "bmesh"):
        if name in sys.modules:
            raise RuntimeError(f"{name} is already loaded; run this preflight in a fresh Python process")
        sys.modules[name] = types.ModuleType(name)
    mathutils = types.ModuleType("mathutils")
    geometry = types.ModuleType("mathutils.geometry")
    mathutils.Vector = Vector
    geometry.tessellate_polygon = tessellate_polygon
    mathutils.geometry = geometry
    sys.modules["mathutils"] = mathutils
    sys.modules["mathutils.geometry"] = geometry
    import build_whole_buildings_blender as generator
    return generator


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def generate_preflight(geometry_sink=None):
    from extract_tile_frontages import read_glb
    from subtract_building_shells import reviewed_faces
    from whole_building_styles import read_style_overrides
    from build_north_market_massing import verify_record

    generator = load_generator()
    import build_mark_lane as mark_lane
    source_sha = digest(TILE)
    document, binary = read_glb(TILE)
    rows = {}
    input_hashes = {}
    used_roles = set()
    for side in ("east", "west"):
        candidate_path = SURVEY / f"north_market_{side}_candidate_20261115.json"
        plan_path = SURVEY / f"north_market_{side}_plan_20261115.json"
        candidate = generator.read_json(candidate_path)
        plan = generator.read_json(plan_path)
        records = {item["id"]: item for item in candidate["buildings"]}
        if (candidate.get("status") != "offline_candidate" or plan.get("status") != "offline_generation_input" or
                source_sha != candidate["source_export_sha256"] or source_sha != plan["source_export_sha256"] or
                candidate["source_tile"] != plan["source_tile"] or len(records) != len(candidate["buildings"]) or
                set(records) != set(plan["styles"]) or set(records) != {item["id"] for item in plan["buildings"]}):
            raise ValueError(f"{side}: source, candidate and plan do not agree")
        selected, face_counts = reviewed_faces(document, binary, candidate)
        override_path = SURVEY / "north_market_east_style_override_20261115.json"
        overrides = read_style_overrides(override_path, plan_path, records.keys()) if side == "east" else {}
        shared = generator.paired_edges(plan)
        input_hashes[side] = {"candidate": digest(candidate_path), "plan": digest(plan_path),
                              "override": digest(override_path) if side == "east" else None,
                              "source_triangles_by_primitive": {str(key): len(value) for key, value in selected.items()}}
        for planned in plan["buildings"]:
            key = planned["id"]
            verify_record(records[key], planned)
            bay, outline, profile, style, x_axis, y_axis, stacks = generator.from_plan(
                records[key], planned, plan["styles"][key], shared.get(key, set()), overrides.get(key))
            if (len(bay.roles) != len(bay.polygons) or not bay.vertices or not bay.polygons or
                    any(len(point) != 3 or not all(math.isfinite(value) for value in point) for point in bay.vertices) or
                    any(len(face) < 3 or any(type(index) is not int or not 0 <= index < len(bay.vertices)
                                             for index in face) for face in bay.polygons)):
                raise ValueError(f"{key}: generated intermediate has invalid vertices, faces or material roles")
            roles = Counter(bay.roles)
            used_roles.update(roles)
            rows[key] = {"side": side, "style": style.name, "source_triangles": face_counts[key],
                         "vertices": len(bay.vertices), "polygons": len(bay.polygons),
                         "fan_triangle_estimate": sum(len(face) - 2 for face in bay.polygons),
                         "material_polygons": dict(sorted(roles.items())),
                         "roof_profile_local_y_z_m": profile, "chimney_count": len(stacks),
                         "world_pivot_m": planned["origin_m"], "yaw_deg": planned["rotation_yaw_deg"],
                         "axis_x_world_xy": tuple(x_axis), "axis_y_world_xy": tuple(y_axis)}
            if geometry_sink is not None:
                rows[key]["source_artifact"] = geometry_sink(side, planned, bay, mark_lane.PALETTE)
            del bay
    texture_report = {}
    for role in sorted(used_roles):
        if role not in mark_lane.PALETTE:
            raise ValueError(f"Unknown material role {role}")
        if mark_lane.PALETTE[role][2]:
            location = ROOT / ("ArtDirection/CityPCG/MedievalOpening/Guildhall/Textures" if role == "GuildRubble"
                               else "ArtDirection/CityPCG/MedievalOpening/Textures") / f"T_GLMedieval_{role}.png"
            with location.open("rb") as image:
                if image.read(8) != b"\x89PNG\r\n\x1a\n":
                    raise ValueError(f"Invalid PNG texture for {role}")
            texture_report[role] = {"path": location.relative_to(ROOT).as_posix(), "sha256": digest(location)}
    return {"status": "detail_geometry_input_preflight_only", "source_glb_sha256": source_sha,
            "inputs": input_hashes, "textures": texture_report, "buildings": rows,
            "limits": ["Python double-precision vector and ear-clipping shims replace Blender mathutils.",
                       "No Blender mesh, FBX, UV, normals, collision, Unreal import or live section mapping verified.",
                       "Recheck exact inputs and coordination gates before the isolated Blender export."]}


if __name__ == "__main__":
    result = generate_preflight()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("x", encoding="utf-8", newline="\n") as out:
        json.dump(result, out, indent=2)
        out.write("\n")
    print(f'Preflighted detailed geometry for {len(result["buildings"])} buildings: {REPORT}')
