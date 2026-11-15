"""Generate closed late-medieval replacements for surveyed Mark Lane plots."""

from dataclasses import dataclass
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

ROOT = Path(__file__).resolve().parent
OPENING = ROOT.parent
sys.path.insert(0, str(OPENING))
sys.path.insert(0, str(OPENING / 'ThamesWarehouse'))
from build_medieval_facades import Bay, crossbeam, leaded, shutter
from build_thames_warehouse import PALETTE, make_material, move_elevation


@dataclass(frozen=True)
class BuildingStyle:
    name: str
    party_edge: int | None
    ground: str
    upper: str
    wood: str
    accent: str
    floors: tuple[float, ...]
    eaves: float
    gables: int


STYLES = {
    '3b4ea8e64fcb': BuildingStyle('Workshop', 4, 'WarmPlaster', 'WarmPlaster', 'WeatheredOak', 'ShopGreen',
                                 (0, 3.0, 5.4), 5.4, 1),
    'd87bb24c9cdb': BuildingStyle('MerchantsHouses', 1, 'GuildRubble', 'LimePlaster', 'Oak', 'ShopRed',
                                 (0, 3.16, 5.66, 8.1), 8.1, 2),
    'c3d845a67ca8': BuildingStyle('TradingCompound', None, 'GuildRubble', 'WarmPlaster', 'WeatheredOak', 'ShopRed',
                                 (0, 3.8, 6.15, 8.65), 8.65, 4),
}


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def ring_pairs(points):
    return zip(points, points[1:] + points[:1])


def local_frame(record):
    ox, oy = record['origin_m'][:2]
    footprint = [(x - ox, y - oy) for x, y in record['footprint']]
    edge = record['entry']['edge']
    (ax, ay), (bx, by) = footprint[edge], footprint[(edge + 1) % len(footprint)]
    length = math.hypot(bx - ax, by - ay)
    y = ((bx - ax) / length, (by - ay) / length)
    x = (y[1], -y[0])
    assert sum(a * b for a, b in zip(x, record['entry']['outward'])) > .9999
    points = [(p * x[0] + q * x[1], p * y[0] + q * y[1]) for p, q in footprint]
    return points, x, y


def inset(points, distance):
    """Inset visible walls for joinery and an eave."""
    lines = []
    for a, b in ring_pairs(points):
        direction = (Vector(b) - Vector(a)).normalized()
        normal = Vector((-direction.y, direction.x))
        lines.append((Vector(a) + normal * distance, direction))
    result = []
    for index, (a, u) in enumerate(lines):
        b, v = lines[index - 1]
        denominator = cross(u, v)
        point = a if abs(denominator) < .0001 else a + u * (cross(b - a, v) / denominator)
        result.append(tuple(point))
    return result


def roof_profile(points, planned_roof, style):
    low, high = min(y for _, y in points), max(y for _, y in points)
    result = [(low, planned_roof[0][1]), *(tuple(p) for p in planned_roof[1:-1]), (high, planned_roof[-1][1])]
    if style.gables == 4:
        # Stagger the range ridges so the long block reads as separate roof spans.
        for index, offset in enumerate((-.88, .64, -.48, .17)):
            y, z = result[index * 2 + 1]
            result[index * 2 + 1] = y, z + offset
    return result


def roof_z(y, profile):
    for (low, start), (high, end) in zip(profile, profile[1:]):
        if y <= high + 1e-6:
            return start + (end - start) * min(1, max(0, (y - low) / (high - low)))
    return profile[-1][1]


def clip_y(polygon, cutoff, keep_above):
    if not polygon:
        return []
    output = []
    for a, b in ring_pairs(polygon):
        keep_a = a[1] >= cutoff if keep_above else a[1] <= cutoff
        keep_b = b[1] >= cutoff if keep_above else b[1] <= cutoff
        if keep_a:
            output.append(a)
        if keep_a != keep_b:
            fraction = (cutoff - a[1]) / (b[1] - a[1])
            output.append((a[0] + (b[0] - a[0]) * fraction, cutoff))
    return output


