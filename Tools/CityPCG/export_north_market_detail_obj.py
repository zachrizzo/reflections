"""Export detailed procedural North Market source meshes without Blender.

The real building generator runs with the preflight's small math/tessellation
shim. These OBJ files preserve its Bay polygons and material roles, but are
review-only source art, not Blender FBXs or validated Unreal assets.
"""

import hashlib
import json
import math
from pathlib import Path
import re
import shutil

import preflight_north_market_details as preflight


ROOT = preflight.ROOT
OUTPUT = ROOT / "Saved/CityPCG/NorthMarketDetailedObj_20261115_codex"
CODE_INPUTS = (
    ROOT / "Tools/CityPCG/build_whole_buildings_blender.py",
    ROOT / "Tools/CityPCG/whole_building_styles.py",
    ROOT / "Tools/CityPCG/build_north_market_massing.py",
    ROOT / "Tools/CityPCG/preflight_north_market_details.py",
    ROOT / "Tools/CityPCG/export_north_market_detail_obj.py",
    ROOT / "ArtDirection/CityPCG/Kit/build_facade_kit.py",
    ROOT / "ArtDirection/CityPCG/MedievalOpening/build_medieval_facades.py",
    ROOT / "ArtDirection/CityPCG/MedievalOpening/WholeBuildings/build_mark_lane.py",
    ROOT / "ArtDirection/CityPCG/MedievalOpening/ThamesWarehouse/build_thames_warehouse.py",
    ROOT / "ArtDirection/CityPCG/MedievalOpening/Guildhall/build_guildhall.py",
)


def face_normal(points):
    normal = [0., 0., 0.]
    for a, b in zip(points, points[1:] + points[:1]):
        normal[0] += (a[1] - b[1]) * (a[2] + b[2])
        normal[1] += (a[2] - b[2]) * (a[0] + b[0])
        normal[2] += (a[0] - b[0]) * (a[1] + b[1])
    magnitude = math.sqrt(sum(value * value for value in normal))
    if not math.isfinite(magnitude) or magnitude <= 1e-10:
        raise ValueError("Cannot project UVs onto a degenerate source polygon")
    return tuple(value / magnitude for value in normal)


def projection(points, tile):
    """Mirror make_object's dominant face-normal UV projection and tiling."""
    normal = face_normal(points)
    axis = max(range(3), key=lambda index: abs(normal[index]))
    first, second = ((1, 2), (0, 2), (0, 1))[axis]
    return normal, [(point[first] / tile, point[second] / tile) for point in points]


def write_obj(path, bay, palette):
    uv_count = 0
    with path.open("x", encoding="utf-8", newline="\n") as out:
        out.write("# Detailed source art: local metres, +X entrance, +Z up; not Blender/Unreal validated.\n")
        out.write("mtllib NorthMarketDetail.mtl\n")
        for point in bay.vertices:
            out.write("v " + " ".join(repr(value) for value in point) + "\n")
        last_role = None
        for index, (face, role) in enumerate(zip(bay.polygons, bay.roles), 1):
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", role) or role not in palette:
                raise ValueError(f"Unknown or unsafe material role {role!r}")
            points = [bay.vertices[vertex] for vertex in face]
            normal, uvs = projection(points, palette[role][2] or 1)
            if role != last_role:
                out.write(f"usemtl M_GLMedieval_{role}\n")
                last_role = role
            for uv in uvs:
                out.write("vt " + " ".join(repr(value) for value in uv) + "\n")
            out.write("vn " + " ".join(repr(value) for value in normal) + "\n")
            out.write("f " + " ".join(f"{vertex + 1}/{uv_count + corner + 1}/{index}"
                                       for corner, vertex in enumerate(face)) + "\n")
            uv_count += len(face)
    return uv_count


