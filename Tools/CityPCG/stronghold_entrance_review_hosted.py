"""Build and reimport an illustrative stronghold entrance on a hosted runner."""
import json
import math
from pathlib import Path
import runpy
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stronghold_entrance_review_common as common


ASSET_NAMES = ('PalisadeWing', 'GuardRack', 'SupplyStack', 'WatchSconce',
               'ClaimMarkerOccupied', 'ClaimMarkerReclaimed')
SCENE_NAMES = ('StrongholdEntrance_Occupied', 'StrongholdEntrance_Reclaimed')


def material(bpy, name, color, roughness=.85, emission=None):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = roughness
    if emission is not None:
        shader.inputs['Emission Color'].default_value = (*emission, 1)
        shader.inputs['Emission Strength'].default_value = 1.2
    return mat


def box(bpy, name, location, dimensions, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return obj


def cylinder(bpy, name, start, end, radius, mat, vertices=10):
    from mathutils import Vector
    a, b = Vector(start), Vector(end)
    direction = b-a
    if direction.length <= 1e-6:
        raise ValueError('Zero-length prop cylinder')
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=direction.length,
                                        location=(a+b)/2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
    obj.data.materials.append(mat)
    return obj


def join_at_origin(bpy, objects, name):
    if not objects or any(obj.type != 'MESH' for obj in objects):
        raise ValueError('Expected generated mesh objects')
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return obj


def make_wing(bpy, workspace):
    module = runpy.run_path(str(workspace/common.WATCH))
    wing = module['wing']
    namespace = wing.__globals__
    mk = module['material']
    oak = mk('Review Palisade Oak', (103, 74, 48))
    shadow = mk('Review Palisade Weathered', (74, 54, 40))
    pale = mk('Review Palisade Hewn', (121, 91, 60))
    iron = mk('Review Palisade Iron', (54, 54, 50), .60, .36)
    namespace.update({'OAK': oak, 'OAK_SHADOW': shadow, 'OAK_PALE': pale,
                      'IRON': iron, 'TIMBER': (oak, shadow, oak, pale, oak, shadow)})
    before = set(bpy.data.objects)
    wing(0)
    objects = [obj for obj in bpy.data.objects if obj not in before]
    return join_at_origin(bpy, objects, 'PalisadeWing')


def make_rack(bpy, mats):
    objects = []
    for y in (-.55, .55):
        objects.append(box(bpy, 'Rack post', (0, y, .83), (.14, .13, 1.66), mats['oak']))
        objects.append(box(bpy, 'Rack foot', (0, y, .07), (.66, .24, .14), mats['dark']))
    for z in (.28, 1.34):
        objects.append(box(bpy, 'Rack rail', (0, 0, z), (.14, 1.20, .12), mats['oak']))
    for y in (-.34, 0., .34):
        objects.append(cylinder(bpy, 'Stored pole', (.02, y, .17), (.02, y, 1.86), .035, mats['pale']))
        objects.append(box(bpy, 'Iron tip', (.02, y, 1.90), (.10, .09, .15), mats['iron']))
    return join_at_origin(bpy, objects, 'GuardRack')


def make_supply(bpy, mats):
    objects = []
    for x, y, z, scale in ((-.25, -.29, .29, 1.), (.17, .30, .2175, .75), (-.25, -.29, .7888, .72)):
        sx, sy, sz = .65*scale, .57*scale, .58*scale
        objects.append(box(bpy, 'Supply chest', (x, y, z), (sx, sy, sz), mats['oak']))
        for dy in (-sy*.35, sy*.35):
            objects.append(box(bpy, 'Chest band', (x+sx*.505, y+dy, z), (.018, .055, sz+.02), mats['dark']))
        objects.append(box(bpy, 'Chest top band', (x, y, z+sz*.505), (sx+.02, .055, .018), mats['dark']))
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=6, location=(.30, -.48, .20))
    sack = bpy.context.object
    sack.name = 'Supply sack'
    sack.scale = (.40, .27, .20)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    sack.data.materials.append(mats['hemp'])
    objects.append(sack)
    return join_at_origin(bpy, objects, 'SupplyStack')


def make_sconce(bpy, mats):
    objects = [box(bpy, 'Sconce post', (0, 0, 1.05), (.13, .13, 2.1), mats['dark']),
               box(bpy, 'Sconce foot', (0, 0, .06), (.48, .40, .12), mats['oak']),
               cylinder(bpy, 'Iron fire basket', (0, 0, 1.84), (0, 0, 2.12), .19, mats['iron'], 12),
               cylinder(bpy, 'Ember core', (0, 0, 2.07), (0, 0, 2.20), .13, mats['ember'], 10)]
    for y in (-.14, .14):
        objects.append(box(bpy, 'Basket strap', (.16, y, 1.98), (.025, .03, .31), mats['iron']))
    return join_at_origin(bpy, objects, 'WatchSconce')