class Surface:
    def __init__(self, bay):
        self.bay = bay
        self.indices = {}

    def face(self, coordinates, material):
        indices = []
        for point in coordinates:
            point = tuple(round(axis, 5) for axis in point)
            if point not in self.indices:
                self.indices[point] = len(self.bay.vertices)
                self.bay.vertices.append(point)
            index = self.indices[point]
            if index not in indices:
                indices.append(index)
        if len(indices) > 2:
            self.bay.polygons.append(indices)
            self.bay.roles.append(material)


def roof_triangles(plot):
    return [[plot[vertex] if isinstance(vertex, int) else (vertex.x, vertex.y) for vertex in triangle]
            for triangle in tessellate_polygon([[Vector(point) for point in plot]])]


def roof_perimeter(plot, profile):
    for a, b in ring_pairs(plot):
        splits = [a]
        if abs(b[1] - a[1]) > 1e-6:
            for y, _ in sorted(profile, reverse=(b[1] < a[1])):
                t = (y - a[1]) / (b[1] - a[1])
                if 1e-5 < t < 1 - 1e-5:
                    splits.append((a[0] + (b[0] - a[0]) * t, y))
        yield splits + [b]


def roof_skin(surface, outline, profile, material, height=0, reverse=False):
    for triangle in roof_triangles(outline):
        for (low, _), (high, _) in zip(profile, profile[1:]):
            polygon = clip_y(clip_y(triangle, low, True), high, False)
            if len(polygon) > 2 and abs(sum(cross(a, b) for a, b in ring_pairs(polygon))) > 1e-7:
                points = [(*point, roof_z(point[1], profile) + height) for point in polygon]
                surface.face(list(reversed(points)) if reverse else points, material)


def shell(bay, plot, walls, gables, profile, style):
    volume = Surface(bay)
    volume.face([(x, y, 0) for x, y in reversed(plot)], 'Fieldstone')
    perimeter = list(roof_perimeter(gables, profile))
    for index, (outer, inner) in enumerate(zip(ring_pairs(plot), ring_pairs(walls))):
        (a, b), (ia, ib) = outer, inner
        volume.face([(*a, 0), (*b, 0), (*b, .40), (*a, .40)], 'Fieldstone')
        volume.face([(*a, .40), (*b, .40), (*ib, .40), (*ia, .40)], 'Fieldstone')
        ground, upper = style.ground, style.upper
        if index == style.party_edge:
            ground = upper = 'GuildRubble'
        for low, high, material in ((.40, style.floors[1], ground), (style.floors[1], style.eaves, upper)):
            volume.face([(*ia, low), (*ib, low), (*ib, high), (*ia, high)], material)
        soffit = [(*p, style.eaves) for p in reversed(perimeter[index])]
        volume.face([(*ia, style.eaves), (*ib, style.eaves), *soffit], style.wood)
    for index, segments in enumerate(perimeter):
        for a, b in zip(segments, segments[1:]):
            vu, vd = roof_z(a[1], profile), roof_z(b[1], profile)
            material = 'GuildRubble' if index == style.party_edge else style.upper
            volume.face([(*a, style.eaves), (*b, style.eaves), (*b, vd), (*a, vu)], material)
    roof_skin(volume, gables, profile, style.wood)


def tiled_roof(bay, plot, profile):
    roof = Surface(bay)
    thickness = .089
    for segments in roof_perimeter(plot, profile):
        for a, b in zip(segments, segments[1:]):
            za, zb = roof_z(a[1], profile), roof_z(b[1], profile)
            roof.face([(*a, za), (*b, zb), (*b, zb + thickness), (*a, za + thickness)], 'ClayTile')
    roof_skin(roof, plot, profile, 'ClayTile', thickness)
    roof_skin(roof, plot, profile, 'Oak', reverse=True)


