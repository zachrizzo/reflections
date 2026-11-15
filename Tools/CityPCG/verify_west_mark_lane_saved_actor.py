"""Verify one pinned source actor's saved references and relative location.

Read-only metadata evidence; this does not inspect the loaded editor actor.
"""

import hashlib
import json
import math
import struct

import verify_west_mark_lane_saved_sections as sections


PATH = ("Content/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/6/RK/"
        "40RMT8C5SHUKBGPOO36KRE.uasset")
SHA256 = "9995fe32db26fae742b16854360cf78bec66208aefa94ba899aa71f087ae8937"
NAME_SHA256 = "df7a0b54eba8bbdec951dfbfb9fda5e7e39aab5c5f9a48e1870dd0a4178c7557"
MESH_PATH = "/Game/GrayLondon/Geodata/Tiles/Tile_p03_p00"


def initialize(data):
    reader = sections.Reader(data)
    if len(data) != 4461:
        raise ValueError("Pinned actor package size differs")
    if struct.unpack("<Iiiiii", reader.take(0, 24)) != (0x9e2a83c1, -9, 864, 522, 1018, 0):
        raise ValueError("Unexpected actor package version")
    if reader.integer(48) != 9:
        raise ValueError("Unexpected actor custom-version count")
    reader.take(52, 9 * 20)
    _, pos = reader.string(52 + 9 * 20, len(data))
    if pos != 324 or struct.unpack("<iii", reader.take(pos, 12)) != (16448, 44, 605):
        raise ValueError("Unexpected actor summary or name table")
    pos = 605
    for _ in range(44):
        value, pos = reader.string(pos, 1837)
        reader.take(pos, 4, 1837)
        pos += 4
        if not value or value in reader.names:
            raise ValueError("Empty or duplicated actor name")
        reader.names.append(value)
    if pos != 1837 or hashlib.sha256(reader.take(605, pos - 605)).hexdigest() != NAME_SHA256:
        raise ValueError("Pinned actor name table differs")
    return reader


def imports(reader):
    _, pos = reader.string(324 + 20, 605)
    expected = (0, 1837, 2, 2690, 20, 1890)
    if struct.unpack("<6i", reader.take(pos, 24, 605)) != expected or 1890 + 20 * 40 != 2690:
        raise ValueError("Unexpected actor import table bounds")
    table = []
    for i in range(20):
        pos = 1890 + i * 40
        class_package, pos = reader.fname(pos, 2690)
        class_name, pos = reader.fname(pos, 2690)
        outer = reader.integer(pos, 2690)
        obj, pos = reader.fname(pos + 4, 2690)
        package, pos = reader.fname(pos, 2690)
        optional = reader.integer(pos, 2690)
        if not -20 <= outer <= 0 or package != "None" or optional != 0:
            raise ValueError("Unexpected actor import outer/package/optional value")
        table.append({"class_package": class_package, "class_name": class_name, "outer": outer, "object": obj})
    return table


def resolve_mesh(ref, table):
    if not -len(table) <= ref < 0:
        raise ValueError("Saved mesh reference is not an import")
    item = table[-ref - 1]
    if (item["class_package"], item["class_name"]) != ("/Script/Engine", "StaticMesh") or item["outer"] >= 0:
        raise ValueError("Saved mesh import has unexpected class or outer")
    package = table[-item["outer"] - 1]
    if ((package["class_package"], package["class_name"], package["outer"]) !=
            ("/Script/CoreUObject", "Package", 0) or package["object"] != MESH_PATH or
            item["object"] != MESH_PATH.rsplit("/", 1)[-1]):
        raise ValueError("Saved mesh import points to the wrong package")
    return package["object"]


def native_relative_location(reader, pos, limit):
    name, pos = reader.fname(pos, limit)
    nodes = []
    for _ in range(3):
        typename, pos = reader.fname(pos, limit)
        count = reader.integer(pos, limit)
        pos += 4
        nodes.append((typename, count))
    if name != "RelativeLocation" or nodes != [("StructProperty", 1), ("Vector", 1), ("/Script/CoreUObject", 0)]:
        raise ValueError("Unexpected relative-location type tree")
    size = reader.integer(pos, limit)
    flag = reader.take(pos + 4, 1, limit)[0]
    pos += 5
    if size != 24 or flag != 8:
        raise ValueError("Unexpected native vector size or flags")
    value = struct.unpack("<3d", reader.take(pos, size, limit))
    if not all(map(math.isfinite, value)) or value != (300000.0, 0.0, 0.0):
        raise ValueError("Saved relative location differs")
    return value, pos + size


def parse_structure(data):
    """Test helper: this parser alone is not authenticated evidence."""
    reader = initialize(data)
    table = imports(reader)
    tag = reader.tag(4197, len(data))
    sections.expect(tag, "StaticMesh", [("ObjectProperty", 0)], 4)
    mesh = resolve_mesh(reader.integer(tag["value"], tag["end"]), table)
    tag = reader.tag(tag["end"], len(data))
    sections.expect(tag, "bUseDefaultCollision", [("BoolProperty", 0)], 0)
    tag = reader.tag(tag["end"], len(data))
    sections.expect(tag, "OverrideMaterials", [("ArrayProperty", 1), ("ObjectProperty", 0)], 24)
    if reader.integer(tag["value"], tag["end"]) != 5:
        raise ValueError("Unexpected override-material count")
    refs = [reader.integer(tag["value"] + 4 + i * 4, tag["end"]) for i in range(5)]
    materials = [sections.resolve_material(ref, table) for ref in refs]
    if tuple(materials) != sections.REPLACEMENT_REFS[:5]:
        raise ValueError("Saved actor override materials differ")
    location, end = native_relative_location(reader, tag["end"], len(data))
    terminal = reader.tag(end, len(data))
    if terminal["name"] != "None" or terminal["end"] != 4393:
        raise ValueError("Component property terminator is missing")
    return mesh, materials, location


def verify_bytes(data):
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError("Actor package does not match its pinned SHA-256")
    mesh, materials, location = parse_structure(data)
    return {"status": "verified_saved_file_only", "actor_package": PATH, "sha256": SHA256,
            "saved_static_mesh": mesh, "saved_override_materials": materials,
            "serialized_relative_location_cm": location,
            "limits": ["The five serialized overrides do not include a sixth entry.",
                       "Live actor identity, transform, loaded mesh and overrides are not verified.",
                       "Rotation and scale are not inferred; collision behavior and gameplay are unverified."]}


def main():
    data = (sections.PROJECT / PATH).read_bytes()
    print(json.dumps(verify_bytes(data), indent=2))


if __name__ == "__main__":
    main()
