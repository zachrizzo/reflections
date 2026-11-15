"""Build late-medieval London's timber bays for a wall-backed Unreal PCG pass."""

import json
import math
from pathlib import Path
import random
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "Kit"))
from build_facade_kit import Bay

HALF = 2.25
STOREY = 2.7
UPPER_LEVELS = 4
PAL = {
    "LimePlaster": ((.57, .50, .36), .94, 1.8),
    "WarmPlaster": ((.46, .35, .23), .96, 1.8),
    "Oak": ((.088, .048, .024), .86, .8),
    "WeatheredOak": ((.145, .073, .037), .91, .8),
    "ShopGreen": ((.050, .100, .067), .84, .8),
    "ShopRed": ((.176, .064, .040), .85, .8),
    "Interior": ((.016, .012, .009), .96, None),
    "LeadedGlass": ((.092, .125, .099), .38, None),
    "Lead": ((.052, .054, .041), .69, None),
    "Fieldstone": ((.25, .23, .176), .94, 1.35),
    "ClayTile": ((.23, .104, .07), .9, 1.0),
}


def crossbeam(bay, x0, x1, a, b, width, role):
    dy, dz = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dy, dz)
    ey, ez = -dz * width / (2 * length), dy * width / (2 * length)
    bay.prism(((a[0] - ey, a[1] - ez), (b[0] - ey, b[1] - ez),
               (b[0] + ey, b[1] + ez), (a[0] + ey, a[1] + ez)), x0, x1, role)


def backfill(bay, left, right, low, high, depth, plaster):
    bay.band(left, right, low, high, -.065, depth, plaster)


def plinth(bay, left, right, rng):
    for row in range(2):
        x = left
        bottom = row * .18
        while x < right - .025:
            end = min(right, x + rng.uniform(.24, .56))
            bay.band(x, end - .009, bottom + .007, bottom + .17, -.02, .127 + rng.uniform(-.007, .018),
                     "Fieldstone")
            x = end


def shutter(bay, left, right, low, high, depth, finish):
    for board in range(max(2, math.ceil((right - left) / .15))):
        width = min(.15, right - left - board * .15)
        if width <= .01:
            break
        y = left + board * .15
        bay.band(y, y + width - .006, low, high, depth, depth + .027, finish)
    for z in (low + .11, high - .14):
        bay.band(left, right, z, z + .062, depth + .026, depth + .061, "Oak")


def leaded(bay, left, right, low, high, depth, square_bay):
    bay.band(left, right, low, high, depth, depth + .017, "LeadedGlass")
    for y in (left, (left + right) / 2, right):
        bay.band(y - .048, y + .048, low, high, depth, depth + .105, "Oak")
    for z in (low, high):
        bay.band(left - .046, right + .046, z - .049, z + .049, depth, depth + .105, "Oak")
    bay.band(left - .113, right + .113, low - .055, low + .005, depth, depth + .196, "WeatheredOak")
    if square_bay:
        for i in (1, 3):
            y = left + (right - left) * i / 4
            crossbeam(bay, depth + .016, depth + .026, (y, low), (y, high), .017, "Lead")
        crossbeam(bay, depth + .016, depth + .026, (left, (low + high) / 2), (right, (low + high) / 2), .017, "Lead")
    else:
        width = right - left
        height = high - low
        for sign in (-1, 1):
            for bias in (-.75, -.25, .25, .75, 1.25, 1.75):
                s0, s1 = sorted((sign * -bias, sign * (1 - bias)))
                s0, s1 = max(0, s0), min(1, s1)
                if s0 < s1:
                    crossbeam(bay, depth + .016, depth + .032, (left + width * s0, low + height * (bias + sign * s0)),
                              (left + width * s1, low + height * (bias + sign * s1)), .016, "Lead")