def dress_gables(bay, gables, profile, style):
    for index, points in enumerate(roof_perimeter(gables, profile)):
        if index == style.party_edge or math.dist(points[0], points[-1]) < 2.2:
            continue
        origin = Vector(points[0])
        direction = (Vector(points[-1]) - origin).normalized()
        coordinates = [(math.dist(points[0], point), roof_z(point[1], profile)) for point in points]
        detail = Bay()
        for (left, low), (right, high) in zip(coordinates, coordinates[1:]):
            if right - left >= 1.0 and abs(high - low) > .25:
                t = min(.19, .29 / (right - left))
                low_trim = max(style.eaves + .08, low + (high - low) * t - .125)
                high_trim = max(style.eaves + .08, high + (low - high) * t - .125)
                crossbeam(detail, -.014, .085, (left + .24, low_trim), (right - .24, high_trim), .155, style.wood)
        for (left, low), (center, peak), (right, high) in zip(coordinates, coordinates[1:], coordinates[2:]):
            if peak - max(low, high) < .9 or min(center - left, right - center) < 1.05:
                continue
            mid = max(style.eaves + .89, peak - 1.63)
            detail.band(center - .43, center + .43, mid - .37, mid + .35, .012, .029, 'Interior')
            for y in (center - .43, center + .43):
                detail.band(y - .051, y + .051, mid - .41, mid + .39, .011, .079, style.wood)
            for z in (mid - .39, mid - .15, mid + .09, mid + .34):
                detail.band(center - .44, center + .44, z, z + .061, .031, .083, style.wood)
            crossbeam(detail, -.023, .077, (center, mid + .40), (center, peak - .19), .14, style.wood)
        move_elevation(bay, detail, origin, (direction.y, -direction.x))


def party_wall(bay, plot, walls, style):
    edge = style.party_edge
    if edge is None:
        return
    after = (edge + 1) % len(plot)
    points = (plot[edge], plot[after], walls[after], walls[edge])
    wall = Surface(bay)
    bottom, top = .375, style.eaves - .012
    for a, b in ring_pairs(points):
        wall.face([(*a, bottom), (*b, bottom), (*b, top), (*a, top)], 'GuildRubble')
    wall.face([(*point, bottom) for point in reversed(points)], 'GuildRubble')
    wall.face([(*point, top) for point in points], 'GuildRubble')


def doorway(bay, middle, stone, finish, span=.76, spring=2.08, rise=.35):
    left, right = middle - span, middle + span
    surround = 'GuildDressed' if stone else 'Oak'
    for center in (left - .06, right + .06):
        bay.band(center - .108, center + .108, .04, spring + .01, -.047, .24, surround)
    for index in range(13):
        a, b = (index + .018) * math.pi / 13, (index + .982) * math.pi / 13
        arch = [(middle + radius * math.cos(t), spring + lifting * math.sin(t))
                for t, radius, lifting in ((a, span, rise), (a, span + .18, rise + .14),
                                          (b, span + .18, rise + .14), (b, span, rise))]
        bay.prism(arch, -.022, .23, surround)
    boards = int(2 * span / .14) + 1
    for index in range(boards):
        a = left + (right - left) * index / boards
        b = left + (right - left) * (index + 1) / boards
        top = lambda y: spring + rise * math.sqrt(max(0, 1 - ((y - middle) / span) ** 2))
        bay.prism(((a + .008, .06), (b - .008, .06), (b - .008, top(b)), (a + .008, top(a))),
                  .018, .071, finish)
    for z in (.48, 1.34):
        bay.band(left, right, z, z + .056, .069, .113, 'Lead')
    bay.band(middle + .135, middle + .20, 1.00, 1.14, .111, .144, 'Lead')
    bay.band(left - .158, right + .158, 0, .095, .025, .244, 'Fieldstone')


