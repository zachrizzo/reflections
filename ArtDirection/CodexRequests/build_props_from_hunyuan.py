import bpy
import json
import os
from pathlib import Path


ROOT = Path(r"C:\Users\zachc\Documents\Unreal Projects\reflections\ArtDirection\CodexRequests\Props2026_11_14")
RAW = ROOT / "RawHunyuan"
REFERENCES = ROOT / "References"
SOURCE = ROOT / "Source"

# Target longest dimensions in metres.  Blender's FBX exporter writes metres as
# Unreal centimetres, so the authored sizes arrive at their real-world scale.
ASSETS = [
    ("Quest", "NellsLetter", 0.18),
    ("Quest", "TramTicket", 0.09),
    ("Quest", "JorysFiddle", 0.65),
    ("Quest", "GlaziersEyeglass", 0.06),
    ("Quest", "LampOilBarrel", 0.40),
    ("Quest", "BoltOfWool", 0.40),
    ("Quest", "BarnabysShears", 0.28),
    ("Pickups", "PewtersideCoin", 0.035),
    ("Pickups", "GiltsideCoin", 0.035),
    ("Pickups", "FrostsideCoin", 0.035),
    ("Pickups", "MirrorShard", 0.25),
    ("Pickups", "MirrorPage", 0.20),
    ("Pickups", "GiltTowerKey", 0.20),
]


def select_only(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)


def make_texture(asset, texture_path):
    image = bpy.data.images.load(str(REFERENCES / f"{asset}.png"), check_existing=False)
    image.scale(1024, 1024)
    image.filepath_raw = str(texture_path)
    image.file_format = "PNG"
    image.save()
    material = bpy.data.materials.new(f"M_{asset}")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.52
    return material


def prepare_mesh(obj, asset, target_size, material):
    select_only(obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    # Hunyuan meshes are normalized.  Scale the largest axis to the requested
    # real-world dimension and bake the scale into the mesh.
    coords = [v.co.copy() for v in obj.data.vertices]
    lo = [min(v[i] for v in coords) for i in range(3)]
    hi = [max(v[i] for v in coords) for i in range(3)]
    extent = max(hi[i] - lo[i] for i in range(3))
    factor = target_size / extent if extent else 1.0
    for vertex in obj.data.vertices:
        vertex.co *= factor

    # Asset-local bottom-centre pivot, with identity object transform.
    coords = [v.co for v in obj.data.vertices]
    min_z = min(v.z for v in coords)
    centre_x = (min(v.x for v in coords) + max(v.x for v in coords)) / 2.0
    centre_y = (min(v.y for v in coords) + max(v.y for v in coords)) / 2.0
    for vertex in obj.data.vertices:
        vertex.co.x -= centre_x
        vertex.co.y -= centre_y
        vertex.co.z -= min_z

    # Reduce AI reconstruction density to leave a margin below the 15k-tri cap.
    modifier = obj.modifiers.new("RuntimeTriangleBudget", "DECIMATE")
    modifier.decimate_type = "COLLAPSE"
    modifier.ratio = min(1.0, 12500.0 / max(1, len(obj.data.polygons)))
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=modifier.name)

    if not obj.data.uv_layers:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(island_margin=0.02)
        bpy.ops.object.mode_set(mode="OBJECT")
    obj.data.materials.clear()
    obj.data.materials.append(material)
    obj.name = f"SM_{asset}"
    obj.data.name = f"SM_{asset}_Mesh"


def export_asset(group, asset, target_size):
    clear_scene()
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(RAW / f"{asset}.glb"))
    imported = [obj for obj in bpy.data.objects if obj not in before and obj.type == "MESH"]
    if not imported:
        raise RuntimeError(f"No mesh imported for {asset}")
    select_only(imported[0])
    for extra in imported[1:]:
        extra.select_set(True)
    if len(imported) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active

    source_dir = SOURCE / group
    texture_dir = source_dir / "Textures"
    source_dir.mkdir(parents=True, exist_ok=True)
    texture_dir.mkdir(parents=True, exist_ok=True)
    texture_path = texture_dir / f"T_{asset}_BaseColor.png"
    material = make_texture(asset, texture_path)
    prepare_mesh(obj, asset, target_size, material)

    output_fbx = source_dir / f"SM_{asset}.fbx"
    select_only(obj)
    bpy.ops.export_scene.fbx(
        filepath=str(output_fbx),
        use_selection=True,
        object_types={"MESH"},
        global_scale=1.0,
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_NONE",
        axis_forward="-Z",
        axis_up="Y",
        use_mesh_modifiers=True,
        mesh_smooth_type="FACE",
        use_triangles=False,
        bake_anim=False,
        path_mode="COPY",
        embed_textures=False,
    )
    triangles = sum(len(poly.vertices) - 2 for poly in obj.data.polygons)
    dimensions_cm = [round(value * 100.0, 2) for value in obj.dimensions]
    return {
        "asset": asset,
        "group": group,
        "fbx": str(output_fbx),
        "texture": str(texture_path),
        "triangles": triangles,
        "dimensions_cm": dimensions_cm,
        "pivot": "bottom-centre",
    }


def main():
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.length_unit = "METERS"
    report = [export_asset(*spec) for spec in ASSETS]
    report_path = ROOT / "source_build_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
