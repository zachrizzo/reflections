"""Create an enclosed exterior for a low Thames merchant warehouse in Blender."""

import json
import math
from pathlib import Path
import random
import sys

import bmesh
import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(ROOT.parent / 'Guildhall'))
from build_medieval_facades import Bay, PAL, crossbeam
from build_guildhall import PALETTE as GUILD_PALETTE


NAME = 'SM_GLMedieval_ThamesWarehouse'
HALF = 2.25
DEPTH = 8.0
EAVES = 6.23
RIDGE = 9.29
STONE = 'GuildRubble'
TRIM = 'GuildDressed'
WOOD = 'WeatheredOak'
PALETTE = {**PAL, STONE: GUILD_PALETTE[STONE], TRIM: GUILD_PALETTE[TRIM]}


def solid(bay, points, faces, role):
    start = len(bay.vertices)
    bay.vertices.extend(points)
    bay.polygons.extend(tuple(start + index for index in face) for face in faces)
    bay.roles.extend([role] * len(faces))


def prism_y(bay, contour, left, right, role):
    count = len(contour)
    points = [(x, y, z) for y in (left, right) for x, z in contour]
    faces = [tuple(range(count - 1, -1, -1)), tuple(range(count, count * 2))]
    for i in range(count):
        j = (i + 1) % count
        faces.append((i, j, j + count, i + count))
    solid(bay, points, faces, role)


def tube(bay, a, b, radius, role, sides=8):
    start, end = Vector(a), Vector(b)
    main = (end - start).normalized()
    u = main.orthogonal().normalized()
    v = main.cross(u)
    points = [tuple(point + radius * (math.cos(math.tau * i / sides) * u + math.sin(math.tau * i / sides) * v))
              for point in (start, end) for i in range(sides)]
    faces = [tuple(range(sides - 1, -1, -1)), tuple(range(sides, sides * 2))]
    for i in range(sides):
        j = (i + 1) % sides
        faces.append((i, j, j + sides, i + sides))
    solid(bay, points, faces, role)


def ring(bay, center, radius, thickness, role, horizontal=False):
    x, y, z = center
    points = [(x + (radius * math.cos(i * math.tau / 10) if horizontal else 0),
               y + (0 if horizontal else radius * math.cos(i * math.tau / 10)),
               z + radius * math.sin(i * math.tau / 10)) for i in range(11)]
    for a, b in zip(points, points[1:]):
        tube(bay, a, b, thickness, role, sides=6)


def planks(bay, left, right, bottom, top, back, grain, step, seed):
    rng = random.Random(seed)
    x = left
    while x < right - .025:
        end = min(right, x + rng.uniform(step * .84, step * 1.19))
        finish = 'Oak' if rng.random() < .32 else grain
        bay.band(x, end - .009, bottom, top, back, back + rng.uniform(.055, .074), finish)
        x = end


def arch_height(y, center, width, spring, rise):
    d = min(1, abs(y - center) / width)
    return spring + rise * math.sqrt(max(0, 1 - d * d))


