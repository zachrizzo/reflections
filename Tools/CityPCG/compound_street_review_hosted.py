"""Illustrative occupied/reclaimed compound in a pinned street source scene."""
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compound_review_common as common

triangles = None
kit = None


def import_glb(bpy, path):
    before = set(bpy.data.objects)
    if bpy.ops.import_scene.gltf(filepath=str(path)) != {'FINISHED'}:
        raise ValueError('Review GLB import failed')
    added = [obj for obj in bpy.data.objects if obj not in before]
    if not added or not any(obj.type == 'MESH' for obj in added) or any(obj.type not in {'MESH', 'EMPTY'} for obj in added):
        raise ValueError('Unexpected source scene object inventory')
    if any(obj.parent and obj.parent not in added for obj in added):
        raise ValueError('Source scene was parented outside its own import')
    bpy.context.view_layer.update()
    return added


def parent_import(objects, parent):
    roots = [obj for obj in objects if obj.parent not in objects]
    if not roots:
        raise ValueError('No root in imported scene')
    for obj in roots:
        obj.parent = parent


def make_standard(bpy, reclaimed):
    red = kit.material(bpy, 'Compound Reclaimed Green' if reclaimed else 'Compound Occupied Red',
                       (.025, .22, .10) if reclaimed else (.36, .025, .035))
    pale = kit.material(bpy, 'Compound Pale Mark', (.78, .65, .42))
    wood = kit.material(bpy, 'Compound Standard Oak', (.19, .10, .055))
    parts = [kit.cylinder(bpy, 'Standard pole', (0, 0, 0), (0, 0, 4.50), .065, wood, 12),
             kit.cylinder(bpy, 'Standard crossbar', (0, -.65, 4.30), (0, .65, 4.30), .045, wood, 10),
             kit.box(bpy, 'Standard cloth', (.035, 0, 3.36), (.035, 1.15, 1.70), red)]
    for y in (-.55, .55):
        parts.append(kit.box(bpy, 'Cloth border', (.058, y, 3.36), (.012, .05, 1.67), pale))
    for z in (2.54, 4.18):
        parts.append(kit.box(bpy, 'Cloth border', (.058, 0, z), (.012, 1.1, .05), pale))
    if reclaimed:
        # Bars distinguish the reclaimed state independently of hue.
        for z in (3.16, 3.56):
            parts.append(kit.box(bpy, 'Reclaimed emblem bar', (.069, 0, z), (.012, .77, .095), pale))
    else:
        # Occupied standard uses a large pale diamond.
        mesh = bpy.data.meshes.new('Standard emblem mesh')
        mesh.from_pydata([(.069, -.39, 3.36), (.069, 0, 2.89),
                          (.069, .39, 3.36), (.069, 0, 3.83)], [], [(0, 1, 2, 3)])
        mesh.update()
        obj = bpy.data.objects.new('Standard emblem', mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.data.materials.append(pale)
        parts.append(obj)
    return kit.join_at_origin(bpy, parts, 'CompoundStandardReclaimed' if reclaimed else 'CompoundStandardOccupied')


def pose_anchor(bpy):
    anchor = bpy.data.objects.new('IllustrativeGatePlacement', None)
    bpy.context.scene.collection.objects.link(anchor)
    anchor.location = common.GATE_TRANSLATION
    anchor.rotation_euler[2] = math.radians(common.GATE_YAW_DEG)
    return anchor


def local_place(objects, parent, location):
    roots = [obj for obj in objects if obj.parent not in objects]
    if not roots:
        raise ValueError('Imported prop has no root')
    for obj in roots:
        obj.parent = parent
        obj.location = location


def measure(bpy, objects, check_passage=False):
    bpy.context.view_layer.update()
    low, high, count = [math.inf]*3, [-math.inf]*3, 0
    for obj in objects:
        if obj.type != 'MESH':
            continue
        obj.data.calc_loop_triangles()
        count += len(obj.data.loop_triangles)
        world = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
        for value in world:
            point = tuple(float(x) for x in value)
            if not all(math.isfinite(x) for x in point):
                raise ValueError('Non-finite scene position')
            for i in range(3):
                low[i] = min(low[i], point[i]); high[i] = max(high[i], point[i])
        if check_passage:
            local = [common.world_to_gate(tuple(float(x) for x in point)) for point in world]
            for face in obj.data.loop_triangles:
                if triangles.triangle_intersects_box([local[i] for i in face.vertices],
                                                    common.CORRIDOR_LOW, common.CORRIDOR_HIGH):
                    raise ValueError('Source surface intersects the illustrative passage')
    if not 0 < count < 350000 or any(not math.isfinite(x) for x in low+high):
        raise ValueError('Unexpected scene geometry')
    return {'triangles': count, 'bounds_m': [low, high]}


def export_scene(bpy, objects, path):
    if path.exists() or path.is_symlink():
        raise ValueError('Review output already exists')
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    meshes = [obj for obj in objects if obj.type == 'MESH']
    if not meshes:
        raise ValueError('No export mesh')
    bpy.context.view_layer.objects.active = meshes[0]
    if bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', use_selection=True,
                                 export_yup=True, export_materials='EXPORT') != {'FINISHED'}:
        raise ValueError('GLB export failed')
    if path.is_symlink() or not path.is_file() or not 12 < path.stat().st_size <= 128*2**20:
        raise ValueError('Invalid review GLB')


