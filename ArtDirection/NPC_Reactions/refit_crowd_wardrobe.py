"""Fit the active crowd's rigged main garments to their own body reference in Blender."""
import argparse
import json
import statistics
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Vector
from mathutils.bvhtree import BVHTree


WARDROBE = {
    "BridgeGuard": (
        "Red London/Bridge Guard/BridgeGuard-Outfit.blend",
        "MetaHuman body fitting reference",
        "SK_BridgeGuard_",
        {"Gambeson": 0.016, "Trousers": 0.011, "Boots": 0.012},
    ),
    "ArchiveApprentice": (
        "Red London/Archive Apprentice/ArchiveApprentice.blend",
        "Native MetaHuman fitting body",
        "SK_Merchant_",
        {"Coat": 0.026, "Waistcoat": 0.012, "Trousers": 0.011, "Boots": 0.012},
    ),
    "CoinClerk": (
        "Merchant/Merchant.blend",
        "Native MetaHuman fitting body",
        "SK_Merchant_",
        {"Coat": 0.026, "Waistcoat": 0.012, "Trousers": 0.011, "Boots": 0.012},
    ),
    "FestivalDrummer": (
        "Red London/Festival Drummer/FestivalDrummer-Outfit.blend",
        "MetaHuman body fitting reference",
        "SK_FestivalDrummer_",
        {"Blouse": 0.013, "Trousers": 0.011, "Boots": 0.012},
    ),
    "Iven": (
        "White London - Rags and Tattoos/IvenMetaHuman/IvenRook_MetaHuman_Outfit.blend",
        "MetaHuman fitting body",
        "SK_Iven_",
        {"WorkTunic": 0.014},
    ),
    "WhiteGuard": (
        "White London - Rags and Tattoos/IvenMetaHuman/WhiteLondon_BridgeGuard_RagFit_Prototype.blend",
        "TargetBody",
        "SK_WhiteGuard_",
        {"WorkTunic": 0.014},
    ),
}

POSES = {
    "walk_left": {"thigh_l": 0.28, "thigh_r": -0.22, "upperarm_l": -0.16, "upperarm_r": 0.14},
    "walk_right": {"thigh_l": -0.22, "thigh_r": 0.28, "upperarm_l": 0.14, "upperarm_r": -0.16},
}


def surface(obj, evaluated=False):
    if evaluated:
        obj = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = obj.data
    mesh.calc_loop_triangles()
    points = [obj.matrix_world @ vertex.co for vertex in mesh.vertices]
    triangles = [tuple(face.vertices) for face in mesh.loop_triangles]
    return BVHTree.FromPolygons(points, triangles, all_triangles=True), points, triangles


def barycentric(point, a, b, c):
    u, v, delta = b - a, c - a, point - a
    uu, uv, vv = u.dot(u), u.dot(v), v.dot(v)
    area = uu * vv - uv * uv
    if area <= 1e-15:
        return 1.0, 0.0, 0.0
    j = (vv * u.dot(delta) - uv * v.dot(delta)) / area
    k = (uu * v.dot(delta) - uv * u.dot(delta)) / area
    weights = [max(0.0, 1 - j - k), max(0.0, j), max(0.0, k)]
    total = sum(weights)
    return [weight / total for weight in weights]


def vertex_weights(obj, rig):
    names = [group.name for group in obj.vertex_groups]
    return [
        {names[g.group]: g.weight for g in v.groups if names[g.group] in rig.data.bones and g.weight > 0.0}
        for v in obj.data.vertices
    ]


