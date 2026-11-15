"""Build an original timber stall and market goods, in metres and facing +X.

Run in background Blender. Output is confined to Saved/MedievalLondon.
"""

import math
from pathlib import Path
import random
import sys

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / 'Saved/MedievalLondon/MarketDressing'
RNG = random.Random(1450)


def linear(channel):
    value = channel / 255.0
    return value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4


def material(name, rgb, roughness=.73, metal=0):
    mat = bpy.data.materials.new(name)
    color = (*map(linear, rgb), 1)
    mat.diffuse_color = color
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = color
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metal
    return mat


def beam(a, b, width, depth, mat, bevel=.011):
    start, end = Vector(a), Vector(b)
    direction = end - start
    obj = block((start + end) / 2, (width, depth, direction.length), mat, bevel)
    obj.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
    return obj


def block(pos, size, mat, bevel=.008):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    obj = bpy.context.object
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        modifier = obj.modifiers.new('Rounded wear', 'BEVEL')
        modifier.width = bevel
        modifier.segments = 1
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    return obj


def cylinder(a, b, radius, mat, vertices=10):
    start, end = Vector(a), Vector(b)
    delta = end - start
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=delta.length,
                                        location=(start + end) / 2)
    obj = bpy.context.object
    obj.rotation_euler = delta.to_track_quat('Z', 'Y').to_euler()
    obj.data.materials.append(mat)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return obj


def rope(points, radius, mat):
    curve = bpy.data.curves.new('Twisted binding', 'CURVE')
    curve.dimensions = '3D'
    curve.resolution_u = 1
    curve.bevel_depth = radius
    curve.bevel_resolution = 1
    path = curve.splines.new('POLY')
    path.points.add(len(points) - 1)
    for point, co in zip(path.points, points, strict=True):
        point.co = (*co, 1)
    obj = bpy.data.objects.new('Binding', curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target='MESH')


def lathe(x, y, z, profile, mat, segments=20, x_scale=1.0, y_scale=1.0, warp=0):
    vertices, faces = [], []
    for ring, (height, radius) in enumerate(profile):
        for i in range(segments):
            angle = math.tau * i / segments
            variation = 1 + warp * (math.sin(angle * 5 + ring * .6) + .45 * math.sin(angle * 3 - ring))
            vertices.append((x + radius * variation * math.cos(angle) * x_scale,
                             y + radius * variation * math.sin(angle) * y_scale, z + height))
    for ring in range(len(profile) - 1):
        for i in range(segments):
            base = ring * segments
            next_i = (i + 1) % segments
            faces.append((base + i, base + next_i, base + next_i + segments, base + i + segments))
    faces.extend((tuple(reversed(range(segments))), tuple(range(len(vertices) - segments, len(vertices)))))
    return mesh('Turned form', vertices, faces, (mat,), smooth=True)


def mesh(name, vertices, faces, materials, smooth=False):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    for mat in materials:
        data.materials.append(mat)
    uv = data.uv_layers.new(name='UVMap')
    for poly in data.polygons:
        poly.use_smooth = smooth and len(poly.vertices) == 4
        for index in poly.loop_indices:
            x, y, z = data.vertices[data.loops[index].vertex_index].co
            uv.data[index].uv = (x + y, z)
    return obj


