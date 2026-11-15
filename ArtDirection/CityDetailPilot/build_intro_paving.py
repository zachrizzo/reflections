"""Export supported, shallow paving strips measured in the London editor."""

import json
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'Source'

# Each row is (Unreal Y, wall X, walk surface Z, strip width in cm).
# East fronts sit beside an unpaved channel; the 47 cm setback keeps the
# paving supported on the existing road-level mesh over its full width.
STRIPS = {
    'West': (1, 3, [
        (31380, 329133.7, 10, 20),
        (31425, 329140.9, 10, 162),
        (31895, 329215.9, 10, 162),
        (31962, 329226.6, 10, 24),
    ]),
    'East': (-1, 47, [
        (31015, 330320.1, 28, 20),
        (31080, 330330.1, 28, 168),
        (32540, 330554.7, 28, 168),
        (32615, 330566.3, 28, 22),
    ]),
}


def material(name):
    return bpy.data.materials.get(name) or bpy.data.materials.new(name)


def build(name, direction, setback, sections):
    pivot_x = round(sections[1][1] + direction * (setback + sections[1][3] / 2))
    pivot_y = round((sections[0][0] + sections[-1][0]) / 2)
    pivot_z = sections[0][2]
    vertices, faces, slots = [], [], []
    for y, wall_x, ground_z, width in sections:
        inner_x = wall_x + direction * setback
        # Flush flagstones, a 14 cm kerb, then a short bevel back to grade.
        for offset, height in ((0, 1.2), (width - 16, 1.2),
                               (width - 12, 2.7), (width - 3, 2.7),
                               (width, .25)):
            vertices.append(((inner_x + direction * offset - pivot_x) / 100,
                             -(y - pivot_y) / 100, (ground_z + height - pivot_z) / 100))
    for i in range(len(sections) - 1):
        for column in range(4):
            n = i * 5 + column
            face = (n, n + 1, n + 6, n + 5)
            faces.append(face[::-1] if direction > 0 else face)
            slots.append(0 if column == 0 else 1)

    asset_name = f'SM_GL_IntroPaving_{name}'
    mesh = bpy.data.meshes.new(asset_name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh.materials.append(material('GL_Flagstones'))
    mesh.materials.append(material('GL_Kerb'))
    uv = mesh.uv_layers.new(name='UVMap')
    for poly, slot in zip(mesh.polygons, slots, strict=True):
        poly.material_index = slot
        for index in poly.loop_indices:
            x, y, _ = mesh.vertices[mesh.loops[index].vertex_index].co
            uv.data[index].uv = (x / 1.8, y / 1.8)

    obj = bpy.data.objects.new(asset_name, mesh)
    bpy.context.collection.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(filepath=str(OUTPUT / f'{asset_name}.fbx'),
                             use_selection=True, object_types={'MESH'},
                             axis_forward='-Z', axis_up='Y', bake_anim=False)
    return {'asset': asset_name, 'location_cm': [pivot_x, pivot_y, pivot_z]}


if __name__ == '__main__':
    OUTPUT.mkdir(parents=True, exist_ok=True)
    stems = [build(name, *profile) for name, profile in STRIPS.items()]
    print(json.dumps(stems))
