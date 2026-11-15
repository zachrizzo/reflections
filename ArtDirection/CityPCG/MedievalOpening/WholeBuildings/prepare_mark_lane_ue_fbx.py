"""Prepare triangulated, handedness-correct FBX copies for Unreal's legacy importer."""

import hashlib
import json
import math
from pathlib import Path

import bmesh
import bpy


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[3]
OUTPUT = PROJECT / 'Saved/MedievalOpening/WestMarkLaneImport'
RECIPE = ROOT / 'whole_buildings_kit.json'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'


def load_mesh(source, raw_axes=False):
    bpy.ops.import_scene.fbx(filepath=str(source), use_custom_normals=False,
                             use_manual_orientation=raw_axes, axis_forward='Y', axis_up='Z')
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    if len(meshes) != 1 or meshes[0].name != source.stem:
        raise RuntimeError(f'Expected one mesh named {source.stem}, got {meshes}')
    obj = meshes[0]
    if any(abs(value) > 1e-5 for value in (*obj.location, *obj.rotation_euler)) or any(
        abs(value - 1) > 1e-5 for value in obj.scale
    ):
        raise RuntimeError(f'{source}: expected identity object transform')
    return obj


def mesh_facts(mesh):
    mesh.calc_loop_triangles()
    return {
        'bounds_cm': [[round(fn(vertex.co[axis] for vertex in mesh.vertices) * 100, 3) for axis in range(3)]
                      for fn in (min, max)],
        'materials': [material.name for material in mesh.materials],
        'uv_layers': [layer.name for layer in mesh.uv_layers],
        'triangles': len(mesh.loop_triangles),
    }


def solid_volume(mesh):
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        if not all(edge.is_manifold for edge in bm.edges):
            raise RuntimeError(f'{mesh.name}: expected all solids to be closed')
        return bm.calc_volume(signed=True)
    finally:
        bm.free()


def verify_facts(actual, expected, mirror=False):
    low, high = expected['bounds_cm']
    bounds = [(low[0], -high[1], low[2]), (high[0], -low[1], high[2])] if mirror else [low, high]
    if any(abs(a - b) > .004 for lhs, rhs in zip(actual['bounds_cm'], bounds) for a, b in zip(lhs, rhs)):
        raise RuntimeError(f'Unexpected signed bounds: {actual["bounds_cm"]}, expected {bounds}')
    if actual['materials'] != expected['materials'] or actual['uv_layers'] != ['UV0']:
        raise RuntimeError(f'Material or UV channels changed: {actual}')
    if actual['triangles'] != expected['triangles']:
        raise RuntimeError(f'Triangle count changed: {actual["triangles"]} != {expected["triangles"]}')


def geometry_digest(mesh):
    """Hash vertices, oriented triangles, UVs and slots independently of FBX timestamps."""
    uv = mesh.uv_layers['UV0'].data
    triangles = []
    for face in mesh.polygons:
        corners = []
        for index in face.loop_indices:
            point = mesh.vertices[mesh.loops[index].vertex_index].co
            corners.append(tuple(round(component, 6) for component in (*point, *uv[index].uv)))
        first = corners.index(min(corners))
        triangles.append((mesh.materials[face.material_index].name, corners[first:] + corners[:first]))
    payload = json.dumps(sorted(triangles), separators=(',', ':')).encode()
    return hashlib.sha256(payload).hexdigest()


def adjust(obj):
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        # Unreal's legacy converter negates Y even with axis conversion disabled.
        for vertex in bm.verts:
            vertex.co.y = -vertex.co.y
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bm.normal_update()
        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()


def prepare(source, dest, expected):
    reset()
    obj = load_mesh(source)
    verify_facts(mesh_facts(obj.data), expected)
    volume = solid_volume(obj.data)
    adjust(obj)
    verify_facts(mesh_facts(obj.data), expected, mirror=True)

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    # Blender's Y-forward, Z-up export basis is identity with scene conversion
    # disabled in Unreal. Left-handed conversion then undoes the pre-reflection.
    bpy.ops.export_scene.fbx(filepath=str(dest), use_selection=True, object_types={'MESH'},
                             axis_forward='Y', axis_up='Z', apply_unit_scale=True,
                             mesh_smooth_type='FACE', bake_anim=False, path_mode='STRIP')

    reset()
    result = load_mesh(dest, raw_axes=True)
    facts = mesh_facts(result.data)
    verify_facts(facts, expected, mirror=True)
    if any(len(face.vertices) != 3 for face in result.data.polygons):
        raise RuntimeError(f'{dest}: expected an entirely triangulated mesh')
    after = solid_volume(result.data)
    if volume <= 0 or abs(after - volume) > 1e-5 * volume:
        raise RuntimeError(f'{dest}: winding or volume changed ({volume} -> {after})')
    # Undo Unreal's future Y conversion numerically and check every ground
    # vertex in the source outline, including the recovered ground pivot.
    ground = [(vertex.co.x, -vertex.co.y) for vertex in result.data.vertices if abs(vertex.co.z) < 1e-5]
    outline = expected['footprint_local_m']
    if not all(any(math.dist(point, vertex) < .0001 for vertex in ground) for point in outline):
        raise RuntimeError(f'{dest}: prepared mesh no longer fits the exact footprint axes and pivot')
    return dict(facts, canonical_sha256=sha256(source), prepared_sha256=sha256(dest),
                geometry_sha256=geometry_digest(result.data), signed_volume_m3=after,
                pivot_m=[0, 0, 0], reflected_axis='Y',
                matched_footprint_vertices=len(outline))


def main():
    data = json.loads(RECIPE.read_text(encoding='utf-8'))
    copies = OUTPUT / 'Source'
    copies.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for shell_id, row in data['buildings'].items():
        source = ROOT / row['fbx']
        manifest[shell_id] = prepare(source, copies / source.name, row)
    audit = OUTPUT / 'prepared_fbx_audit.json'
    audit.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'Audited Unreal FBX copies: {audit}')


if __name__ == '__main__':
    main()
