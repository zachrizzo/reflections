"""Render an isolated before/after of the verified base FBX and tenancy OBJ.

Run only in the existing GitHub-hosted North Market review workflow, after its
FBX export/verify and the separate tenancy generator have completed.
"""
import json
import math
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import north_market_hosted_blender as adapter
import north_market_roundtrip_common as common
import north_market_tenancies as tenancy


def original_material_name(name):
    match = re.fullmatch(r'(M_GLMedieval_[A-Za-z0-9_]+)(?:\.[0-9]{3})?', name)
    if not match:
        raise ValueError('Unexpected overlay material name')
    return match.group(1)


def normalize_overlay_slot_order(obj, expected_names):
    old = list(obj.data.materials)
    names = [original_material_name(mat.name) if mat else '' for mat in old]
    if (len(names) != len(expected_names) or len(set(names)) != len(names)
            or set(names) != set(expected_names)):
        raise ValueError('Overlay material slots differ from the authored OBJ')
    remap = {i: expected_names.index(name) for i, name in enumerate(names)}
    assignments = []
    for face in obj.data.polygons:
        if face.material_index not in remap:
            raise ValueError('Invalid overlay material assignment')
        assignments.append(remap[face.material_index])
    by_name = dict(zip(names, old))
    obj.data.materials.clear()
    for name in expected_names:
        obj.data.materials.append(by_name[name])
    for face, index in zip(obj.data.polygons, assignments):
        face.material_index = index


def look_at(obj, point):
    from mathutils import Vector
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def additional_material(bpy, name, spec, root):
    """Make a missing source-palette slot with its pinned MTL color/texture."""
    mat = bpy.data.materials.new(name + '_TenancyReview')
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    if shader is None:
        raise ValueError('New material has no standard shader')
    shader.inputs['Roughness'].default_value = .85
    texture = spec['texture']
    if texture is None:
        shader.inputs['Base Color'].default_value = (*spec['kd'], 1.0)
    else:
        path = common.within(root/'Textures'/texture['name'], root/'Textures')
        if common.digest(path) != texture['sha256']:
            raise ValueError('Additional material texture does not match source')
        node = mat.node_tree.nodes.new('ShaderNodeTexImage')
        node.image = bpy.data.images.load(str(path), check_existing=True)
        mat.node_tree.links.new(node.outputs['Color'], shader.inputs['Base Color'])
    return mat


