"""Build a reusable temporary watch gate and its timber wing module."""

import math
from pathlib import Path
import random
import runpy
import sys

import bpy
from mathutils import Vector


HERE = Path(__file__).resolve().parent
OUTPUT = HERE.parents[2] / 'Saved/MedievalLondon/MarketDressing'
TOOLS = runpy.run_path(str(HERE / 'build_market_dressing.py'))
block = TOOLS['block']
beam = TOOLS['beam']
cylinder = TOOLS['cylinder']
mesh = TOOLS['mesh']
rope = TOOLS['rope']
material = TOOLS['material']
RNG = random.Random(191)


def stake(y, width, height, depth, mat):
    base = (
        (-depth / 2, y - width / 2, 0), (depth / 2, y - width / 2, 0),
        (depth / 2, y + width / 2, 0), (-depth / 2, y + width / 2, 0),
    )
    vertices = [*base, *((x, side_y, height - .24) for x, side_y, _ in base),
                (-depth / 5, y - .022, height), (depth / 4, y - .022, height)]
    faces = [(3, 2, 1, 0), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6),
             (3, 0, 4, 7), (4, 5, 9, 8), (5, 6, 9), (6, 7, 8, 9), (7, 4, 8)]
    mesh('Hewn stake', vertices, faces, (mat,))


def wing(center):
    for i in range(8):
        y = center + (i - 3.5) * .229
        height = 2.28 + RNG.uniform(-.10, .11)
        stake(y, .216, height, .174 + RNG.uniform(-.017, .025), TIMBER[i % len(TIMBER)])
    for z in (.60, 1.55):
        beam((.124, center - .925, z), (.124, center + .925, z), .14, .165, OAK_SHADOW)
        for i in range(8):
            y = center + (i - 3.5) * .229
            cylinder((.17, y, z), (.217, y, z), .015, IRON, 6)
    for y in (center - .71, center + .71):
        beam((-.138, y, 1.70), (-.94, y, .06), .14, .145, OAK)
        block((-.86, y, .07), (.33, .25, .14), OAK_SHADOW, .02)


def pennant(center):
    y0 = center - .305
    y1 = center + .305
    vertices, faces = [], []
    nx, nz = 24, 26
    for row in range(nz + 1):
        v = row / nz
        for column in range(nx + 1):
            t = column / nx
            y = y0 + (y1 - y0) * t
            z = 2.21 - .92 * v + .14 * v ** 6 * abs(2 * t - 1)
            x = .29 + .038 * math.sin(t * math.tau * 2.5 + v * .6) * math.sin(v * 2.6)
            vertices.append((x, y, z))
    for row in range(nz):
        for column in range(nx):
            a = row * (nx + 1) + column
            faces.append((a, a + nx + 1, a + nx + 2, a + 1))
    cloth = mesh('Wool watch pennant', vertices, faces, (BANNER, EMBLEM, STITCH), smooth=True)
    for face in cloth.data.polygons:
        j, i = divmod(face.index, nx)
        diamond = abs(i + .5 - nx / 2) / 8 + abs(j + .5 - nz / 2) / 9.4
        if .50 < diamond < 1.04:
            face.material_index = 1
        elif i in (0, nx - 1) or j == nz - 1:
            face.material_index = 2
    bpy.ops.object.select_all(action='DESELECT')
    cloth.select_set(True)
    bpy.context.view_layer.objects.active = cloth
    thick = cloth.modifiers.new('Wool thickness', 'SOLIDIFY')
    thick.thickness = .004
    bpy.ops.object.modifier_apply(modifier=thick.name)
    cylinder((.295, center - .395, 2.244), (.295, center + .395, 2.244), .023, OAK, 10)
    for side in (-1, 1):
        y = center + .365 * side
        beam((.09, y, 2.23), (.305, y, 2.244), .041, .05, OAK, .006)
    for edge in (y0 + .045, y1 - .045):
        rope([(.29, edge, 2.18), (.329, edge, 2.244), (.296, edge, 2.276),
              (.263, edge, 2.24), (.274, edge, 2.18)], .009, HEMP)


def gate():
    for side in (-1, 1):
        wing(side * 2.62)
        y = side * 1.79
        block((.025, y, 1.64), (.34, .32, 3.28), OAK, .027)
        block((.025, y, .105), (.39, .40, .21), OAK_SHADOW, .029)
        block((.025, y, 3.267), (.39, .382, .19), OAK_SHADOW, .023)
        beam((.018, y, 2.55), (.018, y - side * .57, 3.136), .155, .185, OAK_PALE, .019)
        for z in (.40, 2.45, 2.83):
            block((.196, y, z), (.022, .261, .077), IRON, .007)
            for dx in (-.08, .08):
                cylinder((.198, y + dx, z), (.238, y + dx, z), .015, IRON, 7)
        pennant(side * 2.38)
    beam((.015, -2.05, 3.23), (.015, 2.05, 3.23), .23, .27, OAK_SHADOW, .025)
    beam((.17, -2.08, 3.32), (.17, 2.08, 3.32), .085, .097, OAK, .013)


def export(name, make):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    make()
    bpy.ops.object.select_all(action='SELECT')
    obj = bpy.context.selected_objects[0]
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.join()
    obj.name = name
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.export_scene.gltf(filepath=str(OUTPUT / f'{name}.glb'), export_format='GLB',
                             use_selection=True, export_yup=True, export_materials='EXPORT')
    obj.data.calc_loop_triangles()
    print(f'{name}: {len(obj.data.loop_triangles)} triangles')


def preview():
    scene = bpy.context.scene
    bpy.ops.mesh.primitive_plane_add(size=200)
    bpy.context.object.data.materials.append(material('Preview earth', (112, 103, 88)))
    for position, power, size in (((4, -5, 7), 1700, 6), ((-3, 2, 5), 1100, 5)):
        bpy.ops.object.light_add(type='AREA', location=position)
        light = bpy.context.object
        light.rotation_euler = (Vector((0, 0, 1.5)) - light.location).to_track_quat('-Z', 'Y').to_euler()
        light.data.energy = power
        light.data.size = size
    bpy.ops.object.camera_add(location=(9.3, -5.1, 4.8))
    cam = bpy.context.object
    cam.rotation_euler = (Vector((0, 0, 1.55)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = 47
    scene.camera = cam
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 20
    scene.render.resolution_x = 1152
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(OUTPUT / 'watch_gate_preview.png')
    bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    OUTPUT.mkdir(parents=True, exist_ok=True)
    OAK = material('Palisade Oak', (103, 74, 48))
    OAK_SHADOW = material('Palisade Weathered', (74, 54, 40))
    OAK_PALE = material('Palisade Hewn', (121, 91, 60))
    IRON = material('Palisade Iron', (54, 54, 50), .60, .36)
    HEMP = material('Palisade Rope', (173, 142, 92), .94)
    BANNER = material('Occupied Burgundy Wool', (84, 42, 48), .93)
    EMBLEM = material('Occupied Pale Badge', (214, 191, 142), .93)
    STITCH = material('Occupied Dark Binding', (57, 45, 43), .93)
    TIMBER = (OAK, OAK_SHADOW, OAK, OAK_PALE, OAK, OAK_SHADOW)
    export('SM_GL1450_WatchPalisadeWing', lambda: wing(0))
    export('SM_GL1450_WatchGate', gate)
    if '--preview' in sys.argv:
        preview()
