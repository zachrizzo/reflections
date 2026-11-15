"""Hosted-only OBJ -> FBX or fresh-process FBX inspection; no Unreal changes."""

import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import north_market_roundtrip_common as common


def hosted_context():
    env = os.environ
    expected = {
        'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted',
        'RUNNER_OS': 'Linux', 'GITHUB_REPOSITORY': 'zachrizzo/reflections',
        'GITHUB_REPOSITORY_ID': '1457160414', 'GITHUB_REF': 'refs/heads/main',
        'GITHUB_WORKFLOW_REF': ('zachrizzo/reflections/.github/workflows/'
                                'north-market-hosted-roundtrip.yml@refs/heads/main'),
    }
    if sys.platform != 'linux' or any(env.get(k) != v for k, v in expected.items()):
        raise RuntimeError('Refusing to run outside the intended GitHub-hosted Linux workflow')
    if env.get('GITHUB_EVENT_NAME') not in ('push', 'workflow_dispatch'):
        raise RuntimeError('Unexpected event')
    sha = env.get('GITHUB_SHA', '')
    if not re.fullmatch(r'[0-9a-f]{40}', sha) or not re.fullmatch(r'[0-9]+', env.get('GITHUB_RUN_ID', '')):
        raise RuntimeError('Invalid workflow identity')
    workspace = Path(env['GITHUB_WORKSPACE']).resolve(strict=True)
    if Path(__file__).resolve() != workspace / 'Tools/CityPCG/north_market_hosted_blender.py':
        raise RuntimeError('Script is outside the checked-out workspace')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=workspace, text=True).strip()
    if head != sha:
        raise RuntimeError('Checked-out revision differs from workflow SHA')
    return workspace


def one_mesh(bpy):
    objects = list(bpy.context.scene.objects)
    if len(objects) != 1 or objects[0].type != 'MESH':
        raise ValueError('Expected exactly one mesh object and no other scene objects')
    obj = objects[0]
    if obj.parent or obj.modifiers or obj.vertex_groups or obj.data.shape_keys:
        raise ValueError('Unexpected parent, modifiers, vertex groups or shape keys')
    if any(not math.isfinite(obj.matrix_world[i][j]) or
           abs(obj.matrix_world[i][j] - (1.0 if i == j else 0.0)) > 1e-6
           for i in range(4) for j in range(4)):
        raise ValueError('Imported object is not at identity transform and local pivot')
    if len(obj.data.uv_layers) != 1 or len(obj.data.color_attributes) != 0:
        raise ValueError('Expected exactly one UV layer and no color attributes')
    return obj


def set_slot_order(obj, names):
    mesh = obj.data
    original = list(mesh.materials)
    if any(m is None for m in original) or len({m.name for m in original}) != len(original):
        raise ValueError('Missing or duplicate material slots')
    if set(m.name for m in original) != set(names):
        raise ValueError('Imported material names do not match the source')
    mapping = {i: names.index(m.name) for i, m in enumerate(original)}
    polygon_indices = [mapping[p.material_index] for p in mesh.polygons]
    by_name = {m.name: m for m in original}
    mesh.materials.clear()
    for name in names:
        mesh.materials.append(by_name[name])
    for polygon, index in zip(mesh.polygons, polygon_indices):
        polygon.material_index = index


def material_textures(bpy, obj, specs, root):
    """Check the image actually feeding Base Color, not merely an unused node."""
    result = {}
    for mat in obj.data.materials:
        spec = specs[mat.name]
        if not mat.use_nodes or mat.node_tree is None:
            raise ValueError(f'{mat.name}: no node material')
        outputs = [n for n in mat.node_tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output]
        if len(outputs) != 1 or len(outputs[0].inputs['Surface'].links) != 1:
            raise ValueError(f'{mat.name}: ambiguous surface shader')
        shader = outputs[0].inputs['Surface'].links[0].from_node
        if shader.type != 'BSDF_PRINCIPLED':
            raise ValueError(f'{mat.name}: unsupported surface shader')
        alpha = shader.inputs['Alpha']
        if alpha.links or not math.isfinite(alpha.default_value) or abs(alpha.default_value - 1.0) > 1e-5:
            raise ValueError(f'{mat.name}: expected opaque, unlinked shader alpha')
        color = shader.inputs['Base Color']
        texture = spec['texture']
        if texture is None:
            if color.links or any(not math.isfinite(color.default_value[i]) or
                                  not math.isfinite(spec['kd'][i]) or
                                  abs(color.default_value[i] - spec['kd'][i]) > 1e-5 for i in range(3)):
                raise ValueError(f'{mat.name}: untextured base color differs from MTL Kd')
            result[mat.name] = {'kind': 'solid', 'kd': list(spec['kd'])}
            continue
        if len(color.links) != 1:
            raise ValueError(f'{mat.name}: expected one direct color link')
        link = color.links[0]
        node = link.from_node
        if (node.type != 'TEX_IMAGE' or link.from_socket.name != 'Color' or node.inputs['Vector'].links
                or node.image is None or node.image.packed_file):
            raise ValueError(f'{mat.name}: unsupported texture graph or UV mapping')
        if (node.image.colorspace_settings.name != 'sRGB' or node.extension != 'REPEAT' or
                node.interpolation != 'Linear' or node.projection != 'FLAT'):
            raise ValueError(f'{mat.name}: unsupported texture sampling or color space')
        image = common.within(Path(bpy.path.abspath(node.image.filepath)), root)
        if image.name != texture['name'] or common.digest(image) != texture['sha256']:
            raise ValueError(f'{mat.name}: texture name or hash differs')
        result[mat.name] = {'kind': 'texture', 'file': image.name, 'sha256': texture['sha256'],
                            'colorspace': node.image.colorspace_settings.name,
                            'extension': node.extension, 'interpolation': node.interpolation,
                            'projection': node.projection}
    return result