def camera_and_lighting(bpy):
    from mathutils import Vector
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = 12
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 960, 540, 100
    scene.render.image_settings.file_format = 'PNG'
    if scene.world is None:
        scene.world = bpy.data.worlds.new('ReviewWorld')
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value = (.52, .56, .62, 1)
    bg.inputs['Strength'].default_value = 1.05
    sun_data = bpy.data.lights.new('ReviewSun', 'SUN'); sun_data.energy = 2.7
    sun = bpy.data.objects.new('ReviewSun', sun_data); scene.collection.objects.link(sun)
    sun.rotation_euler = tuple(math.radians(x) for x in (30, -25, -25))
    lamp_data = bpy.data.lights.new('IllustrativeWatchLight', 'POINT')
    lamp_data.energy, lamp_data.color = 120, (1., .35, .12)
    lamp = bpy.data.objects.new('IllustrativeWatchLight', lamp_data); scene.collection.objects.link(lamp)
    lamp.location = (35.8, -20.18, 2.15)
    camera = bpy.data.objects.new('ReviewCamera', bpy.data.cameras.new('ReviewCamera'))
    scene.collection.objects.link(camera); scene.camera = camera
    camera.data.lens = 28
    label = bpy.data.curves.new('ReviewCaption', 'FONT')
    label.body, label.size = 'ILLUSTRATIVE COMPOUND REVIEW  /  NOT IN GAME', .035
    caption = bpy.data.objects.new('ReviewCaption', label); scene.collection.objects.link(caption)
    caption.parent = camera; caption.location = (-.56, .275, -1.)
    label.materials.append(kit.material(bpy, 'Review Caption', (1., 1., 1.), emission=(1., 1., 1.)))
    return camera


def point_camera(camera, location, target):
    from mathutils import Vector
    camera.location = location
    camera.rotation_euler = (Vector(target)-camera.location).to_track_quat('-Z', 'Y').to_euler()


def render(bpy, path):
    if path.exists() or path.is_symlink():
        raise ValueError('Preview already exists')
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    if path.is_symlink() or not path.is_file() or path.stat().st_size < 24:
        raise ValueError('Preview missing')


