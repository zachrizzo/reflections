"""Build a modular c.1450-inspired London merchant hall frontage.

Meter units. +X faces the street, +Y spans the facade, +Z is up. Each
module has a base-center pivot and exactly 4.5 m of frontage. The combined
mesh uses the center portal's pivot and spans 13.5 m of frontage.
"""

from dataclasses import dataclass
import json
import math
from pathlib import Path
import random
import sys

import bmesh
import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / 'Kit'))
sys.path.insert(0, str(ROOT.parent))
from build_facade_kit import Bay
from build_medieval_facades import PAL as MEDIEVAL_PALETTE, crossbeam


WIDTH = 4.5
HALF = WIDTH / 2
WALL_FRONT = .22
PALETTE = {
    'GuildRubble': ((.25, .21, .15), .94, 1.75),
    'GuildAshlar': ((.39, .32, .23), .91, 1.67),
    'GuildDressed': ((.36, .31, .22), .96, None),
    **{name: MEDIEVAL_PALETTE[name] for name in ('ClayTile', 'Oak', 'WeatheredOak', 'Interior', 'LeadedGlass', 'Lead')},
}


@dataclass(frozen=True)
class Opening:
    center: float
    half: float
    base: float
    spring: float
    rise: float
    lights: int
    arched: bool = True

    def crown(self, y, offset=0):
        t = min(1, abs(y - self.center) / (self.half + offset))
        return self.spring + (self.rise + offset) * (1 - t) ** .63


def inset_outline(opening, offset=0, steps=16):
    span = opening.half + offset
    left, right = opening.center - span, opening.center + span
    if not opening.arched:
        return [(left, opening.base - offset), (right, opening.base - offset),
                (right, opening.spring + offset), (left, opening.spring + offset)]
    head = [(right - 2 * span * i / steps, opening.crown(right - 2 * span * i / steps, offset))
            for i in range(steps + 1)]
    return [(left, opening.base - offset), (right, opening.base - offset), *head]


