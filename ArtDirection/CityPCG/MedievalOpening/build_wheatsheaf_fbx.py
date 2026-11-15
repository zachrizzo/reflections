"""Preserve the painted relief UVs while adding its blackened mounting hook."""

import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
NAME = "SM_GLMedieval_Wheatsheaf"


def rod(points, radius, material):
    for start, end in zip(points, points[1:]):
        a, b = Vector(start), Vector(end)
        delta = b - a
        bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=radius, depth=delta.length + radius,
                                          location=(a + b) / 2)
        part = bpy.context.object
        part.rotation_euler = delta.to_track_quat("Z", "Y").to_euler()
        part.data.materials.append(material)
        yield part


def main(glb):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.ops.import_scene.gltf(filepath=str(glb.resolve()))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if len(meshes) != 1:
        raise ValueError("Expected one wheatsheaf relief mesh.")
    obj = meshes[0]
    obj.name = obj.data.name = NAME
    painted, edge, iron = list(obj.data.materials)
    if [part.name for part in (painted, edge, iron)] != ["Painted oak face", "Dark oak edges", "Blackened iron"]:
        raise ValueError("Unexpected source relief materials.")
    painted.name, edge.name, iron.name = "M_GLMedieval_Wheatsheaf", "M_GLMedieval_Oak", "M_GLMedieval_Lead"
    photo = next(node.image for node in painted.node_tree.nodes if node.type == "TEX_IMAGE")
    texture = ROOT / "Textures/T_GLMedieval_Wheatsheaf.png"
    if not photo.packed_file:
        raise ValueError("The wheatsheaf source must contain its painted image.")
    texture.write_bytes(photo.packed_file.data)
    photo.filepath = str(texture.resolve())

    hook = list(rod(((-.078, 0, .110), (-.019, 0, .092), (.007, 0, .047),
                     (.006, 0, .016), (-.017, 0, .013)), .007, iron))
    bpy.ops.object.select_all(action="DESELECT")
    for part in hook:
        part.select_set(True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.join()
    bpy.context.view_layer.update()
    blueprint = {
        "fbx": f"Source/{NAME}.fbx",
        "texture": f"Textures/{texture.name}",
        "mesh": NAME,
        "min_cm": [round(min(v[axis] for v in obj.bound_box) * 100, 3) for axis in range(3)],
        "max_cm": [round(max(v[axis] for v in obj.bound_box) * 100, 3) for axis in range(3)],
        "materials": [part.name for part in obj.data.materials],
    }
    bpy.ops.export_scene.fbx(filepath=str(ROOT / blueprint["fbx"]), use_selection=True, object_types={"MESH"},
                             global_scale=1.0, apply_unit_scale=True, axis_forward="-Z", axis_up="Y",
                             mesh_smooth_type="FACE", bake_anim=False, path_mode="RELATIVE")
    (ROOT / "wheatsheaf_kit.json").write_text(json.dumps(blueprint, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[sys.argv.index("--") + 1]))
