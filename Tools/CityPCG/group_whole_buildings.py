"""Merge surveyed building geometry into material sections within spatial cells."""

import argparse
from collections import defaultdict
from dataclasses import dataclass
import json
import math
from pathlib import Path, PurePosixPath
import re
import struct
from tempfile import TemporaryDirectory

from read_prepared_building_fbx import load_decoder, material_definitions, read_mesh
from subtract_building_shells import digest, read_json, write_glb


TILE = re.compile(r"Tile_[pm]\d{2}_[pm]\d{2}")
MATERIAL = re.compile(r"M_GLMedieval_[A-Za-z0-9_]+")
MATERIAL_ROOT = "/Game/GrayLondon/MedievalOpening/Kit"
FOOTPRINT_TOLERANCE_M = .0015
PROJECT_ROOT = Path(__file__).resolve().parents[2]
WINDOWS_DEVICE = re.compile(r"^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9¹²³]|LPT[1-9¹²³])(?:\.|$)", re.I)
INVALID_PATH_CHAR = re.compile(r'[\\<>:"|?*\x00-\x1f]')


@dataclass
class Building:
    id: str
    tile: str
    shell: dict
    spec: dict
    manifest: Path
    canonical: Path
    prepared: Path
    bridge: dict


def mask_sha(mask):
    return digest(json.dumps(mask, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def resolve_project_file(root, reference, suffix):
    """Resolve a portable manifest reference without permitting scope escapes."""
    if not isinstance(reference, str) or INVALID_PATH_CHAR.search(reference):
        raise ValueError(f"Unsafe project-relative path: {reference!r}")
    relative = PurePosixPath(reference)
    if (relative.is_absolute() or relative.suffix.lower() != suffix
            or any(not part or part.rstrip(" .") != part or WINDOWS_DEVICE.match(part)
                   for part in reference.split("/"))):
        raise ValueError(f"Unsafe project-relative path: {reference!r}")
    root = root.resolve()
    path = root.joinpath(*relative.parts).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Project-relative path escapes the checkout: {reference!r}")
    return path


def project_reference(root, path, suffix):
    try:
        reference = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise ValueError(f"Input file is outside the portable checkout: {path}") from error
    resolve_project_file(root, reference, suffix)
    return reference


def rotated(x, y, yaw):
    angle = math.radians(yaw)
    c, s = math.cos(angle), math.sin(angle)
    return c * x - s * y, s * x + c * y


def verify_placement(spec, shell):
    pivot, yaw = spec["world_pivot_m"], spec["yaw_deg"]
    if (pivot != shell["origin_m"] or not math.isfinite(yaw) or len(pivot) != 3 or
            not all(math.isfinite(value) for value in pivot)):
        raise ValueError(f"{shell['id']}: mesh pivot differs from the surveyed ground origin.")
    for field, axis in (("axis_x_world_xy", (1, 0)), ("axis_y_world_xy", (0, 1))):
        if math.dist(rotated(*axis, yaw), spec[field]) > 1e-5:
            raise ValueError(f"{shell['id']}: yaw differs from the signed surveyed axes.")
    if math.dist(rotated(1, 0, yaw), shell["entry"]["outward"]) > 1e-5:
        raise ValueError(f"{shell['id']}: rotation points away from the surveyed entry.")
    corners = spec["footprint_local_m"]
    if len(corners) < 3 or len(corners) != len(shell["footprint"]):
        raise ValueError(f"{shell['id']}: mesh footprint corner count changed.")
    for local, surveyed in zip(corners, shell["footprint"]):
        xy = rotated(*local, yaw)
        actual = (pivot[0] + xy[0], pivot[1] + xy[1])
        if math.dist(actual, surveyed) > FOOTPRINT_TOLERANCE_M:
            raise ValueError(f"{shell['id']}: signed local footprint does not match the surveyed plot.")


def owned_file(manifest, relative, subfolder):
    location = (manifest.parent / relative).resolve()
    parent = (manifest.parent / subfolder).resolve()
    if location.parent != parent or location.suffix.lower() != ".fbx":
        raise ValueError(f"{manifest}: expected a direct FBX in {subfolder}.")
    return location


def collect(rollout, manifests, legacy_bridge=None):
    masks = rollout["cumulative_masks"]
    if rollout["status"] != "offline_only" or not masks:
        raise ValueError("Supply a rollout report with explicitly checked nonempty cumulative masks.")
    expected = {}
    for tile, mask in masks.items():
        row = rollout["tile_inventory"][tile]
        if (not TILE.fullmatch(tile) or mask["source_tile"] != tile or row["status"] != "inventoried"
                or row["source_sha256"] != mask["source_export_sha256"]
                or row["offline_mask_buildings"] != len(mask["buildings"])):
            raise ValueError(f"{tile}: incomplete source tile and mask preflight.")
        for shell in mask["buildings"]:
            if shell["id"] in expected:
                raise ValueError(f"Duplicate mask building {shell['id']}.")
            expected[shell["id"]] = (tile, shell)

    legacy = read_json(legacy_bridge) if legacy_bridge else {}
    buildings = {}
    for manifest in sorted(manifests):
        kit = read_json(manifest)
        for identifier, spec in kit["buildings"].items():
            if identifier not in expected or identifier in buildings:
                raise ValueError(f"Unexpected or duplicate building mesh {identifier}.")
            tile, shell = expected[identifier]
            if kit.get("source_tile", tile) != tile:
                raise ValueError(f"{identifier}: the mesh kit targets a different source tile.")
            bridge = spec.get("unreal_bridge", legacy.get(identifier))
            if not bridge:
                raise ValueError(f"{identifier}: missing prepared FBX bridge audit.")
            verify_placement(spec, shell)
            canonical = owned_file(manifest, spec["fbx"], "Source")
            prepared = (owned_file(manifest, bridge["fbx"], "UnrealSource") if "fbx" in bridge else
                        owned_file(legacy_bridge, f"Source/{canonical.name}", "Source"))
            if (canonical.name != prepared.name or digest(canonical.read_bytes()) != bridge["canonical_sha256"]
                    or digest(prepared.read_bytes()) != bridge["prepared_sha256"]):
                raise ValueError(f"{identifier}: canonical or prepared FBX hash mismatch.")
            if (bridge["pivot_m"] != [0, 0, 0] or bridge["reflected_axis"] != "Y"
                    or bridge["uv_layers"] != ["UV0"] or bridge["materials"] != spec["materials"]
                    or bridge["triangles"] != spec["triangles"] or
                    bridge["matched_footprint_vertices"] != len(spec["footprint_local_m"])):
                raise ValueError(f"{identifier}: unsupported or incomplete FBX bridge audit.")
            buildings[identifier] = Building(identifier, tile, shell, spec, manifest, canonical, prepared, bridge)
    if expected.keys() != buildings.keys():
        raise ValueError(f"Missing meshes for cumulative mask buildings: {sorted(expected.keys() - buildings.keys())}")
    return buildings


def group_cells(buildings, masks, cell_m, triangle_budget):
    if not math.isfinite(cell_m) or cell_m <= 0 or triangle_budget < 1:
        raise ValueError("Cell sizes and triangle budgets must be positive.")
    groups = defaultdict(list)
    for identifier, building in sorted(buildings.items()):
        outline = building.shell["footprint"]
        centroid = [math.fsum(point[axis] for point in outline) / len(outline) for axis in (0, 1)]
        origin = masks[building.tile]["source_origin_m"]
        grid = tuple(math.floor((value - offset) / cell_m) for value, offset in zip(centroid, origin))
        groups[(building.tile, *grid)].append(building)
    for (tile, x, y), group in sorted(groups.items()):
        if sum(building.spec["triangles"] for building in group) > triangle_budget:
            raise ValueError(f"{tile} cell {(x, y)} exceeds the triangle budget. Choose smaller cells.")
        tx, ty, tz = masks[tile]["source_origin_m"]
        yield (tile, x, y), (tx + x * cell_m, ty + y * cell_m, tz), group


def gltf_point(point, pivot, yaw, anchor):
    # Prepared FBX has reflected Y. The Unreal-to-glTF axis swap reflects
    # again, so the net transform preserves triangle winding.
    x, y = rotated(point[0], -point[1], yaw)
    return (x + pivot[0] - anchor[0], point[2] + pivot[2] - anchor[2], y + pivot[1] - anchor[1])


def merge_building(building, mesh, anchor, slots):
    spec = building.spec
    if mesh.materials != spec["materials"] or len(mesh.face_materials) != spec["triangles"]:
        raise ValueError(f"{building.id}: parsed FBX materials or triangles differ from the manifest.")
    axes = tuple(zip(*mesh.positions))
    low, high = spec["bounds_cm"]
    actual = ([100 * min(axes[0]), -100 * max(axes[1]), 100 * min(axes[2])],
              [100 * max(axes[0]), -100 * min(axes[1]), 100 * max(axes[2])])
    if any(abs(a - b) > .15 for left, right in zip(actual, (low, high)) for a, b in zip(left, right)):
        raise ValueError(f"{building.id}: signed local bounds changed.")
    ground = [(x, -y) for x, y, z in mesh.positions if abs(z) < FOOTPRINT_TOLERANCE_M]
    if any(not any(math.dist(corner, vertex) <= FOOTPRINT_TOLERANCE_M for vertex in ground)
           for corner in spec["footprint_local_m"]):
        raise ValueError(f"{building.id}: prepared geometry is missing a surveyed ground corner.")
    pivot, yaw = spec["world_pivot_m"], spec["yaw_deg"]
    points = [gltf_point(point, pivot, yaw, anchor) for point in mesh.positions]
    ranges, cache = {}, defaultdict(dict)
    for face, material_index in enumerate(mesh.face_materials):
        material = mesh.materials[material_index]
        if not MATERIAL.fullmatch(material):
            raise ValueError(f"{building.id}: material is outside the medieval kit.")
        vertices, indices = slots.setdefault(material, ([], []))
        record = ranges.setdefault(material, {"first_triangle": len(indices) // 3, "triangles": 0})
        record["triangles"] += 1
        for index in range(face * 3, face * 3 + 3):
            vertex = mesh.corner_vertices[index]
            normal = gltf_point(mesh.normals[index], (0, 0, 0), yaw, (0, 0, 0))
            length = math.hypot(*normal)
            if not math.isclose(length, 1., rel_tol=.001):
                raise ValueError(f"{building.id}: a corner normal is not unit length.")
            u, v = mesh.uv0[index]
            key = (vertex, normal, u, v)
            address = cache[material].get(key)
            if address is None:
                address = len(vertices)
                cache[material][key] = address
                vertices.append((points[vertex], tuple(value / length for value in normal), (u, 1. - v)))
            indices.append(address)
    return ranges


def write_cell(path, slots):
    document = {"asset": {"version": "2.0"}, "scenes": [{"nodes": [0]}], "scene": 0,
                "nodes": [{"mesh": 0}], "meshes": [{"primitives": []}], "materials": [],
                "accessors": [], "bufferViews": []}
    binary = bytearray()

    def encode(rows, width, layout, target, index=False, bounds=False):
        first = len(binary)
        pack = struct.Struct("<" + ("I" if index else "f") * width).pack
        for row in rows:
            binary.extend(pack(*row))
        view = len(document["bufferViews"])
        document["bufferViews"].append({"buffer": 0, "byteOffset": first, "byteLength": len(binary) - first,
                                        "target": target})
        address = len(document["accessors"])
        entry = {"bufferView": view, "componentType": 5125 if index else 5126, "count": len(rows), "type": layout}
        if bounds:
            columns = tuple(zip(*rows))
            def float32(value):
                return struct.unpack("<f", struct.pack("<f", value))[0]
            entry.update(min=[float32(min(axis)) for axis in columns], max=[float32(max(axis)) for axis in columns])
        document["accessors"].append(entry)
        return address

    for index, material in enumerate(sorted(slots)):
        vertices, triangles = slots[material]
        xyz, normals, uvs = map(list, zip(*vertices))
        document["materials"].append({"name": material})
        document["meshes"][0]["primitives"].append({
            "attributes": {"POSITION": encode(xyz, 3, "VEC3", 34962, bounds=True),
                           "NORMAL": encode(normals, 3, "VEC3", 34962),
                           "TEXCOORD_0": encode(uvs, 2, "VEC2", 34962)},
            "indices": encode([(value,) for value in triangles], 1, "SCALAR", 34963, index=True),
            "material": index, "mode": 4,
        })
    document["buffers"] = [{"byteLength": len(binary)}]
    write_glb(path, document, binary)


def check_materials(building, parse, definitions):
    authored = material_definitions(building.canonical, parse)
    if authored.keys() != set(building.spec["materials"]):
        raise ValueError(f"{building.id}: material definitions differ from the audited slots.")
    for name, value in authored.items():
        if name in definitions and definitions[name] != value:
            raise ValueError(f"{building.id}: incompatible authored texture or material definition for {name}.")
        definitions[name] = value


def build(rollout, buildings, parse, destination, cell_m=64., triangle_budget=100_000, *, project_root=PROJECT_ROOT):
    if destination.exists():
        raise FileExistsError(f"Choose a fresh grouped output directory: {destination}")
    registered = rollout["cumulative_masks"]
    tiles = {name: {"source_tile_asset": mask["source_tile_asset"], "source_origin_m": mask["source_origin_m"],
                    "source_export_sha256": mask["source_export_sha256"], "cumulative_mask_sha256": mask_sha(mask),
                    "required_building_ids": sorted(row["id"] for row in mask["buildings"]),
                    "offline_mask_face_counts": rollout["tile_inventory"][name]["offline_mask_face_counts"],
                    "required_cells": []} for name, mask in registered.items()}
    supplied = defaultdict(list)
    for building in buildings.values():
        supplied[building.tile].append(building.id)
    if {name: sorted(ids) for name, ids in supplied.items()} != {
            name: tile["required_building_ids"] for name, tile in tiles.items()}:
        raise ValueError("The output must cover every declared building in each tile's cumulative mask.")
    definitions = {}
    references = {building.id: {
        "kit": project_reference(project_root, building.manifest, ".json"),
        "canonical_fbx": project_reference(project_root, building.canonical, ".fbx"),
        "prepared_fbx": project_reference(project_root, building.prepared, ".fbx"),
    } for building in buildings.values()}
    manifest = {"schema": 2, "status": "offline_geometry_only", "source_paths": "project_relative_posix", "cell_m": cell_m,
                "tile_barriers": tiles, "cells": {}, "material_definition_sha256": definitions}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="city_groups_", dir=destination.parent) as temporary:
        directory = Path(temporary) / "bundle"
        directory.mkdir()
        for (tile, x, y), anchor, group in group_cells(buildings, registered, cell_m, triangle_budget):
            cell = f"{tile}_x{x:+d}_y{y:+d}".replace("+", "p").replace("-", "m")
            slots, records = {}, []
            for building in group:
                if (digest(building.prepared.read_bytes()) != building.bridge["prepared_sha256"]
                        or digest(building.canonical.read_bytes()) != building.bridge["canonical_sha256"]):
                    raise ValueError(f"{building.id}: source mesh changed after validation.")
                check_materials(building, parse, definitions)
                mesh = read_mesh(building.prepared, parse)
                ranges = merge_building(building, mesh, anchor, slots)
                records.append({"id": building.id, "survey": building.shell,
                                "world_pivot_m": building.spec["world_pivot_m"], "yaw_deg": building.spec["yaw_deg"],
                                "footprint_local_m": building.spec["footprint_local_m"], **references[building.id],
                                "canonical_sha256": building.bridge["canonical_sha256"],
                                "prepared_sha256": building.bridge["prepared_sha256"],
                                "source_geometry_sha256": building.bridge["geometry_sha256"],
                                "face_ranges_by_material": ranges})
            bounds = []
            for axis in (0, 2):
                values = [vertex[0][axis] for vertices, _ in slots.values() for vertex in vertices]
                bounds.append((min(values), max(values)))
            if any(hi - lo > 2 * cell_m for lo, hi in bounds):
                raise ValueError(f"{cell}: grouped geometry extends beyond twice the configured cell size.")
            mesh_path = directory / f"{cell}.glb"
            write_cell(mesh_path, slots)
            sections = [{"slot": name, "material_asset": f"{MATERIAL_ROOT}/{name}.{name}",
                         "triangles": len(slots[name][1]) // 3} for name in sorted(slots)]
            manifest["cells"][cell] = {"tile": tile, "grid": [x, y], "origin_ue_m": anchor, "file": mesh_path.name,
                                       "sha256": digest(mesh_path.read_bytes()), "sections": sections,
                                       "buildings": records}
            tiles[tile]["required_cells"].append(cell)
        if any(not tile["required_cells"] for tile in tiles.values()):
            raise ValueError("Every source tile must have a complete replacement cell list.")
        (directory / "grouped_buildings.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        directory.rename(destination)
    return manifest


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("rollout", type=Path, help="Offline rollout preflight with complete cumulative masks")
    cli.add_argument("destination", type=Path, help="Fresh output directory")
    cli.add_argument("--kit", type=Path, action="append", required=True, help="Whole-building kit manifest, repeatable")
    cli.add_argument("--legacy-bridge-audit", type=Path, help="Separately stored Mark Lane bridge audit")
    cli.add_argument("--fbx-decoder-dir", type=Path, required=True, help="Installed Blender 5.3 io_scene_fbx folder")
    cli.add_argument("--project-root", type=Path, default=PROJECT_ROOT, help="Checkout root for manifest paths")
    cli.add_argument("--cell-m", type=float, default=64.)
    cli.add_argument("--triangle-budget", type=int, default=100_000)
    args = cli.parse_args()
    rollout = read_json(args.rollout)
    models = collect(rollout, args.kit, args.legacy_bridge_audit)
    manifest = build(rollout, models, load_decoder(args.fbx_decoder_dir), args.destination,
                     args.cell_m, args.triangle_budget, project_root=args.project_root)
    sections = sum(len(cell["sections"]) for cell in manifest["cells"].values())
    print(f"{len(models)} buildings grouped into {len(manifest['cells'])} cells and {sections} material sections.")


if __name__ == "__main__":
    main()