def verify_obj(path, bay, palette):
    """Read each source face and compare its geometry, slot, normal and UV0."""
    vertex_count = uv_count = normal_count = face_count = 0
    pending_uvs = []
    current_normal = None
    current_role = None
    libraries = []
    max_planarity_error = 0.
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            parts = line.split()
            if not parts or parts[0].startswith("#"):
                continue
            kind = parts[0]
            if kind == "mtllib":
                libraries.append(parts[1:])
            elif kind == "v":
                point = tuple(map(float, parts[1:]))
                if vertex_count >= len(bay.vertices) or point != tuple(bay.vertices[vertex_count]):
                    raise ValueError(f"{path.name}: vertex {vertex_count} changed")
                vertex_count += 1
            elif kind == "usemtl":
                current_role = parts[1]
            elif kind == "vt":
                pending_uvs.append(tuple(map(float, parts[1:])))
                uv_count += 1
            elif kind == "vn":
                if current_normal is not None:
                    raise ValueError(f"{path.name}: extra face normal")
                current_normal = tuple(map(float, parts[1:]))
                normal_count += 1
            elif kind == "f":
                if face_count >= len(bay.polygons):
                    raise ValueError(f"{path.name}: extra face")
                source_face, role = bay.polygons[face_count], bay.roles[face_count]
                corners = [tuple(map(int, item.split("/"))) for item in parts[1:]]
                if (current_role != f"M_GLMedieval_{role}" or len(corners) != len(source_face) or
                        any(len(corner) != 3 for corner in corners) or
                        [corner[0] - 1 for corner in corners] != list(source_face) or
                        [corner[1] for corner in corners] != list(range(uv_count - len(source_face) + 1, uv_count + 1)) or
                        any(corner[2] != normal_count for corner in corners)):
                    raise ValueError(f"{path.name}: material, winding, topology or corner reference changed at face {face_count}")
                points = [bay.vertices[index] for index in source_face]
                expected_normal, expected_uvs = projection(points, palette[role][2] or 1)
                if current_normal != expected_normal or pending_uvs != expected_uvs:
                    raise ValueError(f"{path.name}: normal or projected UV changed at face {face_count}")
                origin = points[0]
                max_planarity_error = max(max_planarity_error, *(abs(sum((point[i] - origin[i]) * expected_normal[i]
                                                                            for i in range(3))) for point in points))
                pending_uvs = []
                current_normal = None
                face_count += 1
            else:
                raise ValueError(f"{path.name}: unexpected OBJ record {kind}")
    if (libraries != [["NorthMarketDetail.mtl"]] or vertex_count != len(bay.vertices) or
            face_count != len(bay.polygons) or normal_count != face_count or pending_uvs or current_normal is not None):
        raise ValueError(f"{path.name}: incomplete OBJ readback")
    return {"vertices": vertex_count, "polygons": face_count, "uv_corners": uv_count,
            "max_polygon_nonplanarity_m": max_planarity_error}


def write_materials(output, palette, roles, textures):
    texture_dir = output / "Textures"
    texture_dir.mkdir()
    for role, item in textures.items():
        source = ROOT / item["path"]
        destination = texture_dir / source.name
        if preflight.digest(source) != item["sha256"]:
            raise ValueError(f"Texture changed during export: {source}")
        with source.open("rb") as inp, destination.open("xb") as out:
            shutil.copyfileobj(inp, out, length=65536)
        if preflight.digest(destination) != item["sha256"]:
            raise ValueError(f"Texture copy did not match: {destination}")
    path = output / "NorthMarketDetail.mtl"
    with path.open("x", encoding="utf-8", newline="\n") as out:
        for role in sorted(roles):
            color, _, tile = palette[role]
            out.write(f"newmtl M_GLMedieval_{role}\nKd {' '.join(repr(value) for value in color)}\n")
            if tile:
                texture = textures[role]
                out.write(f'map_Kd Textures/{Path(texture["path"]).name}\n')
            out.write("\n")
    return path