def cloth_canopy():
    vertices, faces = [], []
    across, longitudinal = 24, 9
    for i in range(longitudinal + 1):
        s = i / longitudinal
        for j in range(across + 1):
            t = j / across
            x = -.67 + 1.40 * s
            y = -1.18 + 2.36 * t
            sway = .013 * math.cos(t * 7.5 * math.tau + .7 * s)
            billow = -.05 * math.sin(math.pi * s) * (1 - .3 * math.cos(t * math.tau * 3))
            z = 2.39 - .35 * s + billow + sway * s
            vertices.append((x, y, z))
    for i in range(longitudinal):
        for j in range(across):
            a = i * (across + 1) + j
            faces.append((a, a + across + 1, a + across + 2, a + 1))
    top_count = len(vertices)
    for j in range(across + 1):
        x, y, z = vertices[longitudinal * (across + 1) + j]
        vertices.append((x + .005, y, z - .103 - .013 * math.sin(j / across * 5 * math.tau)))
    for j in range(across):
        a = longitudinal * (across + 1) + j
        faces.append((a, a + 1, top_count + j + 1, top_count + j))
    obj = mesh('Linen canopy', vertices, faces, (LINEN, OCHRE), smooth=True)
    for poly in obj.data.polygons:
        j = poly.index % across
        poly.material_index = int(j in (2, 3, 20, 21))
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    thickness = obj.modifiers.new('Cloth thickness', 'SOLIDIFY')
    thickness.thickness = .004
    bpy.ops.object.modifier_apply(modifier=thickness.name)
    for x, z in ((-.67, 2.371), (.745, 2.018)):
        cylinder((x, -1.20, z), (x, 1.20, z), .018, DARK_OAK, 8)
    for y in (-1.075, 1.075):
        for x, z in ((-.635, 2.377), (.652, 2.055)):
            rope([(x, y - .019, z), (x + .044, y, z - .045),
                  (x, y + .019, z), (x - .038, y, z + .01)], .009, HEMP)


def basket(x, y, z, radius, produce):
    weave = [(0, .67 * radius), (.025, .75 * radius), (.17, radius),
             (.17, .87 * radius), (.044, .68 * radius)]
    lathe(x, y, z, weave, WICKER, 16)
    for h, mult in ((.035, .76), (.069, .82), (.103, .88), (.136, .94), (.173, .99)):
        ring = [(x + radius * mult * math.cos(i / 20 * math.tau),
                 y + radius * mult * math.sin(i / 20 * math.tau), z + h)
                for i in range(21)]
        rope(ring, .007 if h < .17 else .012, HEMP)
    for index in range(12):
        angle = math.tau * index / 12
        a = (x + .76 * radius * math.cos(angle), y + .76 * radius * math.sin(angle), z + .03)
        b = (x + radius * math.cos(angle + .10), y + radius * math.sin(angle + .10), z + .173)
        cylinder(a, b, .0045, HEMP, 5)
    for j in range(9):
        angle = j * 2.399963
        radial = .77 * radius * math.sqrt(j / 9)
        center = (x + radial * math.cos(angle), y + radial * math.sin(angle), z + .162 + .025 * RNG.random())
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=radius * .24, location=center)
        fruit = bpy.context.object
        fruit.scale = (.88 + RNG.random() * .18, .88 + RNG.random() * .18, .92)
        fruit.data.materials.append(produce[j % len(produce)])
        for poly in fruit.data.polygons:
            poly.use_smooth = True
        if j % 2 == 0:
            xr, yr, zr = center
            cylinder((xr, yr, zr + radius * .19), (xr + .012, yr - .009, zr + radius * .31),
                     .0035, DARK_OAK, 5)


def sack(x, y, z, scale=1):
    profile = [(h * scale, r * scale) for h, r in [(.0, .145), (.06, .21), (.19, .217),
               (.29, .197), (.36, .139), (.43, .073), (.45, .069), (.485, .087), (.512, .072)]]
    lathe(x, y, z, profile, SACK, 18, 1.15, .86, .075)
    ring = [(x + .08 * scale * 1.15 * math.cos(i * math.tau / 20),
             y + .08 * scale * .86 * math.sin(i * math.tau / 20), z + .446 * scale)
            for i in range(21)]
    rope(ring, .008 * scale, HEMP)
    rope([(x + .08 * scale, y, z + .445 * scale), (x + .12 * scale, y + .02, z + .431 * scale),
          (x + .15 * scale, y + .015, z + .382 * scale)], .006 * scale, HEMP)


