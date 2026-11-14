"""Add collision clearance around a coat and skirt across representative stride poses."""
from pathlib import Path
import json
import math
import runpy
import statistics

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
ROOT = PROJECT / "Intermediate/NpcMovement/Wardrobe"
FIT = runpy.run_path(str(HERE / "refit_crowd_wardrobe.py"))
POSES = {
    "rest": {},
    "short_left": FIT["POSES"]["walk_left"],
    "short_right": FIT["POSES"]["walk_right"],
    "long_left": {"thigh_l": 0.50, "thigh_r": -0.44, "upperarm_l": -0.32, "upperarm_r": 0.27},
    "long_right": {"thigh_l": -0.44, "thigh_r": 0.50, "upperarm_l": 0.27, "upperarm_r": -0.32},
}


def sample_distances(outer, lowers, rig, region):
    rows = {}
    for name, pose in POSES.items():
        FIT["set_pose"](rig, pose)
        trees = [FIT["surface"](lower, evaluated=True)[0] for lower in lowers]
        evaluated = outer.evaluated_get(bpy.context.evaluated_depsgraph_get())
        distances = {}
        for index in region:
            point = evaluated.matrix_world @ evaluated.data.vertices[index].co
            original_point = outer.matrix_world @ outer.data.vertices[index].co
            direction = Vector((original_point.x, (original_point.y + 0.025) * 1.55, 0)).normalized()
            if direction.length_squared < 0.05:
                continue
            # Start outside the layer and trace inwards, so open seams on the
            # underlying garment keep their intended area instead of closing.
            outside_distance = 0.21
            distance = -0.055
            for tree in trees:
                hit, normal, _, _ = tree.ray_cast(point + direction * outside_distance, -direction, 0.30)
                if hit is not None and normal.dot(direction) > 0.09:
                    distance = max(distance, (hit - point).dot(direction))
            distances[index] = distance
        rows[name] = distances
    FIT["set_pose"](rig, {})
    return rows


def summary(rows):
    return {
        name: {
            "inside_over_3mm": sum(v > 0.003 for v in row.values()),
            "worst_mm": round(max(row.values(), default=0) * 1000, 1),
        }
        for name, row in rows.items()
    }


def run(identity, outer_name, lower_names, output_name, kind):
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / f"{identity}_Refit.blend"))
    outer = bpy.data.objects[outer_name]
    lowers = [bpy.data.objects[name] for name in lower_names]
    rig = next(modifier.object for modifier in outer.modifiers if modifier.type == "ARMATURE")
    world = outer.matrix_world.copy()
    to_local = world.inverted()
    points = [world @ vertex.co for vertex in outer.data.vertices]
    pelvis_z = (rig.matrix_world @ rig.data.bones["pelvis"].head_local).z
    if kind == "coat":
        region = {i for i, p in enumerate(points) if p.z < pelvis_z + 0.12 and p.y < 0.025 and abs(p.x) > 0.03}
    else:
        region = {i for i, p in enumerate(points) if p.z < pelvis_z + 0.095 and p.y < 0.04}
    before = sample_distances(outer, lowers, rig, region)
    moves = {}
    ceiling = 0.049 if kind == "coat" else 0.072
    for i in region:
        need = max(row.get(i, -0.055) for row in before.values())
        moves[i] = min(ceiling, max(0.0, need + 0.009))
    neighbors = [set() for _ in points]
    for edge in outer.data.edges:
        a, b = edge.vertices
        neighbors[a].add(b)
        neighbors[b].add(a)
    displacement_by_point = {}
    for i, p in enumerate(points):
        amount = moves.get(i, 0.0)
        if neighbors[i]:
            amount = 0.67 * amount + 0.33 * statistics.mean(moves.get(j, 0.0) for j in neighbors[i])
        displacement_by_point.setdefault(tuple(round(v, 5) for v in p), []).append(amount)
    # Surface and trims use disconnected islands. Carry neighboring deformation
    # onto lace/piping that falls too far from the underlayer for a direct hit.
    from mathutils.kdtree import KDTree
    kd = KDTree(len(points))
    for i, p in enumerate(points):
        kd.insert(p, i)
    kd.balance()
    for i, p in enumerate(points):
        if i not in region:
            continue
        key = tuple(round(v, 5) for v in p)
        amount = statistics.mean(displacement_by_point[key])
        nearby = [moves.get(j, 0.0) for _, j, distance in kd.find_range(p, 0.018) if j != i]
        if nearby:
            amount = max(amount, statistics.mean(nearby) * 0.76)
        direction = Vector((p.x, (p.y + 0.025) * 1.55, 0)).normalized()
        outer.data.vertices[i].co = to_local @ (p + direction * amount)
    outer.data.update()
    after = sample_distances(outer, lowers, rig, region)
    prefix = f"SK_{identity}_{output_name}_LayerFit"
    outer.name = prefix
    FIT["export_fbx"](outer, rig, ROOT / f"{prefix}.fbx")
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / f"{identity}_{output_name}_LayerFit.blend"))
    result = {"before": summary(before), "after": summary(after), "vertices_checked": len(region)}
    (ROOT / f"{prefix}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


run("ArchiveApprentice", "SK_Merchant_Coat", ["SK_Merchant_Waistcoat", "SK_Merchant_Trousers"], "Coat", "coat")
run("FestivalDrummer", "SK_FestivalDrummer_Skirt", ["SK_FestivalDrummer_Trousers"], "Skirt", "skirt")
