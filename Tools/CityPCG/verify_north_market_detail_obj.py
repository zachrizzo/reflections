"""Independently compare the detailed source OBJ files to regenerated Bay data."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import preflight_north_market_details as preflight


ROOT = preflight.ROOT
OUTPUT = ROOT / "Saved/CityPCG/NorthMarketDetailedObj_20261115_codex"


def matches_recorded_text(path, recorded_sha):
    """Compare source bytes while permitting only uniform LF/CRLF checkout changes."""
    original = path.read_bytes()
    lf = original.replace(b"\r\n", b"\n")
    candidates = (original, lf, lf.replace(b"\n", b"\r\n"))
    return any(hashlib.sha256(data).hexdigest() == recorded_sha for data in candidates)


def verify_input_provenance(recorded, current):
    if set(recorded) != {"east", "west"} or set(current) != set(recorded):
        raise ValueError("Unexpected block set in source provenance")
    for side, expected in recorded.items():
        actual = current[side]
        if (set(expected) != {"candidate", "plan", "override", "source_triangles_by_primitive"} or
                set(actual) != set(expected) or
                actual["source_triangles_by_primitive"] != expected["source_triangles_by_primitive"]):
            raise ValueError(f"{side}: source face evidence differs")
        for kind in ("candidate", "plan"):
            path = preflight.SURVEY / f"north_market_{side}_{kind}_20261115.json"
            if not matches_recorded_text(path, expected[kind]):
                raise ValueError(f"{side}: source {kind} text differs")
        if expected["override"] is None:
            if actual["override"] is not None:
                raise ValueError(f"{side}: unexpected style override")
        else:
            if side != "east" or actual["override"] is None or not matches_recorded_text(
                    preflight.SURVEY / "north_market_east_style_override_20261115.json", expected["override"]):
                raise ValueError(f"{side}: style override text differs")


def geometric_normal(points):
    """An independent area-vector sum over a polygon's triangle fan."""
    a = points[0]
    nx = ny = nz = 0.
    for b, c in zip(points[1:-1], points[2:]):
        u = tuple(b[i] - a[i] for i in range(3))
        v = tuple(c[i] - a[i] for i in range(3))
        nx += u[1] * v[2] - u[2] * v[1]
        ny += u[2] * v[0] - u[0] * v[2]
        nz += u[0] * v[1] - u[1] * v[0]
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if not math.isfinite(length) or length <= 1e-10:
        raise ValueError("Degenerate source polygon")
    return nx / length, ny / length, nz / length


def audit_obj(path, bay, palette):
    vertices = uv_count = normal_count = face_count = 0
    pending_uvs = []
    normal = None
    material = None
    library = None
    max_nonplanarity = 0.
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            fields = line.split()
            if not fields or fields[0].startswith("#"):
                continue
            kind = fields[0]
            if kind == "mtllib":
                if library is not None or fields != ["mtllib", "NorthMarketDetail.mtl"]:
                    raise ValueError(f"{path.name}: material library changed")
                library = fields[1]
            elif kind == "v":
                coords = tuple(map(float, fields[1:]))
                if (len(coords) != 3 or vertices >= len(bay.vertices) or
                        coords != tuple(bay.vertices[vertices])):
                    raise ValueError(f"{path.name}: position {vertices} differs from source geometry")
                vertices += 1
            elif kind == "vt":
                coords = tuple(map(float, fields[1:]))
                if len(coords) != 2 or not all(math.isfinite(value) for value in coords):
                    raise ValueError(f"{path.name}: invalid UV")
                pending_uvs.append(coords)
                uv_count += 1
            elif kind == "vn":
                normal = tuple(map(float, fields[1:]))
                if len(normal) != 3 or not all(math.isfinite(value) for value in normal):
                    raise ValueError(f"{path.name}: invalid normal")
                normal_count += 1
            elif kind == "usemtl":
                if len(fields) != 2:
                    raise ValueError(f"{path.name}: invalid material")
                material = fields[1]
            elif kind == "f":
                if face_count >= len(bay.polygons):
                    raise ValueError(f"{path.name}: extra face")
                source = bay.polygons[face_count]
                role = bay.roles[face_count]
                corners = [tuple(map(int, corner.split("/"))) for corner in fields[1:]]
                if (len(corners) != len(source) or any(len(corner) != 3 for corner in corners) or
                        tuple(corner[0] - 1 for corner in corners) != tuple(source) or
                        tuple(corner[1] for corner in corners) != tuple(range(uv_count - len(source) + 1, uv_count + 1)) or
                        any(corner[2] != normal_count for corner in corners) or
                        material != f"M_GLMedieval_{role}" or len(pending_uvs) != len(source) or normal is None):
                    raise ValueError(f"{path.name}: polygon winding, topology, UV indices or material differ at {face_count}")
                points = [bay.vertices[index] for index in source]
                expected_normal = geometric_normal(points)
                length = math.sqrt(sum(value * value for value in normal))
                alignment = sum(a * b for a, b in zip(expected_normal, normal))
                if not math.isclose(length, 1., abs_tol=1e-9) or alignment < 1 - 1e-8:
                    raise ValueError(f"{path.name}: face normal differs at {face_count}")
                maximum = max(abs(value) for value in expected_normal)
                axes = [axis for axis in range(3) if maximum - abs(expected_normal[axis]) < 1e-9]
                tile = palette[role][2] or 1
                dimensions = ((1, 2), (0, 2), (0, 1))
                if not any(all(math.isclose(uv[0], point[dimensions[axis][0]] / tile, abs_tol=1e-9) and
                                   math.isclose(uv[1], point[dimensions[axis][1]] / tile, abs_tol=1e-9)
                                   for uv, point in zip(pending_uvs, points)) for axis in axes):
                    raise ValueError(f"{path.name}: UV projection differs at face {face_count}")
                origin = points[0]
                max_nonplanarity = max(max_nonplanarity, *(abs(sum((point[i] - origin[i]) * expected_normal[i]
                                                                    for i in range(3))) for point in points))
                pending_uvs = []
                normal = None
                face_count += 1
            else:
                raise ValueError(f"{path.name}: unsupported OBJ record {kind}")
    if (library is None or vertices != len(bay.vertices) or face_count != len(bay.polygons) or
            normal_count != face_count or pending_uvs or normal is not None):
        raise ValueError(f"{path.name}: incomplete geometry or channel data")
    return {"vertices": vertices, "polygons": face_count, "uv_corners": uv_count,
            "max_polygon_nonplanarity_m": max_nonplanarity}


