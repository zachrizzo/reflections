"""Original handcart and cargo for Gray London warehouse thresholds.

Run with Blender in background; pass -- --preview for an optional studio image.
GLBs are in metres, +X forward, with the pivot on the ground under each load.
"""

import json
import math
from pathlib import Path
import runpy
import sys

import bpy
from mathutils import Vector


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / 'Source'
LIB = runpy.run_path(str(HERE.parent / 'MarketDressing' / 'build_market_dressing.py'))
material, box, beam, cylinder, rope, lathe, mesh = (
    LIB[key] for key in ('material', 'block', 'beam', 'cylinder', 'rope', 'lathe', 'mesh')
)


def wheel(y):
    zc, broad = .445, .088
    yaw_segments = 32
    # Outer iron tire, then the wooden rim. The square cross-section is broken by a bevel.
    for mat, center_r, half_r, width in ((OAK, .385, .050, broad), (IRON, .438, .007, .070)):
        bevel = min(.007, half_r / 2)
        section = [(-width/2, -half_r + bevel), (-width/2 + bevel, -half_r),
                   (width/2 - bevel, -half_r), (width/2, -half_r + bevel),
                   (width/2, half_r - bevel), (width/2 - bevel, half_r),
                   (-width/2 + bevel, half_r), (-width/2, half_r - bevel)]
        corners, faces = [], []
        for index in range(yaw_segments):
            angle = math.tau * index / yaw_segments
            for dy, dr in section:
                r = center_r + dr
                corners.append((r * math.sin(angle), y + dy, zc + r * math.cos(angle)))
        for i in range(yaw_segments):
            for j in range(len(section)):
                k, nxt, n = (i + 1) % yaw_segments, (j + 1) % len(section), len(section)
                faces.append((i*n+j, i*n+nxt, k*n+nxt, k*n+j))
        mesh('Wheel tire' if mat == IRON else 'Elm wheel rim', corners, faces, (mat,))

    for i in range(8):
        a = math.tau * i / 8
        beam((.073 * math.sin(a), y, zc + .073 * math.cos(a)),
             (.377 * math.sin(a + .04), y, zc + .377 * math.cos(a + .04)),
             .057, .051, (OAK, EXPOSED, OAK, DARK)[i % 4], .009)
        for sign in (-1, 1):
            yy = y + .048 * sign
            cylinder((.388 * math.sin(a), yy, zc + .388 * math.cos(a)),
                     (.388 * math.sin(a), yy + .008 * sign, zc + .388 * math.cos(a)), .012, DARK, 7)
    cylinder((0, y-.09, zc), (0, y+.09, zc), .115, DARK, 16)
    cylinder((0, y-.10, zc), (0, y+.10, zc), .069, OAK, 14)
    for sign in (-1, 1):
        cylinder((0, y+.077*sign, zc), (0, y+.10*sign, zc), .097, IRON, 14)
    pin = y + math.copysign(.117, y)
    cylinder((0, pin, zc-.061), (0, pin, zc+.061), .012, IRON, 8)


def sack(x, y, z, size, squash=1):
    profile = [(h*size*squash, r*size) for h, r in (
        (0, .146), (.046, .203), (.18, .227), (.304, .203),
        (.372, .153), (.425, .074), (.442, .064), (.476, .096), (.49, .076)
    )]
    lathe(x, y, z, profile, SACK, 18, 1.17, .85, .069)
    rope([(x + .08*size*1.17*math.cos(i*math.tau/20),
           y + .08*size*.85*math.sin(i*math.tau/20), z + .439*size*squash)
          for i in range(21)], .009*size, HEMP)
    rope([(x+.09*size, y, z+.448*size*squash), (x+.14*size, y+.019*size, z+.423*size*squash),
          (x+.16*size, y+.046*size, z+.396*size*squash)], .007*size, HEMP)


