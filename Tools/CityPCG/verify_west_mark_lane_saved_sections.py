"""Read narrowly pinned saved section/material metadata; never opens Unreal.

This is deliberately not a general-purpose UE package reader. The verified
bytes are useful evidence about two saved files, not their loaded runtime state.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct


PROJECT = Path(__file__).resolve().parents[2]
SLOTS = ("GL_Facade", "GL_Roof", "GL_Road", "GL_Park", "GL_Water", "GL_CentralFacade")
MATERIAL_ROOT = "/Game/GrayLondon/Geodata/Materials/"
CENTRAL = MATERIAL_ROOT + "CentralSelective/M_CentralStoneWindows"
SOURCE_REFS = ("/Engine/EngineMaterials/WorldGridMaterial",) * 5 + (CENTRAL,)
REPLACEMENT_REFS = tuple(MATERIAL_ROOT + name for name in (
    "M_ResidentialFacadeTrial", "M_OSM_Roof", "M_OSM_Road", "M_OSM_Park", "M_WaterBroadTrial")) + (CENTRAL,)
SPECS = {
    "source": {
        "path": "Content/GrayLondon/Geodata/Tiles/Tile_p03_p00.uasset",
        "size": 1704433,
        "sha256": "fad42a2a33c47b14298e5206fbbd3f3e60b3124ea8316f4f35077539824673f1",
        "summary": 340, "name_count": 141, "name_start": 621, "name_end": 4396,
        "name_sha256": "524b6a0cf66bf0d57f542e48d4863223da459702ae3e8cc0a46f27dcb404a12d",
        "import_count": 14, "import_start": 4449, "export_start": 5009,
        "root": 76824, "materials": 77987, "refs": SOURCE_REFS,
    },
    "replacement": {
        "path": "Content/GrayLondon/MedievalOpening/WholeBuildings/WestMarkLane/SM_GLMedieval_WestBlockTile.uasset",
        "size": 1098621,
        "sha256": "e138c7f6c31e251c96b377c06cf43193ee44a2aba9576424e59b85a079d2ff63",
        "summary": 385, "name_count": 149, "name_start": 666, "name_end": 4832,
        "name_sha256": "363efd667ab5507e71400c6188dded1d2397e460373432568357cb37dc6b2c31",
        "import_count": 22, "import_start": 4885, "export_start": 5765,
        "root": 34717, "materials": 35880, "refs": REPLACEMENT_REFS,
    },
}


class Reader:
    def __init__(self, data):
        self.data = data
        self.names = []

    def take(self, pos, size, limit=None):
        end = len(self.data) if limit is None else min(limit, len(self.data))
        if pos < 0 or size < 0 or pos > end or size > end - pos:
            raise ValueError("Truncated or out-of-bounds serialized data")
        return self.data[pos:pos + size]

    def integer(self, pos, limit=None, unsigned=False):
        return struct.unpack("<I" if unsigned else "<i", self.take(pos, 4, limit))[0]

    def string(self, pos, limit):
        length = self.integer(pos, limit)
        pos += 4
        if length == 0:
            return "", pos
        size = length if length > 0 else -2 * length
        if size > 16384:
            raise ValueError("Serialized string too long")
        raw = self.take(pos, size, limit)
        if length > 0:
            if raw[-1:] != b"\0" or b"\0" in raw[:-1]:
                raise ValueError("Invalid UTF-8 string terminator")
            value = raw[:-1].decode("utf-8")
        else:
            if raw[-2:] != b"\0\0":
                raise ValueError("Invalid UTF-16 string terminator")
            value = raw[:-2].decode("utf-16le")
            if "\0" in value:
                raise ValueError("Embedded UTF-16 null")
        return value, pos + size

    def fname(self, pos, limit):
        index, number = struct.unpack("<ii", self.take(pos, 8, limit))
        if not 0 <= index < len(self.names) or number != 0:
            raise ValueError("Invalid or numbered serialized name")
        return self.names[index], pos + 8

    def tag(self, pos, limit):
        start = pos
        name, pos = self.fname(pos, limit)
        if name == "None":
            return {"name": name, "start": start, "end": pos}
        remaining, nodes = 1, []
        while remaining:
            typename, pos = self.fname(pos, limit)
            children = self.integer(pos, limit)
            pos += 4
            if not 0 <= children <= 4 or len(nodes) >= 10:
                raise ValueError("Invalid tagged-property type tree")
            nodes.append((typename, children))
            remaining += children - 1
        size = self.integer(pos, limit)
        flags = self.take(pos + 4, 1, limit)[0]
        pos += 5
        if flags & ~0x11:
            raise ValueError("Unsupported tagged-property flags")
        index = self.integer(pos, limit) if flags & 1 else 0
        pos += 4 if flags & 1 else 0
        if index < 0:
            raise ValueError("Negative static array index")
        self.take(pos, size, limit)
        return {"name": name, "start": start, "type": nodes, "size": size,
                "flags": flags, "index": index, "value": pos, "end": pos + size}

    def fields(self, pos, limit):
        result = {}
        while True:
            item = self.tag(pos, limit)
            pos = item["end"]
            if item["name"] == "None":
                return result, pos
            key = (item["name"], item["index"])
            if key in result:
                raise ValueError(f"Duplicate tagged property: {key}")
            result[key] = item
            if len(result) > 32:
                raise ValueError("Too many tagged fields")


def expect(tag, name, tree, size, flags=0, index=0):
    if (tag.get("name") != name or tag.get("type") != tree or tag.get("size") != size or
            tag.get("flags") != flags or tag.get("index") != index):
        raise ValueError(f"Unexpected tag/type/size/flags for {name}")


def initialize(data, spec):
    r = Reader(data)
    if len(data) != spec["size"]:
        raise ValueError("Pinned package size differs")
    if struct.unpack("<Iiiiii", r.take(0, 24)) != (0x9e2a83c1, -9, 864, 522, 1018, 0):
        raise ValueError("Unexpected UE package version")
    custom = r.integer(48)
    if custom != 12:
        raise ValueError("Unexpected custom-version table count")
    r.take(52, custom * 20)
    _, summary = r.string(52 + custom * 20, len(data))
    if summary != spec["summary"]:
        raise ValueError("Unexpected package summary position")
    flags, count, start = struct.unpack("<iii", r.take(summary, 12))
    if (flags, count, start) != (0, spec["name_count"], spec["name_start"]):
        raise ValueError("Unexpected package name-table header")
    pos = start
    for _ in range(count):
        value, pos = r.string(pos, spec["name_end"])
        r.take(pos, 4, spec["name_end"])  # UE's two serialized name hashes
        pos += 4
        if not value or value in r.names:
            raise ValueError("Empty or duplicate name-table entry")
        r.names.append(value)
    if pos != spec["name_end"] or hashlib.sha256(r.take(start, pos-start)).hexdigest() != spec["name_sha256"]:
        raise ValueError("Pinned name table differs")
    return r, summary


def imports(reader, summary, spec):
    _, pos = reader.string(summary + 20, spec["name_start"])
    values = struct.unpack("<6i", reader.take(pos, 24, spec["name_start"]))
    expected = (0, spec["name_end"], 6, spec["export_start"], spec["import_count"], spec["import_start"])
    if values != expected or spec["import_start"] + spec["import_count"] * 40 != spec["export_start"]:
        raise ValueError("Unexpected import table bounds or count")
    result = []
    for number in range(spec["import_count"]):
        pos = spec["import_start"] + number * 40
        package, pos = reader.fname(pos, spec["export_start"])
        cls, pos = reader.fname(pos, spec["export_start"])
        outer = reader.integer(pos, spec["export_start"])
        obj, pos = reader.fname(pos + 4, spec["export_start"])
        package_name, pos = reader.fname(pos, spec["export_start"])
        optional = reader.integer(pos, spec["export_start"])
        if not -spec["import_count"] <= outer <= 0 or package_name != "None" or optional != 0:
            raise ValueError("Unexpected import outer/package/optional value")
        result.append({"class_package": package, "class_name": cls, "outer": outer, "object": obj})
    return result


def resolve_material(ref, table):
    if not -len(table) <= ref < 0:
        raise ValueError("Material is not a valid import reference")
    item = table[-ref - 1]
    if (item["class_package"], item["class_name"]) != ("/Script/Engine", "Material") or item["outer"] >= 0:
        raise ValueError("Material reference has an unexpected class or outer")
    package = table[-item["outer"] - 1]
    if ((package["class_package"], package["class_name"], package["outer"]) !=
            ("/Script/CoreUObject", "Package", 0) or package["object"].rsplit("/", 1)[-1] != item["object"]):
        raise ValueError("Material package/object relationship is inconsistent")
    return package["object"]


def section_map(reader, spec):
    root = reader.tag(spec["root"], len(reader.data))
    expect(root, "SectionInfoMap", [("StructProperty", 1), ("MeshSectionInfoMap", 1), ("/Script/Engine", 0)], 1085)
    inner = reader.tag(root["value"], root["end"])
    expect(inner, "Map", [("MapProperty", 2), ("UInt32Property", 0), ("StructProperty", 1),
                          ("MeshSectionInfo", 1), ("/Script/Engine", 0)], 1004)
    removed = reader.integer(inner["value"], inner["end"])
    count = reader.integer(inner["value"] + 4, inner["end"])
    if (removed, count) != (0, 6):
        raise ValueError("Unexpected removed keys or section count")
    pos, rows = inner["value"] + 8, {}
    expected_fields = {"MaterialIndex", "bEnableCollision", "bCastShadow", "bVisibleInRayTracing",
                       "bAffectDistanceFieldLighting", "bForceOpaque"}
    for _ in range(count):
        key = reader.integer(pos, inner["end"], unsigned=True)
        pos += 4
        if key in rows:
            raise ValueError("Duplicate section-map key")
        fields, pos = reader.fields(pos, inner["end"])
        if set(fields) != {(name, 0) for name in expected_fields}:
            raise ValueError("Unexpected section fields")
        item = fields[("MaterialIndex", 0)]
        expect(item, "MaterialIndex", [("IntProperty", 0)], 4)
        material = reader.integer(item["value"], item["end"])
        for name in expected_fields - {"MaterialIndex"}:
            item = fields[(name, 0)]
            expect(item, name, [("BoolProperty", 0)], 0, 0 if name == "bForceOpaque" else 16)
        lod, section = (key >> 16) & 0xffff, key & 0xffff
        if lod != 0 or section not in range(6) or material != section:
            raise ValueError("Unexpected saved LOD/section/material mapping")
        rows[key] = {"lod": lod, "section": section, "material_index": material, "collision_enabled": True}
    if pos != inner["end"] or set(rows) != set(range(6)):
        raise ValueError("Section map payload or keys are incomplete")
    terminator = reader.tag(inner["end"], root["end"])
    if terminator["name"] != "None" or terminator["end"] != root["end"]:
        raise ValueError("SectionInfoMap struct terminator is missing")
    adjacent = reader.tag(root["end"], spec["materials"])
    expect(adjacent, "LightmapUVVersion", [("IntProperty", 0)], 4)
    if adjacent["end"] != spec["materials"]:
        raise ValueError("Unexpected top-level property sequence")
    return [rows[i] for i in range(6)]


def uv_channel_data(reader, item):
    expect(item, "UVChannelData", [("StructProperty", 1), ("MeshUVChannelInfo", 1), ("/Script/Engine", 0)], 186)
    fields, end = reader.fields(item["value"], item["end"])
    expected = {("bInitialized", 0), ("bOverrideDensities", 0)} | {("LocalUVDensities", i) for i in range(4)}
    if end != item["end"] or set(fields) != expected:
        raise ValueError("UV-channel tagged fields or terminator differ")
    expect(fields[("bInitialized", 0)], "bInitialized", [("BoolProperty", 0)], 0, 16)
    expect(fields[("bOverrideDensities", 0)], "bOverrideDensities", [("BoolProperty", 0)], 0)
    for i in range(4):
        field = fields[("LocalUVDensities", i)]
        expect(field, "LocalUVDensities", [("FloatProperty", 0)], 4, 0 if i == 0 else 1, i)
        value = struct.unpack("<f", reader.take(field["value"], 4, field["end"]))[0]
        if not math.isfinite(value):
            raise ValueError("Non-finite serialized UV density")


def static_materials(reader, spec, table):
    root = reader.tag(spec["materials"], len(reader.data))
    expect(root, "StaticMaterials", [("ArrayProperty", 1), ("StructProperty", 1),
                                     ("StaticMaterial", 1), ("/Script/Engine", 0)], 2206)
    if reader.integer(root["value"], root["end"]) != 6:
        raise ValueError("Unexpected static material count")
    pos, result = root["value"] + 4, []
    for index, expected_slot in enumerate(SLOTS):
        fields, pos = reader.fields(pos, root["end"])
        names = ("MaterialInterface", "MaterialSlotName", "ImportedMaterialSlotName",
                 "UVChannelData", "OverlayMaterialInterface")
        if set(fields) != {(name, 0) for name in names}:
            raise ValueError("Unexpected static material fields")
        for name in ("MaterialSlotName", "ImportedMaterialSlotName"):
            field = fields[(name, 0)]
            expect(field, name, [("NameProperty", 0)], 8)
            actual, end = reader.fname(field["value"], field["end"])
            if end != field["end"] or actual != expected_slot:
                raise ValueError("Unexpected saved material slot name")
        field = fields[("MaterialInterface", 0)]
        expect(field, "MaterialInterface", [("ObjectProperty", 0)], 4)
        ref = reader.integer(field["value"], field["end"])
        path = resolve_material(ref, table)
        if path != spec["refs"][index]:
            raise ValueError("Unexpected saved material reference")
        field = fields[("OverlayMaterialInterface", 0)]
        expect(field, "OverlayMaterialInterface", [("ObjectProperty", 0)], 4)
        if reader.integer(field["value"], field["end"]) != 0:
            raise ValueError("Unexpected overlay material")
        uv_channel_data(reader, fields[("UVChannelData", 0)])
        result.append({"index": index, "slot": expected_slot, "imported_slot": expected_slot,
                       "saved_material_path": path})
    if pos != root["end"]:
        raise ValueError("Static material array terminators or bounds differ")
    # Bound the contiguous top-level continuation and its final None. The
    # unrelated native ExtendedBounds payload is deliberately not interpreted.
    tail = (("LightmapUVDensity", [("FloatProperty", 0)], 4),
            ("AssetImportData", [("ObjectProperty", 0)], 4),
            ("ExtendedBounds", [("StructProperty", 1), ("BoxSphereBounds", 1), ("/Script/CoreUObject", 0)], 187))
    for name, tree, size in tail:
        item = reader.tag(pos, len(reader.data))
        expect(item, name, tree, size)
        pos = item["end"]
    if reader.tag(pos, len(reader.data))["name"] != "None":
        raise ValueError("Top-level property terminator is missing")
    return result


def parse_structure(data, spec):
    """Testable structure parser; this alone is not authenticated evidence."""
    reader, summary = initialize(data, spec)
    table = imports(reader, summary, spec)
    return section_map(reader, spec), static_materials(reader, spec, table)


def verify_bytes(data, spec):
    if hashlib.sha256(data).hexdigest() != spec["sha256"]:
        raise ValueError("Saved uasset does not match its pinned SHA-256")
    sections, materials = parse_structure(data, spec)
    return {"status": "verified_saved_file_only", "asset": spec["path"], "sha256": spec["sha256"],
            "package_versions": {"legacy": -9, "ue3": 864, "ue4": 522, "ue5": 1018, "licensee": 0},
            "sections": sections, "materials": materials,
            "limits": ["No loaded section/render binding or component material overrides checked.",
                       "No asset geometry, UVs, actor transform, collision behavior, or gameplay checked."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", choices=("source", "replacement", "both"), default="both")
    args = parser.parse_args()
    chosen = list(SPECS) if args.asset == "both" else [args.asset]
    result = {name: verify_bytes((PROJECT / SPECS[name]["path"]).read_bytes(), SPECS[name]) for name in chosen}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