def audit_materials(output, manifest, roles, palette):
    path = output / manifest["material_file"]
    if path.name != "NorthMarketDetail.mtl" or preflight.digest(path) != manifest["material_sha256"]:
        raise ValueError("Material library identity changed")
    materials = {}
    role = None
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] == "newmtl" and len(fields) == 2 and fields[1].startswith("M_GLMedieval_"):
            role = fields[1][len("M_GLMedieval_"):]
            if role in materials:
                raise ValueError("Duplicate material")
            materials[role] = {}
        elif role is not None and fields[0] in {"Kd", "map_Kd"} and fields[0] not in materials[role]:
            materials[role][fields[0]] = fields[1:]
        else:
            raise ValueError("Unexpected material record")
    if set(materials) != roles:
        raise ValueError("Material roles differ from the generated building geometry")
    for role, properties in materials.items():
        if tuple(map(float, properties.get("Kd", []))) != tuple(palette[role][0]):
            raise ValueError(f"{role}: material color differs")
        if palette[role][2]:
            record = manifest["textures"][role]
            expected = "Textures/" + Path(record["path"]).name
            if properties.get("map_Kd") != [expected]:
                raise ValueError(f"{role}: texture reference differs")
            texture = output / expected
            if not texture.is_file() or preflight.digest(texture) != record["sha256"]:
                raise ValueError(f"{role}: local texture bytes differ")
        elif "map_Kd" in properties:
            raise ValueError(f"{role}: unexpected texture")


def audit(output=OUTPUT):
    output = Path(output).resolve()
    manifest = json.loads((output / "detailed_obj_manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("status") != "unreviewed_detailed_obj_source" or
            manifest.get("runtime_activation_eligible") is not False or
            manifest.get("source_ue_section_mapping") != "unverified"):
        raise ValueError("The source-art status or safety flags changed")
    for name, expected in manifest["code_input_sha256"].items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or not matches_recorded_text(path, expected):
            raise ValueError(f"Generator code identity changed: {name}")
    roles, palette = set(), {}
    checked = {}

    def sink(side, planned, bay, source_palette):
        row = manifest["buildings"][planned["id"]]
        record = row["source_artifact"]
        name = record["file"]
        if Path(name).name != name:
            raise ValueError("An OBJ reference escaped the source folder")
        path = output / name
        if preflight.digest(path) != record["sha256"]:
            raise ValueError(f"{name}: file hash changed")
        facts = audit_obj(path, bay, source_palette)
        expected = record["readback"]
        if (any(facts[field] != expected[field] for field in ("vertices", "polygons", "uv_corners")) or
                not math.isclose(facts["max_polygon_nonplanarity_m"], expected["max_polygon_nonplanarity_m"],
                                 abs_tol=1e-8)):
            raise ValueError(f"{name}: independently measured geometry differs")
        roles.update(bay.roles)
        palette.update({role: source_palette[role] for role in bay.roles})
        checked[planned["id"]] = facts
        return {}

    current = preflight.generate_preflight(sink)
    if (current["source_glb_sha256"] != manifest["source_glb_sha256"] or
            current["textures"] != manifest["textures"] or set(checked) != set(manifest["buildings"])):
        raise ValueError("Source candidates, plans, source tile or textures changed")
    verify_input_provenance(manifest["inputs"], current["inputs"])
    for key, expected in current["buildings"].items():
        recorded = manifest["buildings"][key]
        for field, value in expected.items():
            if field != "source_artifact" and json.dumps(recorded.get(field), sort_keys=True) != json.dumps(value, sort_keys=True):
                raise ValueError(f"{key}: recorded {field} differs from regenerated geometry")
    audit_materials(output, manifest, roles, palette)
    return {"status": "independent_source_readback_passed", "buildings": checked,
            "material_roles": len(roles), "textures": len(manifest["textures"]),
            "limits": manifest["limits"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", nargs="?", type=Path, default=OUTPUT,
                        help="Directory containing detailed_obj_manifest.json (default: Saved source bundle)")
    args = parser.parse_args()
    result = audit(args.bundle)
    print(f'Independently verified {len(result["buildings"])} detailed source OBJs, '
          f'{result["material_roles"]} material roles, and {result["textures"]} texture copies.')