def cask(x, y, z):
    profile = [(0, .24), (.095, .278), (.31, .300), (.56, .277), (.66, .236)]
    body = lathe(x, y, z, profile, OAK, 24, warp=.013)
    for mat in (EXPOSED, DARK):
        body.data.materials.append(mat)
    for p in body.data.polygons:
        if len(p.vertices) == 4:
            p.material_index = (0, 0, 2, 0, 1, 0, 0, 0)[p.index % 8]
    for h, r in ((.046,.261),(.128,.287),(.493,.289),(.589,.269)):
        lathe(x, y, z, [(h,r), (h+.03,r+.007), (h+.053,r+.003)], DARK, 24)
    for i in range(5):
        dy = (i-2)*.080
        chord = .223 * math.sqrt(1 - (dy/.236)**2)
        box((x, y+dy, z+.663), (2*chord, .077, .016), (OAK, EXPOSED, OAK, OAK, EXPOSED)[i], .003)
    cylinder((x+.092, y-.042, z+.667), (x+.092, y-.042, z+.685), .021, DARK, 9)


def coil(x, y, z, r):
    rope([(x + (r - .021*i/34)*math.cos(i*math.tau/34),
           y + .85*(r - .021*i/34)*math.sin(i*math.tau/34), z + .017*i/68)
          for i in range(103)], .0105, HEMP)
    rope([(x+r-.06, y, z+.025), (x+r+.072, y-.039, z+.017),
          (x+r+.120, y-.123, z+.014), (x+r+.093, y-.208, z+.012)], .010, HEMP)


def handcart():
    for y in (-.674, .674):
        wheel(y)
    cylinder((0, -.77, .445), (0, .77, .445), .052, DARK, 10)
    for y in (-.37, .37):
        side = math.copysign(1, y)
        beam((-.929, y, .565), (.730, y, .565), .082, .122, DARK, .013)
        beam((.486, y, .577), (1.589, side*.493, .789), .078, .091, OAK, .012)
        beam((1.526, side*.487, .777), (1.795, side*.503, .831), .068, .066, EXPOSED, .017)
        # Parked cart rests on both forward legs and both wheels.
        beam((.613, side*.368, .571), (.756, side*.390, .034), .076, .073, DARK, .012)
        box((.756, side*.390, .021), (.108, .093, .042), DARK, .007)
        beam((.715, side*.384, .227), (.374, side*.366, .538), .047, .052, OAK, .007)
        for zz, mat in ((.673, OAK), (.773, EXPOSED)):
            beam((-.872, side*.516, zz), (.562, side*.516, zz), .059, .049, mat, .007)
        for x in (-.841, -.19, .538):
            box((x, side*.517, .720), (.063, .070, .235), DARK, .008)
            cylinder((x, side*.55, .773), (x, side*.564, .773), .010, EXPOSED, 8)
    for x in (-.781, .018, .559):
        beam((x, -.557, .553), (x, .557, .553), .106, .091, OAK)
    for i in range(6):
        y = (i-2.5)*.159
        box((-.148,y,.628),(1.453,.151,.051),(OAK,EXPOSED,OAK,DARK,OAK,EXPOSED)[i],.006)
    box((-.857, 0, .73), (.080, 1.010, .167), OAK, .010)
    cask(-.491, .133, .653)
    sack(.180, -.221, .653, .97)
    sack(.289, .219, .653, .87, .75)
    coil(-.540, -.313, .659, .144)
    for t in (-.621, -.361):
        # Follow the outside of the bulged staves and the lid before tying to the rails.
        rope([(t,-.529,.760), (t,-.302,.803), (t,-.151,.892), (t,-.155,1.121),
              (t,-.120,1.255), (t,-.081,1.317), (t,-.030,1.336), (t,.282,1.336),
              (t,.348,1.317), (t,.390,1.255), (t,.419,1.121), (t,.412,.892),
              (t,.522,.790), (t,.547,.708), (t+.014,.505,.658)], .010, HEMP)


def loose_cargo():
    cask(-.205,.093,0)
    sack(.331,-.080,0,.92,.79)
    coil(-.033,-.322,.012,.132)


def reset_scene(clear_materials=False):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    if clear_materials:
        for old_material in list(bpy.data.materials):
            bpy.data.materials.remove(old_material)


