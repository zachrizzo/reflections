"""Verify saved opening marker evidence and conservative clearance against the source shell."""

import json
import math
from pathlib import Path
import runpy
import struct
import sys

if __name__ == "__main__":
    sys.dont_write_bytecode = True

from extract_building_shells import faces
from extract_tile_frontages import det, project_to_segment, read_glb, vector
from group_stacked_roofs import ring_edges
from plan_whole_building_replacements import distance_to_building
from scan_opening_view_alternatives import delta, ray_distance
from select_whole_building_blocks import guide_distance
from subtract_building_shells import digest, read_json
from verify_spawn_building_review import DEFAULT_REVIEW, PROJECT, SOURCE, verify


ACTOR_ROOT = Path("Content/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata")
MARKER_PACKAGES = {
    "CutsceneAnchor_FirstPage": "9/BQ/WOAAHAQTHPOHYIU0WI5GSH",
    "Home_frank_dunning": "9/7S/P2MSGDZBGCXVFNH5MGY2AR",
    "Mk_Pew_Stair_WeighHouse": "3/U9/8LWD8IKG5HNN0XQV73PEVU",
    "Mk_Pew_Square_WeighHouse": "D/A3/UHUR3VWVZM21QX2Y7TWSXU",
    "Mk_Gilt_Inn_Lamplight": "C/RQ/9PPH290M64SBSVQZ146WMN",
}
HERO_CAPSULE_RADIUS_M = .42
SWEEP_PADDING_M = .10
CONSERVATIVE_RADIUS_M = 25.
VECTOR_NAMES = {"RelativeLocation", "StructProperty", "Vector", "/Script/CoreUObject",
                "Root", "RootComponent", "ReflectionsStoryMarker"}


def read_name_map(data):
    """Recognize the name-map table in these small UE 5.9 external packages."""
    recognized = {}
    for offset in range(min(512, len(data) - 8)):
        count, start = struct.unpack_from("<ii", data, offset)
        if not 8 <= count <= 256 or not 64 <= start < len(data) - count * 8:
            continue
        names, cursor = [], start
        for _ in range(count):
            if cursor + 4 > len(data):
                break
            size = struct.unpack_from("<i", data, cursor)[0]
            wide = size < 0
            end = cursor + 4 + abs(size) * (2 if wide else 1)
            if not 1 <= abs(size) <= 1024 or end + 4 > len(data):
                break
            tail = 2 if wide else 1
            if data[end - tail:end] != bytes(tail):
                break
            try:
                names.append(data[cursor + 4:end - tail].decode("utf-16-le" if wide else "utf-8"))
            except UnicodeDecodeError:
                break
            cursor = end + 4
        if len(names) == count and VECTOR_NAMES.issubset(names):
            recognized[start] = (names, cursor)
    if len(recognized) != 1:
        raise ValueError("Expected exactly one UE name-map table for the marker.")
    return next(iter(recognized.values()))


def serialized_location(package, label):
    data = package.read_bytes()
    actor_label = "LT_Marker_" + label
    if actor_label.encode() + b"\0" not in data and actor_label.encode("utf-16-le") + b"\0\0" not in data:
        raise ValueError(f"Expected {actor_label} in the saved package.")
    entries, name_map_end = read_name_map(data)
    relative, structure, vector_type, core = (
        entries.index(name) for name in ("RelativeLocation", "StructProperty", "Vector", "/Script/CoreUObject")
    )
    # FName, full type tree, 24-byte FVector size and BinaryOrNative tag flag.
    header = struct.pack("<12iB", relative, 0, structure, 0, 1, vector_type, 0, 1, core, 0, 0, 24, 8)
    at = data.find(header, name_map_end)
    if at == -1 or data.find(header, at + len(header)) != -1 or at + len(header) + 24 > len(data):
        raise ValueError(f"Expected one complete typed RelativeLocation property for {actor_label}.")
    offset = at + len(header)
    payload = data[offset:offset + 24]
    metres = [value / 100 for value in struct.unpack("<3d", payload)]
    if not all(math.isfinite(value) for value in metres):
        raise ValueError(f"Invalid saved position for {actor_label}.")
    return {"actor_label": actor_label, "package_file": package.relative_to(PROJECT).as_posix(),
            "package_sha256": digest(data), "property": "RelativeLocation/StructProperty/Vector",
            "type_package": "/Script/CoreUObject", "tag_offset": at, "value_offset": offset,
            "value_sha256": digest(payload), "serialized_relative_m": metres}


def support_at(point, surfaces):
    """List geometric heights below or above the XY projection in the pinned tile."""
    heights = {}
    for label, triangles in surfaces.items():
        levels = set()
        for a, b, c in triangles:
            ab, ac = vector(a, b), vector(a, c)
            divisor = det(ab, ac)
            if not divisor:
                continue
            ap = vector(a, point)
            u, v = det(ap, ac) / divisor, det(ab, ap) / divisor
            if u >= -1e-9 and v >= -1e-9 and u + v <= 1. + 1e-9:
                levels.add(round(a[2] + u * (b[2] - a[2]) + v * (c[2] - a[2]), 6))
        if levels:
            heights[label] = sorted(levels)
    return heights