def shop(bay, variant, plaster, oak):
    finish = ("ShopGreen", "ShopRed", "WeatheredOak")[variant]
    door_l, door_r = ((.87, 1.91), (-1.94, -.93), (.67, 1.93))[variant]
    stall_l, stall_r = ((-1.91, .66), (-.68, 1.88), (-1.93, .44))[variant]
    backfill(bay, -HALF, HALF, 0, STOREY, .014, "Interior")
    for left, right in ((-HALF, min(door_l, stall_l)), (max(door_r, stall_r), HALF),
                        (min(door_r, stall_r), max(door_l, stall_l))):
        if left < right:
            backfill(bay, left, right, .02, STOREY, .19, plaster)
    plinth(bay, stall_l, stall_r, random.Random(411 + variant))
    shutter(bay, stall_l, stall_r, .36, .87, .11, oak)
    bay.band(stall_l - .075, stall_r + .08, .85, .952, .09, .393, "WeatheredOak")
    bay.band(stall_l, stall_r, 2.09, STOREY, .04, .24, plaster)
    if variant == 1:
        for y in (stall_l + .10, stall_r - .59):
            shutter(bay, y, y + .49, .96, 2.06, .19, finish)
        crossbeam(bay, .025, .057, (stall_l, 1.54), (stall_r, 1.54), .075, oak)
    elif variant == 2:
        for i in range(3):
            left = stall_l + .06 + i * (stall_r - stall_l - .096) / 3
            leaded(bay, left, left + .66, .99, 2.035, .033, True)
    else:
        for x in (stall_l + .19, stall_l + .34, stall_r - .33):
            bay.band(x, x + .075, 1.0, 2.07, .034, .095, "WeatheredOak")
        bay.band(stall_l, stall_r, 1.12, 1.18, .041, .167, oak)
        bay.band(stall_l, stall_r, 1.48, 1.52, .043, .096, oak)
    for y in (stall_l, stall_r):
        bay.band(y - .049, y + .049, .88, 2.26, .034, .244, oak)
    bay.band(stall_l - .05, stall_r + .05, 2.055, 2.22, .023, .272, oak)
    # Uneven board door recessed into the deep external frame.
    shutter(bay, door_l + .043, door_r - .041, .043, 1.99, .046, finish)
    for y in (door_l, door_r):
        bay.band(y - .049, y + .049, .02, 2.16, .035, .265, oak)
    peak = 2.36 if variant == 0 else 2.26
    ymid = (door_l + door_r) / 2
    bay.prism(((door_l, 1.96), (door_r, 1.96), (door_r, 2.14), (ymid, peak), (door_l, 2.14)), .023, .094, finish)
    crossbeam(bay, .075, .258, (door_l, 2.14), (ymid, peak), .133, oak)
    crossbeam(bay, .075, .258, (ymid, peak), (door_r, 2.14), .133, oak)
    backfill(bay, door_l, door_r, peak, STOREY, .175, plaster)
    crossbeam(bay, .077, .114, (door_r - .22, .93), (door_r - .08, .93), .035, "Lead")
    for y in (-HALF + .10, HALF - .10):
        bay.band(y - .10, y + .10, 0, STOREY, .073, .257, oak)
    bay.band(-HALF, HALF, 2.49, 2.71, .036, .463, oak)
    for y in [-1.89, -.87, .09, 1.10, 1.94]:
        bay.band(y - .074, y + .074, 2.43, 2.64, .254, .452, "WeatheredOak")


def upper_floor(bay, variant, level, plaster, oak):
    low = STOREY + level * 2.42
    high = low + 2.42
    depth = (0.36, .54, .56, .58)[level]
    indices = ((-.80, +.82), (-.98, +.63), (0,))[variant]
    width = 1.61 if len(indices) == 1 else 1.01
    sill = low + (.68 if level == 0 else .73)
    head = high - .49
    backfill(bay, -HALF, HALF, low, high, depth - .134, "Interior")
    backfill(bay, -HALF, HALF, low, sill - .023, depth, plaster)
    backfill(bay, -HALF, HALF, head + .049, high, depth, plaster)
    left = -HALF
    for center in indices:
        right = center - width / 2
        backfill(bay, left, right, sill - .046, head + .053, depth, plaster)
        leaded(bay, right, center + width / 2, sill, head, depth - .111, variant == 2)
        left = center + width / 2
    backfill(bay, left, HALF, sill - .046, head + .053, depth, plaster)
    for y in (-HALF + .083, HALF - .083):
        bay.band(y - .083, y + .083, low, high, depth - .028, depth + .125, oak)
    for y in ((0, -1.45, 1.49) if variant == 2 else (0,)):
        bay.band(y - .078, y + .078, low + .09, sill - .03, depth - .078, depth + .099, oak)
        bay.band(y - .069, y + .069, head + .043, high, depth - .073, depth + .096, oak)
    a, b = (1, -1) if variant == 1 else (-1, 1)
    for sign in (a, b):
        foot = (sign * (2.08 if variant != 1 else 1.98), low + .12)
        knee = (sign * (.71 if variant != 2 else .28), sill - .075)
        crossbeam(bay, depth - .071, depth + .103, foot, knee, .137, oak)
    bay.band(-HALF, HALF, low, low + .149, depth - .083, depth + .141, oak)
    bay.band(-HALF, HALF, high - .184, high, depth - .098, depth + .163, oak)


