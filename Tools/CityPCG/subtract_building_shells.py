"""Remove reviewed wall and roof faces from an offline Gray London GLB copy."""

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct

from extract_building_shells import faces
from extract_tile_frontages import accessor, read_glb

INDEX_TYPES = {5121: "B", 5123: "H", 5125: "I"}
FACE_ADDRESS_FIELDS = (
    ("ordinary_wall_primitive", "source_wall_faces_by_edge", "wall_triangle_signature_by_edge"),
    ("roof_primitive", "source_roof_faces", "roof_triangle_signatures"),
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def triangle_signature(triangle):
    return digest(json.dumps(sorted(triangle), separators=(",", ":")).encode("ascii"))[:20]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def flatten(groups):
    return [entry for group in groups for entry in group]


def indices(document, blob, primitive):
    address = document["meshes"][0]["primitives"][primitive]["indices"]
    supported = {("SCALAR", kind) for kind in INDEX_TYPES}
    return tuple(item[0] for item in accessor(document, blob, address, supported))


def reviewed_faces(document, blob, candidate):
    origin = candidate["source_origin_m"]
    buildings = candidate["buildings"]
    if not buildings or len({item["id"] for item in buildings}) != len(buildings):
        raise ValueError("Expected unique reviewed building IDs.")
    selected = {}
    counts = {item["id"]: {} for item in buildings}
    for primitive_field, ordinal_field, signature_field in FACE_ADDRESS_FIELDS:
        primitive = candidate[primitive_field]
        source = faces(document, blob, primitive, origin)
        signatures = tuple(triangle_signature(triangle) for triangle in source)
        frequencies = Counter(signatures)
        blocked = set()
        for item in buildings:
            ordinals = item[ordinal_field]
            expected = item[signature_field]
            if primitive_field == "ordinary_wall_primitive":
                if len(ordinals) != len(expected) or any(
                        len(edge) != 2 or len(signatures) != 2 for edge, signatures in zip(ordinals, expected)):
                    raise ValueError(f"Invalid wall-edge triangle pairs for {item['id']}.")
                ordinals, expected = flatten(ordinals), flatten(expected)
            if not ordinals or len(ordinals) != len(expected):
                raise ValueError(f"Missing triangle signature evidence for {item['id']}.")
            for ordinal, signature in zip(ordinals, expected):
                if type(ordinal) is not int or not 0 <= ordinal < len(source) or ordinal in blocked:
                    raise ValueError(f"Ineligible or duplicate triangle {primitive}:{ordinal}.")
                if signatures[ordinal] != signature or frequencies[signature] != 1:
                    raise ValueError(f"Triangle {primitive}:{ordinal} no longer has its unique reviewed geometry.")
                blocked.add(ordinal)
            counts[item["id"]][str(primitive)] = len(ordinals)
        selected[primitive] = blocked
    if len(selected) != len(FACE_ADDRESS_FIELDS):
        raise ValueError("Wall and roof must be separate primitives.")
    return selected, counts


def append_indices(document, binary, primitive, retained):
    record = document["meshes"][0]["primitives"][primitive]
    template = document["accessors"][record["indices"]]
    encoded = struct.pack(f"<{len(retained)}{INDEX_TYPES[template['componentType']]}", *retained)
    binary.extend(b"\0" * (-len(binary) % 4))
    view = len(document["bufferViews"])
    document["bufferViews"].append({"buffer": 0, "byteOffset": len(binary), "byteLength": len(encoded),
                                   "target": 34963})
    binary.extend(encoded)
    record["indices"] = len(document["accessors"])
    document["accessors"].append({"bufferView": view, "componentType": template["componentType"],
                                 "count": len(retained), "type": "SCALAR"})


def write_glb(path, document, binary):
    doc = json.dumps(document, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    doc += b" " * (-len(doc) % 4)
    binary.extend(b"\0" * (-len(binary) % 4))
    total_bytes = 28 + len(doc) + len(binary)
    with path.open("xb") as stream:
        stream.write(struct.pack("<4sIII4s", b"glTF", 2, total_bytes, len(doc), b"JSON"))
        stream.write(doc)
        stream.write(struct.pack("<I4s", len(binary), b"BIN\0"))
        stream.write(binary)


def subtract(source, metadata, candidate_path, destination, report_path):
    paths = [source, metadata, candidate_path, destination, report_path]
    if len({path.resolve() for path in paths}) != len(paths):
        raise ValueError("Choose separate source, derivative, and report files.")
    if destination.exists() or report_path.exists():
        raise FileExistsError("Choose fresh derivative and report paths.")
    candidate, tile = read_json(candidate_path), read_json(metadata)
    physical_sha = digest(source.read_bytes())
    if (physical_sha != candidate["source_export_sha256"] or candidate["source_tile"] != tile["tile"] or
            candidate["source_origin_m"] != tile["origin_m"] or candidate["source_tile_asset"] != tile["asset"]):
        raise ValueError("The candidate targets a different source geometry export.")
    document, original_binary = read_glb(source)
    primitive_count = len(document["meshes"][0]["primitives"])
    slot_names = list(tile["primitives"])
    if primitive_count != len(slot_names) or len(document["buffers"]) != 1:
        raise ValueError("Source primitive and material slot metadata differ.")
    selected, buildings = reviewed_faces(document, original_binary, candidate)
    protected = {int(index): slot for index, slot in candidate["untouched_primitives"].items()}
    if (set(selected) & protected.keys() or set(selected) | protected.keys() != set(range(primitive_count)) or
            any(slot_names[index] != name for index, name in protected.items())):
        raise ValueError("The reviewed and protected primitives do not match the source slots.")

    modified = deepcopy(document)
    binary = bytearray(original_binary)
    originals, remaining = {}, {}
    for primitive, slot in enumerate(slot_names):
        before = indices(document, original_binary, primitive)
        if len(before) != 3 * tile["primitives"][slot]:
            raise ValueError(f"Source face count no longer matches slot {slot}.")
        blocked = selected.get(primitive, set())
        after = tuple(value for start in range(0, len(before), 3) if start // 3 not in blocked
                      for value in before[start:start + 3])
        if not after:
            raise ValueError(f"Removal would empty slot {slot}.")
        originals[primitive], remaining[primitive] = before, after
        if blocked:
            append_indices(modified, binary, primitive, after)
    modified["buffers"][0]["byteLength"] = len(binary)
    write_glb(destination, modified, binary)

    result_doc, result_binary = read_glb(destination)
    if result_doc != modified or result_binary[:len(original_binary)] != original_binary:
        raise RuntimeError("Derivative did not preserve the original vertex, UV, normal, and image data.")
    before_defs = document["meshes"][0]["primitives"]
    after_defs = result_doc["meshes"][0]["primitives"]
    for primitive, (before, after) in enumerate(zip(before_defs, after_defs)):
        if ({k: v for k, v in before.items() if k != "indices"} !=
                {k: v for k, v in after.items() if k != "indices"} or
                indices(result_doc, result_binary, primitive) != remaining[primitive]):
            raise RuntimeError(f"Derivative changed unintended geometry or attributes in primitive {primitive}.")
        if primitive in protected and before != after:
            raise RuntimeError(f"Protected primitive {primitive} changed.")
    if result_doc["materials"] != document["materials"] or digest(source.read_bytes()) != physical_sha:
        raise RuntimeError("Source or embedded material identity changed.")
    report = {
        "source": str(source.resolve()),
        "original_sha256": physical_sha,
        "derivative": str(destination.resolve()),
        "derivative_sha256": digest(destination.read_bytes()),
        "original_binary_prefix_unchanged": True,
        "embedded_materials_unchanged": True,
        "source_actor_location_m": tile["origin_m"],
        "reviewed_buildings": buildings,
        "removed_face_ordinals": {str(index): sorted(values) for index, values in selected.items()},
        "primitives": [{"index": index, "unreal_slot": slot, "embedded_material_index": before_defs[index]["material"],
                        "source_triangles": len(originals[index]) // 3, "output_triangles": len(remaining[index]) // 3,
                        "unchanged": originals[index] == remaining[index]}
                       for index, slot in enumerate(slot_names)],
    }
    with report_path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "metadata", "candidate", "destination", "report"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    report = subtract(args.source, args.metadata, args.candidate, args.destination, args.report)
    print(f"Verified {sum(len(ids) for ids in report['removed_face_ordinals'].values())} removed triangles.")


if __name__ == "__main__":
    main()
