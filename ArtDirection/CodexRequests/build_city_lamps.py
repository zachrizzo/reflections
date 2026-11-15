import bpy
import json
from pathlib import Path


ROOT = Path(r"C:\Users\zachc\Documents\Unreal Projects\reflections\ArtDirection\CodexRequests\City2026_11_14")
RAW = ROOT / "RawHunyuan"
REFERENCES = ROOT / "References"
SOURCE = ROOT / "Source"

ASSETS = [
    ("Pewterside", "GasLamp", "Pewterside_GasLamp_Reference", 4.0),
    ("Giltside", "LanternPost", "Giltside_LanternPost_Reference", 4.0),
    ("Frostside", "BrazierStand", "Frostside_BrazierStand_Reference", 4.0),
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


def make_texture(side, reference, texture_path):
    image = bpy.data.images.load(str(REFERENCES / f"{reference}.png"), check_existing=False)
    image.scale(1024, 1024)
    image.filepath_raw = str(texture_path)
    image.file_format = "PNG"
    image.save()
    material = bpy.data.materials.new(f"M_{side}_CityLamp")
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.48
    return material


def prepare(obj, side, name, target_height, material):
    select_only(obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    coords = [v.co.copy() for v in obj.data.vertices]
    height = max(v.z for v in coords) - min(v.z for v in coords)
    factor = target_height / height if height else 1.0
    for vert in obj.data.vertices:
        vert.co *= factor
    coords = [v.co for v in obj.data.vertices]
    min_z = min(v.z for v in coords)
    centre_x = (min(v.x for v in coords) + max(v.x for v in coords)) / 2.0
    centre_y = (min(v.y for v in coords) + max(v.y for v in coords)) / 2.0
    for vert in obj.data.vertices:
        vert.co.x -= centre_x
        vert.co.y -= centre_y
        vert.co.z -= min_z
    modifier = obj.modifiers.new("RuntimeTriangleBudget", "DECIMATE")
    modifier.decimate_type = "COLLAPSE"
    modifier.ratio = min(1.0, 4000.0 / max(1, len(obj.data.polygons)))
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    if not obj.data.uv_layers:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(island_margin=0.02)
        bpy.ops.object.mode_set(mode="OBJECT")
    obj.data.materials.clear()
    obj.data.materials.append(material)
    obj.name = f"SM_{side}_{name}"
    obj.data.name = f"SM_{side}_{name}_Mesh"


def export_asset(side, name, reference, target_height):
    clear_scene()
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(RAW / f"{side}_{name}.glb"))
    imported = [obj for obj in bpy.data.objects if obj not in before and obj.type == "MESH"]
    if not imported:
        raise RuntimeError(f"No mesh in {side}_{name}.glb")
    select_only(imported[0])
    for obj in imported[1:]:
        obj.select_set(True)
    if len(imported) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    source_dir = SOURCE / side / "City"
    texture_dir = source_dir / "Textures"
    texture_dir.mkdir(parents=True, exist_ok=True)
    texture_path = texture_dir / f"T_{side}_{name}_BaseColor.png"
    material = make_texture(side, reference, texture_path)
    prepare(obj, side, name, target_height, material)
    output = source_dir / f"SM_{side}_{name}.fbx"
    select_only(obj)
    bpy.ops.export_scene.fbx(filepath=str(output), use_selection=True, object_types={"MESH"},
        global_scale=1.0, apply_unit_scale=True, apply_scale_options="FBX_SCALE_NONE",
        axis_forward="-Z", axis_up="Y", use_mesh_modifiers=True, mesh_smooth_type="FACE",
        bake_anim=False, path_mode="COPY", embed_textures=False)
    return {"asset": obj.name, "fbx": str(output), "texture": str(texture_path),
            "triangles": sum(len(poly.vertices)-2 for poly in obj.data.polygons),
            "dimensions_cm": [round(v * 100, 1) for v in obj.dimensions], "pivot": "bottom-centre"}


def main():
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.length_unit = "METERS"
    report = [export_asset(*spec) for spec in ASSETS]
    (ROOT / "lamp_source_build_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
