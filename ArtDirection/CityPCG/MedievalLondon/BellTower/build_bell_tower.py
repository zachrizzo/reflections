"""Build the Medieval London bell tower as four FBX meshes (run in headless Blender).

blender --background --factory-startup --python build_bell_tower.py

Everything is generated here from boxes, extruded profiles and one lathe (the
bell); no third-party geometry. Units are metres in Blender and centimetres in
Unreal. Blender +X maps to Unreal +X and Blender +Y to Unreal -Y, so the door
on the -X face looks west in Unreal.

Meshes (pivot at the tower's base centre unless noted):
  SM_BellTower_Shell   walls, plinth, buttresses, courses, belfry floor, frame, roof
  SM_BellTower_Stairs  9 flights (13 risers of 20 cm, 30 cm treads, 1.3 m wide) + landings
  SM_BellTower_Rails   stone rail on the well side of every flight + belfry hatch rail
  SM_BellTower_Bell    bronze bell and clapper; pivot at the hanging point (top)
Material slot names are the medieval kit roles, so Unreal assigns
/Game/GrayLondon/MedievalOpening/Kit/M_GLMedieval_<role> (Bronze: M_GLPCG_Bronze).
"""

import json
import math
from pathlib import Path

import bmesh
import bpy

OUT = Path(__file__).resolve().parent
# Box-projection UV size per role in metres, as in the Guildhall/facade kit.
UV_SCALE = {'GuildAshlar': 1.67, 'GuildDressed': 1.0, 'GuildRubble': 1.75, 'Fieldstone': 1.35,
            'ClayTile': 1.0, 'Oak': .8, 'WeatheredOak': .8, 'Lead': 1.0, 'Bronze': 1.0}
COLOR = {'GuildAshlar': (.39, .32, .23), 'GuildDressed': (.36, .31, .22), 'GuildRubble': (.25, .21, .15),
         'Fieldstone': (.25, .23, .176), 'ClayTile': (.23, .104, .07), 'Oak': (.088, .048, .024),
         'WeatheredOak': (.145, .073, .037), 'Lead': (.052, .054, .041), 'Bronze': (.45, .3, .12)}

# --- Dimensions (metres) -------------------------------------------------------
E = 4.0                 # outer half width of the walls
T = 0.9                 # wall thickness
A = E - T               # inner half width: 6.2 m clear inside
W = 1.3                 # stair width
G = 0.30                # tread going
R = 0.20                # riser
TREADS = 12             # treads per flight (13 risers incl. the step onto the landing)
FLIGHT_RISE = (TREADS + 1) * R   # 2.6 m
FLIGHTS = 9
Z0 = 0.2                # ground floor = plinth top
SOFFIT = 0.45           # stair slab depth below the nosing line
BELFRY = Z0 + FLIGHTS * FLIGHT_RISE   # 23.6 m
SILL = BELFRY + 1.1     # parapet top in the belfry openings
WALL_TOP = 30.6
CORNICE = (30.2, 30.6)
APEX = 37.4
assert abs(2 * A - 2 * W - TREADS * G) < 1e-6, 'flights must fill the wall between landings'


