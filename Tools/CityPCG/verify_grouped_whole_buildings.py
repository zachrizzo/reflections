"""Independently read back oriented grouped GLB corners against source FBXs."""

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import re
import struct

from extract_tile_frontages import accessor, read_glb
from group_whole_buildings import PROJECT_ROOT, mask_sha, resolve_project_file
from read_prepared_building_fbx import load_decoder, read_mesh
from subtract_building_shells import digest, indices, read_json


CELL = re.compile(r"Tile_[pm]\d{2}_[pm]\d{2}_x[pm]\d+_y[pm]\d+")


def decode_uv(document, binary, index):
    entry = document["accessors"][index]
    view = document["bufferViews"][entry["bufferView"]]
    if (entry["type"], entry["componentType"], view["buffer"]) != ("VEC2", 5126, 0):
        raise ValueError("Expected grouped float UV0 coordinates.")
    start = view["byteOffset"] + entry.get("byteOffset", 0)
    stride = view.get("byteStride", 8)
    return [struct.unpack_from("<2f", binary, start + i * stride) for i in range(entry["count"])]


def verify(bundle, rollout, parse, *, project_root=PROJECT_ROOT):
    manifest = read_json(bundle / "grouped_buildings.json")
    if manifest.get("schema") != 2 or manifest.get("source_paths") != "project_relative_posix":
        raise ValueError("Expected a portable schema 2 grouped bundle. Regenerate the older manifest.")
    audited = rollout["cumulative_masks"]
    barriers = manifest["tile_barriers"]
    if manifest["status"] != "offline_geometry_only" or barriers.keys() != audited.keys():
        raise ValueError("The grouped bundle and reviewed report have different tile barriers.")
    seen_cells, seen_buildings = defaultdict(list), defaultdict(list)
    source_sections = 0
    stats = {"cells": len(manifest["cells"]), "triangles": 0, "checked_corners": 0, "grouped_sections": 0,
             "max_position_error_m": 0., "max_normal_vector_error": 0., "max_uv_error": 0.}
    for name, cell in manifest["cells"].items():
        tile = cell["tile"]
        if not CELL.fullmatch(name):
            raise ValueError(f"{name!r}: invalid grouped cell name.")
        seen_cells[tile].append(name)
        selected = {row["id"]: row for row in audited[tile]["buildings"]}
        path = bundle / f"{name}.glb"
        if path.parent != bundle or path.resolve().parent != bundle.resolve():
            raise ValueError(f"{name!r}: grouped GLB is outside the bundle.")
        if path.name != cell["file"] or digest(path.read_bytes()) != cell["sha256"]:
            raise ValueError(f"{name}: wrong grouped mesh or digest.")
        document, binary = read_glb(path)
        streams = {}
        for index, primitive in enumerate(document["meshes"][0]["primitives"]):
            material = document["materials"][primitive["material"]]["name"]
            if material in streams:
                raise ValueError(f"{name}: material appears in more than one primitive.")
            attrs = primitive["attributes"]
            streams[material] = (indices(document, binary, index),
                                 accessor(document, binary, attrs["POSITION"], {("VEC3", 5126)}),
                                 accessor(document, binary, attrs["NORMAL"], {("VEC3", 5126)}),
                                 decode_uv(document, binary, attrs["TEXCOORD_0"]))
        if {row["slot"]: row["triangles"] * 3 for row in cell["sections"]} != {
                key: len(stream[0]) for key, stream in streams.items()}:
            raise ValueError(f"{name}: section readback does not match the bundle.")
        stats["grouped_sections"] += len(streams)
        section_end = defaultdict(int)
        ox, oy, oz = cell["origin_ue_m"]
        for record in cell["buildings"]:
            identifier = record["id"]
            seen_buildings[tile].append(identifier)
            if record["survey"] != selected[identifier]:
                raise ValueError(f"{identifier}: face or footprint provenance changed.")
            kit_path = resolve_project_file(project_root, record["kit"], ".json")
            canonical = resolve_project_file(project_root, record["canonical_fbx"], ".fbx")
            source = resolve_project_file(project_root, record["prepared_fbx"], ".fbx")
            spec = read_json(kit_path)["buildings"][identifier]
            if (record["world_pivot_m"], record["yaw_deg"], record["footprint_local_m"]) != (
                    spec["world_pivot_m"], spec["yaw_deg"], spec["footprint_local_m"]):
                raise ValueError(f"{identifier}: bundle transform differs from the original kit.")
            if (digest(canonical.read_bytes()) != record["canonical_sha256"]
                    or digest(source.read_bytes()) != record["prepared_sha256"]):
                raise ValueError(f"{identifier}: canonical or prepared source FBX changed.")
            mesh = read_mesh(source, parse)
            source_sections += len(mesh.materials)
            by_material = defaultdict(list)
            for face_index, slot_index in enumerate(mesh.face_materials):
                by_material[mesh.materials[slot_index]].append(face_index)
            px, py, pz = spec["world_pivot_m"]
            (fx, fy), (rx, ry) = spec["axis_x_world_xy"], spec["axis_y_world_xy"]
            if by_material.keys() != record["face_ranges_by_material"].keys():
                raise ValueError(f"{identifier}: output is missing a source material range.")
            for material, face_ids in by_material.items():
                ranges = record["face_ranges_by_material"][material]
                start, count = ranges["first_triangle"], ranges["triangles"]
                if start != section_end[material] or count != len(face_ids):
                    raise ValueError(f"{identifier}: the source face range is missing, duplicated or disordered.")
                faces, dst_position, dst_normal, dst_uv = streams[material]
                section_end[material] += count
                if section_end[material] * 3 > len(faces):
                    raise ValueError(f"{identifier}: face range exceeds its material section.")
                for face_number, source_face in enumerate(face_ids):
                    for corner in range(3):
                        src_corner = source_face * 3 + corner
                        dst_vertex = faces[(start + face_number) * 3 + corner]
                        x, y, z = mesh.positions[mesh.corner_vertices[src_corner]]
                        a, b, c = dst_position[dst_vertex]
                        position_error = math.dist((px + x * fx - y * rx, py + x * fy - y * ry, pz + z),
                                                   (ox + a, oy + c, oz + b))
                        nx, ny, nz = mesh.normals[src_corner]
                        norm = math.hypot(nx, ny, nz)
                        expected = ((nx * fx - ny * rx) / norm, (nx * fy - ny * ry) / norm, nz / norm)
                        a, b, c = dst_normal[dst_vertex]
                        normal_error = math.dist(expected, (a, c, b))
                        u, v = dst_uv[dst_vertex]
                        uv_error = math.dist(mesh.uv0[src_corner], (u, 1. - v))
                        if position_error > 1e-4 or normal_error > 1e-5 or uv_error > 1e-5:
                            raise ValueError(f"{identifier} {material} triangle {source_face}, corner {corner}: "
                                             f"world position={position_error}, normal={normal_error}, UV={uv_error}")
                        stats["checked_corners"] += 1
                        stats["max_position_error_m"] = max(stats["max_position_error_m"], position_error)
                        stats["max_normal_vector_error"] = max(stats["max_normal_vector_error"], normal_error)
                        stats["max_uv_error"] = max(stats["max_uv_error"], uv_error)
                stats["triangles"] += count
        if any(section_end[key] * 3 != len(values[0]) for key, values in streams.items()):
            raise ValueError(f"{name}: extra output triangles lack building provenance.")
    for tile, barrier in barriers.items():
        mask = audited[tile]
        expected_buildings = sorted(row["id"] for row in mask["buildings"])
        if (barrier["source_tile_asset"] != mask["source_tile_asset"] or
                barrier["source_origin_m"] != mask["source_origin_m"] or
                barrier["source_export_sha256"] != mask["source_export_sha256"] or
                barrier["cumulative_mask_sha256"] != mask_sha(mask) or
                sorted(seen_cells[tile]) != sorted(barrier["required_cells"]) or
                expected_buildings != sorted(seen_buildings[tile]) or
                expected_buildings != barrier["required_building_ids"]):
            raise ValueError(f"{tile}: incomplete or inconsistent rollback barrier.")
    return {**stats, "source_sections": source_sections, "buildings": sum(map(len, seen_buildings.values())),
            "status": "offline_geometry_only"}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("bundle", type=Path)
    cli.add_argument("rollout", type=Path)
    cli.add_argument("--fbx-decoder-dir", type=Path, required=True)
    cli.add_argument("--project-root", type=Path, default=PROJECT_ROOT, help="Checkout containing the referenced source files")
    args = cli.parse_args()
    print(json.dumps(verify(args.bundle, read_json(args.rollout), load_decoder(args.fbx_decoder_dir),
                            project_root=args.project_root), indent=2))


if __name__ == "__main__":
    main()