def fit_garment(garment, body, rig, clearance, restricted):
    tree, points, triangles = surface(body)
    skin_weights = vertex_weights(body, rig)
    old_weights = vertex_weights(garment, rig)
    world = garment.matrix_world.copy()
    to_local = world.inverted()
    pelvis_z = (rig.matrix_world @ rig.data.bones["pelvis"].head_local).z
    neck_z = (rig.matrix_world @ rig.data.bones["neck_01"].head_local).z
    original = [world @ vertex.co for vertex in garment.data.vertices]
    moves = [Vector((0, 0, 0)) for _ in original]
    transfers = {}
    for index, point in enumerate(original):
        area = 1.0
        if restricted:
            # The coat's free tails, and the tunic's ragged hem, keep their authored ease.
            area = min(1.0, max(0.0, (point.z - pelvis_z + 0.035) / 0.11))
        near, normal, tri, distance = tree.find_nearest(point)
        if near is None or distance > 0.105 or area <= 0.0 or point.z > neck_z + 0.015:
            continue
        signed = (point - near).dot(normal)
        if signed < -0.034:
            continue
        if signed < 0.003:
            moves[index] = normal * (clearance - signed) * area
        elif distance > clearance + 0.01:
            moves[index] = (near - point).normalized() * (distance - clearance - 0.01) * 0.72 * area
        fractions = barycentric(near, *(points[i] for i in triangles[tri]))
        blended = {}
        ratio = area * (0.78 if distance < 0.045 else 0.48)
        for name, weight in old_weights[index].items():
            blended[name] = weight * (1.0 - ratio)
        for vertex_index, fraction in zip(triangles[tri], fractions):
            for name, weight in skin_weights[vertex_index].items():
                blended[name] = blended.get(name, 0.0) + weight * fraction * ratio
        if blended:
            transfers[index] = blended

    neighbors = [set() for _ in original]
    for edge in garment.data.edges:
        a, b = edge.vertices
        neighbors[a].add(b)
        neighbors[b].add(a)
    for index, point in enumerate(original):
        if not moves[index].length_squared:
            continue
        others = neighbors[index]
        direction = moves[index]
        if others:
            direction = moves[index] * 0.65 + sum((moves[i] for i in others), Vector()) * (0.35 / len(others))
        garment.data.vertices[index].co = to_local @ (point + direction)
    # Imported neural topology can have split UV vertices. Move coincident points together
    # to preserve seam positions while maintaining the original UV loops.
    coincident = {}
    for i, point in enumerate(original):
        coincident.setdefault(tuple(round(v, 5) for v in point), []).append(i)
    for indexes in coincident.values():
        if len(indexes) < 2:
            continue
        mean = sum((garment.data.vertices[i].co for i in indexes), Vector()) / len(indexes)
        for i in indexes:
            garment.data.vertices[i].co = mean
        mapped = [transfers.get(i, old_weights[i]) for i in indexes]
        seam_weights = {}
        for weights in mapped:
            for name, weight in weights.items():
                seam_weights[name] = seam_weights.get(name, 0.0) + weight / len(mapped)
        if seam_weights:
            for i in indexes:
                transfers[i] = seam_weights

    for index, blended in transfers.items():
        top = sorted(((n, w) for n, w in blended.items() if w > 0.001), key=lambda pair: -pair[1])[:8]
        total = sum(weight for _, weight in top)
        if total == 0:
            continue
        affected_groups = [group.group for group in garment.data.vertices[index].groups]
        for group_index in affected_groups:
            if garment.vertex_groups[group_index].name in rig.data.bones:
                garment.vertex_groups[group_index].remove([index])
        for name, weight in top:
            group = garment.vertex_groups.get(name) or garment.vertex_groups.new(name=name)
            group.add([index], weight / total, "REPLACE")
    garment.data.update()
    return dict(vertices_moved=sum(move.length_squared > 0 for move in moves), vertices_reweighted=len(transfers))