def storage_storey(bay):
    center, span, spring, rise = -.24, .93, 1.94, .45
    left, right = center - span, center + span
    head = 3.15
    bay.band(-HALF, left, 0, head, -.065, .235, STONE)
    bay.band(right, HALF, 0, head, -.065, .235, STONE)
    bay.band(left, right, 0, .09, -.065, .365, TRIM)
    for index in range(17):
        y0, y1 = left + 2 * span * index / 17, left + 2 * span * (index + 1) / 17
        z0 = arch_height(y0, center, span, spring, rise)
        z1 = arch_height(y1, center, span, spring, rise)
        bay.prism(((y0, z0), (y1, z1), (y1, head), (y0, head)), -.065, .235, STONE)
        bay.prism(((y0 + .008, .09), (y1 - .008, .09), (y1 - .008, z1 - .03), (y0 + .008, z0 - .03)),
                  .031, .083 + .008 * (index % 3), 'Oak' if index % 4 == 1 else WOOD)
    for z in (.36, 1.07, 1.69):
        bay.band(left + .07, center - .052, z, z + .053, .071, .122, 'Lead')
        bay.band(center + .052, right - .07, z, z + .053, .071, .122, 'Lead')
    for y in (center - .164, center + .164):
        ring(bay, (.149, y, 1.02), .062, .018, 'Lead')
    for side in (-1, 1):
        for course in range(5):
            z = course * spring / 5
            y = center + side * span
            bay.band(y - .158, y + .158, z, z + spring / 5 - .015, .165, .335 + .011 * (course % 2), TRIM)
    for index in range(19):
        a, b = math.pi * (index + .024) / 19, math.pi * (index + .976) / 19
        contour = [(center + widths * math.cos(t), spring + rises * math.sin(t))
                   for t, widths, rises in ((a, span, rise), (a, span + .241, rise + .22),
                                            (b, span + .241, rise + .22), (b, span, rise))]
        bay.prism(contour, .181, .382 + (.045 if index == 9 else 0), TRIM)
    # The surviving wall is behind this recessed-looking cellar cover.
    bay.band(1.04, 1.82, 1.00, 1.56, .235, .252, 'Interior')
    bay.band(1.00, 1.89, .925, 1.00, .231, .390, TRIM)
    bay.band(.996, 1.87, 1.555, 1.627, .232, .334, TRIM)
    for y in (1.14, 1.31, 1.48, 1.65, 1.82):
        bay.band(y - .017, y + .017, 1.00, 1.56, .247, .278, 'Lead')
    bay.band(.997, 1.868, 1.308, 1.34, .23, .275, 'Lead')
    for y in (-2.067, 2.067):
        bay.band(y - .183, y + .183, 0, .43, -.065, .44, STONE)
        bay.band(y - .14, y + .14, .43, head + .18, .13, .311, TRIM)
    bay.band(-HALF, HALF, 2.87, 3.18, .177, .44, 'Oak')
    for y in (-1.91, -1.13, -.41, .38, 1.16, 1.90):
        bay.band(y - .063, y + .063, 2.77, 2.96, .239, .452, WOOD)


def loading_storey(bay):
    bottom, top = 3.15, EAVES
    planks(bay, -HALF, HALF, bottom, top, .278, WOOD, .171, 1226)
    low, high, left, right = 3.53, 5.70, -.56, .81
    bay.band(left - .06, right + .06, low - .041, high + .034, .338, .39, 'Interior')
    planks(bay, left, right, low, high, .391, WOOD, .137, 358)
    for z in (low + .18, high - .20):
        bay.band(left, .08, z, z + .106, .447, .499, 'Oak')
        bay.band(.15, right, z, z + .106, .446, .503, 'Oak')
    bay.band(left - .091, right + .091, low - .145, low, .30, .677, WOOD)
    bay.band(left - .093, right + .093, high - .035, high + .106, .309, .522, 'Oak')
    for y in (left, right):
        bay.band(y - .079, y + .079, low, high, .325, .549, 'Oak')
    for y in (left + .48, right - .48):
        ring(bay, (.529, y, 4.53), .055, .013, 'Lead')
    for y in (-2.112, -1.31, 1.43, 2.109):
        bay.band(y - .133, y + .133, bottom, top, .291, .515, 'Oak')
    for start, end in (((-2.03, 3.38), (-1.385, 5.46)), ((2.057, 3.33), (1.53, 5.32))):
        crossbeam(bay, .33, .51, start, end, .209, WOOD)
    for left, right in ((-1.99, -1.51), (1.65, 1.99)):
        bay.band(left, right, 4.66, 5.63, .345, .376, 'Interior')
        for z in (4.76, 4.94, 5.12, 5.30, 5.48):
            bay.band(left + .017, right - .017, z, z + .074, .369, .414, WOOD)
        bay.band(left - .036, right + .036, 4.633, 4.708, .344, .466, 'Oak')
        bay.band(left - .043, right + .043, 5.598, 5.674, .356, .47, 'Oak')
    # Rectangular hoist timber and braced heel. Attached rope is a decorative static prop.
    bay.band(-.024, .269, 5.907, 6.164, .126, 1.26, 'Oak')
    prism_y(bay, ((.395, 5.42), (.506, 5.434), (.904, 5.936), (.741, 5.945)), -.016, .262, WOOD)
    bay.band(-.042, .284, 5.878, 6.199, 1.186, 1.209, 'Lead')
    ring(bay, (1.202, .132, 5.875), .072, .017, 'Lead', horizontal=True)
    for x, y in ((1.207, .119), (1.226, .139)):
        tube(bay, (x, y, 5.866), (x, y, 5.09), .018, 'WarmPlaster')
    ring(bay, (1.213, .13, 5.039), .054, .013, 'Lead', horizontal=True)