def verify_materials(path, palette, roles, textures):
    """Independently parse slots and verify each local texture and its hash."""
    found = {}
    current = None
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] == "newmtl":
            if len(fields) != 2 or not fields[1].startswith("M_GLMedieval_"):
                raise ValueError("Invalid material declaration")
            current = fields[1][len("M_GLMedieval_"):]
            if current in found:
                raise ValueError("Duplicate material declaration")
            found[current] = {}
        elif fields[0] in ("Kd", "map_Kd") and current:
            if fields[0] in found[current]:
                raise ValueError("Repeated material property")
            found[current][fields[0]] = fields[1:]
        else:
            raise ValueError("Unexpected material file record")
    if set(found) != set(roles):
        raise ValueError("Material slots changed")
    for role, fields in found.items():
        if tuple(map(float, fields.get("Kd", []))) != tuple(palette[role][0]):
            raise ValueError(f"{role}: base color changed")
        if palette[role][2]:
            expected = "Textures/" + Path(textures[role]["path"]).name
            if fields.get("map_Kd") != [expected] or preflight.digest(path.parent / expected) != textures[role]["sha256"]:
                raise ValueError(f"{role}: texture reference or bytes changed")
        elif "map_Kd" in fields:
            raise ValueError(f"{role}: unexpected texture reference")


def export(output=OUTPUT):
    output = Path(output).resolve()
    if not output.is_relative_to((ROOT / "Saved").resolve()) or output == (ROOT / "Saved").resolve():
        raise ValueError("Choose a new source-art folder under Saved")
    output.mkdir(parents=True, exist_ok=False)
    source_code_hashes = {path.relative_to(ROOT).as_posix(): preflight.digest(path) for path in CODE_INPUTS}
    roles, palette_used = set(), {}

    def sink(side, planned, bay, palette):
        roles.update(bay.roles)
        palette_used.update({role: palette[role] for role in bay.roles})
        name = f'SM_GLMedieval_NorthMarketDetail_{side}_{planned["id"].rsplit("_", 1)[-1][:8]}.obj'
        path = output / name
        written_uvs = write_obj(path, bay, palette)
        checked = verify_obj(path, bay, palette)
        if checked["uv_corners"] != written_uvs:
            raise ValueError(f"{name}: UV count changed on readback")
        return {"file": name, "sha256": preflight.digest(path), "readback": checked}

    report = preflight.generate_preflight(sink)
    material = write_materials(output, palette_used, roles, report["textures"])
    verify_materials(material, palette_used, roles, report["textures"])
    if any(preflight.digest(ROOT / path) != expected for path, expected in source_code_hashes.items()):
        raise RuntimeError("Generator source changed during export; source-art folder is incomplete")
    if preflight.digest(preflight.TILE) != report["source_glb_sha256"]:
        raise RuntimeError("Survey source tile changed during export; source-art folder is incomplete")
    for side, hashes in report["inputs"].items():
        for field, suffix in (("candidate", "candidate"), ("plan", "plan")):
            path = preflight.SURVEY / f"north_market_{side}_{suffix}_20261115.json"
            if preflight.digest(path) != hashes[field]:
                raise RuntimeError(f"{side} {field} changed during export")
        if hashes["override"] is not None and preflight.digest(
                preflight.SURVEY / "north_market_east_style_override_20261115.json") != hashes["override"]:
            raise RuntimeError("East style override changed during export")
    report.update({"status": "unreviewed_detailed_obj_source", "runtime_activation_eligible": False,
                   "source_ue_section_mapping": "unverified", "code_input_sha256": source_code_hashes,
                   "material_file": material.name, "material_sha256": preflight.digest(material),
                   "mesh_contract": "OBJ local metres; +X entrance, +Z up; pivots and yaw are in this manifest.",
                   "limits": ["Detailed source polygons are preserved as n-gons; Blender tessellation may differ.",
                              "Python mathutils/ear-clipping shim differs from Blender and has not been round-tripped.",
                              "Face normals follow original Bay winding; Blender's bmesh normal recalculation was not run.",
                              "UVs mirror dominant-normal projection but exact Blender UV identity is not verified.",
                              "No FBX, collision, Unreal import, source-section mapping or gameplay validation."]})
    with (output / "detailed_obj_manifest.json").open("x", encoding="utf-8", newline="\n") as out:
        json.dump(report, out, indent=2)
        out.write("\n")
    return report


if __name__ == "__main__":
    result = export()
    print(f'Exported and read back {len(result["buildings"])} unreviewed detailed source OBJ files: {OUTPUT}')