def tighten_boots(boots, body, rig):
    """Shorten generated toe boxes and narrow leather around the actual foot."""
    world = boots.matrix_world.copy()
    to_local = world.inverted()
    foot_frames = {}
    tree, skin_points, _ = surface(body)
    boot_points = [world @ v.co for v in boots.data.vertices]
    rig_world = rig.matrix_world
    for side in ("l", "r"):
        ankle = rig_world @ rig.data.bones["foot_" + side].head_local
        ball = rig_world @ rig.data.bones["ball_" + side].head_local
        forward = ball - ankle
        forward.z = 0.0
        forward.normalize()
        across = forward.cross(Vector((0, 0, 1)))
        foot_frames[side] = (ankle, forward, across)

    def side_of(point):
        return min(foot_frames, key=lambda side: (point.xy - foot_frames[side][0].xy).length_squared)

    metrics = {}
    for side, (ankle, forward, across) in foot_frames.items():
        body_foot = [p for p in skin_points if p.z < ankle.z + 0.015 and side_of(p) == side]
        indices = [i for i, p in enumerate(boot_points) if side_of(p) == side]
        if len(body_foot) < 10:
            raise RuntimeError(f"Missing fitting foot on {side}")
        longs = [(p - ankle).dot(forward) for p in body_foot]
        shorts = [(p - ankle).dot(across) for p in body_foot]
        a, b = min(longs) - 0.022, max(longs) + 0.018
        c, d = min(shorts) - 0.013, max(shorts) + 0.013
        boot_foot = [boot_points[i] for i in indices if boot_points[i].z < ankle.z + 0.045]
        old_long = [(p - ankle).dot(forward) for p in boot_foot]
        low, high = min(old_long), max(old_long)
        repaired = []
        for i in indices:
            p = boot_points[i]
            # Keep the boot shaft and cuff stable, and taper the closer fit up the ankle.
            blend = min(1.0, max(0.0, (ankle.z + 0.11 - p.z) / 0.09))
            longitudinal = (p - ankle).dot(forward)
            across_foot = (p - ankle).dot(across)
            fitted_long = longitudinal
            if longitudinal > 0:
                fitted_long *= min(1.0, b / max(0.001, high))
            else:
                fitted_long *= min(1.0, a / min(-0.001, low))
            fitted_across = across_foot
            if across_foot > d or across_foot < c:
                edge = d if across_foot > 0 else c
                fitted_across = edge + (across_foot - edge) * 0.24
            proposed = p + ((fitted_long - longitudinal) * forward + (fitted_across - across_foot) * across) * blend
            if blend > 0:
                near, normal, _, distance = tree.find_nearest(proposed)
                old_near, old_normal, _, _ = tree.find_nearest(p)
                signed = (proposed - near).dot(normal)
                old_signed = (p - old_near).dot(old_normal)
                if distance < 0.05 and signed < 0.002 and signed < old_signed:
                    proposed += normal * (max(0.002, min(0.01, old_signed)) - signed)
            boots.data.vertices[i].co = to_local @ proposed
            if p.z < ankle.z + 0.045:
                repaired.append((proposed - ankle).dot(forward))
        metrics[side] = dict(
            original_foot_length_cm=round((high - low) * 100, 2),
            fitted_foot_length_cm=round((max(repaired) - min(repaired)) * 100, 2),
        )
    boots.data.update()
    return metrics


def measures(garment, tree):
    evaluated = garment.evaluated_get(bpy.context.evaluated_depsgraph_get())
    distances = []
    negative = 0
    for vertex in evaluated.data.vertices:
        point = evaluated.matrix_world @ vertex.co
        near, normal, _, distance = tree.find_nearest(point)
        distances.append(distance * 1000)
        negative += (point - near).dot(normal) < -0.002
    return dict(
        vertex_count=len(distances),
        median_mm=round(statistics.median(distances), 2),
        p95_mm=round(statistics.quantiles(distances, n=20)[18], 2),
        nearest_normal_flag_count=negative,
    )


def set_pose(rig, pose):
    for bone in rig.pose.bones:
        bone.rotation_mode = "QUATERNION"
        bone.rotation_quaternion = Euler((pose.get(bone.name, 0.0), 0.0, 0.0)).to_quaternion()
    bpy.context.view_layer.update()