def make_marker(bpy, mats, reclaimed):
    finish = mats['green'] if reclaimed else mats['red']
    objects = [box(bpy, 'Marker post', (0, 0, 1.04), (.12, .12, 2.08), mats['dark']),
               box(bpy, 'Marker foot', (0, 0, .06), (.42, .42, .12), mats['oak']),
               box(bpy, 'Claim board', (.02, 0, 1.72), (.10, .75, .52), finish)]
    # A pale border and central diamond remain readable without relying on color.
    for y in (-.35, .35):
        objects.append(box(bpy, 'Board border', (.079, y, 1.72), (.016, .04, .52), mats['pale']))
    for z in (1.48, 1.96):
        objects.append(box(bpy, 'Board border', (.079, 0, z), (.016, .72, .04), mats['pale']))
    mesh = bpy.data.meshes.new('Claim diamond mesh')
    mesh.from_pydata([(.09, -.20, 1.72), (.09, 0, 1.54), (.09, .20, 1.72), (.09, 0, 1.90)],
                     [], [(0, 1, 2, 3)])
    mesh.update()
    diamond = bpy.data.objects.new('Claim diamond', mesh)
    bpy.context.scene.collection.objects.link(diamond)
    diamond.data.materials.append(mats['pale'])
    objects.append(diamond)
    return join_at_origin(bpy, objects, 'ClaimMarkerReclaimed' if reclaimed else 'ClaimMarkerOccupied')


def import_glb(bpy, path):
    before = set(bpy.data.objects)
    if bpy.ops.import_scene.gltf(filepath=str(path)) != {'FINISHED'}:
        raise ValueError('Could not import stronghold GLB')
    added = [obj for obj in bpy.data.objects if obj not in before]
    if not added or any(obj.type != 'MESH' for obj in added):
        raise ValueError('Expected only mesh objects from the stronghold GLB')
    bpy.context.view_layer.update()
    return added


def measure(bpy, objects, check_corridor=False):
    bpy.context.view_layer.update()
    low, high = [math.inf]*3, [-math.inf]*3
    triangles = 0
    materials = set()
    for obj in objects:
        if obj.type != 'MESH':
            raise ValueError('Review export contains a non-mesh object')
        obj.data.calc_loop_triangles()
        triangles += len(obj.data.loop_triangles)
        for polygon in obj.data.polygons:
            if not 0 <= polygon.material_index < len(obj.data.materials):
                raise ValueError('Mesh polygon has an invalid material index')
            mat = obj.data.materials[polygon.material_index]
            if mat is None:
                raise ValueError('Mesh polygon has no material')
            materials.add(mat.name)
        world = [tuple(float(x) for x in obj.matrix_world @ v.co) for v in obj.data.vertices]
        for point in world:
            if not all(math.isfinite(x) for x in point):
                raise ValueError('Non-finite mesh coordinates')
            for axis in range(3):
                low[axis], high[axis] = min(low[axis], point[axis]), max(high[axis], point[axis])
        if check_corridor:
            for triangle in obj.data.loop_triangles:
                points = [world[index] for index in triangle.vertices]
                if common.triangle_intersects_box(points):
                    raise ValueError('Source triangle intersects the planned passage box')
    if not 0 < triangles < 300000 or not materials or any(not math.isfinite(x) for x in low+high):
        raise ValueError('Unexpected review geometry')
    return {'triangles': triangles, 'bounds_m': [low, high], 'material_count': len(materials)}


def export_glb(bpy, objects, path):
    if path.exists() or path.is_symlink():
        raise ValueError('Refusing to overwrite a GLB')
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    if bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', use_selection=True,
                                 export_yup=True, export_materials='EXPORT') != {'FINISHED'}:
        raise ValueError('GLB export failed')
    if not path.is_file() or path.is_symlink() or not 12 < path.stat().st_size < 64*2**20:
        raise ValueError('Invalid generated GLB')