def barrel(x, y, scale=1.0):
    staves = [(.015, .215), (.105, .249), (.242, .267), (.417, .253), (.568, .218)]
    staves = [(h * scale, r * scale) for h, r in staves]
    obj = lathe(x, y, 0, staves, OAK, 22)
    obj.data.materials.append(DARK_OAK)
    obj.data.materials.append(PALE_OAK)
    for poly in obj.data.polygons:
        poly.material_index = (0, 0, 0, 1, 0, 2, 0)[(poly.index % 22) % 7]
    for h, radius in ((.073, .24), (.151, .266), (.436, .254), (.51, .237)):
        lathe(x, y, 0, [(h * scale, radius * scale), ((h + .028) * scale, radius * scale)],
              IRON, 22)
    for i in (-1, 0, 1):
        y_line = y + .107 * i * scale
        width = .39 * math.sqrt(1 - (.107 * i / .216) ** 2) * scale
        beam((x - width / 2, y_line, .572 * scale), (x + width / 2, y_line, .572 * scale),
             .106 * scale, .017, PALE_OAK, .003)
    cylinder((x + .079 * scale, y, .579 * scale), (x + .079 * scale, y, .604 * scale),
             .025 * scale, DARK_OAK, 10)


def crate(x, y, z, length=.63, width=.43, height=.35):
    block((x, y, z + .035), (length, width, .07), DARK_OAK, .017)
    for dx in (-length / 2 + .027, length / 2 - .027):
        for dy in (-width / 2 + .025, width / 2 - .025):
            block((x + dx, y + dy, z + height / 2), (.045, .046, height), OAK)
    for i in range(3):
        h = z + (i + .55) * height / 3
        for dy in (-width / 2, width / 2):
            block((x, y + dy, h), (length, .026, height / 3 - .009), (OAK, PALE_OAK, OAK)[i], .006)
        for dx in (-length / 2, length / 2):
            block((x + dx, y, h), (.024, width, height / 3 - .009), PALE_OAK, .006)
    for i in (-1, 0, 1):
        block((x, y + .12 * i, z + height + .008), (length - .035, width / 3 - .004, .018), OAK, .004)


def stall():
    for y in (-1.075, 1.075):
        for x, length in ((-.52, 2.325), (.50, 2.043)):
            block((x, y, length / 2), (.098, .105, length), OAK, .017)
            block((x, y, .065), (.122, .128, .13), DARK_OAK, .011)
        beam((-.52, y, 2.266), (.73, y, 1.957), .076, .083, DARK_OAK)
        beam((.50, y, 1.62), (.21, y, 2.065), .058, .062, PALE_OAK)
        beam((-.52, y, 1.87), (-.20, y, 2.26), .060, .061, OAK)
        for height in (.965, .29):
            beam((-.51, y, height), (.50, y, height), .079, .073, DARK_OAK)
        for x, z in ((-.52, 2.30), (.50, 1.99), (-.52, .945), (.50, .945)):
            cylinder((x, y - .063, z), (x, y + .063, z), .014, PALE_OAK, 8)

    for x, z in ((-.52, 2.285), (.51, 1.994), (-.33, .915), (.33, .915)):
        beam((x, -1.122, z), (x, 1.122, z), .078, .081, DARK_OAK)
    for i in range(5):
        x = -.35 + i * .174
        block((x, 0, .978), (.165, 2.18, .048), (OAK, PALE_OAK, OAK, DARK_OAK, OAK)[i], .009)
    for x in (-.42, .42):
        block((x, 0, .89), (.047, 2.29, .121), PALE_OAK, .007)
    for y in (-1.075, 1.075):
        beam((.495, y, .65), (.495, y + (-.28 if y > 0 else .28), .89), .054, .045, DARK_OAK)
    cloth_canopy()
    basket(.06, -.78, 1.01, .225, (APPLE, APPLE_DARK, FRUIT_GOLD))
    basket(.012, -.24, 1.01, .20, (ROOT_BROWN, FRUIT_GOLD, ROOT_BROWN))
    basket(-.09, .31, 1.01, .21, (APPLE_LEAF, FRUIT_GOLD, APPLE_LEAF))
    sack(-.13, .80, 1.007, .68)
    crate(-.337, .57, .015, .48, .39, .25)


