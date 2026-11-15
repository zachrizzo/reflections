import bpy
from pathlib import Path


ROOT = Path(r"C:\Users\zachc\Documents\Unreal Projects\reflections\ArtDirection\CodexRequests\Clothing2026_11_14\Giltside\Props")
STATUS = Path(r"C:\Users\zachc\Documents\Unreal Projects\reflections\ArtDirection\CodexRequests\clothing_status.md")
ASSETS = {
    "Giltside_MedievalShieldRound": 0.80,
    "Giltside_MedievalShieldHeater": 0.85,
}


def select_only(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)


def triangles(obj):
    return sum(len(poly.vertices) - 2 for poly in obj.data.polygons)


def texture_and_material(stem):
    ref = ROOT / "References" / f"{stem}_Reference.png"
    tex_dir = ROOT / "Textures"
    tex_dir.mkdir(parents=True, exist_ok=True)
    tex_path = tex_dir / f"T_{stem}_BaseColor.png"
    image = bpy.data.images.load(str(ref), check_existing=False)
    image.scale(1024, 1024)
    image.filepath_raw = str(tex_path)
    image.file_format = "PNG"
    image.save()
    material = bpy.data.materials.new(f"M_{stem}")
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    node = material.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = image
    material.node_tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.46
    return material, tex_path


def build(stem, diameter):
    clear_scene()
    raw = ROOT / "RawHunyuan" / f"{stem}.glb"
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(raw))
    meshes = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"No mesh in {raw}")
    select_only(meshes[0])
    for extra in meshes[1:]:
        extra.select_set(True)
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.object
    coords = [v.co.copy() for v in obj.data.vertices]
    extent = max(max(v[i] for v in coords) - min(v[i] for v in coords) for i in range(3))
    factor = diameter / extent
    for vert in obj.data.vertices:
        vert.co *= factor
    coords = [v.co for v in obj.data.vertices]
    # Centre the hand grip: horizontal/vertical bounds centre; shallow back face.
    centre_x = (min(v.x for v in coords) + max(v.x for v in coords)) / 2.0
    centre_y = min(v.y for v in coords)
    centre_z = (min(v.z for v in coords) + max(v.z for v in coords)) / 2.0
    for vert in obj.data.vertices:
        vert.co.x -= centre_x
        vert.co.y -= centre_y
        vert.co.z -= centre_z
    if triangles(obj) > 12500:
        decimate = obj.modifiers.new("TriangleBudget", "DECIMATE")
        decimate.ratio = 12500.0 / triangles(obj)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=decimate.name)
    if not obj.data.uv_layers:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(island_margin=0.02)
        bpy.ops.object.mode_set(mode="OBJECT")
    material, tex_path = texture_and_material(stem)
    obj.data.materials.clear()
    obj.data.materials.append(material)
    obj.name = f"SM_{stem}"
    obj.data.name = f"SM_{stem}_Mesh"
    select_only(obj)
    output = ROOT / f"SM_{stem}.fbx"
    bpy.ops.export_scene.fbx(filepath=str(output), use_selection=True, object_types={"MESH"},
        global_scale=1.0, apply_unit_scale=True, apply_scale_options="FBX_SCALE_NONE",
        axis_forward="-Z", axis_up="Y", use_mesh_modifiers=True, mesh_smooth_type="FACE",
        bake_anim=False, path_mode="COPY", embed_textures=False)
    return output, tex_path, triangles(obj)


def main():
    bpy.context.scene.unit_settings.system = "METRIC"
    rows = [build(stem, diameter) for stem, diameter in ASSETS.items()]
    old = STATUS.read_text(encoding="utf-8") if STATUS.exists() else ""
    with STATUS.open("a", encoding="utf-8") as out:
        for output, texture, count in rows:
            if str(output) not in old:
                out.write(f"- `{output}` — Local Hunyuan3D-2 + Blender export; grip pivot; {count} tris; 1K base-color `{texture}`\n")


if __name__ == "__main__":
    main()
