"""Build period-inspired London facade modules in a background Blender process.

Meters, +X faces the street, +Y spans the bay, +Z goes up. The pivot is the
centre of the bottom seam on the existing wall plane. The backing overlaps
the wall by 2.5 cm, and the visible detailing projects toward +X.
"""

from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'Source'
WIDTH = 4.0
STOREY = 3.2
CAP = .55

# The slot names are shared by all meshes. Albedo tiles are authored outside Blender.
PALETTE = {
    'RedBrick': ((.173, .055, .032), .84, 0, 1.024),
    'PortlandStone': ((.38, .34, .28), .76, 0, 1.6),
    'GreyGranite': ((.17, .18, .18), .72, 0, 1.6),
    'BlackIron': ((.024, .031, .032), .58, .35, None),
    'SashGlass': ((.059, .095, .107), .26, .12, None),
    'Bronze': ((.132, .074, .030), .37, .65, None),
    'ShadowGlass': ((.028, .062, .059), .24, .16, None),
    'BlueGlass': ((.079, .141, .167), .24, .20, None),
}


@dataclass
class Bay:
    vertices: list = field(default_factory=list)
    polygons: list = field(default_factory=list)
    roles: list = field(default_factory=list)

    def prism(self, contour, back, front, role):
        """Extrude a convex Y/Z contour and give every side the same material."""
        start = len(self.vertices)
        count = len(contour)
        for x in (back, front):
            self.vertices.extend((x, y, z) for y, z in contour)
        self.polygons.append(tuple(start + i for i in range(count - 1, -1, -1)))
        self.polygons.append(tuple(start + count + i for i in range(count)))
        for index in range(count):
            next_index = (index + 1) % count
            self.polygons.append(tuple(start + i for i in (index, next_index,
                                                            next_index + count, index + count)))
        self.roles.extend([role] * (count + 2))

    def band(self, left, right, low, high, back, front, role):
        self.prism(((left, low), (right, low), (right, high), (left, high)), back, front, role)

    def arch(self, center, spring, radius, rise, thick, back, front, role, steps=13):
        """Make shallow voussoirs as individual wedge meshes with mortar joints."""
        for step in range(steps):
            lo = math.pi * (step + .033) / steps
            hi = math.pi * (step + .967) / steps
            outline = tuple((center + r * math.cos(a), spring + h * math.sin(a))
                            for a, r, h in ((lo, radius, rise), (lo, radius + thick, rise + thick),
                                            (hi, radius + thick, rise + thick), (hi, radius, rise)))
            self.prism(outline, back, front + (.014 if step == steps // 2 else 0), role)

    def sash(self, center, width, low, high, surround='PortlandStone', glass='SashGlass', dividers=1):
        left, right = center - width / 2, center + width / 2
        self.band(left, right, low, high, .012, .041, glass)
        for y in (left, right):
            self.band(y - .052, y + .052, low, high, .043, .135, 'BlackIron')
            self.band(y - .096, y + .096, low - .04, high + .06, .036, .21, surround)
        for z in (low, (low + high) / 2, high):
            self.band(left + .05, right - .05, z - .032, z + .032, .045, .116, 'BlackIron')
        for part in range(1, dividers + 1):
            y = left + width * part / (dividers + 1)
            self.band(y - .022, y + .022, low, high, .044, .114, 'BlackIron')
        self.band(left - .15, right + .15, low - .12, low - .04, .03, .28, surround)
        self.band(left - .122, right + .122, high + .02, high + .13, .03, .226, surround)

    def infill_behind_arch(self, left, right, spring, rise, back, front, role):
        center, radius = (left + right) / 2, (right - left) / 2
        for step in range(12):
            a, b = math.pi * step / 12, math.pi * (step + 1) / 12
            y0, y1 = center + radius * math.cos(a), center + radius * math.cos(b)
            z0, z1 = spring + rise * math.sin(a), spring + rise * math.sin(b)
            self.prism(((y1, z1), (y0, z0), (y0, STOREY), (y1, STOREY)), back, front, role)


def brick_bay(layer):
    bay = Bay()
    if layer == 'Cornice':
        return cornice_bay('RedBrick', 'PortlandStone', dentils=True)
    ground = layer in ('Base', 'Entrance')
    bottom = .48 if ground else .70
    top = 2.35 if ground else 2.45
    if layer == 'Entrance':
        low_windows = ((-1.30, .75), (1.30, .75))
        for left, right in ((-2, -.68), (.68, 2)):
            bay.band(left, right, 0, bottom, -.025, .145, 'RedBrick')
        walls = ((-2, -1.675), (-.925, -.68), (.68, .925), (1.675, 2))
        bay.band(-.68, .68, .08, 2.61, .012, .055, 'ShadowGlass')
        bay.band(-.68, .68, 2.61, STOREY, -.025, .145, 'RedBrick')
        for y in (-.68, .68):
            bay.band(y - .115, y + .115, 0, 2.70, .04, .34, 'PortlandStone')
            bay.band(y - .156, y + .156, 2.48, 2.62, .30, .39, 'PortlandStone')
        bay.arch(0, 2.34, .68, .27, .095, .145, .29, 'PortlandStone', steps=11)
        bay.band(-.81, .81, .00, .09, .00, .22, 'GreyGranite')
        bay.band(-.035, .035, .09, 2.60, .054, .128, 'BlackIron')
        bay.band(-.60, .60, 2.12, 2.17, .056, .128, 'BlackIron')
        for y in (-.17, .17):
            bay.band(y - .025, y + .025, .97, 1.17, .11, .22, 'Bronze')
        for left, right in ((-2, -.68), (.68, 2)):
            bay.band(left, right, top, STOREY, -.025, .145, 'RedBrick')
    else:
        low_windows = ((-.94, 1.10), (.94, 1.10))
        bay.band(-2, 2, 0, bottom, -.025, .145, 'RedBrick')
        bay.band(-2, 2, top, STOREY, -.025, .145, 'RedBrick')
        walls = ((-2, -1.49), (-.34, .34), (1.49, 2))
    for left, right in walls:
        bay.band(left, right, bottom, top, -.025, .145, 'RedBrick')
    for center, width in low_windows:
        bay.sash(center, width, bottom, top, dividers=2 if ground else 1)
        bay.arch(center, top + .025, width / 2, .22, .085, .143, .209, 'PortlandStone', steps=11)
    plinths = ((-2, -.68), (.68, 2)) if layer == 'Entrance' else ((-2, 2),)
    for left, right in plinths:
        bay.band(left, right, .075, .165, .142, .216, 'PortlandStone')
    bay.band(-2, 2, 2.97, 3.055, .142, .227, 'PortlandStone')
    if ground:
        for height in (.24, .39, 2.79):
            for left, right in plinths if height < .4 else ((-2, 2),):
                bay.band(left, right, height, height + .026, .143, .161, 'PortlandStone')
    else:
        bay.band(-2, 2, .35, .44, .141, .221, 'PortlandStone')
        for y in (-1.86, -.19, .19, 1.86):
            bay.band(y - .085, y + .085, .45, 2.91, .144, .212, 'RedBrick')
    return bay


def stone_bay(layer):
    if layer == 'Cornice':
        return cornice_bay('PortlandStone', 'PortlandStone', dentils=True)
    bay = Bay()
    ground = layer in ('Base', 'Entrance')
    opening = 1.28 if ground else .66
    centers = (0,) if ground else (-.89, .89)
    spring = 2.13 if ground else 2.22
    rise = .48 if ground else .37
    bottom = .07 if layer == 'Entrance' else (.33 if ground else .61)
    bay.band(-2, 2, 0, bottom, -.025, .21, 'GreyGranite' if ground else 'PortlandStone')
    right_previous = -2
    for center in centers:
        left, right = center - opening, center + opening
        bay.band(right_previous, left, bottom, STOREY, -.025, .20, 'PortlandStone')
        right_previous = right
        bay.infill_behind_arch(left, right, spring, rise, -.025, .20, 'PortlandStone')
        bay.band(left, right, bottom, spring, .014, .047, 'ShadowGlass')
        # Quartered arch transom, kept behind the outer arch frame.
        contour = [(left, spring), (right, spring)]
        contour += [(center + opening * math.cos(j * math.pi / 12),
                     spring + rise * math.sin(j * math.pi / 12)) for j in range(1, 12)]
        bay.prism(contour, .013, .047, 'ShadowGlass')
        bay.arch(center, spring, opening, rise, .162, .199, .343, 'PortlandStone')
        for y in (left, right):
            bay.band(y - .095, y + .095, bottom, spring, .044, .31, 'PortlandStone')
            bay.band(y - .133, y + .133, spring - .04, spring + .058, .18, .377, 'PortlandStone')
        if layer == 'Entrance':
            for y in (-.57, 0, .57):
                bay.band(y - .032, y + .032, bottom, spring, .048, .109, 'BlackIron')
            for y in (-.13, .13):
                bay.band(y - .021, y + .021, 1.02, 1.21, .11, .20, 'Bronze')
        elif ground:
            for y in (-.82, -.4, 0, .4, .82):
                bay.band(y - .028, y + .028, bottom, spring, .048, .109, 'BlackIron')
        else:
            bay.band(center - .03, center + .03, bottom, spring + rise - .022, .048, .107, 'BlackIron')
        transoms = (bottom, spring - .01) if layer == 'Entrance' else (bottom, spring - .01, spring * .55 + bottom * .45)
        for z in transoms:
            bay.band(left + .08, right - .08, z - .027, z + .027, .047, .122, 'BlackIron')
        bay.band(left - .12, right + .12, max(0, bottom - .105), bottom - .028, .19, .38, 'PortlandStone')
    bay.band(right_previous, 2, bottom, STOREY, -.025, .20, 'PortlandStone')
    for y in (-1.83, 1.83):
        bay.band(y - .10, y + .10, bottom, 2.95, .199, .304, 'PortlandStone')
        bay.band(y - .154, y + .154, 2.78, 2.9, .303, .394, 'PortlandStone')
    bay.band(-2, 2, 3.04, 3.115, .201, .358, 'PortlandStone')
    if ground:
        for z in (.86, 1.37, 1.88):
            for y0, y1 in ((-2, -1.41), (1.41, 2)):
                bay.band(y0, y1, z, z + .03, .20, .239, 'PortlandStone')
    return bay


def glass_bay(layer):
    if layer == 'Cornice':
        return cornice_bay('GreyGranite', 'BlackIron', dentils=False)
    bay = Bay()
    ground = layer in ('Base', 'Entrance')
    sill = .30 if ground else .83
    if layer == 'Entrance':
        bay.band(-2, -.67, 0, sill, -.025, .127, 'GreyGranite')
        bay.band(.67, 2, 0, sill, -.025, .127, 'GreyGranite')
        bay.band(-.67, .67, 0, .09, -.025, .10, 'GreyGranite')
        bay.band(-.67, .67, .09, sill, -.025, .052, 'BlueGlass')
    else:
        bay.band(-2, 2, 0, sill, -.025, .127, 'GreyGranite' if ground else 'ShadowGlass')
    bay.band(-2, 2, sill, 2.96, -.025, .052, 'BlueGlass')
    bay.band(-2, 2, 2.96, STOREY, -.025, .131, 'GreyGranite')
    for y, width in ((-1.9, .20), (-.97, .06), (0, .07), (.97, .06), (1.90, .20)):
        role = 'GreyGranite' if abs(y) > 1 else 'BlackIron'
        bay.band(y - width / 2, y + width / 2, 0, STOREY,
                 .048, .286 if abs(y) > 1 else .164, role)
    for z in (sill, 2.35, 2.93):
        spans = ((-1.795, -.67), (.67, 1.795)) if layer == 'Entrance' and z == sill else ((-1.795, 1.795),)
        for left, right in spans:
            bay.band(left, right, z - .037, z + .037, .05, .145, 'BlackIron')
    if layer == 'Entrance':
        # Central paired floor-height office doors and bronze push rails.
        for y in (-.67, .67):
            bay.band(y - .035, y + .035, .09, 2.30, .054, .20, 'BlackIron')
        bay.band(-.67, .67, 2.29, 2.36, .054, .20, 'BlackIron')
        for y in (-.33, .33):
            bay.band(y - .26, y + .26, 1.10, 1.145, .11, .22, 'Bronze')
    return bay


def cornice_bay(core, trim, dentils):
    bay = Bay()
    bay.band(-2, 2, 0, CAP, -.025, .13, core)
    for low, high, front in ((.03, .075, .21), (.235, .31, .32), (.45, .535, .46)):
        bay.band(-2, 2, low, high, .127, front, trim)
    if dentils:
        for index in range(18):
            y = -1.88 + index * .22
            bay.band(y - .048, y + .048, .312, .447, .128, .275, trim)
    return bay


def material(role):
    name = 'M_GLPCG_' + role
    existing = bpy.data.materials.get(name)
    if existing:
        return existing
    color, roughness, metallic, tile_size = PALETTE[role]
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Metallic'].default_value = metallic
    if tile_size:
        tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(str(ROOT / 'Textures' / f'T_GLPCG_{role}.png'), check_existing=True)
        mat.node_tree.links.new(tex.outputs['Color'], shader.inputs['Base Color'])
    return mat


def mesh_for(name, bay):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(bay.vertices, [], bay.polygons)
    mesh.update()
    roles = [role for role in PALETTE if role in bay.roles]
    indices = {role: index for index, role in enumerate(roles)}
    for role in roles:
        mesh.materials.append(material(role))
    for polygon, role in zip(mesh.polygons, bay.roles):
        polygon.material_index = indices[role]
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()

    uv = mesh.uv_layers.new(name='UV0')
    for polygon in mesh.polygons:
        role = roles[polygon.material_index]
        size = PALETTE[role][3] or 1.0
        normal_axis = max(range(3), key=lambda axis: abs(polygon.normal[axis]))
        u, v = ((1, 2), (0, 2), (1, 0))[normal_axis]
        for loop in polygon.loop_indices:
            point = mesh.vertices[mesh.loops[loop].vertex_index].co
            uv.data[loop].uv = (point[u] / size, point[v] / size)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    mesh.calc_loop_triangles()
    return obj, roles


def export(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    output = SOURCE / f'{obj.name}.fbx'
    # This exporter baseline also produces +X-facing FBXs in the existing shop kit.
    bpy.ops.export_scene.fbx(filepath=str(output), use_selection=True, object_types={'MESH'},
                             axis_forward='-Z', axis_up='Y', mesh_smooth_type='FACE',
                             bake_anim=False, path_mode='COPY', embed_textures=True)
    return output.relative_to(ROOT).as_posix()


def preview(objects, output):
    for number, modules in enumerate(objects):
        for row, obj in enumerate(modules):
            if row == 0:
                obj.hide_render = True
            else:
                obj.location = (0, (number - 1) * 4.34, (0, STOREY, STOREY * 2)[row - 1])
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.03))
    floor = bpy.context.object
    floor_mat = bpy.data.materials.new('Preview Ground')
    floor_mat.diffuse_color = (.112, .111, .103, 1)
    floor.data.materials.append(floor_mat)
    for position, energy, size in (((5, -5, 10), 2350, 8), ((4, 6, 7), 1100, 8)):
        bpy.ops.object.light_add(type='AREA', location=position)
        light = bpy.context.object
        light.data.energy = energy
        light.data.size = size
        light.rotation_euler = (Vector((0, 0, 2.5)) - light.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.ops.object.camera_add(location=(17, -5, 7.7))
    camera = bpy.context.object
    camera.rotation_euler = (Vector((0, 0, 3.2)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 14.4
    scene = bpy.context.scene
    scene.camera = camera
    scene.world = bpy.data.worlds.new('Overcast preview')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value = .4
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 14
    scene.cycles.use_denoising = True
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 4
    scene.render.resolution_x = 1360
    scene.render.resolution_y = 880
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(output.resolve())
    bpy.ops.render.render(write_still=True)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'
    SOURCE.mkdir(parents=True, exist_ok=True)
    objects = []
    manifest = {'schema': 1, 'width_cm': 400, 'storey_height_cm': 320, 'cornice_height_cm': 55,
                'axes': {'front': '+X', 'lateral': 'Y', 'up': '+Z'},
                'pivot': 'wall plane at bottom centre', 'collision': False, 'styles': {},
                'materials': {f'M_GLPCG_{key}': {'linear_rgba': [*values[0], 1], 'roughness': values[1],
                                                 'metallic': values[2],
                                                 'texture': f'Textures/T_GLPCG_{key}.png' if values[3] else None}
                              for key, values in PALETTE.items()}}
    families = (('edwardian_brick', 'EdwardianBrick', brick_bay),
                ('stone_office', 'StoneOffice', stone_bay), ('glass_office', 'GlassOffice', glass_bay))
    for style, prefix, build in families:
        modules = {}
        objects.append([])
        for layer in ('Base', 'Entrance', 'Upper', 'Cornice'):
            obj, roles = mesh_for(f'SM_GLPCG_{prefix}_{layer}', build(layer))
            obj['collision'] = 'None; original map shell provides collision'
            references = {'fbx': export(obj), 'mesh': obj.name,
                          'triangles': len(obj.data.loop_triangles),
                          'materials': [f'M_GLPCG_{role}' for role in roles],
                          'min_cm': [round(min(v[i] for v in obj.bound_box) * 100, 3) for i in range(3)],
                          'max_cm': [round(max(v[i] for v in obj.bound_box) * 100, 3) for i in range(3)]}
            modules[layer.lower()] = references
            objects[-1].append(obj)
        manifest['styles'][style] = modules
    (ROOT / 'kit_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    if '--' in sys.argv:
        preview(objects, Path(sys.argv[sys.argv.index('--') + 1]))


if __name__ == '__main__':
    main()