def elevation(a, b, index, entry, fraction, style, grounded_left, grounded_right):
    bay = Bay()
    if index == style.party_edge:
        return bay
    length = math.dist(a, b)
    left, right = -length / 2 + .30, length / 2 - .30
    if right - left < .68:
        return bay
    front = index == entry
    for height in style.floors[1:]:
        bay.band(left, right, height - .143, height + .02, -.03, .205 if front else .112, style.wood)
    panels = max(1, math.ceil((right - left) / (2.63 if front else 3.08)))
    line = [left + (right - left) * i / panels for i in range(panels + 1)]
    for column, y in enumerate(line):
        bay.band(y - .074, y + .074, style.floors[1], style.eaves - .10, -.019, .164, style.wood)
        if front and style.gables > 1 and column % 2 == 0:
            bay.band(y - .075, y + .075, style.floors[1] - .31, style.floors[1] + .03, .055, .238, style.wood)
    for panel, (first, last) in enumerate(zip(line, line[1:])):
        middle = (first + last) / 2
        for level, (low, high) in enumerate(zip(style.floors[1:], style.floors[2:])):
            width = min((last - first) * .56, 1.28)
            if width > .43 and (front or (panel + level * 2 + index) % 3 == 0):
                if style.gables == 1:
                    bay.band(middle - width / 2, middle + width / 2, low + .58, low + 1.57, .017, .044, 'Interior')
                    for i in (-1, 0, 1):
                        y = middle + width * i * .25
                        bay.band(y - .021, y + .021, low + .59, low + 1.57, .036, .077, 'Oak')
                    shutter(bay, middle + width / 2, middle + width * .86, low + .57, low + 1.58, .075, style.accent)
                    for z in (low + .54, low + 1.55):
                        bay.band(middle - width * .57, middle + width * .57, z, z + .056, .037, .147, style.wood)
                else:
                    leaded(bay, middle - width / 2, middle + width / 2, low + .66, low + 1.76, .027, False)
            elif last - first > .73:
                begin, end = (first + .12, last - .12) if (panel + index) % 2 else (last - .12, first + .12)
                crossbeam(bay, -.023, .108, (begin, low + .09), (end, high - .16), .132, style.wood)
    if front:
        center = grounded_left + (grounded_right - grounded_left) * fraction
        gate = style.gables == 4
        span = 1.48 if gate else .76
        doorway(bay, center, style.gables > 1, style.wood, span=span,
                spring=2.57 if gate else 2.08, rise=.62 if gate else .35)
        for sign in (-1, 1):
            near = center + sign * (span + .81)
            while left + .96 < near < right - .96:
                win_l, win_r = near - .69, near + .69
                bay.band(win_l, win_r, .96, 2.16, .027, .062, 'Interior')
                for i in range(4):
                    y = win_l + (win_r - win_l) * i / 3
                    bay.band(y - .046, y + .046, .97, 2.20, .048, .141, style.wood)
                for z in (.91, 2.17):
                    bay.band(win_l - .09, win_r + .09, z, z + .09, .049, .219, style.wood)
                shutter(bay, win_l, win_r, .49, .89, .064, style.accent)
                near += sign * 2.45
        sign_height = 3.47 if gate else 2.72
        bay.band(center - .39, center + .39, sign_height, sign_height + .19, .047, .153, style.accent)
    elif right - left > 3.0:
        for center in (-length * .232, length * .232):
            bay.band(center - .23, center + .23, 1.31, 1.82, .018, .084, 'Interior')
            for y in (center - .14, center, center + .14):
                bay.band(y - .018, y + .018, 1.3, 1.83, .078, .104, 'Lead')
            bay.band(center - .30, center + .30, 1.26, 1.32, .045, .158, 'Fieldstone')
    return bay


