"""Export the shared fascia panel for the Gray London shopfronts."""

from pathlib import Path

import bpy


NAME = 'SM_GL_Fascia'
WIDTH = 3.08
HEIGHT = 0.272
DEPTH = 0.018
BEVEL = 0.003
OUT = Path(__file__).resolve().parent / 'Source' / f'{NAME}.fbx'


def contour(depth, inset):
    half_width = WIDTH / 2 - inset
    half_height = HEIGHT / 2 - inset
    return [(depth, -half_width, -half_height), (depth, half_width, -half_height),
            (depth, half_width, half_height), (depth, -half_width, half_height)]


def build_panel():
    # The origin is centered on the back so the panel mounts directly on a fascia.
    vertices = contour(0, 0) + contour(DEPTH - BEVEL, 0) + contour(DEPTH, BEVEL)
    faces = [(3, 2, 1, 0)]
    for layer in (0, 4):
        for edge in range(4):
            end = (edge + 1) % 4
            faces.append((layer + edge, layer + end, layer + end + 4, layer + edge + 4))
    faces.append((8, 9, 10, 11))

    mesh = bpy.data.meshes.new(NAME)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh.validate()
    uv = mesh.uv_layers.new(name='UVMap')
    for polygon in mesh.polygons:
        for loop_index in polygon.loop_indices:
            vertex = mesh.vertices[mesh.loops[loop_index].vertex_index].co
            if polygon.index == len(faces) - 1:
                u = vertex.y / (WIDTH - 2 * BEVEL) + 0.5
                v = vertex.z / (HEIGHT - 2 * BEVEL) + 0.5
            elif polygon.index == 0:
                u = 0.002 + 0.003 * (vertex.y / WIDTH + 0.5)
                v = 0.002 + 0.003 * (vertex.z / HEIGHT + 0.5)
            else:
                # The edges sample a narrow strip inside the unlettered border.
                along = vertex.y / WIDTH if polygon.index % 2 else vertex.z / HEIGHT
                u = 0.002 + 0.003 * vertex.x / DEPTH
                v = 0.002 + 0.003 * (along + 0.5)
            uv.data[loop_index].uv = (u, v)

    placeholder = bpy.data.materials.new('Fascia')
    placeholder.diffuse_color = (0.10, 0.14, 0.12, 1)
    mesh.materials.append(placeholder)
    panel = bpy.data.objects.new(NAME, mesh)
    bpy.context.collection.objects.link(panel)
    return panel


if __name__ == '__main__':
    bpy.ops.object.select_all(action='DESELECT')
    panel = build_panel()
    panel.select_set(True)
    bpy.context.view_layer.objects.active = panel
    OUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=str(OUT), use_selection=True, object_types={'MESH'}, global_scale=1.0,
        apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE', use_space_transform=True,
        bake_space_transform=False, axis_forward='-Z', axis_up='Y', mesh_smooth_type='FACE',
        bake_anim=False, path_mode='AUTO',
    )
