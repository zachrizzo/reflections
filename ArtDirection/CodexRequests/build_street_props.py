import bpy
from pathlib import Path


ROOT = Path(r"C:\Users\zachc\Documents\Unreal Projects\reflections\ArtDirection\CodexRequests\Props2026_11_14\Street")
RAW = ROOT / "RawHunyuan"
TEXTURES = ROOT / "Textures"

SPECS = {
    "StreetWoodenCrate": {
        "longest_m": 0.45,
        "colour": (0.22, 0.085, 0.025, 1.0),
        "pivot": "centre",
    },
    "StreetClayPipe": {
        "longest_m": 0.18,
        "colour": (0.70, 0.57, 0.40, 1.0),
        "pivot": "mouthpiece",
    },
}


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)


def active_only(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def triangles(obj):
    return sum(max(0, len(poly.vertices) - 2) for poly in obj.data.polygons)


def bounds(obj):
    coords = [vertex.co for vertex in obj.data.vertices]
    lo = [min(vertex[axis] for vertex in coords) for axis in range(3)]
    hi = [max(vertex[axis] for vertex in coords) for axis in range(3)]
    return lo, hi


def create_material(stem, colour):
    TEXTURES.mkdir(parents=True, exist_ok=True)
    texture_path = TEXTURES / f"T_{stem}_BaseColor.png"
    image = bpy.data.images.new(f"T_{stem}_BaseColor", width=512, height=512, alpha=False)
    image.generated_color = colour
    image.filepath_raw = str(texture_path)
    image.file_format = "PNG"
    image.save()
    material = bpy.data.materials.new(f"M_{stem}")
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    node = material.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = image
    material.node_tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.64
    return material, texture_path


def orient_pipe_on_x(obj):
    lo, hi = bounds(obj)
    sizes = [hi[axis] - lo[axis] for axis in range(3)]
    long_axis = max(range(3), key=lambda axis: sizes[axis])
    # Re-map the longest inferred pipe axis to local +X.  Sign is corrected
    # below by putting its lowest-X end (the left/mouthpiece reference end) at 0.
    for vertex in obj.data.vertices:
        vector = vertex.co.copy()
        if long_axis == 1:
            vertex.co = (vector.y, vector.x, vector.z)
        elif long_axis == 2:
            vertex.co = (vector.z, vector.y, vector.x)


def prepare(stem, obj, spec):
    active_only(obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if spec["pivot"] == "mouthpiece":
        orient_pipe_on_x(obj)
    lo, hi = bounds(obj)
    sizes = [hi[axis] - lo[axis] for axis in range(3)]
    scale = spec["longest_m"] / max(sizes)
    for vertex in obj.data.vertices:
        vertex.co *= scale
    lo, hi = bounds(obj)
    if spec["pivot"] == "centre":
        offset = [(lo[axis] + hi[axis]) / 2.0 for axis in range(3)]
    else:
        # The source pipe is framed mouthpiece-left.  Local +X therefore runs
        # mouthpiece-to-bowl, with its grip end at the object origin.
        offset = [lo[0], (lo[1] + hi[1]) / 2.0, (lo[2] + hi[2]) / 2.0]
    for vertex in obj.data.vertices:
        vertex.co.x -= offset[0]
        vertex.co.y -= offset[1]
        vertex.co.z -= offset[2]
    if triangles(obj) > 2800:
        modifier = obj.modifiers.new("TriangleBudget", "DECIMATE")
        modifier.decimate_type = "COLLAPSE"
        modifier.ratio = 2800.0 / triangles(obj)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    uv = obj.data.uv_layers.get("UVMap") or obj.data.uv_layers.new(name="UVMap")
    lo, hi = bounds(obj)
    width = max(0.0001, hi[0] - lo[0])
    height = max(0.0001, hi[2] - lo[2])
    for polygon in obj.data.polygons:
        for loop_index in polygon.loop_indices:
            vertex = obj.data.vertices[obj.data.loops[loop_index].vertex_index].co
            uv.data[loop_index].uv = ((vertex.x - lo[0]) / width, (vertex.z - lo[2]) / height)
    material, texture_path = create_material(stem, spec["colour"])
    obj.data.materials.clear()
    obj.data.materials.append(material)
    obj.name = stem
    obj.data.name = f"{stem}_Mesh"
    obj.location = (0, 0, 0)
    return texture_path


def export(stem):
    spec = SPECS[stem]
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(RAW / f"{stem}.glb"))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"No mesh imported for {stem}")
    active_only(meshes[0])
    for obj in meshes[1:]:
        obj.select_set(True)
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    texture = prepare(stem, obj, spec)
    output = ROOT / f"{stem}.fbx"
    active_only(obj)
    bpy.ops.export_scene.fbx(
        filepath=str(output), use_selection=True, object_types={"MESH"},
        global_scale=1.0, apply_unit_scale=True, apply_scale_options="FBX_SCALE_NONE",
        axis_forward="-Z", axis_up="Y", use_mesh_modifiers=True,
        mesh_smooth_type="FACE", bake_anim=False, path_mode="COPY", embed_textures=False,
    )
    print(f"EXPORTED {output} tris={triangles(obj)} texture={texture}")


if __name__ == "__main__":
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.length_unit = "CENTIMETERS"
    for asset in SPECS:
        raw = RAW / f"{asset}.glb"
        if raw.exists():
            export(asset)