def crown(bay, variant, plaster, oak):
    base = STOREY + UPPER_LEVELS * 2.42
    peak = base + (1.62, 1.82, 1.40)[variant]
    center = (0, -.16, .09)[variant]
    # The retained backing masks the original 15 m wall behind the gable.
    bay.band(-HALF, HALF, base, 14.84, -.06, .036, "ClayTile")
    bay.prism(((-HALF, base), (HALF, base), (center, peak)), -.064, .637, plaster)
    crossbeam(bay, .58, .782, (center, base), (center, peak - .06), .148, oak)
    for y in (-1.18, 1.18):
        rise = (1 - abs(y - center) / (HALF - math.copysign(center, y))) * (peak - base)
        bay.band(y - .058, y + .058, base, base + rise - .022, .57, .765, oak)
    for y in (-HALF, HALF):
        crossbeam(bay, .612, .835, (y, base), (center, peak), .175, oak)
        crossbeam(bay, -.065, .90, (y, base + .062), (center, peak + .068), .095, "ClayTile")
        for index in range(1, 9):
            t = index / 9
            y0, z0 = y + (center - y) * t, base + (peak - base) * t + .1
            crossbeam(bay, .753, .918, (y0 - .060, z0 - .027), (y0 + .060, z0 + .027), .066, "ClayTile")
    bay.band(center - .061, center + .061, peak - .028, peak + .236, .669, .825, oak)


def make_bay(variant, name):
    bay = Bay()
    plaster = "WarmPlaster" if variant == 1 else "LimePlaster"
    oak = "WeatheredOak" if variant == 2 else "Oak"
    shop(bay, variant, plaster, oak)
    for level in range(UPPER_LEVELS):
        upper_floor(bay, variant, level, plaster, oak)
    crown(bay, variant, plaster, oak)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(bay.vertices, [], bay.polygons)
    mesh.update()
    roles = list(dict.fromkeys(bay.roles))
    for role in roles:
        mat_name = "M_GLMedieval_" + role
        material = bpy.data.materials.get(mat_name) or bpy.data.materials.new(mat_name)
        material.diffuse_color = (*PAL[role][0], 1)
        material.roughness = PAL[role][1]
        mesh.materials.append(material)
    uv_layer = mesh.uv_layers.new(name="UV0")
    for polygon, role in zip(mesh.polygons, bay.roles):
        polygon.material_index = roles.index(role)
        normal = polygon.normal
        tile = PAL[role][2] or 1.0
        direction = max(range(3), key=lambda axis: abs(normal[axis]))
        u, v = ((1, 2), (0, 2), (1, 0))[direction]
        for loop_idx in polygon.loop_indices:
            xyz = mesh.vertices[mesh.loops[loop_idx].vertex_index].co
            uv_layer.data[loop_idx].uv = xyz[u] / tile, xyz[v] / tile
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.update()
    return obj, roles


def source(out_dir):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": 1,
        "width_cm": int(HALF * 200),
        "pivot": "center of bottom seam, authored wall plane, +X streetside",
        "meshes": {},
        "materials": {},
    }
    for index, style in enumerate(("Mercer", "Chandler", "Scrivener")):
        name = "SM_GLMedieval_" + style
        obj, roles = make_bay(index, name)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.export_scene.fbx(filepath=str(out_dir / f"{name}.fbx"), use_selection=True, object_types={"MESH"},
                                 global_scale=1.0, apply_unit_scale=True, axis_forward="-Z", axis_up="Y",
                                 use_mesh_modifiers=True, mesh_smooth_type="FACE", use_triangles=False,
                                 bake_anim=False)
        manifest["meshes"][name] = {
            "fbx": f"Source/{name}.fbx",
            "min_cm": [round(min(v[axis] for v in obj.bound_box) * 100, 3) for axis in range(3)],
            "max_cm": [round(max(v[axis] for v in obj.bound_box) * 100, 3) for axis in range(3)],
            "materials": ["M_GLMedieval_" + r for r in roles],
        }
        for role in roles:
            rgb, roughness, tile = PAL[role]
            manifest["materials"]["M_GLMedieval_" + role] = {
                "linear_rgba": [*rgb, 1],
                "roughness": roughness,
                "metallic": 0,
                "texture": f"Textures/T_GLMedieval_{role}.png" if tile else None,
            }
        obj.location.y = (index - 1) * 4.5
    (ROOT / "medieval_kit.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if "--" in sys.argv:
        preview(Path(sys.argv[sys.argv.index("--") + 1]))


def preview(output):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studiolight_rotate_z = 0.36
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.display.shading.background_type = "WORLD"
    scene.world = bpy.data.worlds.new("Overcast preview")
    scene.world.color = (.135, .123, .106)
    bpy.ops.object.camera_add(location=(19.2, -3.2, 7.5))
    camera = bpy.context.object
    camera.rotation_euler = (Vector((.0, .0, 7.1)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 18.9
    scene.camera = camera
    scene.render.resolution_x = 1040
    scene.render.resolution_y = 880
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(output.resolve())
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    source(ROOT / "Source")