def roof(bay):
    center = -.17
    roof_field = ((-HALF, EAVES), (HALF, EAVES), (center, RIDGE))
    bay.prism(roof_field, -.065, .328, WOOD)
    for i in range(16):
        bottom = EAVES + i * (RIDGE - EAVES) / 16
        top = EAVES + (i + .97) * (RIDGE - EAVES) / 16
        ratio0, ratio1 = (bottom - EAVES) / (RIDGE - EAVES), (top - EAVES) / (RIDGE - EAVES)
        inner_left = -HALF + (center + HALF) * ratio0
        inner_right = HALF + (center - HALF) * ratio0
        inset_left = -HALF + (center + HALF) * ratio1
        inset_right = HALF + (center - HALF) * ratio1
        bay.prism(((inner_left, bottom), (inner_right, bottom), (inset_right, top), (inset_left, top)),
                  .329, .382 + .013 * (i % 2), WOOD if i % 3 else 'Oak')
    bay.band(-HALF, HALF, EAVES - .07, EAVES + .075, .271, .553, 'Oak')
    for y in (-HALF, HALF):
        a, b = (y, EAVES), (center, RIDGE)
        crossbeam(bay, .305, .583, a, b, .148, 'Oak')
        crossbeam(bay, -.093, .65, (a[0], a[1] + .084), (b[0], b[1] + .084), .106, 'ClayTile')
    bay.band(-.77, .34, 6.782, 7.632, .38, .399, 'Interior')
    for z in (6.81, 7.00, 7.19, 7.38, 7.57):
        bay.band(-.754, .324, z, z + .084, .399, .45, 'Oak')
    for y in (-.767, .338):
        bay.band(y - .05, y + .05, 6.761, 7.662, .389, .487, 'Oak')
    bay.band(-.817, .396, 6.726, 6.779, .389, .515, 'Oak')
    bay.band(-.817, .396, 7.628, 7.691, .388, .485, 'Oak')
    crossbeam(bay, .39, .47, (center, 7.69), (center, RIDGE - .081), .133, 'Oak')


def move_elevation(destination, face, origin, normal):
    nx, ny = normal
    ox, oy = origin
    points = [(ox + x * nx - y * ny, oy + x * ny + y * nx, z) for x, y, z in face.vertices]
    start = len(destination.vertices)
    destination.vertices.extend(points)
    destination.polygons.extend(tuple(start + i for i in polygon) for polygon in face.polygons)
    destination.roles.extend(face.roles)


def side_wall(seed):
    wall = Bay()
    half = DEPTH / 2
    wall.band(-half, half, 0, 3.15, -.238, .013, STONE)
    wall.band(-half, half, 2.92, 3.173, -.015, .092, 'Oak')
    wall.band(-half, half, 3.15, EAVES, -.202, -.114, 'Interior')
    planks(wall, -half, half, 3.15, EAVES, -.111, WOOD, .187, seed)
    wall.band(-half, half, EAVES - .162, EAVES + .01, -.023, .097, 'Oak')
    for y in (-3.86, -1.93, 0, 1.92, 3.86):
        wall.band(y - .12, y + .12, 3.11, EAVES, -.065, .096, 'Oak')
    for index, (a, b) in enumerate(((-3.74, -2.07), (-1.81, -.12), (.12, 1.78), (2.06, 3.74))):
        if (index + seed) % 3 == 0:
            mid = (a + b) / 2
            for low, high in ((1.21, 1.69), (4.62, 5.48)):
                wall.band(mid - .294, mid + .294, low, high, .02 if low < 2 else -.024, .049, 'Interior')
                for y in (mid - .177, mid, mid + .177):
                    wall.band(y - .027, y + .027, low, high, .045, .089, 'Lead' if low < 2 else 'Oak')
                finish = TRIM if low < 2 else 'Oak'
                wall.band(mid - .35, mid + .35, low - .093, low, .03, .145, finish)
                wall.band(mid - .34, mid + .34, high, high + .084, .025, .109, finish)
        else:
            start, end = (a, 3.34), (b, 4.99)
            if index % 2:
                start, end = (b, 3.29), (a, 5.06)
            crossbeam(wall, -.12, .075, start, end, .164, WOOD)
    return wall