def crate_group():
    crate(-.02, .09, 0)
    crate(.026, .08, .37, .52, .37, .27)
    basket(.166, -.35, 0, .20, (FRUIT_GOLD, ROOT_BROWN, APPLE_LEAF))


def barrel_group():
    barrel(-.095, .116, 1.0)
    sack(.228, -.13, .0, .86)


def export(name, make):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    make()
    bpy.ops.object.select_all(action='SELECT')
    root = bpy.context.selected_objects[0]
    bpy.context.view_layer.objects.active = root
    bpy.ops.object.join()
    root.name = name
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.export_scene.gltf(filepath=str(OUTPUT / f'{name}.glb'), export_format='GLB',
                             use_selection=True, export_yup=True, export_materials='EXPORT')
    root.data.calc_loop_triangles()
    print(f'{name}: {len(root.data.loop_triangles)} triangles, {len(root.data.materials)} material slots')
    return root


def preview():
    scene = bpy.context.scene
    bpy.ops.mesh.primitive_plane_add(size=200)
    bpy.context.object.data.materials.append(material('Preview earth', (116, 111, 96)))
    bpy.ops.object.light_add(type='AREA', location=(3.1, -3.6, 5.0))
    main = bpy.context.object
    main.rotation_euler = (Vector((0, 0, 1.0)) - main.location).to_track_quat('-Z', 'Y').to_euler()
    main.data.energy = 850
    main.data.shape = 'DISK'
    main.data.size = 5.0
    bpy.ops.object.light_add(type='AREA', location=(-1.7, 1.2, 3.3))
    fill = bpy.context.object
    fill.rotation_euler = (Vector((0, 0, 1.1)) - fill.location).to_track_quat('-Z', 'Y').to_euler()
    fill.data.energy = 520
    fill.data.size = 4
    bpy.ops.object.camera_add(location=(3.7, -4.5, 2.9))
    cam = bpy.context.object
    cam.rotation_euler = (Vector((0, 0, 1.2)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = 49
    scene.camera = cam
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 24
    scene.render.resolution_x = 1152
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(OUTPUT / 'market_stall_preview.png')
    bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    OUTPUT.mkdir(parents=True, exist_ok=True)
    OAK = material('Oak Weathered', (104, 73, 44))
    PALE_OAK = material('Oak Exposed', (142, 104, 67))
    DARK_OAK = material('Oak Shadow', (69, 47, 31))
    LINEN = material('Undyed Linen', (180, 161, 118), .93)
    OCHRE = material('Ochre Linen', (137, 94, 50), .93)
    HEMP = material('Hemp Binding', (166, 136, 82), .96)
    WICKER = material('Wicker', (118, 81, 43), .88)
    SACK = material('Flax Sacking', (152, 116, 76), .95)
    APPLE = material('Apple Red', (147, 56, 36), .51)
    APPLE_DARK = material('Apple Oxide', (106, 35, 27), .57)
    APPLE_LEAF = material('Apple Green', (108, 110, 48), .56)
    FRUIT_GOLD = material('Yellow Fruit', (166, 129, 50), .61)
    ROOT_BROWN = material('Root Russet', (150, 90, 39), .69)
    IRON = material('Forged Iron', (67, 62, 53), .62, .42)
    export('SM_GL1450_CratesAndBasket', crate_group)
    export('SM_GL1450_CaskAndSack', barrel_group)
    export('SM_GL1450_MarketStall', stall)
    if '--preview' in sys.argv:
        preview()
