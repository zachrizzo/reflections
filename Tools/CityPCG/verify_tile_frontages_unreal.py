"""Compare a bounded facade feed against live geodata collision in Unreal."""

import json
import math
from pathlib import Path

import unreal


MAP = "/Game/GrayLondon/Maps/GrayLondon_Geodata"
SAMPLE_FRACTIONS = (.15, .50, .85)


def cast(world, start, end):
    trace = unreal.SystemLibrary.line_trace_single(
        world, unreal.Vector(*start), unreal.Vector(*end),
        unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [], unreal.DrawDebugTrace.NONE,
    )
    return trace.to_tuple() if trace else None


def verify_frontages(path):
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    return verify_document(document)


def verify_document(document):
    if document["coordinate_system"] != "ue_local_m":
        raise ValueError("Expected Unreal local metres.")
    if len(document["frontages"]) > 50:
        raise ValueError("Limit each live check to a review batch of at most 50 walls.")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not world or world.get_path_name().split(".")[0] != MAP:
        raise RuntimeError(f"Open {MAP} before verifying tile alignment.")

    expected_actor = f"OSM {document['source']}"
    samples = []
    for facade in document["frontages"]:
        p, q = facade["start"], facade["end"]
        nx, ny = facade["outward"]
        heights = (160, .55 * facade["height_m"] * 100, .90 * facade["height_m"] * 100)
        for fraction in SAMPLE_FRACTIONS:
            x, y, z = [(a + fraction * (b - a)) * 100 for a, b in zip(p, q)]
            floor = cast(world, (x + 80 * nx, y + 80 * ny, z + 100),
                         (x + 80 * nx, y + 80 * ny, z - 100))
            ground_z = round(floor[4].z, 1) if floor else None
            for height in heights:
                ray_z = z + height
                hit = cast(world, (x + 165 * nx, y + 165 * ny, ray_z),
                           (x - 40 * nx, y - 40 * ny, ray_z))
                if hit:
                    location, normal, actor = hit[4], hit[7], hit[9]
                    error = math.hypot(location.x - x, location.y - y)
                    normal_dot = normal.x * nx + normal.y * ny
                    label = actor.get_actor_label()
                    passed = error <= 1 and normal_dot >= .99 and label == expected_actor
                else:
                    error, normal_dot, label, passed = None, None, None, False
                samples.append({
                    "id": facade["id"], "fraction": fraction, "height_cm": round(height, 1),
                    "actor": label, "offset_cm": round(error, 3) if error is not None else None,
                    "normal_dot": round(normal_dot, 4) if normal_dot is not None else None,
                    "exterior_floor_z_cm": ground_z, "passes": passed,
                })
    errors = [entry["offset_cm"] for entry in samples if entry["offset_cm"] is not None]
    return {
        "expected_actor": expected_actor,
        "wall_runs": len(document["frontages"]),
        "rays": len(samples),
        "passed": sum(entry["passes"] for entry in samples),
        "max_offset_cm": max(errors, default=None),
        "samples": samples,
    }
