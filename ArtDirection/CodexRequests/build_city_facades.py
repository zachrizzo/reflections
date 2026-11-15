import bpy
import json
from pathlib import Path


ROOT = Path(r"C:\Users\zachc\Documents\Unreal Projects\reflections\ArtDirection\CodexRequests\City2026_11_14")
REFERENCES = ROOT / "References"
SOURCE = ROOT / "Source"

SIDES = {
    "Pewterside": {
        "wall": (0.22, 0.23, 0.24, 1), "trim": (0.38, 0.37, 0.34, 1),
        "accent": (0.12, 0.08, 0.05, 1), "glass": (0.14, 0.18, 0.19, 1),
    },
    "Giltside": {
        "wall": (0.31, 0.09, 0.07, 1), "trim": (0.55, 0.32, 0.13, 1),
        "accent": (0.16, 0.06, 0.025, 1), "glass": (0.66, 0.37, 0.10, 1),
    },
    "Frostside": {
        "wall": (0.48, 0.54, 0.58, 1), "trim": (0.71, 0.76, 0.79, 1),
        "accent": (0.10, 0.13, 0.15, 1), "glass": (0.40, 0.57, 0.67, 1),
    },
}


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)


def select_only(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def ensure_texture(side, source_dir):
    texture_dir = source_dir / "Textures"
    texture_dir.mkdir(parents=True, exist_ok=True)
    texture_path = texture_dir / f"T_{side}_Facade_BaseColor.png"
    image = bpy.data.images.load(str(REFERENCES / f"{side}_FacadeKit_Reference.png"), check_existing=False)
    image.scale(1024, 1024)
    image.filepath_raw = str(texture_path)
    image.file_format = "PNG"
    image.save()
    return bpy.data.images.load(str(texture_path), check_existing=False), texture_path


def material(side, role, image):
    name = f"M_{side}_Facade_{role.title()}"
    existing = bpy.data.materials.get(name)
    if existing:
        return existing
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = SIDES[side][role]
    bsdf.inputs["Roughness"].default_value = 0.67 if role != "glass" else 0.28
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    mix = nodes.new("ShaderNodeMixRGB")
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 0.13
    mix.inputs[1].default_value = SIDES[side][role]
    links.new(tex.outputs["Color"], mix.inputs[2])
    links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def box(name, location, dimensions, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return obj


def join_parts(name, parts):
    select_only(parts[0])
    for obj in parts[1:]:
        obj.select_set(True)
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    obj.data.name = f"{name}_Mesh"
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    obj.location = (0, 0, 0)
    if not obj.data.uv_layers:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(island_margin=0.02)
        bpy.ops.object.mode_set(mode="OBJECT")
    return obj


def facade_ground(side, mats):
    p, wall, trim, accent = [], mats["wall"], mats["trim"], mats["accent"]
    # Exact 4m side extent; facade depth is deliberately shallow for stacking.
    p += [box("back", (0, 0.10, 1.60), (4.0, 0.25, 3.20), wall)]
    p += [box("leftPier", (-1.70, -0.11, 1.60), (0.60, 0.24, 3.20), trim),
          box("rightPier", (1.70, -0.11, 1.60), (0.60, 0.24, 3.20), trim),
          box("lintel", (0, -0.12, 2.96), (4.0, 0.26, 0.40), trim),
          box("base", (0, -0.13, 0.20), (4.0, 0.28, 0.40), trim)]
    p += [box("door", (0, -0.17, 1.18), (1.18, 0.13, 2.20), accent),
          box("doorHead", (0, -0.23, 2.36), (1.56, 0.12, 0.26), trim),
          box("doorLeft", (-0.77, -0.23, 1.25), (0.18, 0.12, 2.25), trim),
          box("doorRight", (0.77, -0.23, 1.25), (0.18, 0.12, 2.25), trim)]
    return join_parts(f"SM_{side}_FacadeGround", p)


def facade_upper(side, mats):
    p, wall, trim, glass = [], mats["wall"], mats["trim"], mats["glass"]
    p += [box("back", (0, 0.10, 1.60), (4.0, 0.25, 3.20), wall),
          box("top", (0, -0.11, 2.98), (4.0, 0.24, 0.32), trim),
          box("base", (0, -0.11, 0.18), (4.0, 0.24, 0.36), trim)]
    for x in (-0.95, 0.95):
        p += [box("window", (x, -0.16, 1.70), (1.05, 0.10, 1.50), glass),
              box("winTop", (x, -0.22, 2.50), (1.35, 0.12, 0.20), trim),
              box("winBottom", (x, -0.22, 0.91), (1.35, 0.12, 0.18), trim),
              box("winL", (x - 0.62, -0.22, 1.70), (0.15, 0.12, 1.65), trim),
              box("winR", (x + 0.62, -0.22, 1.70), (0.15, 0.12, 1.65), trim),
              box("mullion", (x, -0.24, 1.70), (0.07, 0.06, 1.40), trim)]
    return join_parts(f"SM_{side}_FacadeUpper", p)


def facade_corner(side, mats):
    p, wall, trim, glass = [], mats["wall"], mats["trim"], mats["glass"]
    p += [box("core", (0, 0, 1.60), (4.0, 4.0, 3.20), wall),
          # Keep all detail inside the exact 4m x 4m placement footprint.
          box("frontTop", (0, -1.91, 2.96), (4.0, 0.18, 0.35), trim),
          box("sideTop", (1.91, 0, 2.96), (0.18, 4.0, 0.35), trim),
          box("cornerQuoin", (1.825, -1.825, 1.60), (0.35, 0.35, 3.20), trim)]
    for x, y, dx, dy in [(-0.80, -1.95, 0.95, 0.08), (1.95, -0.80, 0.08, 0.95)]:
        p += [box("cornerWindow", (x, y, 1.70), (dx, dy, 1.35), glass),
              box("cornerSill", (x, y, 0.96), (dx + 0.25 if dx > dy else dx, dy + 0.25 if dy > dx else dy, 0.16), trim)]
    return join_parts(f"SM_{side}_FacadeCorner", p)


def facade_cornice(side, mats):
    p, trim, wall = [], mats["trim"], mats["wall"]
    p += [box("body", (0, 0, 0.30), (4.0, 0.65, 0.60), wall),
          box("cap", (0, -0.02, 0.55), (4.0, 0.78, 0.16), trim),
          box("lowerBand", (0, -0.34, 0.18), (4.0, 0.12, 0.15), trim),
          box("upperBand", (0, -0.37, 0.43), (4.0, 0.09, 0.10), trim)]
    for x in (-1.45, -0.48, 0.48, 1.45):
        p.append(box("bracket", (x, -0.38, 0.12), (0.20, 0.14, 0.24), trim))
    return join_parts(f"SM_{side}_FacadeCornice", p)


def export_obj(obj, side, source_dir):
    source_dir.mkdir(parents=True, exist_ok=True)
    output = source_dir / f"{obj.name}.fbx"
    select_only(obj)
    bpy.ops.export_scene.fbx(
        filepath=str(output), use_selection=True, object_types={"MESH"},
        global_scale=1.0, apply_unit_scale=True, apply_scale_options="FBX_SCALE_NONE",
        axis_forward="-Z", axis_up="Y", use_mesh_modifiers=True,
        mesh_smooth_type="FACE", bake_anim=False, path_mode="COPY", embed_textures=False,
    )
    triangles = sum(len(poly.vertices) - 2 for poly in obj.data.polygons)
    return {"asset": obj.name, "fbx": str(output), "triangles": triangles,
            "dimensions_cm": [round(v * 100, 1) for v in obj.dimensions], "pivot": "bottom-centre"}


def main():
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.length_unit = "METERS"
    report = []
    for side in SIDES:
        clear_scene()
        source_dir = SOURCE / side / "City"
        image, texture_path = ensure_texture(side, source_dir)
        mats = {role: material(side, role, image) for role in ("wall", "trim", "accent", "glass")}
        for builder in (facade_ground, facade_upper, facade_corner, facade_cornice):
            obj = builder(side, mats)
            row = export_obj(obj, side, source_dir)
            row["texture"] = str(texture_path)
            report.append(row)
            bpy.data.objects.remove(obj, do_unlink=True)
    (ROOT / "facade_source_build_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