def build(bpy, workspace, temp, run, attempt):
    stage, paths = common.extract_inputs(workspace, temp, run, attempt)
    out = workspace/'ci-compound-street-review'
    if out.exists() or out.is_symlink():
        raise ValueError('Review output already exists')
    out.mkdir(); assets = out/'ReusableAssets'; assets.mkdir()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    street = import_glb(bpy, paths['street'])
    anchor = pose_anchor(bpy)
    occupied = import_glb(bpy, paths['occupied']); parent_import(occupied, anchor)
    reclaimed = import_glb(bpy, paths['reclaimed']); parent_import(reclaimed, anchor)
    standards = {'occupied': make_standard(bpy, False), 'reclaimed': make_standard(bpy, True)}
    asset_hashes = {}
    for state, obj in standards.items():
        path = assets/('CompoundStandard_'+state.title()+'.glb')
        facts = measure(bpy, [obj])
        export_scene(bpy, [obj], path)
        asset_hashes[path.name] = {'sha256': common.digest(path, 64*2**20)[1], 'facts': facts}
    standard_objects = {}
    for state, obj in standards.items():
        obj.parent = anchor; obj.location = (.25, -3.0, 0)
        other = obj.copy(); other.data = obj.data.copy(); other.name = obj.name+'_other'
        bpy.context.scene.collection.objects.link(other)
        other.parent = anchor; other.location = (.25, 3.0, 0)
        standard_objects[state] = [obj, other]
    supplies = import_glb(bpy, paths['supplies']); local_place(supplies, anchor, (-2.8, 3.4, 0))
    rack = import_glb(bpy, paths['rack']); local_place(rack, anchor, (-2.8, -3.3, 0))
    shared = supplies+rack
    common_groups = street+[anchor]+shared
    scenes = {'occupied': common_groups+occupied+standard_objects['occupied'],
              'reclaimed': common_groups+reclaimed+standard_objects['reclaimed']}
    evidence = {}
    for state, objects in scenes.items():
        facts = measure(bpy, objects, check_passage=True)
        path = out/('CompoundStreet_'+state.title()+'.glb')
        export_scene(bpy, objects, path)
        evidence[state] = {'sha256': common.digest(path, 128*2**20)[1], 'facts': facts}
    camera = camera_and_lighting(bpy)
    for obj in reclaimed+standard_objects['reclaimed']+standard_objects['occupied']+shared:
        obj.hide_render = True
    point_camera(camera, (39, -13.8, 3.0), (30.8, -20.5, 2.0))
    render(bpy, out/'01_existing_gate_in_street.png')
    for obj in standard_objects['occupied']+shared:
        obj.hide_render = False
    render(bpy, out/'02_occupied_compound.png')
    for obj in occupied+standard_objects['occupied']:
        obj.hide_render = True
    for obj in reclaimed+standard_objects['reclaimed']:
        obj.hide_render = False
    render(bpy, out/'03_reclaimed_compound.png')
    for obj in reclaimed+standard_objects['reclaimed']:
        obj.hide_render = True
    for obj in occupied+standard_objects['occupied']:
        obj.hide_render = False
    point_camera(camera, (37.5, -28.0, 2.2), (31.8, -20.5, 1.8))
    render(bpy, out/'04_occupied_reverse.png')
    report = {'status': 'illustrative_source_review_not_in_game', 'scenes': evidence,
              'standard_assets': asset_hashes,
              'input_archive_sha256': {str(path): pin[1] for path, pin in common.ARCHIVES.items()},
              'input_member_sha256': {key: spec[2] for key, spec in common.MEMBERS.items()},
              'gate_pose': {'translation_m': common.GATE_TRANSLATION, 'yaw_deg': common.GATE_YAW_DEG},
              'corridor_box_gate_local_m': [common.CORRIDOR_LOW, common.CORRIDOR_HIGH],
              'corridor_result': 'no source triangle surface intersects the box',
              'preview_sha256': {name: common.digest(out/name, 8*2**20)[1] for name in
                                 ('01_existing_gate_in_street.png', '02_occupied_compound.png',
                                  '03_reclaimed_compound.png', '04_occupied_reverse.png')},
              'limits': ['Illustrative placement and lighting; no live-world or gameplay claim.',
                         'Passage checks source triangle surfaces, not Unreal collision or navigation.']}
    common.validate_inputs(workspace)
    with (out/'build.report.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2, sort_keys=True); stream.write('\n')
    print(json.dumps({'status': report['status'], 'scenes': evidence, 'preview_sha256': report['preview_sha256']}))


def verify(bpy, workspace):
    out = workspace/'ci-compound-street-review'
    if out.is_symlink() or out.resolve(strict=True) != out:
        raise ValueError('Unexpected review directory')
    report = json.loads((out/'build.report.json').read_text(encoding='utf-8'))
    if report.get('status') != 'illustrative_source_review_not_in_game':
        raise ValueError('Unexpected source report')
    verified = {}
    for state in ('occupied', 'reclaimed'):
        path = out/('CompoundStreet_'+state.title()+'.glb')
        old = report['scenes'][state]
        if path.is_symlink() or common.digest(path, 128*2**20)[1] != old['sha256']:
            raise ValueError('Scene GLB changed')
        bpy.ops.wm.read_factory_settings(use_empty=True)
        objects = import_glb(bpy, path)
        facts = measure(bpy, objects, check_passage=True)
        if (facts['triangles'] != old['facts']['triangles']
                or any(abs(x-y) > .01 for a, b in zip(facts['bounds_m'], old['facts']['bounds_m'])
                       for x, y in zip(a, b))):
            raise ValueError('Clean GLB import changed triangle count or bounds')
        verified[state] = {'sha256': old['sha256'], 'facts': facts}
    assets = {}
    for state in ('occupied', 'reclaimed'):
        name = 'CompoundStandard_'+state.title()+'.glb'
        path = out/'ReusableAssets'/name
        old = report['standard_assets'][name]
        if path.is_symlink() or common.digest(path, 64*2**20)[1] != old['sha256']:
            raise ValueError('Standard GLB changed')
        bpy.ops.wm.read_factory_settings(use_empty=True)
        objects = import_glb(bpy, path)
        facts = measure(bpy, objects)
        if (facts['triangles'] != old['facts']['triangles']
                or any(abs(x-y) > .01 for a, b in zip(facts['bounds_m'], old['facts']['bounds_m'])
                       for x, y in zip(a, b))):
            raise ValueError('Clean standard import changed triangle count or bounds')
        assets[state] = {'sha256': old['sha256'], 'facts': facts}
    common.validate_inputs(workspace)
    result = {'status': 'review_only_clean_glb_reimport', 'scenes': verified, 'standard_assets': assets,
              'corridor_box_gate_local_m': [common.CORRIDOR_LOW, common.CORRIDOR_HIGH],
              'limits': ['Counts and bounds checked; full UV, material and normal fidelity unverified.',
                         'Source triangle passage does not establish in-game collision or navigation.']}
    with (out/'verify.report.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2, sort_keys=True); stream.write('\n')
    print(json.dumps(result))


def main():
    global triangles, kit
    workspace, temp, run, attempt = common.hosted_context()
    common.validate_inputs(workspace)
    # Load executable helper modules only after validating their pinned bytes.
    import stronghold_entrance_review_common as triangles
    import stronghold_entrance_review_hosted as kit
    import bpy
    if bpy.app.version != (4, 5, 3):
        raise RuntimeError('Unexpected Blender release')
    args = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    if args == ['build']:
        build(bpy, workspace, temp, run, attempt)
    elif args == ['verify']:
        verify(bpy, workspace)
    else:
        raise ValueError('Expected -- build or -- verify')


if __name__ == '__main__':
    main()