def rear_wall():
    wall = Bay()
    wall.band(-HALF, HALF, 0, 3.15, -.25, .011, STONE)
    wall.band(-HALF, HALF, 2.92, 3.16, -.01, .098, 'Oak')
    wall.band(-HALF, HALF, 3.15, EAVES, -.202, -.11, 'Interior')
    planks(wall, -HALF, HALF, 3.15, EAVES, -.107, WOOD, .161, 1701)
    wall.band(-HALF, HALF, EAVES - .161, EAVES + .003, -.025, .098, 'Oak')
    wall.prism(((-HALF, EAVES), (HALF, EAVES), (.17, RIDGE)), -.236, .035, WOOD)
    for side in (-1, 1):
        y = side * HALF
        crossbeam(wall, -.042, .144, (y, EAVES), (.17, RIDGE), .136, 'Oak')
        bay_side = side * 2.109
        wall.band(bay_side - .132, bay_side + .132, 3.15, EAVES, -.067, .13, 'Oak')
        crossbeam(wall, -.049, .119, (side * 1.01, 3.35), (side * 1.95, 5.08), .165, WOOD)
    left, right = .045, 1.176
    wall.band(left - .073, right + .065, .055, 2.43, .018, .05, 'Interior')
    planks(wall, left, right, .079, 2.27, .052, WOOD, .125, 971)
    for y in (left, right):
        wall.band(y - .09, y + .09, 0, 2.425, .045, .176, TRIM)
    wall.band(left - .09, right + .09, 2.31, 2.47, .036, .169, TRIM)
    wall.band(left - .126, right + .126, 0, .096, .023, .299, TRIM)
    for z in (.62, 1.69):
        wall.band(left + .045, right - .051, z, z + .065, .09, .14, 'Lead')
    ring(wall, (.153, .86, 1.02), .058, .013, 'Lead')
    wall.band(-1.04, -.62, 4.86, 5.68, -.03, .012, 'Interior')
    for z in (4.97, 5.14, 5.31, 5.48, 5.63):
        wall.band(-1.02, -.64, z, z + .068, .011, .075, 'Oak')
    return wall


def close_shell(bay):
    move_elevation(bay, side_wall(210), (-DEPTH / 2, -HALF), (0, -1))
    move_elevation(bay, side_wall(211), (-DEPTH / 2, HALF), (0, 1))
    move_elevation(bay, rear_wall(), (-DEPTH, 0), (-1, 0))
    bay.band(-HALF, HALF, 0, .11, -DEPTH, .019, STONE)
    # Back the decorative doors and planks with a closed wall. Wrap the front
    # corners so the loading face meets each side wall through the joinery.
    bay.band(-HALF + .105, HALF - .105, .08, EAVES, -.142, -.04, 'Interior')
    for side in (-1, 1):
        corner = side * (HALF - .092)
        bay.band(corner - .104, corner + .104, 0, 3.168, -.148, .227, STONE)
        bay.band(corner - .125, corner + .125, 3.053, EAVES + .025, -.158, .354, 'Oak')
    center = -.17
    # Timber deck and two closed pitched slopes, front to rear.
    bay.prism(((-HALF - .08, EAVES - .045), (HALF + .08, EAVES - .045), (center, RIDGE)),
              -DEPTH - .108, .353, 'Oak')
    for side in (-1, 1):
        eave = side * (HALF + .215)
        for i in range(15):
            t0, t1 = i / 15, min(1, (i + 1.09) / 15)
            y0, y1 = eave + (center - eave) * t0, eave + (center - eave) * t1
            z0, z1 = EAVES - .047 + (RIDGE - EAVES + .047) * t0, EAVES - .047 + (RIDGE - EAVES + .047) * t1
            contour = ((y0, z0 + .09), (y1, z1 + .09), (y1, z1 + .145), (y0, z0 + .137))
            bay.prism(contour, -DEPTH - .207 + .007 * (i % 2), .613 - .012 * (i % 3), 'ClayTile')
        y = side * HALF
        bay.band(y - .093, y + .093, EAVES - .159, EAVES + .037, -DEPTH - .146, .443, 'Oak')
    tube(bay, (-DEPTH - .205, center, RIDGE + .124), (.641, center, RIDGE + .124), .097, 'ClayTile', sides=10)