def contains(point, plot, tolerance=.00025):
    x, y = point
    inside = False
    for (ax, ay), (bx, by) in ring_pairs(plot):
        dx, dy = bx - ax, by - ay
        fraction = ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)
        if -1e-5 <= fraction <= 1 + 1e-5 and abs(cross((x - ax, y - ay), (dx, dy))) <= tolerance * math.hypot(dx, dy):
            return True
        if (ay > y) != (by > y) and x < ax + (bx - ax) * (y - ay) / (by - ay):
            inside = not inside
    return inside


def verify_envelope(bay, plot, ceiling):
    for x, y, z in bay.vertices:
        if z < -.00001 or z > ceiling + 1e-5 or not contains((x, y), plot):
            raise ValueError(f'Vertex {(x, y, z)} lies outside the surveyed envelope')


def build(record, style, planned_roof):
    plot, x, y = local_frame(record)
    walls = inset(plot, .315)
    gables = inset(plot, .14)
    entry = record['entry']['edge']
    profile = roof_profile(plot, planned_roof, style)
    bay = Bay()
    shell(bay, plot, walls, gables, profile, style)
    tiled_roof(bay, plot, profile)
    dress_gables(bay, gables, profile, style)
    party_wall(bay, plot, walls, style)
    for index, (a, b) in enumerate(ring_pairs(walls)):
        center = (Vector(a) + Vector(b)) / 2
        direction = (Vector(b) - Vector(a)).normalized()
        normal = (direction.y, -direction.x)
        left = (Vector(plot[index]) - center).dot(direction)
        right = (Vector(plot[(index + 1) % len(plot)]) - center).dot(direction)
        decor = elevation(a, b, index, entry, record['entry']['fraction'], style, left, right)
        move_elevation(bay, decor, center, normal)
    verify_envelope(bay, plot, record['source_roof_m'] - record['base_m'])
    return bay, plot, x, y


