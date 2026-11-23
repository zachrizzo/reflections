"""Blender (no window): textured pictures of garment meshes from different generators, one row each.

  blender -b --python render_compare.py -- <out.png> <label>=<textured.obj> ...

Each mesh is scaled to the same height and centred; views: front, back, side, from above at the front.
Workbench renderer, texture colour, studio light, backfaces shown (so inside walls are visible through openings).
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
out = Path(args[0]).resolve()
items = [a.split("=", 1) for a in args[1:]]
VIEWS = [("front", 0, 5), ("back", 180, 5), ("side", 90, 5), ("front, from above", 25, 40)]
CELL = 560

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
shading = scene.display.shading
shading.light = "STUDIO"
shading.color_type = "TEXTURE"
shading.show_backface_culling = False
shading.show_cavity = True
shading.cavity_type = "WORLD"
scene.display.render_aa = "8"
scene.render.resolution_x = CELL
scene.render.resolution_y = CELL
scene.render.film_transparent = False
world = bpy.data.worlds.new("w"); world.color = (0.6, 0.6, 0.62); scene.world = world
scene.view_settings.view_transform = "Standard"
scene.view_settings.exposure = 0.6
cam_data = bpy.data.cameras.new("cam"); cam_data.type = "ORTHO"; cam_data.ortho_scale = 1.25
cam = bpy.data.objects.new("cam", cam_data); scene.collection.objects.link(cam); scene.camera = cam

objects = []
for label, path in items:
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=path, forward_axis="NEGATIVE_Z", up_axis="Y")
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    for o in new:
        o.hide_render = True
    objects.append((label, new))


def frame(objs):
    lo = Vector((1e9, 1e9, 1e9)); hi = Vector((-1e9, -1e9, -1e9))
    for o in objs:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
    return lo, hi


tiles = []
for label, objs in objects:
    lo, hi = frame(objs)
    size = max(hi - lo)
    centre = (lo + hi) / 2
    for o in objs:
        o.hide_render = False
    row = []
    for name, yaw, pitch in VIEWS:
        r = 4.0 * size
        a, p = math.radians(yaw), math.radians(pitch)
        offset = Vector((math.sin(a) * math.cos(p), -math.cos(a) * math.cos(p), math.sin(p))) * r
        cam.location = centre + offset
        cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam_data.ortho_scale = 1.15 * size
        target = out.with_name(f"_{out.stem}_{len(tiles)}_{len(row)}.png")
        scene.render.filepath = str(target)
        bpy.ops.render.render(write_still=True)
        row.append((target, f"{label}: {name}"))
    for o in objs:
        o.hide_render = True
    tiles.append(row)

# assemble with Blender's image API (no PIL inside Blender)
W, H = CELL * len(VIEWS), CELL * len(tiles)
sheet = bpy.data.images.new("sheet", W, H, alpha=False)
pixels = [0.12] * (W * H * 4)
for ri, row in enumerate(tiles):
    for ci, (path, _) in enumerate(row):
        img = bpy.data.images.load(str(path))
        src = list(img.pixels)
        y0 = (len(tiles) - 1 - ri) * CELL
        for y in range(CELL):
            s = y * CELL * 4
            d = ((y0 + y) * W + ci * CELL) * 4
            pixels[d:d + CELL * 4] = src[s:s + CELL * 4]
        bpy.data.images.remove(img)
        Path(path).unlink()
sheet.pixels = pixels
sheet.filepath_raw = str(out)
sheet.file_format = "PNG"
sheet.save()
print("WROTE", out, [[t[1] for t in row] for row in tiles])
