"""Create a photo-referenced architectural study in background Blender.

Run after build_material_textures.py with this file's output directory after --.
Local +X faces Great Tower Street. +Y runs toward the west passage.
"""

import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


OUT = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)

# OGL listed-building outline, rotated into a local metre frame. The point
# along the north front is redundant at modelling tolerance and is omitted.
WEST_FRONT = (0.0, 7.498)
EAST_FRONT = (0.0, -7.498)
EAST_REAR = (-23.484, -11.758)
OUTLINE = (
    WEST_FRONT, (-13.017, 6.242), (-13.104, 4.713),
    (-25.859, 3.459), EAST_REAR, EAST_FRONT,
)

VERTICES = []
FACES = []
FACE_MATERIALS = []
MATERIALS = {}


def create_material(name, color, roughness, image_name=None, metallic=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Metallic'].default_value = metallic
    if image_name:
        node = mat.node_tree.nodes.new('ShaderNodeTexImage')
        node.image = bpy.data.images.load(str(OUT / 'textures' / image_name), check_existing=True)
        node.image.pack()
        mat.node_tree.links.new(node.outputs['Color'], shader.inputs['Base Color'])
    MATERIALS[name] = mat


def solid(vertices, faces, material):
    offset = len(VERTICES)
    VERTICES.extend(vertices)
    for face in faces:
        FACES.append(tuple(index + offset for index in face))
        FACE_MATERIALS.append(material)


class Elevation:
    def __init__(self, origin=(0, 0), across=(0, 1)):
        self.origin = Vector(origin)
        self.across = Vector(across).normalized()
        self.out = Vector((self.across.y, -self.across.x))

    def point(self, across, depth, height):
        xy = self.origin + self.across * across + self.out * depth
        return (xy.x, xy.y, height)

    def prism(self, outline, back, front, material):
        count = len(outline)
        verts = [self.point(u, depth, z) for depth in (back, front) for u, z in outline]
        faces = [tuple(range(count-1, -1, -1)), tuple(range(count, count*2))]
        faces += [
            (i, (i+1) % count, (i+1) % count + count, i + count)
            for i in range(count)
        ]
        solid(verts, faces, material)

    def box(self, left, right, bottom, top, back, front, material):
        if right > left and top > bottom:
            self.prism(((left, bottom), (right, bottom), (right, top), (left, top)),
                       back, front, material)

    def band(self, points, height, back, front, material):
        outline = list(points) + [(u, z-height) for u, z in reversed(points)]
        self.prism(outline, back, front, material)

    def wall_with_openings(self, left, right, bottom, top, openings, material='Brick'):
        edge = left
        for center, width, sill, head in sorted(openings):
            start, end = center-width/2, center+width/2
            self.box(edge, start, bottom, top, -.30, 0, material)
            self.box(start, end, bottom, sill, -.30, 0, material)
            self.box(start, end, head, top, -.30, 0, material)
            edge = end
        self.box(edge, right, bottom, top, -.30, 0, material)

    def sash(self, u, sill, head, width, tone, trim='Portland'):
        left, right = u-width/2, u+width/2
        self.box(left, right, sill, head, -.20, -.11, tone)
        for x in (left, right-.085):
            self.box(x, x+.085, sill, head, -.12, -.025, 'Sash')
        for z in (sill, head-.09, sill+(head-sill)*.49):
            self.box(left, right, z, z+.085, -.13, -.018, 'Sash')
        for column in (1, 2):
            x = left + width*column/3
            self.box(x-.017, x+.017, sill, head, -.115, -.054, 'Sash')
        for row in (1, 3):
            z = sill+(head-sill)*row/4
            self.box(left, right, z-.013, z+.013, -.115, -.053, 'Sash')
        self.box(left-.08, right+.08, sill-.10, sill-.04, -.19, .115, trim)

    def radiating_lintel(self, u, z, width):
        base = width/2
        crown = base+.20
        for i in range(9):
            a, b = i/9, (i+1)/9 - .007
            self.prism(((u-base+2*base*a, z), (u-base+2*base*b, z),
                        (u-crown+2*crown*b, z+.26), (u-crown+2*crown*a, z+.26)),
                       -.025, .038, 'Lintel')

    def pilaster(self, u):
        self.box(u-.21, u+.21, 4.29, 9.78, -.035, .188, 'Brick')
        self.box(u-.245, u+.245, 4.24, 4.42, -.04, .22, 'Portland')
        self.box(u-.28, u+.28, 9.68, 9.93, -.04, .25, 'Portland')
        for center in (u-.18, u+.18):
            points = [(center+.078*math.cos(a*math.tau/12),
                       9.76+.078*math.sin(a*math.tau/12)) for a in range(12)]
            self.prism(points, .23, .285, 'Portland')
        self.box(u-.31, u+.31, 9.91, 10.02, -.04, .27, 'Portland')

    def cornice(self, left, right):
        for bottom, top, reach in ((9.91, 10.02, .20), (10.05, 10.16, .28),
                                   (10.16, 10.30, .36), (10.30, 10.43, .42),
                                   (10.43, 10.50, .46)):
            self.box(left, right, bottom, top, -.1, reach, 'Portland')
        for index in range(math.ceil((right-left)/.34)):
            u = left + .06 + index*.34
            self.box(u, min(u+.15, right), 10.01, 10.19, .10, .32, 'Portland')

    def rustication(self, left, right, openings):
        for index in range(13):
            bottom, top = .38+index*.298, .64+index*.298
            edge = left
            for u, width, sill, head in sorted(openings):
                if top < sill or bottom > head:
                    continue
                self.box(edge, u-width/2-.024, bottom, top, -.018, .048, 'Brick')
                edge = u+width/2+.024
            self.box(edge, right, bottom, top, -.018, .048, 'Brick')

    def portal(self, center):
        for direction in (-1, 1):
            u = center + direction*.93
            self.box(u-.15, u+.15, .02, 3.63, -.12, .26, 'Portland')
            self.box(u-.20, u+.20, .02, .37, -.13, .34, 'Portland')
            self.box(u-.22, u+.22, 3.48, 3.73, -.12, .36, 'Portland')
        self.box(center-1.16, center+1.16, 3.70, 3.94, -.08, .39, 'Portland')
        self.prism(((center-1.27, 3.92), (center+1.27, 3.92), (center, 4.63)),
                   -.11, .30, 'Portland')
        self.prism(((center-1.07, 3.99), (center+1.07, 3.99), (center, 4.53)),
                   .29, .36, 'Portland')
        self.sash(center, .12, 3.63, 1.50, 'Door')


def upper(elevation, left, right, bays, pilasters):
    levels = [(4.84, 6.84), (7.55, 9.44)]
    strips = [(u, 1.24, lo, hi) for u in bays for lo, hi in levels]
    for bottom, top in [(4.17, 7.13), (7.13, 10.41)]:
        elevation.wall_with_openings(left, right, bottom, top,
                                     [entry for entry in strips if bottom < entry[2] < top])
    for u, width, lo, hi in strips:
        elevation.sash(u, lo, hi, width, 'GlassUpper')
        elevation.radiating_lintel(u, hi, width)
    for u in pilasters:
        elevation.pilaster(u)
    elevation.cornice(left, right)


def ground(elevation, left, right, openings, passage=None):
    elevation.wall_with_openings(left, right, 0, 4.17, openings)
    elevation.rustication(left, right, openings)
    elevation.box(left, right, 3.99, 4.19, -.03, .148, 'Brick')
    edge = left
    for center, width, sill, head in sorted(openings):
        if sill < .38:
            elevation.box(edge, center-width/2, 0, .38, -.08, .10, 'Portland')
            edge = center+width/2
        if sill > .4:
            elevation.sash(center, sill, head, width, 'GlassGround')
            elevation.radiating_lintel(center, head, width)
    elevation.box(edge, right, 0, .38, -.08, .10, 'Portland')
    if passage is not None:
        center, width, _, head = passage
        elevation.radiating_lintel(center, head, width)
        elevation.box(center-width/2-.10, center-width/2, 0, head, -2, .015, 'Brick')
        elevation.box(center+width/2, center+width/2+.10, 0, head, -2, .015, 'Brick')
        elevation.box(center-width/2, center+width/2, 0, head, -2.08, -2, 'Door')


def mansard(footprint, inner, crown):
    count = len(footprint)
    levels = ((footprint, 10.47), (inner, 13.2), (crown, 13.36))
    verts = [(x, y, height) for loop, height in levels for x, y in loop]
    faces = [tuple(range(2*count, 3*count))]
    for level in (0, 1):
        offset = level*count
        for index in range(count):
            following = (index+1) % count
            faces.append((offset+index, offset+following, offset+following+count, offset+index+count))
    solid(verts, faces, 'RoofTile')


def swept_gable(north):
    # The oblique photographs show a high segmental centre and curved shoulders.
    def profile(u):
        distance = abs(u)
        if distance < 1.44:
            return 13.69 + .65*math.sqrt(max(0, 1-(distance/1.54)**2))
        if distance < 3.25:
            t = 1-(distance-1.44)/1.81
            return 11.31 + 2.66*t**2.5
        return 11.31

    sections = ((-7.48, -.575, 10.40), (-.575, .575, 13.24), (.575, 7.48, 10.40))
    points = []
    for left, right, bottom in sections:
        curve = [(u, profile(u)) for u in
                 (left + step * (right-left) / 24 for step in range(25))]
        north.prism([(left, bottom), (right, bottom)] + list(reversed(curve)), -.29, .05, 'Brick')
        points.extend(curve if not points else curve[1:])
    north.box(-.575, .575, 10.40, 11.98, -.29, .05, 'Brick')
    north.band(points, .10, -.30, .15, 'Portland')
    north.box(-1.52, 1.52, 13.68, 13.77, -.08, .15, 'Portland')
    north.sash(0, 11.98, 13.24, 1.15, 'GlassUpper')
    for u in (-3.86, 3.86):
        dormer = Elevation((-.79, 0))
        dormer.wall_with_openings(u-.65, u+.65, 11.28, 12.72,
                                  [(u, 1.13, 11.58, 12.61)], material='Sash')
        dormer.box(u-.65, u-.565, 11.28, 12.72, -1.30, 0, 'Sash')
        dormer.box(u+.565, u+.65, 11.28, 12.72, -1.30, 0, 'Sash')
        dormer.box(u-.72, u+.72, 12.72, 12.88, -1.37, .11, 'RoofTile')
        dormer.sash(u, 11.58, 12.61, 1.13, 'GlassUpper', trim='Sash')


def assemble_building():
    north = Elevation()
    gate = (5.77, 1.30, 0, 3.34)
    ground(north, -7.50, 7.50, [(-5.89, 1.49, .87, 3.39),
                              (-2.94, 1.49, .87, 3.39),
                              (0, 1.55, .03, 3.67),
                              (2.94, 1.49, .87, 3.39), gate], passage=gate)
    north.portal(0.0)
    upper(north, -7.49, 7.49, (-5.77, -2.90, 0, 2.90, 5.77),
          (-7.18, -4.37, -1.47, 1.47, 4.37, 7.18))
    swept_gable(north)

    direction = Vector(EAST_FRONT)-Vector(EAST_REAR)
    span = direction.length
    east = Elevation(EAST_REAR, direction)
    # The dated centre panel divides the two near-corner stacks of windows.
    near_left = span - 11.25
    ground(east, near_left, span, [(span-8.96, 1.44, .88, 3.35),
                                    (span-2.19, 1.44, .88, 3.35)])
    upper(east, near_left, span, (span-8.96, span-2.19),
          (near_left+.17, span-6.96, span-4.56, span-.20))
    east.box(span-6.43, span-5.07, 6.73, 7.52, -.05, .12, 'Lintel')
    east.box(span-6.36, span-5.14, 6.78, 6.89, .11, .17, 'Portland')
    east.box(near_left, span, 10.45, 11.16, -.25, .055, 'Brick')
    east.box(near_left, span, 11.13, 11.23, -.30, .15, 'Portland')
    east.box(0, near_left, 0, 10.62, -.29, .016, 'Brick')
    east.box(0, near_left, 0, .38, -.30, .105, 'Portland')
    sash_plane = Elevation(east.origin + .22*east.out, east.across)
    for u in (near_left*.24, near_left*.68):
        for sill in (.91, 4.98, 7.59):
            sash_plane.sash(u, sill, sill+1.65, 1.24, 'GlassUpper')
            east.radiating_lintel(u, sill+1.65, 1.24)
    east.cornice(0, near_left)

    # Secondary walls follow the public map. Their fenestration is unverified.
    for start, end in zip(OUTLINE, OUTLINE[1:]):
        if end == EAST_FRONT:
            continue
        axis = Vector(end)-Vector(start)
        wall = Elevation(start, axis)
        wall.box(0, axis.length, 0, 10.48, -.30, 0, 'Brick')
        wall.box(0, axis.length, 0, .36, -.30, .04, 'Portland')
        wall.cornice(0, axis.length)

    center = Vector((-11.5, -1))
    inset = tuple(tuple(center + (Vector(point)-center)*.78) for point in OUTLINE)
    ridge = tuple(tuple(center + (Vector(point)-center)*.75) for point in OUTLINE)
    mansard(OUTLINE, inset, ridge)
    for x, y, height, width in ((-2.07, -6.18, 14.04, 1.45),
                                (-2.31, 6.74, 14.17, 1.46),
                                (-11.92, -4.35, 14.14, 1.35),
                                (-18.85, 2.20, 14.32, 1.42)):
        stack = Elevation((x, y))
        stack.box(-width/2, width/2, 11.45, height-.28, -.48, .48, 'Brick')
        stack.box(-width/2-.10, width/2+.1, height-.33, height-.17, -.57, .57, 'Portland')
        stack.box(-width/2-.13, width/2+.13, height-.17, height, -.64, .64, 'RoofTile')


def finish_mesh():
    data = bpy.data.meshes.new('Great_Tower_Street_27_Exterior')
    data.from_pydata(VERTICES, [], FACES)
    data.update()
    obj = bpy.data.objects.new('SM_GreatTowerStreet_27_Exterior', data)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    names = [name for name in MATERIALS if name in set(FACE_MATERIALS)]
    for name in names:
        data.materials.append(MATERIALS[name])
    slots = {name: index for index, name in enumerate(names)}
    for polygon, material in zip(data.polygons, FACE_MATERIALS):
        polygon.material_index = slots[material]

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    uv = data.uv_layers.new(name='UV0')
    for polygon in data.polygons:
        axis = max(range(3), key=lambda i: abs(polygon.normal[i]))
        scale = (1.024 if polygon.material_index in (slots['Brick'], slots['Lintel']) else 1.65)
        dimensions = ((1, 2), (0, 2), (0, 1))[axis]
        for loop_index in polygon.loop_indices:
            vertex = data.vertices[data.loops[loop_index].vertex_index].co
            uv.data[loop_index].uv = tuple(vertex[dim]/scale for dim in dimensions)
    data.calc_loop_triangles()
    return obj


def studio(obj):
    scene = bpy.context.scene
    bpy.ops.mesh.primitive_plane_add(size=500, location=(-7, 0, -.05))
    ground_plane = bpy.context.object
    ground_plane.name = 'Preview floor only'
    ground_plane.data.materials.append(MATERIALS['PreviewFloor'])

    bpy.ops.object.light_add(type='AREA', location=(20, -14, 30))
    bpy.context.object.data.energy = 10000
    bpy.context.object.data.shape = 'DISK'
    bpy.context.object.data.size = 25
    bpy.ops.object.light_add(type='AREA', location=(-6, 22, 19))
    bpy.context.object.data.energy = 5500
    bpy.context.object.data.size = 20
    scene.world = bpy.data.worlds.new('Overcast studio')
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get('Background')
    background.inputs['Color'].default_value = (.43, .46, .50, 1)
    background.inputs['Strength'].default_value = .55

    # This view shows both photo-referenced street elevations.
    bpy.ops.object.camera_add(location=(36, -34, 17))
    camera = bpy.context.object
    camera.rotation_euler = (Vector((-10.7, -1.5, 6.35))-camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 38.5
    scene.camera = camera
    for other in bpy.context.selected_objects:
        other.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    scene.unit_settings.system = 'METRIC'
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 14
    scene.cycles.use_denoising = True
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 4
    scene.render.resolution_x, scene.render.resolution_y = 1200, 840
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(OUT/'GreatTowerStreet_27_preview.png')
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.exposure = .40


bpy.ops.wm.read_factory_settings(use_empty=True)
create_material('Brick', (.20, .056, .031), .82, 'stock_brick.png')
create_material('Lintel', (.23, .069, .038), .83, 'stock_brick.png')
create_material('Portland', (.52, .44, .35), .73, 'portland_stone.png')
create_material('RoofTile', (.075, .066, .058), .85, 'roof_tile.png')
create_material('Sash', (.029, .027, .023), .56)
create_material('GlassUpper', (.09, .109, .12), .23)
create_material('GlassGround', (.105, .073, .05), .25)
create_material('Door', (.032, .024, .015), .60)
create_material('PreviewFloor', (.30, .275, .236), .88)
assemble_building()
building = finish_mesh()
studio(building)

report = {
    'subject': '27 Great Tower Street, London EC3',
    'dimensions_m': list(building.dimensions),
    'triangles': len(building.data.loop_triangles),
    'position': list(building.location),
    'scale': list(building.scale),
    'uv_channels': [layer.name for layer in building.data.uv_layers],
    'materials': [material.name for material in building.data.materials],
    'frontage_m': 14.996,
    'notes': 'Physical height is an estimate. No site survey, interiors, collision, or engine placement.',
}
(OUT / 'GreatTowerStreet_27_geometry.json').write_text(json.dumps(report, indent=2), encoding='utf-8')

bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'GreatTowerStreet_27.blend'))
bpy.ops.export_scene.gltf(filepath=str(OUT/'GreatTowerStreet_27.glb'),
                         export_format='GLB', use_selection=True)
bpy.ops.render.render(write_still=True)