class Part:
    def __init__(self, name):
        self.name, self.verts, self.faces, self.roles = name, [], [], []

    def solid(self, rings, role):
        """Add a closed prism from two matching rings of 3D points (bottom, top)."""
        bottom, top = rings
        n = len(bottom)
        base = len(self.verts)
        self.verts += [tuple(p) for p in bottom] + [tuple(p) for p in top]
        self.faces.append(list(range(base, base + n)))
        self.faces.append(list(range(base + n, base + 2 * n)))
        self.faces += [[base + i, base + (i + 1) % n, base + n + (i + 1) % n, base + n + i] for i in range(n)]
        self.roles += [role] * (n + 2)

    def box(self, x0, x1, y0, y1, z0, z1, role):
        if x1 - x0 < 1e-4 or y1 - y0 < 1e-4 or z1 - z0 < 1e-4:
            return
        ring = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        self.solid(([(x, y, z0) for x, y in ring], [(x, y, z1) for x, y in ring]), role)

    def prism(self, poly, to_world, d0, d1, role):
        """Extrude a 2D polygon poly[(u, v)] between depths d0 and d1."""
        self.solid(([to_world(u, v, d0) for u, v in poly], [to_world(u, v, d1) for u, v in poly]), role)

    def build(self, pivot=(0, 0, 0), smooth=()):
        mesh = bpy.data.meshes.new(self.name)
        px, py, pz = pivot
        mesh.from_pydata([(x - px, y - py, z - pz) for x, y, z in self.verts], [], self.faces)
        roles = sorted(set(self.roles), key=list(UV_SCALE).index)
        for role in roles:
            mesh.materials.append(material(role))
        for poly, role in zip(mesh.polygons, self.roles):
            poly.material_index = roles.index(role)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bmesh.ops.triangulate(bm, faces=list(bm.faces), quad_method='BEAUTY', ngon_method='BEAUTY')
        bm.to_mesh(mesh)
        bm.free()
        uv = mesh.uv_layers.new(name='UV0')
        for poly in mesh.polygons:
            scale = UV_SCALE[roles[poly.material_index]]
            axis = max(range(3), key=lambda i: abs(poly.normal[i]))
            a, b = ((1, 2), (0, 2), (1, 0))[axis]
            for li in poly.loop_indices:
                co = mesh.vertices[mesh.loops[li].vertex_index].co
                uv.data[li].uv = ((co[a] + pivot[a]) / scale, (co[b] + pivot[b]) / scale)
            poly.use_smooth = roles[poly.material_index] in smooth
        mesh.validate()
        mesh.update()
        obj = bpy.data.objects.new(self.name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        return obj


def material(role):
    mat = bpy.data.materials.get(role) or bpy.data.materials.new(role)
    mat.diffuse_color = (*COLOR[role], 1)
    return mat


# --- Walls ----------------------------------------------------------------------
# Each side: (u range, function (u, z, d) -> world, depth range). North/south walls
# run the full 8 m; east/west sit between them so no outer faces overlap.
SIDES = {
    'S': ((-E, E), lambda u, z, d: (u, -d, z), (A, E)),
    'N': ((-E, E), lambda u, z, d: (u, d, z), (A, E)),
    'E': ((-A, A), lambda u, z, d: (d, u, z), (A, E)),
    'W': ((-A, A), lambda u, z, d: (-d, u, z), (A, E)),
}
FACE_OF_FLIGHT = 'SENW'


def openings():
    """Rectangular holes (u0, u1, z0, z1) and arches (u_centre, half, spring) per side."""
    holes = {side: [] for side in SIDES}
    arches = {side: [] for side in SIDES}
    # Door: 1.6 m wide, 2.6 m clear to the springing, round arch to 3.4 m above the floor.
    holes['W'].append((-.8, .8, -1, Z0 + 2.6))
    arches['W'].append((0, .8, Z0 + 2.6))
    # Arrow slits at eye level beside each flight below the belfry.
    for k in range(FLIGHTS - 1):
        level = Z0 + k * FLIGHT_RISE
        holes[FACE_OF_FLIGHT[k % 4]].append((-.16, .16, level + 2.15, level + 3.45))
    # Belfry: one great round-arched opening per face above a 1.1 m parapet.
    for side in SIDES:
        holes[side].append((-1.8, 1.8, SILL, BELFRY + 3.8))
        arches[side].append((0, 1.8, BELFRY + 3.8))
    return holes, arches


def wall_side(shell, side, holes, arches):
    (u_min, u_max), to_world, (d0, d1) = SIDES[side]
    rects = list(holes) + [(c - h, c + h, s, s + h) for c, h, s in arches]
    cuts = sorted({-0.3, WALL_TOP, *[z for r in rects for z in r[2:]]})
    cuts = [z for z in cuts if -0.3 <= z <= WALL_TOP]
    for za, zb in zip(cuts, cuts[1:]):
        blocked = sorted((max(u_min, r[0]), min(u_max, r[1])) for r in rects if r[2] < zb - 1e-6 and r[3] > za + 1e-6)
        u = u_min
        for b0, b1 in blocked + [(u_max, u_max)]:
            if b0 > u + 1e-6:
                shell.prism([(u, za), (b0, za), (b0, zb), (u, zb)], to_world, d0, d1, 'GuildAshlar')
            u = max(u, b1)
    for c, h, s in arches:
        steps = 14
        left = [(c - h, s), (c - h, s + h), (c, s + h)] + [
            (c + h * math.cos(t), s + h * math.sin(t))
            for t in (math.pi / 2 + (math.pi / 2) * i / steps for i in range(1, steps))]
        right = [(c + h, s)] + [
            (c + h * math.cos(t), s + h * math.sin(t)) for t in ((math.pi / 2) * i / steps for i in range(1, steps))
        ] + [(c, s + h), (c + h, s + h)]
        shell.prism(left, to_world, d0, d1, 'GuildAshlar')
        shell.prism(right, to_world, d0, d1, 'GuildAshlar')
        # Dressed voussoir ring standing 6 cm proud of the outer face.
        ring = .3
        for i in range(12):
            t0, t1 = math.pi * i / 12, math.pi * (i + 1) / 12
            quad = [(c + h * math.cos(t0), s + h * math.sin(t0)), (c + (h + ring) * math.cos(t0), s + (h + ring) * math.sin(t0)),
                    (c + (h + ring) * math.cos(t1), s + (h + ring) * math.sin(t1)), (c + h * math.cos(t1), s + h * math.sin(t1))]
            shell.prism(quad, to_world, d1 - .02, d1 + .06, 'GuildDressed')


def ring(part, z0, z1, outer, inner, role):
    part.box(-outer, outer, inner, outer, z0, z1, role)
    part.box(-outer, outer, -outer, -inner, z0, z1, role)
    part.box(inner, outer, -inner, inner, z0, z1, role)
    part.box(-outer, -inner, -inner, inner, z0, z1, role)


def build_shell():
    shell = Part('SM_BellTower_Shell')
    holes, arches = openings()
    for side in SIDES:
        wall_side(shell, side, holes[side], arches[side])
    shell.box(-4.5, 4.5, -4.5, 4.5, -0.6, Z0, 'Fieldstone')          # plinth and ground floor
    for sx in (-1, 1):                                               # clasping corner buttresses
        for sy in (-1, 1):
            for z0, z1, reach in ((-0.3, 12.0, 4.35), (12.0, 22.0, 4.22), (22.0, BELFRY + .1, 4.12)):
                xs, ys = sorted((sx * 3.2, sx * reach)), sorted((sy * 3.2, sy * reach))
                shell.box(*xs, *ys, z0, z1, 'GuildAshlar')
    for z in (7.0, 15.0):
        ring(shell, z, z + .22, 4.12, 3.9, 'GuildDressed')
    ring(shell, BELFRY - .2, BELFRY + .1, 4.2, 3.9, 'GuildDressed')
    ring(shell, *CORNICE, 4.45, 3.5, 'GuildDressed')
    for i in range(10):                                              # corbel table under the cornice
        u = -3.6 + .8 * i
        for to_world in (lambda a, b, z: (a, b, z), lambda a, b, z: (a, -b, z),
                         lambda a, b, z: (b, a, z), lambda a, b, z: (-b, a, z)):
            lo, hi = to_world(u - .11, 3.95, CORNICE[0] - .38), to_world(u + .11, 4.3, CORNICE[0])
            shell.box(min(lo[0], hi[0]), max(lo[0], hi[0]), min(lo[1], hi[1]), max(lo[1], hi[1]),
                      lo[2], hi[2], 'GuildDressed')
    # Belfry floor: everything but the hatch over the last flight and the SW corner.
    # (1 cm back from the hatch edge so it never shares a plane with the stone rail.)
    shell.box(-A, A, -(A - W) + .01, A, BELFRY - SOFFIT, BELFRY, 'WeatheredOak')
    shell.box(A - W, A, -A, -(A - W), BELFRY - SOFFIT, BELFRY, 'WeatheredOak')
    # Oak bell frame: two posts on sill beams and a headstock beam.
    for x in (-2.5, 2.5):
        shell.box(x - .17, x + .17, -.8, .8, BELFRY, BELFRY + .2, 'Oak')
        shell.box(x - .17, x + .17, -.17, .17, BELFRY + .2, 28.36, 'Oak')
        for dy in (-1, 1):                                           # raking braces
            shell.solid(([(x - .1, dy * .7, BELFRY + .2), (x + .1, dy * .7, BELFRY + .2), (x + .1, dy * .55, BELFRY + .2), (x - .1, dy * .55, BELFRY + .2)],
                         [(x - .1, dy * .17, 26.2), (x + .1, dy * .17, 26.2), (x + .1, dy * .02, 26.4), (x - .1, dy * .02, 26.4)]), 'Oak')
    shell.box(-2.75, 2.75, -.18, .18, 28.0, 28.36, 'Oak')
    # Pyramid roof on the cornice; its base is the oak-boarded belfry ceiling.
    base = [(-4.5, -4.5), (4.5, -4.5), (4.5, 4.5), (-4.5, 4.5)]
    start = len(shell.verts)
    shell.verts += [(x, y, CORNICE[1]) for x, y in base] + [(0, 0, APEX)]
    shell.faces.append([start + 3, start + 2, start + 1, start])
    shell.roles.append('WeatheredOak')
    for i in range(4):
        shell.faces.append([start + i, start + (i + 1) % 4, start + 4])
        shell.roles.append('ClayTile')
    shell.box(-.07, .07, -.07, .07, APEX - .4, APEX + 1.2, 'Lead')   # finial
    shell.box(-.45, .45, -.03, .03, APEX + .7, APEX + .82, 'Lead')
    return shell


# --- Stairs and rails -------------------------------------------------------------
# Per face of the flight: start point at the wall, direction up the flight, and the
# direction from the wall into the well. world = p + s*a + w*n.
FLIGHT_FRAME = {
    'S': ((-(A - W), -A), (1, 0), (0, 1)),
    'E': ((A, -(A - W)), (0, 1), (-1, 0)),
    'N': ((A - W, A), (-1, 0), (0, -1)),
    'W': ((-A, A - W), (0, -1), (1, 0)),
}
CORNER_AFTER = {'S': ((A - W, A), (-A, -(A - W))), 'E': ((A - W, A), (A - W, A)),
                'N': ((-A, -(A - W)), (A - W, A)), 'W': ((-A, -(A - W)), (-A, -(A - W)))}
INNER_CORNER = {'S': (A - W, -(A - W)), 'E': (A - W, A - W), 'N': (-(A - W), A - W), 'W': (-(A - W), -(A - W))}
RAIL = .12
RAIL_HEIGHT = 1.15      # above the nosing line: 0.93-1.15 m above each tread


def frame_world(face):
    (px, py), (ax, ay), (nx, ny) = FLIGHT_FRAME[face]
    return lambda s, z, w: (px + s * ax + w * nx, py + s * ay + w * ny, z)


def build_stairs():
    stairs, rails = Part('SM_BellTower_Stairs'), Part('SM_BellTower_Rails')
    run = TREADS * G
    for k in range(FLIGHTS):
        face = FACE_OF_FLIGHT[k % 4]
        level = Z0 + k * FLIGHT_RISE
        top = level + FLIGHT_RISE
        to_world = frame_world(face)
        bottom0, bottom1 = (Z0, Z0) if k == 0 else (level - SOFFIT, top - SOFFIT)
        profile = [(0, bottom0), (0, level + R)]
        for i in range(1, TREADS):
            profile += [(i * G, level + i * R), (i * G, level + (i + 1) * R)]
        profile += [(run, level + TREADS * R), (run, bottom1)]
        stairs.prism(profile, to_world, 0, W, 'GuildDressed')
        rail = [(0, bottom0), (run, bottom1), (run, top + RAIL_HEIGHT), (0, level + RAIL_HEIGHT)]
        rails.prism(rail, to_world, W, W + RAIL, 'GuildDressed')
        if k < FLIGHTS - 1:                         # the last corner is the belfry floor
            xs, ys = CORNER_AFTER[face]
            stairs.box(*xs, *ys, Z0 if k == 0 else top - SOFFIT, top, 'GuildDressed')
        cx, cy = INNER_CORNER[face]                 # newel post where two rails meet
        sx, sy = (1 if cx > 0 else -1), (1 if cy > 0 else -1)
        x0, x1 = sorted((cx, cx - sx * .18))
        y0, y1 = sorted((cy, cy - sy * .18))
        rails.box(x0, x1, y0, y1, top - SOFFIT, top + RAIL_HEIGHT + .1, 'GuildDressed')
    # Rail round the hatch on the belfry floor (the hatch's west and south sides are walls).
    rails.box(-A, A - W, -(A - W), -(A - W) + RAIL, BELFRY, BELFRY + RAIL_HEIGHT, 'GuildDressed')
    return stairs, rails


# --- Bell -------------------------------------------------------------------------
HANG_Z = 28.0           # underside of the headstock beam
BELL_OUTER = [(.86, 0), (.89, .06), (.86, .16), (.77, .3), (.67, .5), (.61, .75), (.58, 1.0), (.56, 1.2),
              (.53, 1.34), (.45, 1.45), (.26, 1.51)]
BELL_INNER = [(.24, 1.42), (.42, 1.37), (.49, 1.2), (.51, 1.0), (.54, .75), (.59, .5), (.69, .3), (.77, .12), (.78, 0)]
BELL_HEIGHT = 1.52


def build_bell():
    bell = Part('SM_BellTower_Bell')
    crown = HANG_Z - .18
    mouth = crown - BELL_HEIGHT
    profile = BELL_OUTER + BELL_INNER          # closed loop: outer up, inner down
    segments = 36
    rings = [[(r * math.cos(2 * math.pi * j / segments), r * math.sin(2 * math.pi * j / segments), mouth + h)
              for r, h in profile] for j in range(segments)]
    n = len(profile)
    start = len(bell.verts)
    for ring_points in rings:
        bell.verts += ring_points
    for j in range(segments):
        a, b = start + j * n, start + ((j + 1) % segments) * n
        for i in range(n):
            bell.faces.append([a + i, a + (i + 1) % n, b + (i + 1) % n, b + i])
            bell.roles.append('Bronze')
    # Flat crown caps (outer top and inner roof) close the lathe.
    bell.verts += [(0, 0, mouth + BELL_OUTER[-1][1] + .01), (0, 0, mouth + BELL_INNER[0][1])]
    top_c, in_c = len(bell.verts) - 2, len(bell.verts) - 1
    for j in range(segments):
        a, b = start + j * n, start + ((j + 1) % segments) * n
        bell.faces.append([a + len(BELL_OUTER) - 1, b + len(BELL_OUTER) - 1, top_c])
        bell.faces.append([b + len(BELL_OUTER), a + len(BELL_OUTER), in_c])
        bell.roles += ['Bronze', 'Bronze']
    bell.box(-.12, .12, -.07, .07, crown, HANG_Z, 'Bronze')          # hanger to the headstock
    bell.box(-.03, .03, -.03, .03, mouth + .35, crown - .05, 'Bronze')  # clapper rod
    bell.box(-.09, .09, -.09, .09, mouth + .15, mouth + .35, 'Bronze')  # clapper ball
    return bell


def export(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = OUT / f'{obj.name}.fbx'
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, object_types={'MESH'},
                             axis_forward='-Z', axis_up='Y', mesh_smooth_type='FACE',
                             apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE',
                             bake_space_transform=False, add_leaf_bones=False, bake_anim=False,
                             use_mesh_modifiers=False, path_mode='AUTO', embed_textures=False)
    mesh = obj.data
    mesh.calc_loop_triangles()
    return {'fbx': path.name,
            'min_cm': [round(min(v.co[i] for v in mesh.vertices) * 100, 2) for i in range(3)],
            'max_cm': [round(max(v.co[i] for v in mesh.vertices) * 100, 2) for i in range(3)],
            'triangles': len(mesh.loop_triangles), 'materials': [m.name for m in mesh.materials]}


def main():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    stairs, rails = build_stairs()
    objects = [build_shell().build(), stairs.build(), rails.build(),
               build_bell().build(pivot=(0, 0, HANG_Z), smooth=('Bronze',))]
    manifest = {'units': 'cm, Unreal axes after import: X same, Y flipped',
                'belfry_floor_cm': round(BELFRY * 100, 1), 'hang_point_cm': HANG_Z * 100,
                'flights': FLIGHTS, 'risers_per_flight': TREADS + 1, 'riser_cm': R * 100,
                'tread_cm': G * 100, 'stair_width_cm': W * 100, 'inner_clear_cm': 2 * A * 100,
                'door_cm': {'width': 160, 'clear_height_to_spring': 260, 'crown_above_floor': 340},
                'meshes': {obj.name: export(obj) for obj in objects}}
    (OUT / 'bell_tower_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'bell_tower.blend'))
    print('BELL_TOWER_OK', json.dumps(manifest))


main()
