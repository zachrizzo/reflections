"""Write an import copy with a distinct slot name for each Unreal tile primitive."""

import argparse
from copy import deepcopy
from pathlib import Path

from extract_tile_frontages import read_glb
from subtract_building_shells import digest, indices, read_json, write_glb


def write_import_copy(filtered_glb, audit_file, destination):
    if len({path.resolve() for path in (filtered_glb, audit_file, destination)}) != 3:
        raise ValueError("Choose separate derivative, audit, and import files.")
    audit = read_json(audit_file)
    if not audit["embedded_materials_unchanged"] or digest(filtered_glb.read_bytes()) != audit["derivative_sha256"]:
        raise ValueError("The input is not the verified filtered tile.")
    original, binary = read_glb(filtered_glb)
    document = deepcopy(original)
    inputs = original["meshes"][0]["primitives"]
    outputs = document["meshes"][0]["primitives"]
    slots = audit["primitives"]
    names = [slot["unreal_slot"] for slot in slots]
    if len(slots) != len(inputs) or len(set(names)) != len(names):
        raise ValueError("The input primitives do not map to unique named Unreal slots.")
    materials = []
    for index, (slot, source, target) in enumerate(zip(slots, inputs, outputs)):
        if slot["index"] != index or source["material"] != slot["embedded_material_index"]:
            raise ValueError(f"The verified section mapping no longer matches {slot['unreal_slot']}.")
        material = deepcopy(original["materials"][source["material"]])
        material["name"] = slot["unreal_slot"]
        materials.append(material)
        target["material"] = index
    document["materials"] = materials
    write_glb(destination, document, bytearray(binary))
    checked, saved_binary = read_glb(destination)
    if (binary != saved_binary or checked != document or
            any(indices(checked, saved_binary, index) != indices(original, binary, index)
                for index in range(len(inputs)))):
        raise RuntimeError("The slot import copy changed filtered geometry.")
    return names


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filtered_glb", type=Path)
    parser.add_argument("audit_file", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print("Material slots:", ", ".join(write_import_copy(args.filtered_glb, args.audit_file, args.destination)))


if __name__ == "__main__":
    main()