def mesh_data(obj):
    mesh = obj.data
    uv = mesh.uv_layers.active.data
    normals = mesh.corner_normals
    if len(normals) != len(mesh.loops):
        raise ValueError('Missing per-corner normals')
    slots = [m.name for m in mesh.materials]
    faces = []
    for polygon in mesh.polygons:
        if not 0 <= polygon.material_index < len(slots):
            raise ValueError('Invalid polygon material assignment')
        corners = []
        for li in polygon.loop_indices:
            values = (tuple(mesh.vertices[mesh.loops[li].vertex_index].co) +
                      tuple(uv[li].uv) + tuple(normals[li].vector))
            if len(values) != 8 or not all(math.isfinite(x) for x in values):
                raise ValueError('Invalid imported geometry channel')
            corners.append(values)
        faces.append((slots[polygon.material_index], tuple(corners)))
    return {'vertices': len(mesh.vertices), 'edges': len(mesh.edges), 'uv_corners': len(mesh.loops),
            'slots': slots, 'faces': faces}


def normal_boundaries(mesh, face_normals):
    """Plan necessary sharp edges and loop normals without changing the mesh."""
    if len(face_normals) != len(mesh.polygons):
        raise ValueError('Normal plan does not cover every imported face')
    loop_normals = [None] * len(mesh.loops)
    edge_normals = {}
    for face_index, polygon in enumerate(mesh.polygons):
        normal = face_normals[face_index]
        for li in polygon.loop_indices:
            if not 0 <= li < len(loop_normals) or loop_normals[li] is not None:
                raise ValueError('Invalid or duplicated mesh corner')
            edge_index = mesh.loops[li].edge_index
            if not 0 <= edge_index < len(mesh.edges):
                raise ValueError('Invalid mesh corner edge')
            loop_normals[li] = normal
            edge_normals.setdefault(edge_index, []).append(normal)
    if any(normal is None for normal in loop_normals):
        raise ValueError('Normal plan does not cover every mesh corner')
    required = set()
    for edge_index, values in edge_normals.items():
        if any(any(abs(normal[i] - values[0][i]) > 1e-7 for i in range(3)) for normal in values[1:]):
            required.add(edge_index)
    return required, loop_normals


def restore_flat_source_normals(obj, expected, actual, *, apply):
    """Restore authored OBJ normals only on export; verify split edges on reimport."""
    face_normals = common.flat_source_normal_plan(expected, actual)
    mesh = obj.data
    required, loop_normals = normal_boundaries(mesh, face_normals)
    if apply:
        # Preserve all existing sharp edges; add only authored normal boundaries.
        # We do not change face smooth flags or topology.
        for edge_index in required:
            mesh.edges[edge_index].use_edge_sharp = True
        mesh.normals_split_custom_set(loop_normals)
        mesh.update()
    if any(not mesh.edges[i].use_edge_sharp for i in required):
        raise ValueError('Required authored-normal boundary is not a sharp edge')
    return {'method': 'validated flat OBJ normals; sharp edges at differing face normals',
            'required_sharp_edges': len(required), 'face_smooth_flags_edited': False}


def write_report(path, report):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')