def inspect_fit(body, rig, garments):
    report = {}
    for name, pose in {"rest": {}, **POSES}.items():
        set_pose(rig, pose)
        tree, _, _ = surface(body, evaluated=True)
        report[name] = {key: measures(garment, tree) for key, garment in garments.items()}
    set_pose(rig, {})
    return report


def export_fbx(garment, rig, path):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in (garment, rig):
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = garment
    old_name = rig.name
    other_armature = bpy.data.objects.get("Armature")
    if other_armature == rig:
        other_armature = None
    if other_armature:
        other_armature.name = "SourceFitArmature"
    rig.name = "Armature"
    bpy.ops.export_scene.fbx(
        filepath=str(path),
        use_selection=True,
        object_types={"MESH", "ARMATURE"},
        axis_forward="-Z",
        axis_up="Y",
        apply_unit_scale=True,
        add_leaf_bones=False,
        bake_anim=False,
        mesh_smooth_type="FACE",
    )
    rig.name = old_name
    if other_armature:
        other_armature.name = "Armature"


def verify_exports(output):
    report = {}
    for path in sorted(output.glob("SK_*_Refit.fbx")):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(path))
        rig = next(obj for obj in bpy.context.selected_objects if obj.type == "ARMATURE")
        garment = next(obj for obj in bpy.context.selected_objects if obj.type == "MESH")
        weights = vertex_weights(garment, rig)
        max_error = max(abs(sum(row.values()) - 1.0) for row in weights)
        if max_error > 0.001 or not garment.data.uv_layers or rig.data.bones["pelvis"].parent.name != "root":
            raise RuntimeError(f"Roundtrip failed for {path.name}: weight error {max_error:.5f}")
        report[path.name] = dict(
            vertices=len(garment.data.vertices),
            materials=[slot.name for slot in garment.material_slots],
            uv_layers=len(garment.data.uv_layers),
            weights_max_error=max_error,
            bones=len(rig.data.bones),
        )
    (output / "roundtrip.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def run(identity, config, root, output):
    source, body_name, prefix, clearances = config
    bpy.ops.wm.open_mainfile(filepath=str(root / source))
    garment_by_name = {key: bpy.data.objects[prefix + key] for key in clearances}
    rig = next(modifier.object for modifier in next(iter(garment_by_name.values())).modifiers if modifier.type == "ARMATURE")
    body = bpy.data.objects.get(body_name)
    if body is None and body_name == "TargetBody":
        body = next(
            obj for obj in bpy.context.scene.objects
            if obj.type == "MESH" and not obj.name.startswith("SK_")
            and any(modifier.type == "ARMATURE" and modifier.object == rig for modifier in obj.modifiers)
        )
    before = inspect_fit(body, rig, garment_by_name)
    edits = {}
    for key, garment in garment_by_name.items():
        if key == "Boots":
            edits[key] = tighten_boots(garment, body, rig)
        else:
            edits[key] = fit_garment(garment, body, rig, clearances[key], key in {"Coat", "WorkTunic"})
    after = inspect_fit(body, rig, garment_by_name)
    for key, garment in garment_by_name.items():
        path = output / f"SK_{identity}_{key}_Refit.fbx"
        original_name = garment.name
        garment.name = path.stem
        export_fbx(garment, rig, path)
        garment.name = original_name
        edits[key]["fbx"] = path.name
        edits[key]["material_slots"] = [slot.name for slot in garment.material_slots]
        edits[key]["uv_layers"] = len(garment.data.uv_layers)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(output / f"{identity}_Refit.blend"))
    return dict(source=source, body=body_name, before=before, after=after, edits=edits)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity", choices=WARDROBE)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    project = Path(__file__).resolve().parents[2]
    root = project / "ArtDirection/Three-Londons-Wardrobe"
    output = project / "Intermediate/NpcMovement/Wardrobe"
    output.mkdir(parents=True, exist_ok=True)
    if args.verify_only:
        verify_exports(output)
        return
    for identity, config in WARDROBE.items():
        if args.identity and identity != args.identity:
            continue
        result = run(identity, config, root, output)
        (output / f"{identity}_metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