def texture(role):
    directory = ROOT.parent / ('Guildhall/Textures' if role == STONE else 'Textures')
    return directory / f'T_GLMedieval_{role}.png'


def make_material(role):
    mat = bpy.data.materials.new('M_GLMedieval_' + role)
    color, roughness, tile = PALETTE[role]
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Base Color'].default_value = (*color, 1)
    if tile:
        node = mat.node_tree.nodes.new('ShaderNodeTexImage')
        node.image = bpy.data.images.load(str(texture(role)), check_existing=True)
        mat.node_tree.links.new(node.outputs['Color'], shader.inputs['Base Color'])
    return mat


def make_object(bay):
    mesh = bpy.data.meshes.new(NAME)
    mesh.from_pydata([(x + DEPTH / 2, y, z) for x, y, z in bay.vertices], [], bay.polygons)
    mesh.update()
    roles = list(dict.fromkeys(bay.roles))
    indices = {role: index for index, role in enumerate(roles)}
    for role in roles:
        mesh.materials.append(make_material(role))
    for face, role in zip(mesh.polygons, bay.roles):
        face.material_index = indices[role]
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    uv = mesh.uv_layers.new(name='UV0')
    for polygon in mesh.polygons:
        tile = PALETTE[roles[polygon.material_index]][2] or 1
        axis = max(range(3), key=lambda i: abs(polygon.normal[i]))
        a, b = ((1, 2), (0, 2), (1, 0))[axis]
        for index in polygon.loop_indices:
            point = mesh.vertices[mesh.loops[index].vertex_index].co
            uv.data[index].uv = (point[a] / tile, point[b] / tile)
    mesh.calc_loop_triangles()
    obj = bpy.data.objects.new(NAME, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def render(output):
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, -.026))
    floor = bpy.context.object
    stone = bpy.data.materials.new('Preview ground')
    stone.diffuse_color = (.115, .092, .069, 1)
    floor.data.materials.append(stone)
    aim = Vector((0, 0, 4.55))
    for location, power, size in (((7, -7, 11), 3100, 9), ((7, 7, 8), 1750, 11), ((-8, 4, 11), 2600, 11)):
        bpy.ops.object.light_add(type='AREA', location=location)
        light = bpy.context.object
        light.data.energy = power
        light.data.size = size
        light.rotation_euler = (aim - light.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.ops.object.camera_add(location=(16, -13, 11.0))
    camera = bpy.context.object
    camera.rotation_euler = (aim - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 13.7
    scene = bpy.context.scene
    scene.camera = camera
    scene.world = bpy.data.worlds.new('Thames overcast')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .5
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 15
    scene.cycles.use_denoising = True
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 4
    scene.render.resolution_x = 850
    scene.render.resolution_y = 1100
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(output.resolve())
    bpy.ops.render.render(write_still=True)
    camera.location = (-15, 12, 9.9)
    camera.rotation_euler = (aim - camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = str(output.with_name('warehouse_rear_preview.png').resolve())
    bpy.ops.render.render(write_still=True)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'
    bay = Bay()
    storage_storey(bay)
    loading_storey(bay)
    roof(bay)
    close_shell(bay)
    obj = make_object(bay)
    fbx = ROOT / 'Source' / f'{NAME}.fbx'
    fbx.parent.mkdir(parents=True, exist_ok=True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, object_types={'MESH'},
                             axis_forward='-Z', axis_up='Y', mesh_smooth_type='FACE',
                             bake_anim=False, path_mode='COPY', embed_textures=True)
    spec = {'fbx': f'Source/{NAME}.fbx', 'triangles': len(obj.data.loop_triangles),
            'min_cm': [round(min(v[i] for v in obj.bound_box) * 100, 3) for i in range(3)],
            'max_cm': [round(max(v[i] for v in obj.bound_box) * 100, 3) for i in range(3)],
            'materials': [material.name for material in obj.data.materials]}
    info = {'schema': 1, 'width_cm': 450, 'depth_cm': 800,
            'pivot': 'center of nominal footprint at ground, +X street face, +Z up',
            'front_plane_cm': 400, 'meshes': {NAME: spec}, 'collision': False}
    (ROOT / 'warehouse_kit.json').write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
    if '--' in sys.argv:
        render(Path(sys.argv[sys.argv.index('--') + 1]))


if __name__ == '__main__':
    main()