def run():
    workspace = adapter.hosted_context()
    import bpy
    if bpy.app.version != (4, 5, 3):
        raise RuntimeError('Unexpected Blender release')
    name = tenancy.MODEL
    source = workspace / common.SOURCE_REL
    _, row, obj_path, materials = common.source_spec(source, name)
    expected = common.read_obj(obj_path, materials)
    bundle = workspace / 'ci-north-market-fbx' / name
    fbx = common.within(bundle / (name + '.fbx'), bundle)
    verified = json.loads(common.within(bundle / 'verify.report.json', bundle).read_text(encoding='utf-8'))
    if (verified.get('fbx_sha256') != common.digest(fbx)
            or verified.get('source_manifest_sha256') != common.MANIFEST_SHA):
        raise ValueError('The base FBX does not match its verification report')
    out = workspace / 'ci-north-market-tenancy'
    if out.is_symlink() or out.resolve(strict=True) != out:
        raise ValueError('Unexpected review output')
    report = json.loads(common.within(out/'tenancies.report.json', out).read_text(encoding='utf-8'))
    overlay_path = common.within(out/'tenancies_overlay.obj', out)
    if (report.get('building') != tenancy.BUILDING or report.get('source_obj_sha256') != tenancy.PINNED['obj']
            or report.get('status') != 'review_only_not_unreal_validated'
            or report.get('overlay_sha256') != common.digest(overlay_path)):
        raise ValueError('The overlay does not match the selected building and report')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if bpy.ops.import_scene.fbx(filepath=str(fbx), use_custom_normals=True,
                                use_image_search=False, use_anim=False) != {'FINISHED'}:
        raise ValueError('Base FBX import failed')
    base = adapter.one_mesh(bpy)
    common.compare(expected, adapter.mesh_data(base))
    adapter.material_textures(bpy, base, materials, bundle)
    slots = {m.name: m for m in base.data.materials}
    before = set(bpy.context.scene.objects)
    if bpy.ops.wm.obj_import(filepath=str(overlay_path), forward_axis='Y', up_axis='Z',
                             global_scale=1.0, use_split_objects=False, use_split_groups=False) != {'FINISHED'}:
        raise ValueError('Overlay OBJ import failed')
    added = set(bpy.context.scene.objects) - before
    if len(added) != 1:
        raise ValueError('Overlay import did not produce one object')
    overlay = added.pop()
    if (overlay.type != 'MESH' or overlay.parent or overlay.modifiers or len(overlay.data.uv_layers) != 1
            or len(overlay.data.vertices) != report['added_vertices']
            or len(overlay.data.polygons) != report['added_faces']
            or any(not math.isfinite(overlay.matrix_world[i][j])
                   or abs(overlay.matrix_world[i][j] - (1.0 if i == j else 0.0)) > 1e-6
                   for i in range(4) for j in range(4))):
        raise ValueError('Unexpected imported overlay geometry or transform')
    if not overlay.data.materials:
        raise ValueError('Overlay has no material slots')
    # Blender can suffix newly imported material datablock names. Compare every
    # position, winding, UV, normal and assignment using the original names
    # before substituting the verified base or source-palette materials.
    expected_overlay = common.read_obj(overlay_path, materials)
    normalize_overlay_slot_order(overlay, expected_overlay['slots'])
    actual_overlay = adapter.mesh_data(overlay)
    actual_overlay['slots'] = [original_material_name(slot) for slot in actual_overlay['slots']]
    actual_overlay['faces'] = [(original_material_name(role), corners)
                               for role, corners in actual_overlay['faces']]
    common.compare(expected_overlay, actual_overlay)
    for i, mat in enumerate(overlay.data.materials):
        name = original_material_name(mat.name) if mat else ''
        if name not in materials:
            raise ValueError('Overlay uses a material absent from the pinned MTL')
        if name not in slots:
            slots[name] = additional_material(bpy, name, materials[name], out)
        overlay.data.materials[i] = slots[name]

    coords = [tuple(v.co) for v in base.data.vertices]
    bounds = [(min(c[i] for c in coords), max(c[i] for c in coords)) for i in range(3)]
    center = [(a+b)/2 for a, b in bounds]
    size = [b-a for a, b in bounds]
    span = max(size)
    if not 1 < span < 200 or size[2] <= 1:
        raise ValueError('Unexpected source bounds')
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 8
    scene.cycles.use_denoising = False
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 720, 480, 100
    scene.render.image_settings.file_format = 'PNG'
    if scene.world is None:
        scene.world = bpy.data.worlds.new('DiagnosticWorld')
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get('Background')
    background.inputs['Color'].default_value = (.35, .39, .44, 1)
    background.inputs['Strength'].default_value = .8
    light = bpy.data.lights.new('DiagnosticSun', 'SUN')
    light.energy = 2.0
    sun = bpy.data.objects.new('DiagnosticSun', light)
    scene.collection.objects.link(sun)
    sun.rotation_euler = tuple(math.radians(x) for x in (25, -30, -25))
    camera_obj = bpy.data.objects.new('DiagnosticCamera', bpy.data.cameras.new('DiagnosticCamera'))
    scene.collection.objects.link(camera_obj)
    scene.camera = camera_obj
    camera = camera_obj.data
    images = {}
    for view in ('eye_level', 'three_quarter'):
        if view == 'eye_level':
            camera.type, camera.lens = 'PERSP', 28
            camera_obj.location = (bounds[0][1] + max(8, size[1]*.28), center[1], 1.7)
            look_at(camera_obj, (center[0], center[1], 2.1))
        else:
            camera.type, camera.ortho_scale = 'ORTHO', span*1.65
            camera_obj.location = (center[0]+span, center[1]-span, center[2]+span*.65)
            look_at(camera_obj, center)
        for label, hidden in (('before', True), ('after', False)):
            overlay.hide_render = hidden
            path = out / f'{view}_{label}.png'
            if path.exists() or path.is_symlink():
                raise ValueError('Refusing to overwrite a preview')
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            if path.is_symlink() or not path.is_file() or path.stat().st_size <= 24:
                raise ValueError('Preview render was not written')
            images[path.name] = common.digest(path)
    result = {'status': 'source_diagnostic_not_in_game', 'model': tenancy.MODEL,
              'base_fbx_sha256': verified['fbx_sha256'], 'overlay_sha256': report['overlay_sha256'],
              'images': images, 'tenancy_count': len(report['units']),
              'render': 'Blender Cycles CPU; identical camera and lighting in each pair',
              'world_pivot_m': row['world_pivot_m'], 'yaw_deg': row['yaw_deg'],
              'limits': ['Closed decorative doors and hatches.', 'Unreal visual, collision and placement checks pending.']}
    with (out/'before_after.report.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'status': result['status'], 'images': images}))


if __name__ == '__main__':
    run()