def point_clearance(point, ring, surfaces):
    unsigned = min(project_to_segment(point[:2], a, b)[0] for a, b in ring_edges(ring))
    signed = -unsigned if distance_to_building(point[:2], ring) < .00001 else unsigned
    return {"signed_shell_edge_clearance_m": round(signed, 6),
            "capsule_radius_plus_padding_clearance_m": round(signed - HERO_CAPSULE_RADIUS_M - SWEEP_PADDING_M, 6),
            "source_surface_z_at_xy_m": support_at(point[:2], surfaces)}


def cinematic_baseline(anchor, ring, triangles):
    """Check source-shell occlusion at each authored FirstPage key under nominal yaw zero."""
    scene = runpy.run_path(str(PROJECT / "Tools/Cinematics/cutscene_defs.py"))["CUTSCENES"]["FirstPage"]
    results = []
    for shot in scene["shots"]:
        for key in shot["keys"]:
            camera, look = ([base + offset / 100 for base, offset in zip(anchor, key[field])]
                            for field in ("pos", "look"))
            length = math.dist(camera, look)
            direction = tuple(value / length for value in delta(look, camera))
            distance = min(ray_distance(direction, (delta(b, a), delta(c, a), delta(camera, a)))
                           for a, b, c in triangles)
            inside = .2 <= camera[2] <= 15. and distance_to_building(camera[:2], ring) <= .00001
            results.append({"shot": shot["label"], "time": key["t"], "camera_m": camera, "look_m": look,
                            "camera_inside_source_shell": inside,
                            "view_ray_intersects_source_before_target": distance < length})
    return results


def survey():
    verification = verify()
    review = read_json(DEFAULT_REVIEW)
    shell = review["shell_geometry"]
    ring = shell["footprint_m"]
    source = PROJECT / SOURCE
    document, blob = read_glb(source)
    metadata = read_json(source.with_suffix(".asset.json"))
    geometry = {slot: faces(document, blob, index, metadata["origin_m"])
                for index, slot in enumerate(metadata["primitives"])}
    baseline = [geometry["GL_Facade"][i] for row in shell["wall_faces_by_ring_edge"]
                for i in row["ordinary_wall_faces"]]
    baseline += [geometry["GL_Roof"][i] for i in shell["roof_face_ordinals"]]
    stories = {marker["name"]: marker for marker in read_json(PROJECT / "ArtDirection/WorldJump/graylondon_markers.json")}
    surfaces = {key: geometry[key] for key in ("GL_Roof", "GL_Road", "GL_Park", "GL_Water")}
    markers = {}
    for name, relative in MARKER_PACKAGES.items():
        story = stories[name]
        source_point = [story["east_m"], story["north_m"], story["z_m"]]
        row = serialized_location(PROJECT / ACTOR_ROOT / f"{relative}.uasset", name)
        saved = row["serialized_relative_m"]
        offset = math.dist(saved[:2], source_point[:2])
        if offset > 20.001:
            raise ValueError(f"The saved relative coordinates for {name} exceed the published placement search.")
        markers[name] = {**row, "nominal_m": source_point, "xy_offset_m": round(offset, 6),
                         "nominal": point_clearance(source_point, ring, surfaces),
                         "saved_relative_as_world_hypothesis": point_clearance(saved, ring, surfaces)}

    stair = markers["Mk_Pew_Stair_WeighHouse"]
    frank = markers["Home_frank_dunning"]
    farthest = max(math.dist(stair["nominal_m"][:2], point) for point in ring)
    routes = {}
    for key in ("nominal_m", "serialized_relative_m"):
        points = [frank[key][:2], stair[key][:2]]
        separation = guide_distance(ring, points)
        routes[key] = {"points_m": points, "straight_probe_clearance_to_shell_m": round(separation, 6),
                       "capsule_radius_plus_padding_clearance_m": round(separation - HERO_CAPSULE_RADIUS_M - SWEEP_PADDING_M, 6)}
    first_page = markers["CutsceneAnchor_FirstPage"]
    return {
        "status": "blocked_review_only",
        "source": verification,
        "markers": markers,
        "frank_to_stair_straight_probe": routes,
        "nominal_stair_guard_m": CONSERVATIVE_RADIUS_M,
        "farthest_footprint_vertex_from_nominal_stair_m": round(farthest, 6),
        "nominal_stair_guard_covers_entire_shell": farthest < CONSERVATIVE_RADIUS_M,
        "capsule_radius_m": HERO_CAPSULE_RADIUS_M,
        "capsule_extra_horizontal_padding_m": SWEEP_PADDING_M,
        "first_page_yaw_zero_keys": {
            key: cinematic_baseline(first_page[key], ring, baseline)
            for key in ("nominal_m", "serialized_relative_m")
        },
        "interpretation": "Saved relative location evidence cannot establish live world transform, gameplay clearance, "
                          "collision support, or the cutscene's resolved origin and yaw.",
    }


if __name__ == "__main__":
    print(json.dumps(survey(), indent=2))
