"""Measure directional body-to-garment clearance on aligned MetaHuman FBXs."""

import argparse
import json
import sys
from pathlib import Path
from statistics import median

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def load_fbx(path, *, read_bones=False):
    if not path.is_file():
        raise ValueError(f"FBX does not exist: {path}")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(path))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if len(meshes) != 1:
        raise ValueError(f"Expected one combined mesh in {path}, found {len(meshes)}")

    mesh = meshes[0]
    mesh.data.calc_loop_triangles()
    tree = BVHTree.FromPolygons(
        [mesh.matrix_world @ vertex.co for vertex in mesh.data.vertices],
        [tuple(triangle.vertices) for triangle in mesh.data.loop_triangles],
        all_triangles=True,
    )
    bones = {}
    if read_bones:
        armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
        if len(armatures) != 1:
            raise ValueError(f"Expected one MetaHuman armature in {path}, found {len(armatures)}")
        armature = armatures[0]
        for name in ("spine_05", "spine_03", "pelvis", "upperarm_l", "upperarm_r"):
            bone = armature.data.bones.get(name)
            if bone is None:
                raise ValueError(f"Missing landmark bone {name} in {path}")
            bones[name] = armature.matrix_world @ bone.head_local
    return tree, bones


def summarize(samples, total):
    return {
        "sample_count": len(samples),
        "attempted_samples": total,
        "median_mm": round(median(samples), 1) if samples else None,
        "min_mm": round(min(samples), 1) if samples else None,
        "max_mm": round(max(samples), 1) if samples else None,
    }


def audit(body_path, garment_path, hem_above_pelvis_mm):
    body, bones = load_fbx(body_path, read_bones=True)
    garment, _ = load_fbx(garment_path)
    center_x = bones["pelvis"].x
    left = bones["upperarm_l"]
    right = bones["upperarm_r"]
    half_width = abs(left.x - right.x) / 2
    # The FBXs are imported in meters with +Z up and -Y forward.
    if not 0.07 <= half_width <= 0.45:
        raise ValueError("Unexpected shoulder width. Check FBX scale and axes.")

    def clearance(origins, direction, *, shoulder_height=None):
        distances = []
        for origin in origins:
            body_hit, body_normal, _, _ = body.ray_cast(origin, direction, 4.0)
            garment_hit, garment_normal, _, _ = garment.ray_cast(origin, direction, 4.0)
            if body_hit is None or garment_hit is None:
                continue
            # A ray through an opening can reach the opposite side of the garment.
            # That hit measures torso depth, so count it as an unmatched sample.
            if body_normal.dot(direction) >= 0 or garment_normal.dot(direction) >= 0:
                continue
            if shoulder_height is not None and abs(body_hit.z - shoulder_height) > 0.13:
                continue
            distances.append((body_hit - garment_hit).dot(direction) * 1000)
        return summarize(distances, len(origins))

    report = {}
    levels = {
        "chest": bones["spine_05"].z,
        "waist": bones["spine_03"].z,
        "above_hem": bones["pelvis"].z + hem_above_pelvis_mm / 1000,
    }
    for label, height in levels.items():
        report[label] = {}
        for side, direction in (("front", 1), ("back", -1)):
            origins = [
                Vector((center_x + half_width * column, -direction * 1.5, height + offset))
                for column in (-0.6, -0.45, -0.3, -0.15, 0, 0.15, 0.3, 0.45, 0.6)
                for offset in (-0.01, 0, 0.01)
            ]
            report[label][side] = clearance(origins, Vector((0, direction, 0)))

    for label, shoulder in (("left_shoulder", left), ("right_shoulder", right)):
        origins = [
            Vector((center_x + (shoulder.x - center_x) * fraction, shoulder.y + depth, shoulder.z + 0.75))
            for fraction in (0.78, 0.88, 0.98)
            for depth in (-0.025, 0, 0.025)
        ]
        report[label] = clearance(origins, Vector((0, 0, -1)), shoulder_height=shoulder.z)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair", action="append", nargs=3, required=True, metavar=("NAME", "BODY_FBX", "GARMENT_FBX"))
    parser.add_argument("--hem-above-pelvis-mm", type=float, default=65, help="Torso sampling height near the tunic hem")
    parser.add_argument("--output", type=Path, help="Write the JSON report to this path")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    result = {}
    for name, body, garment in args.pair:
        if name in result:
            parser.error(f"Duplicate pair name: {name}")
        try:
            result[name] = audit(Path(body), Path(garment), args.hem_above_pelvis_mm)
        except ValueError as error:
            parser.error(str(error))
    report = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(report + "\n", encoding="utf-8")
    else:
        print(report)


if __name__ == "__main__":
    main()