def camera_and_lighting(bpy):
    from mathutils import Vector
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 12
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 960, 540, 100
    scene.render.image_settings.file_format = 'PNG'
    if scene.world is None:
        scene.world = bpy.data.worlds.new('ReviewWorld')
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value = (.50, .54, .60, 1)
    bg.inputs['Strength'].default_value = .9
    sun_data = bpy.data.lights.new('ReviewSun', 'SUN')
    sun_data.energy = 2.4
    sun = bpy.data.objects.new('ReviewSun', sun_data)
    scene.collection.objects.link(sun)
    sun.rotation_euler = tuple(math.radians(x) for x in (30, -25, -25))
    lamp_data = bpy.data.lights.new('IllustrativeWarmLight', 'POINT')
    lamp_data.energy, lamp_data.color = 80, (1.0, .34, .12)
    lamp = bpy.data.objects.new('IllustrativeWarmLight', lamp_data)
    scene.collection.objects.link(lamp)
    lamp.location = (.35, -3.65, 2.15)
    camera = bpy.data.objects.new('ReviewCamera', bpy.data.cameras.new('ReviewCamera'))
    scene.collection.objects.link(camera)
    camera.location = (10.4, -7.8, 3.8)
    camera.rotation_euler = (Vector((-.3, 0, 1.55))-camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.lens = 32
    scene.camera = camera
    label = bpy.data.curves.new('ReviewCaption', 'FONT')
    label.body = 'ILLUSTRATIVE SOURCE REVIEW  /  NOT IN GAME'
    label.size = .035
    caption = bpy.data.objects.new('ReviewCaption', label)
    scene.collection.objects.link(caption)
    caption.parent = camera
    caption.location = (-.53, .275, -1.0)
    label_mat = material(bpy, 'Review Caption', (1., 1., 1.), emission=(1., 1., 1.))
    label.materials.append(label_mat)
    ground = material(bpy, 'Illustrative ground', (.22, .20, .16))
    box(bpy, 'Illustrative ground', (0, 0, -.08), (34, 34, .15), ground)


def render(bpy, path):
    if path.exists() or path.is_symlink():
        raise ValueError('Refusing to overwrite a preview')
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    if path.is_symlink() or not path.is_file() or path.stat().st_size < 24:
        raise ValueError('Preview image missing')


def build(bpy, workspace):
    out = workspace/'ci-stronghold-entrance-review'
    if out.exists() or out.is_symlink():
        raise ValueError('Review output already exists')
    out.mkdir()
    assets = out/'ReusableAssets'
    assets.mkdir()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    frame = import_glb(bpy, workspace/common.KIT/'SM_GL1450_StrongholdGateFrame.glb')
    occupied = import_glb(bpy, workspace/common.KIT/'SM_GL1450_StrongholdPennantsOccupied.glb')
    reclaimed = import_glb(bpy, workspace/common.KIT/'SM_GL1450_StrongholdPennantsReclaimed.glb')
    mats = {'oak': material(bpy, 'Stronghold Oak', (.25, .14, .07)),
            'dark': material(bpy, 'Stronghold Dark Oak', (.12, .075, .045)),
            'pale': material(bpy, 'Stronghold Hewn Oak', (.38, .24, .12)),
            'iron': material(bpy, 'Stronghold Iron', (.10, .10, .09)),
            'hemp': material(bpy, 'Stronghold Linen', (.46, .38, .25)),
            'ember': material(bpy, 'Stronghold Embers', (.55, .09, .015), emission=(1., .12, .01)),
            'red': material(bpy, 'Occupied Red', (.27, .035, .04)),
            'green': material(bpy, 'Reclaimed Green', (.035, .20, .11))}
    templates = {'PalisadeWing': make_wing(bpy, workspace), 'GuardRack': make_rack(bpy, mats),
                 'SupplyStack': make_supply(bpy, mats), 'WatchSconce': make_sconce(bpy, mats),
                 'ClaimMarkerOccupied': make_marker(bpy, mats, False),
                 'ClaimMarkerReclaimed': make_marker(bpy, mats, True)}
    asset_evidence = {}
    for name, obj in templates.items():
        path = assets/(name+'.glb')
        facts = measure(bpy, [obj])
        export_glb(bpy, [obj], path)
        asset_evidence[name] = {'sha256': common.sha(path), 'facts': facts}
    # Review placement only: flanks join the existing gate while leaving the
    # source gate's central box clear. No actual World Partition placement.
    placements = {'PalisadeWing': ((-.08, -4.42, 0), (-.08, 4.42, 0)),
                  'GuardRack': ((-1.65, -2.75, 0),),
                  'SupplyStack': ((-2.30, 3.0, 0),),
                  'WatchSconce': ((.32, -3.70, 0),)}
    props = []
    for name, obj in templates.items():
        if name.startswith('ClaimMarker'):
            obj.location = (.42, 3.75, 0)
            continue
        positions = placements[name]
        obj.location = positions[0]
        props.append(obj)
        for index, position in enumerate(positions[1:], 1):
            duplicate = obj.copy()
            duplicate.data = obj.data.copy()
            duplicate.name = name+'_'+str(index)
            bpy.context.scene.collection.objects.link(duplicate)
            duplicate.location = position
            props.append(duplicate)
    marker_occupied = templates['ClaimMarkerOccupied']
    marker_reclaimed = templates['ClaimMarkerReclaimed']
    states = {'occupied': frame+occupied+props+[marker_occupied],
              'reclaimed': frame+reclaimed+props+[marker_reclaimed]}
    scenes = {}
    for state, objects in states.items():
        facts = measure(bpy, objects, check_corridor=True)
        path = out/('StrongholdEntrance_'+state.title()+'.glb')
        export_glb(bpy, objects, path)
        scenes[state] = {'sha256': common.sha(path), 'facts': facts}
    camera_and_lighting(bpy)
    for obj in reclaimed+props+[marker_occupied, marker_reclaimed]:
        obj.hide_render = True
    render(bpy, out/'01_gate_only.png')
    for obj in props:
        obj.hide_render = False
    marker_occupied.hide_render = False
    render(bpy, out/'02_occupied_dressed.png')
    for obj in occupied:
        obj.hide_render = True
    for obj in reclaimed:
        obj.hide_render = False
    marker_occupied.hide_render = True
    marker_reclaimed.hide_render = False
    render(bpy, out/'03_reclaimed_dressed.png')
    report = {'status': 'illustrative_source_review_not_in_game',
              'source_sha256': {str(k): v for k, v in common.SOURCE_HASHES.items()},
              'source_text_lf_sha256': {str(k): v for k, v in common.TEXT_HASHES.items()},
              'assets': asset_evidence, 'scenes': scenes,
              'preview_sha256': {name: common.sha(out/name) for name in
                                 ('01_gate_only.png', '02_occupied_dressed.png', '03_reclaimed_dressed.png')},
              'corridor_box_m': [common.CORRIDOR_LOW, common.CORRIDOR_HIGH],
              'corridor_result': 'no source triangle surface intersects the box',
              'limits': ['Illustrative lighting and ground are not part of exported source scenes.',
                         'No live map placement, collision, navigation, reclamation or gameplay is verified.']}
    with (out/'build.report.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps({'status': report['status'], 'scenes': scenes, 'preview_sha256': report['preview_sha256']}))


def verify(bpy, workspace):
    out = workspace/'ci-stronghold-entrance-review'
    if out.is_symlink() or out.resolve(strict=True) != out:
        raise ValueError('Review output is redirected')
    report = json.loads((out/'build.report.json').read_text(encoding='utf-8'))
    if report.get('status') != 'illustrative_source_review_not_in_game':
        raise ValueError('Unexpected build report')
    verified = {}
    for name in (*ASSET_NAMES, *SCENE_NAMES):
        path = out/'ReusableAssets'/(name+'.glb') if name in ASSET_NAMES else out/(name+'.glb')
        expected = report['assets'][name] if name in ASSET_NAMES else report['scenes'][name.rsplit('_', 1)[1].lower()]
        if path.is_symlink() or not path.is_file() or common.sha(path) != expected['sha256']:
            raise ValueError('GLB changed before reimport')
        bpy.ops.wm.read_factory_settings(use_empty=True)
        objects = import_glb(bpy, path)
        facts = measure(bpy, objects, check_corridor=name in SCENE_NAMES)
        old = expected['facts']
        if (facts['triangles'] != old['triangles'] or facts['material_count'] != old['material_count']
                or any(abs(a-b) > .01 for row_a, row_b in zip(facts['bounds_m'], old['bounds_m'])
                       for a, b in zip(row_a, row_b))):
            raise ValueError('Fresh GLB import differs in counts, bounds or materials')
        verified[name] = {'sha256': expected['sha256'], 'facts': facts}
    common.validate_inputs(workspace)
    result = {'status': 'review_only_clean_glb_reimport', 'assets': verified,
              'corridor_box_m': [common.CORRIDOR_LOW, common.CORRIDOR_HIGH],
              'limits': ['Counts, material count and bounds are checked, not full per-corner channel identity.',
                         'Source triangle clearance does not prove imported collision or in-game navigation.']}
    with (out/'verify.report.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps(result))


def main():
    workspace = common.hosted_context()
    common.validate_inputs(workspace)
    import bpy
    if bpy.app.version != (4, 5, 3):
        raise RuntimeError('Unexpected Blender release')
    args = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    if args == ['build']:
        build(bpy, workspace)
    elif args == ['verify']:
        verify(bpy, workspace)
    else:
        raise ValueError('Expected -- build or -- verify')


if __name__ == '__main__':
    main()