def arch_courses(bay, opening, inner, outer, x0, x1, role, steps=14):
    center, span = opening.center, opening.half
    for step in range(steps):
        t0 = -1 + 2 * (step + .018) / steps
        t1 = -1 + 2 * (step + .982) / steps
        y0, y1 = center + (span + inner) * t0, center + (span + inner) * t1
        yo0, yo1 = center + (span + outer) * t0, center + (span + outer) * t1
        bay.prism(((y0, opening.crown(y0, inner)), (y1, opening.crown(y1, inner)),
                   (yo1, opening.crown(yo1, outer)), (yo0, opening.crown(yo0, outer))),
                  x0, x1 + (.018 if step in (steps // 2 - 1, steps // 2) else 0), role)


def opening_row(bay, z0, z1, openings):
    cursor = -HALF
    for opening in sorted(openings, key=lambda item: item.center):
        left, right = opening.center - opening.half, opening.center + opening.half
        bay.band(cursor, left, z0, z1, -.065, WALL_FRONT, 'GuildRubble')
        if opening.base > z0:
            bay.band(left, right, z0, opening.base, -.065, WALL_FRONT, 'GuildRubble')
        if opening.arched:
            steps = 16
            for i in range(steps):
                a, b = left + (right - left) * i / steps, left + (right - left) * (i + 1) / steps
                bay.prism(((a, opening.crown(a)), (b, opening.crown(b)), (b, z1), (a, z1)),
                          -.065, WALL_FRONT, 'GuildRubble')
        else:
            bay.band(left, right, opening.spring, z1, -.065, WALL_FRONT, 'GuildRubble')
        cursor = right
    bay.band(cursor, HALF, z0, z1, -.065, WALL_FRONT, 'GuildRubble')


def diamond_lights(bay, left, right, bottom, top):
    step_y, step_z = .145, .22
    width, height = right - left, top - bottom
    limit = math.ceil(width / step_y + height / step_z)
    for direction in (-1, 1):
        for index in range(-limit, limit + 1):
            bias = step_z * index
            a, b = ((-bias / step_z, (height - bias) / step_z) if direction == 1
                    else ((bias - height) / step_z, bias / step_z))
            a, b = max(0, a), min(width / step_y, b)
            if b - a < .08:
                continue
            start = (left + a * step_y, bottom + bias + direction * a * step_z)
            end = (left + b * step_y, bottom + bias + direction * b * step_z)
            crossbeam(bay, .061, .069, start, end, .016, 'Lead')


def quatrefoil(bay, center, z, radius, x0, x1, role):
    # Interlocking lobes leave a genuine aperture in the tracery.
    radii = lambda angle: radius * (.81 + .19 * math.cos(4 * angle))
    for step in range(24):
        a, b = math.tau * step / 24, math.tau * (step + 1) / 24
        crossbeam(bay, x0, x1,
                  (center + radii(a) * math.cos(a), z + radii(a) * math.sin(a)),
                  (center + radii(b) * math.cos(b), z + radii(b) * math.sin(b)),
                  .055, role)


def window(bay, opening):
    left, right = opening.center - opening.half, opening.center + opening.half
    bay.prism(inset_outline(opening), .035, .061, 'LeadedGlass')
    gap = .09
    cell = (right - left) / opening.lights
    for number in range(opening.lights):
        a, b = left + number * cell + gap / 2, left + (number + 1) * cell - gap / 2
        diamond_lights(bay, a, b, opening.base + .05, opening.spring - .06)
        if opening.arched:
            small = Opening((a + b) / 2, (b - a) / 2, opening.base,
                            opening.spring - .27, .29, 1)
            arch_courses(bay, small, .0, .048, .069, .126, 'GuildDressed', steps=6)
        if number > 0:
            y = left + number * cell
            bay.band(y - gap / 2, y + gap / 2, opening.base, opening.crown(y) - .055 if opening.arched else opening.spring,
                     .061, .174, 'GuildDressed')
    for y in (left, right):
        bay.band(y - .10, y + .10, opening.base, opening.spring + .02, .055, .339, 'GuildDressed')
    bay.band(left - .16, right + .16, opening.base - .14, opening.base, .052, .441, 'GuildDressed')
    if opening.arched:
        arch_courses(bay, opening, .02, .147, WALL_FRONT - .02, .348, 'GuildDressed')
        if opening.rise >= .55:
            quatrefoil(bay, opening.center, opening.spring + opening.rise * .49, opening.rise * .245,
                       .061, .154, 'GuildDressed')
    else:
        bay.band(left - .14, right + .14, opening.spring, opening.spring + .11, .062, .322, 'GuildDressed')


def portal(bay, opening):
    left, right = opening.center - opening.half, opening.center + opening.half
    bay.prism(inset_outline(opening), .024, .093, 'Oak')
    # Irregular oak boards and forged iron decoration sit behind deep dressed jambs.
    for i in range(11):
        a = left + i * 2 * opening.half / 11
        b = left + (i + 1) * 2 * opening.half / 11 - .018
        outline = ((a, .09), (b, .09), (b, opening.crown(b) - .035), (a, opening.crown(a) - .035))
        bay.prism(outline, .084, .138, 'WeatheredOak' if i % 3 == 2 else 'Oak')
    for z in (.54, 1.47, 2.40):
        for a, b in ((left + .06, -.095), (.095, right - .06)):
            bay.band(a, b, z - .033, z + .033, .136, .160, 'Lead')
    for y in (-.174, .174):
        for angle in range(8):
            a, b = math.tau * angle / 8, math.tau * (angle + 1) / 8
            crossbeam(bay, .147, .208, (y + .073 * math.sin(a), 1.34 + .073 * math.cos(a)),
                      (y + .073 * math.sin(b), 1.34 + .073 * math.cos(b)), .038, 'Lead')
    for side in (-1, 1):
        y = opening.center + side * opening.half
        for index in range(7):
            z = index * opening.spring / 7
            height = opening.spring / 7 - .015
            bay.band(y - .22, y + .22, z, z + height, .087, .445 + .008 * (index % 3), 'GuildAshlar')
        for inn, out, depth in ((.04, .123, .475), (.15, .215, .56), (.235, .32, .665)):
            a, b = sorted((y + side * inn, y + side * out))
            bay.band(a, b, .29, opening.spring, .32, depth, 'GuildDressed')
        for z in (.125, .28, opening.spring - .22, opening.spring - .14):
            bay.band(y - .29, y + .29, z, z + .075, .31, .71, 'GuildDressed')
    for inn, out, depth in ((.04, .123, .475), (.15, .215, .56), (.235, .32, .665)):
        arch_courses(bay, opening, inn, out, .091, depth, 'GuildDressed', steps=18)
    bay.band(left - .29, right + .29, 0, .085, -.065, .565, 'GuildAshlar')
    z = opening.spring + opening.rise + .61
    badge = ((-.32, z + .29), (-.32, z - .04), (0, z - .28), (.32, z - .04), (.32, z + .29))
    bay.prism(badge, WALL_FRONT, .43, 'GuildDressed')
    for y in (-.116, 0, .116):
        bay.prism(((y - .037, z + .15), (y, z + .215), (y + .037, z + .15), (y, z - .092)),
                  .424, .487, 'GuildAshlar')


def buttress(bay, y, top):
    for start, end, half, depth in ((0, .29, .22, .63), (.29, 2.7, .18, .51),
                                    (2.7, 2.91, .21, .49), (2.91, 5.73, .15, .375),
                                    (5.73, 5.96, .19, .39), (5.96, top, .12, .30)):
        if end > start:
            bay.band(y - half, y + half, start, end, .18, depth, 'GuildAshlar')


def roof(bay, eaves, ridge, ridge_y, seed, clay=True):
    left, right = -HALF, HALF
    bay.prism(((left, eaves), (right, eaves), (ridge_y, ridge)), -.065, .22, 'GuildRubble')
    rng = random.Random(seed)
    for a, b in (((left, eaves), (ridge_y, ridge)), ((ridge_y, ridge), (right, eaves))):
        # Project toward the street like the existing jetty shop kit. The tiled
        # band is a shallow visual roof return, with the geodata roof behind it.
        crossbeam(bay, -.128, .576, a, b, .145, 'WeatheredOak')
        ay, az = a
        by, bz = b
        dy, dz = by - ay, bz - az
        distance = math.hypot(dy, dz)
        if clay:
            pitch_count = max(1, round(distance / .24))
            for index in range(pitch_count):
                t0, t1 = index / pitch_count, (index + 1.055) / pitch_count
                p = (max(left + .10, min(right - .10, ay + dy * t0)), az + dz * t0 + .105)
                q = (max(left + .10, min(right - .10, ay + dy * t1)), az + dz * t1 + .105)
                crossbeam(bay, -.16 + rng.uniform(-.018, .018), .687 + rng.uniform(-.016, .018),
                          p, q, .10, 'ClayTile')
    bay.band(-HALF, HALF, eaves - .14, eaves - .02, .18, .477, 'GuildDressed')


LEFT = (
    Opening(-.76, .89, 1.10, 2.66, .23, 3),
    Opening(.91, .39, 1.58, 2.36, 0, 1, False),
    Opening(-.48, 1.25, 5.43, 8.55, .63, 3),
    Opening(1.35, .38, 6.02, 7.46, .38, 1),
)
CENTER = (Opening(0, 1.07, .08, 2.92, .97, 0), Opening(0, 1.44, 5.77, 9.33, .94, 4))
RIGHT = (
    Opening(-.96, .53, 1.03, 2.48, 0, 2, False),
    Opening(.99, .68, 1.22, 2.49, .39, 2),
    Opening(-.68, 1.03, 5.10, 7.84, .64, 3),
    Opening(1.27, .52, 5.70, 7.33, .42, 2),
)
MODULES = (
    ('WestWing', 10.82, 13.04, -.35, LEFT),
    ('Portal', 11.31, 14.46, .10, CENTER),
    ('EastWing', 10.48, 12.52, .43, RIGHT),
)


def module(kind, eaves, ridge, ridge_y, openings):
    bay = Bay()
    low = [o for o in openings if o.base < 4]
    high = [o for o in openings if o.base >= 4]
    opening_row(bay, 0, 4.80, low)
    opening_row(bay, 4.80, eaves, high)
    for item in openings:
        portal(bay, item) if item.lights == 0 else window(bay, item)
    base = ((-HALF, -1.08), (1.08, HALF)) if kind == 'Portal' else ((-HALF, HALF),)
    for left, right in base:
        bay.band(left, right, 0, .18, -.065, .305, 'GuildAshlar')
        bay.band(left, right, .18, .30, -.03, .275, 'GuildDressed')
    bay.band(-HALF, HALF, 4.77, 4.90, .18, .368, 'GuildDressed')
    for y in (-2.026, 2.026):
        buttress(bay, y, eaves - .36)
    roof(bay, eaves, ridge, ridge_y, 441 + len(kind))
    return bay


def texture_path(role):
    return ((ROOT if role.startswith('Guild') else ROOT.parent) / 'Textures' /
            f'T_GLMedieval_{role}.png')


def material(role):
    name = 'M_GLMedieval_' + role
    existing = bpy.data.materials.get(name)
    if existing:
        return existing
    color, roughness, scale = PALETTE[role]
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = roughness
    if scale is not None:
        tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(str(texture_path(role)), check_existing=True)
        mat.node_tree.links.new(tex.outputs['Color'], shader.inputs['Base Color'])
    return mat


def make_mesh(name, components):
    bay = Bay()
    for component, offset in components:
        start = len(bay.vertices)
        bay.vertices.extend((x, max(-HALF, min(HALF, y)) + offset, z) for x, y, z in component.vertices)
        bay.polygons.extend(tuple(start + i for i in face) for face in component.polygons)
        bay.roles.extend(component.roles)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(bay.vertices, [], bay.polygons)
    mesh.update()
    roles = [role for role in PALETTE if role in bay.roles]
    indices = {role: index for index, role in enumerate(roles)}
    for role in roles:
        mesh.materials.append(material(role))
    for face, role in zip(mesh.polygons, bay.roles):
        face.material_index = indices[role]
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    uv = mesh.uv_layers.new(name='UV0')
    for face in mesh.polygons:
        scale = PALETTE[roles[face.material_index]][2] or 1
        normal_axis = max(range(3), key=lambda i: abs(face.normal[i]))
        a, b = ((1, 2), (0, 2), (1, 0))[normal_axis]
        for loop_index in face.loop_indices:
            position = mesh.vertices[mesh.loops[loop_index].vertex_index].co
            uv.data[loop_index].uv = (position[a] / scale, position[b] / scale)
    mesh.calc_loop_triangles()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def export(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = ROOT / 'Source' / f'{obj.name}.fbx'
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, object_types={'MESH'},
                             axis_forward='-Z', axis_up='Y', mesh_smooth_type='FACE',
                             bake_anim=False, path_mode='COPY', embed_textures=True)
    return {'fbx': str(path.relative_to(ROOT)).replace('\\', '/'),
            'min_cm': [round(min(v[i] for v in obj.bound_box) * 100, 3) for i in range(3)],
            'max_cm': [round(max(v[i] for v in obj.bound_box) * 100, 3) for i in range(3)],
            'triangles': len(obj.data.loop_triangles), 'materials': [mat.name for mat in obj.data.materials]}


def preview(output):
    bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, -.018))
    floor = bpy.context.object
    mat = bpy.data.materials.new('Preview Earth')
    mat.diffuse_color = (.10, .078, .046, 1)
    floor.data.materials.append(mat)
    for position, energy, size in (((8, -9, 14), 4200, 13), ((5, 7, 12), 2700, 16)):
        bpy.ops.object.light_add(type='AREA', location=position)
        light = bpy.context.object
        light.data.energy = energy
        light.data.size = size
        light.rotation_euler = (Vector((0, 0, 7)) - light.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.ops.object.camera_add(location=(23, -8.9, 14.8))
    camera = bpy.context.object
    camera.rotation_euler = (Vector((0, 0, 7.09)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 18.5
    scene = bpy.context.scene
    scene.camera = camera
    scene.world = bpy.data.worlds.new('Guildhall overcast')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .46
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 16
    scene.cycles.use_denoising = True
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 4
    scene.render.resolution_x = 1350
    scene.render.resolution_y = 1240
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(output.resolve())
    bpy.ops.render.render(write_still=True)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'
    (ROOT / 'Source').mkdir(parents=True, exist_ok=True)
    modules = [(params[0], module(*params)) for params in MODULES]
    info = {'schema': 1, 'width_cm': 450, 'combined_width_cm': 1350,
            'pivot': 'bottom-center on the wall plane, face +X, up +Z', 'meshes': {}, 'materials': {}}
    for name, bay in modules:
        obj = make_mesh(f'SM_GLMedieval_Guildhall_{name}', [(bay, 0)])
        info['meshes'][obj.name] = export(obj)
        obj.hide_render = True
    complete = make_mesh('SM_GLMedieval_Guildhall_Frontage',
                         [(bay, (number - 1) * WIDTH) for number, (_, bay) in enumerate(modules)])
    info['meshes'][complete.name] = export(complete)
    for role, (color, roughness, scale) in PALETTE.items():
        texture = None
        if scale is not None:
            texture = texture_path(role).relative_to(ROOT.parent).as_posix()
            texture = texture.split('Guildhall/', 1)[-1] if role.startswith('Guild') else '../' + texture
        info['materials']['M_GLMedieval_' + role] = {'linear_rgba': [*color, 1], 'roughness': roughness,
                                                      'metallic': 0, 'texture': texture}
    (ROOT / 'guildhall_kit.json').write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
    if '--' in sys.argv:
        preview(Path(sys.argv[sys.argv.index('--') + 1]))


if __name__ == '__main__':
    main()