def run():
    workspace = hosted_context()
    import bpy
    if bpy.app.version != (4, 5, 3):
        raise RuntimeError(f'Unexpected Blender version: {bpy.app.version_string}')
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if len(args) != 2 or args[0] not in ('export', 'verify') or args[1] not in common.NAMES:
        raise ValueError('Expected -- export|verify <known model name>')
    phase, name = args
    source = workspace / common.SOURCE_REL
    manifest, row, obj_path, materials = common.source_spec(source, name)
    expected = common.read_obj(obj_path, materials)
    readback = row['source_artifact']['readback']
    if (expected['vertices'] != readback['vertices'] or len(expected['faces']) != readback['polygons']
            or expected['uv_corners'] != readback['uv_corners']):
        raise ValueError('Source geometry counts differ from its manifest')
    base = workspace / 'ci-north-market-fbx'
    if base.is_symlink() or not base.is_dir() or base.resolve() != base:
        raise ValueError('Output root is absent or redirected')
    out = base / name
    if phase == 'export':
        out.mkdir()  # exclusive: an earlier result is never overwritten
    elif out.is_symlink() or not out.is_dir() or out.resolve() != out:
        raise ValueError('Review bundle is absent or redirected')
    fbx = out / (name + '.fbx')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if phase == 'export':
        result = bpy.ops.wm.obj_import(filepath=str(obj_path), forward_axis='Y', up_axis='Z',
                                       global_scale=1.0, use_split_objects=False, use_split_groups=False)
    else:
        common.within(fbx, out)
        result = bpy.ops.import_scene.fbx(filepath=str(fbx), use_custom_normals=True,
                                          use_image_search=False, use_anim=False)
    if result != {'FINISHED'}:
        raise ValueError(f'{phase}: Blender importer did not finish')
    obj = one_mesh(bpy)
    if phase == 'export':
        obj.name = name
        obj.data.name = name
        set_slot_order(obj, expected['slots'])
    elif obj.name != name:
        raise ValueError(f'FBX object name changed: {obj.name}')
    # The west source has neighboring flat normals Blender averages on OBJ
    # import. Repair only this known case; the normal matcher still runs below
    # and again in a fresh FBX process, where no restoration is performed.
    normal_repair = None
    if name == 'SM_GLMedieval_NorthMarketDetail_west_736fd5c6':
        normal_repair = restore_flat_source_normals(obj, expected, mesh_data(obj), apply=phase == 'export')
    facts = common.compare(expected, mesh_data(obj))
    textures = material_textures(bpy, obj, materials, source if phase == 'export' else out)
    if phase == 'export':
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        result = bpy.ops.export_scene.fbx(
            filepath=str(fbx), use_selection=True, object_types={'MESH'}, global_scale=1.0,
            apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE', use_space_transform=True,
            bake_space_transform=False, axis_forward='-Z', axis_up='Y', use_mesh_modifiers=True,
            mesh_smooth_type='EDGE' if normal_repair else 'FACE', use_triangles=False, bake_anim=False,
            path_mode='COPY', embed_textures=False)
        if result != {'FINISHED'}:
            raise ValueError('Blender FBX exporter did not finish')
        common.within(fbx, out)
    common.source_spec(source, name)  # recheck source OBJ, MTL and all referenced texture hashes
    report = {
        'status': 'review-only: no Unreal or visual approval', 'phase': phase,
        'model': name, 'source_manifest_sha256': common.MANIFEST_SHA,
        'source_obj_sha256': row['source_artifact']['sha256'],
        'source_mtl_sha256': manifest['material_sha256'], 'fbx_sha256': common.digest(fbx),
        'world_pivot_m': row['world_pivot_m'], 'yaw_deg': row['yaw_deg'],
        'source_axes': '+X entrance, +Z up', 'scene_unit': 'metres',
        'blender_version': bpy.app.version_string, 'uv_layer': obj.data.uv_layers.active.name,
        'facts': facts, 'textures': textures, 'normal_repair': normal_repair,
        'limitations': ['No visual approval', 'No Unreal import, collision, navigation or placement validation',
                        'OBJ has no native slot order; used-material MTL order is the FBX contract',
                        'Blender shader and FBX round trip cannot prove Unreal material appearance',
                        'Blender round-trip agreement alone does not prove FBX scale or axes in Unreal'],
    }
    if phase == 'verify':
        previous = json.loads(common.within(out / 'export.report.json', out).read_text(encoding='utf-8'))
        for key in ('model', 'source_manifest_sha256', 'source_obj_sha256', 'source_mtl_sha256',
                    'fbx_sha256', 'world_pivot_m', 'yaw_deg', 'source_axes', 'scene_unit',
                    'blender_version', 'uv_layer', 'facts', 'textures', 'normal_repair'):
            if previous.get(key) != report.get(key):
                raise ValueError(f'Fresh-process FBX check differs from export: {key}')
    write_report(out / (phase + '.report.json'), report)
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    run()