def audit(obj):
    data = obj.data
    data.calc_loop_triangles()
    mins = [min(v.co[i] for v in data.vertices) for i in range(3)]
    maxs = [max(v.co[i] for v in data.vertices) for i in range(3)]
    assert min(v.normal.length for v in data.vertices) > .9
    return dict(name=obj.name, triangles=len(data.loop_triangles),
                material_sections=[m.name for m in data.materials],
                uv_layers=len(data.uv_layers),
                minimum_m=[round(x,4) for x in mins], maximum_m=[round(x,4) for x in maxs],
                dimensions_m=[round(b-a,4) for a,b in zip(mins,maxs,strict=True)],
                location=list(obj.location), rotation=list(obj.rotation_euler), scale=list(obj.scale))


def build(name, factory):
    reset_scene()
    factory()
    bpy.ops.object.select_all(action='SELECT')
    obj = bpy.context.selected_objects[0]
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.join()
    obj.name = obj.data.name = name
    bpy.context.scene.cursor.location = (0,0,0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    # Planar UV0 with no collapsed horizontal faces. The materials use solid PBR factors.
    obj.data.update()
    uv = obj.data.uv_layers.active or obj.data.uv_layers.new(name='UVMap')
    for poly in obj.data.polygons:
        normal = poly.normal
        axis = max(range(3), key=lambda i: abs(normal[i]))
        u, v = ((1,2),(0,2),(0,1))[axis]
        for index in poly.loop_indices:
            co = obj.data.vertices[obj.data.loops[index].vertex_index].co
            uv.data[index].uv = ((co[u]+2) / 4, (co[v]+2) / 4)
    report = audit(obj)
    assert report['minimum_m'][2] >= -.002 and abs(report['minimum_m'][2]) < .002
    bpy.ops.export_scene.gltf(filepath=str(OUTPUT / (name + '.glb')), export_format='GLB',
                             use_selection=True, export_yup=True, export_materials='EXPORT')
    return report


def preview():
    reset_scene()
    for name, offset in (('SM_GL1450_QuayHandcart',(0,0,0)),('SM_GL1450_QuayCargo',(-.78,-1.17,0))):
        bpy.ops.import_scene.gltf(filepath=str(OUTPUT / (name + '.glb')))
        bpy.context.selected_objects[0].location = offset
    bpy.ops.mesh.primitive_plane_add(size=200)
    bpy.context.object.data.materials.append(material('Preview earth', (114,112,101)))
    target = Vector((.13,-.30,.55))
    for location, power, size in (((2,-3,4),500,3),((-1,2,3),680,3)):
        bpy.ops.object.light_add(type='AREA', location=location)
        lamp = bpy.context.object
        lamp.rotation_euler = (target - lamp.location).to_track_quat('-Z','Y').to_euler()
        lamp.data.energy = power
        lamp.data.size = size
    bpy.ops.object.camera_add(location=(3.45,-4.9,2.7))
    cam = bpy.context.object
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.lens = 52
    scene = bpy.context.scene
    scene.camera = cam
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 16
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1080, 720
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(OUTPUT/'quay_dressing_preview.png')
    bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if '--audit-import' in sys.argv:
        expected = json.loads((OUTPUT/'quay_dressing_export.json').read_text(encoding='utf-8'))
        imported = []
        for source in expected:
            reset_scene(clear_materials=True)
            bpy.ops.import_scene.gltf(filepath=str(OUTPUT/(source['name'] + '.glb')))
            objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
            assert len(objects) == 1
            record = audit(objects[0])
            for key in ('triangles','uv_layers','material_sections','minimum_m','maximum_m',
                        'location','rotation','scale','name'):
                assert record[key] == source[key], (key, source[key], record[key])
            imported.append(record)
        (OUTPUT/'quay_dressing_roundtrip.json').write_text(json.dumps(imported, indent=2)+'\n', encoding='utf-8')
    else:
        OAK = material('Oak Weathered', (104,73,44))
        EXPOSED = material('Oak Exposed', (142,104,67))
        DARK = material('Oak Shadow', (69,47,31))
        SACK = material('Flax Sacking', (152,116,76), .95)
        HEMP = material('Hemp Binding', (166,136,82), .96)
        IRON = material('Forged Iron', (67,62,53), .62, .42)
        output = [build('SM_GL1450_QuayHandcart', handcart), build('SM_GL1450_QuayCargo', loose_cargo)]
        (OUTPUT/'quay_dressing_export.json').write_text(json.dumps(output, indent=2)+'\n', encoding='utf-8')
        if '--preview' in sys.argv:
            preview()