def make_object(bay, name):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(bay.vertices, [], bay.polygons)
    mesh.update()
    roles = list(dict.fromkeys(bay.roles))
    slots = {name: index for index, name in enumerate(roles)}
    for role in roles:
        material = bpy.data.materials.get('M_GLMedieval_' + role) or make_material(role)
        mesh.materials.append(material)
    for face, role in zip(mesh.polygons, bay.roles):
        face.material_index = slots[role]
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    uv = mesh.uv_layers.new(name='UV0')
    for face in mesh.polygons:
        tile = PALETTE[roles[face.material_index]][2] or 1
        axis = max(range(3), key=lambda index: abs(face.normal[index]))
        a, b = ((1, 2), (0, 2), (0, 1))[axis]
        for index in face.loop_indices:
            vertex = mesh.vertices[mesh.loops[index].vertex_index].co
            uv.data[index].uv = (vertex[a] / tile, vertex[b] / tile)
    mesh.calc_loop_triangles()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def preview(output, objects, view=(1.32, -.86, .72)):
    scene = bpy.context.scene
    lights = []
    bpy.context.view_layer.update()
    corners = [obj.matrix_world @ Vector(point) for obj in objects for point in obj.bound_box]
    low = Vector(tuple(min(point[i] for point in corners) for i in range(3)))
    high = Vector(tuple(max(point[i] for point in corners) for i in range(3)))
    size = max(high.x - low.x, high.y - low.y)
    center = (low + high) / 2
    aim = Vector((center.x, center.y, center.z * .84))
    bpy.ops.mesh.primitive_plane_add(size=size * 8, location=(center.x, center.y, low.z - .02))
    floor = bpy.context.object
    ground = bpy.data.materials.new('Medieval masonry preview ground')
    ground.diffuse_color = (.115, .106, .09, 1)
    floor.data.materials.append(ground)
    for vector, strength, width in (((.89, -.52, 1.1), 27, .60), ((.5, 1.1, .61), 13, .76), ((-.81, .1, .85), 22, .64)):
        bpy.ops.object.light_add(type='AREA', location=aim + Vector(vector) * size)
        light = bpy.context.object
        lights.append(light)
        light.data.energy = size * size * strength
        light.data.size = size * width
        light.rotation_euler = (aim - light.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.ops.object.camera_add(location=aim + Vector(view) * size)
    camera = bpy.context.object
    camera.rotation_euler = (aim - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = max(size * 1.39, high.z * 1.42)
    scene.camera = camera
    scene.world = scene.world or bpy.data.worlds.new('Soft overcast')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .5
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 17
    scene.cycles.use_denoising = True
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 4
    scene.render.resolution_x = 1000
    scene.render.resolution_y = 850
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(output.resolve())
    bpy.ops.render.render(write_still=True)
    for item in [floor, camera, *lights]:
        bpy.data.objects.remove(item, do_unlink=True)


def main():
    arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    source = OPENING / 'west_mark_lane_whole_buildings_candidate.json'
    plan_source = OPENING / 'west_mark_lane_whole_building_plan.json'
    records = json.loads(source.read_text(encoding='utf-8'))['buildings']
    plans = {p['id']: p for p in json.loads(plan_source.read_text(encoding='utf-8'))['buildings']}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'
    output = ROOT / 'Source'
    output.mkdir(exist_ok=True)
    manifest = {'schema': 1, 'sources': [f'../{source.name}', f'../{plan_source.name}'], 'coordinate_system': 'Unreal world meters',
                'pivot': 'Source shell origin on ground. Mesh +X faces the street. +Z is up.', 'buildings': {}}
    rendered = []
    for record in records:
        shell_id = record['id']
        style = STYLES.get(shell_id.rsplit('_', 1)[-1])
        if not style:
            continue
        name = 'SM_GLMedieval_MarkLane' + style.name
        bay, plot, x, y = build(record, style, plans[shell_id]['roof_profile_local_y_z_m'])
        obj = make_object(bay, name)
        export = output / f'{name}.fbx'
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.export_scene.fbx(filepath=str(export), use_selection=True, object_types={'MESH'},
                                 axis_forward='-Z', axis_up='Y', mesh_smooth_type='FACE',
                                 bake_anim=False, path_mode='COPY', embed_textures=True)
        manifest['buildings'][shell_id] = {
            'fbx': f'Source/{name}.fbx', 'world_pivot_m': record['origin_m'],
            'axis_x_world_xy': x, 'axis_y_world_xy': y,
            'yaw_deg': math.degrees(math.atan2(x[1], x[0])),
            'footprint_local_m': [[round(c, 5) for c in p] for p in plot],
            'source_height_cm': round((record['source_roof_m'] - record['base_m']) * 100, 3),
            'entry_edge': record['entry']['edge'], 'entry_fraction': record['entry']['fraction'],
            'party_wall_edge': style.party_edge,
            'bounds_cm': [[round(fn(vertex[i] for vertex in obj.bound_box) * 100, 3) for i in range(3)]
                          for fn in (min, max)],
            'triangles': len(obj.data.loop_triangles),
            'materials': [material.name for material in obj.data.materials],
            'collision': False,
        }
        if '--preview' in arguments:
            preview(ROOT / f'{style.name}_preview.png', [obj])
            obj.hide_render = True
            rendered.append((obj, manifest['buildings'][shell_id]))
        else:
            bpy.data.objects.remove(obj, do_unlink=True)
    (ROOT / 'whole_buildings_kit.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    if rendered:
        anchor = Vector(rendered[0][1]['world_pivot_m'])
        for obj, spec in rendered:
            obj.location = Vector(spec['world_pivot_m']) - anchor
            obj.rotation_euler[2] = math.radians(spec['yaw_deg'])
            obj.hide_render = False
        objects = [obj for obj, _ in rendered]
        preview(ROOT / 'MarkLane_preview.png', objects, (.52, 1.18, 1.08))
        preview(ROOT / 'MarkLane_workshop_approach_preview.png', objects, (-.82, -1.18, 1.22))


if __name__ == '__main__':
    main()
