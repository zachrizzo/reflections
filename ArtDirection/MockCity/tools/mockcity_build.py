"""Builds the mock Lanthorne: /Game/MockCity/Lvl_MockCity_<Side> (same layout, same coordinates) streamed into
/Game/MockCity/Lvl_MockCity as world-jump offset copies (Pewterside 0, Giltside +150000, Frostside +300000 in X).

ARGS: one of 'mats', 'Pewterside', 'Giltside', 'Frostside', 'persistent'. Layout is in metres; spawned in cm.
Story markers are placed by mockcity_markers.py (a separate pass).
"""
import json
import math
import os
import random
import unreal

EAL = unreal.EditorAssetLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()
L = unreal.ReflectionsWorldLibrary
ROOT = '/Game/MockCity'
SIDES = ['Pewterside', 'Giltside', 'Frostside']
OFFSET_X = {'Pewterside': 0.0, 'Giltside': 150000.0, 'Frostside': 300000.0}
WORLD_ENUM = {'Pewterside': unreal.ReflectionsWorld.GRAY, 'Giltside': unreal.ReflectionsWorld.RED,
              'Frostside': unreal.ReflectionsWorld.WHITE}
CUBE = unreal.load_asset('/Engine/BasicShapes/Cube')
CYL = unreal.load_asset('/Engine/BasicShapes/Cylinder')
CONE = unreal.load_asset('/Engine/BasicShapes/Cone')
out = {'log': [], 'counts': {}}

COLORS = {
    'Pewterside': {'Ground': (0.15, 0.15, 0.16), 'Street': (0.085, 0.09, 0.095), 'Wall': (0.30, 0.30, 0.31),
                   'WallAlt': (0.23, 0.24, 0.26), 'Trim': (0.40, 0.40, 0.40), 'Door': (0.05, 0.05, 0.06),
                   'Water': (0.03, 0.05, 0.06), 'Stall': (0.24, 0.21, 0.19), 'Metal': (0.10, 0.10, 0.11),
                   'Tower': (0.26, 0.26, 0.27), 'Rail': (0.05, 0.05, 0.05), 'Canvas': (0.33, 0.33, 0.30)},
    'Giltside': {'Ground': (0.26, 0.18, 0.10), 'Street': (0.15, 0.10, 0.06), 'Wall': (0.52, 0.36, 0.21),
                 'WallAlt': (0.42, 0.26, 0.15), 'Trim': (0.72, 0.52, 0.22), 'Door': (0.14, 0.05, 0.02),
                 'Water': (0.03, 0.045, 0.07), 'Stall': (0.55, 0.16, 0.06), 'Metal': (0.22, 0.15, 0.05),
                 'Tower': (0.80, 0.58, 0.20), 'Rail': (0.08, 0.06, 0.04), 'Canvas': (0.62, 0.40, 0.14)},
    # Frostside (18:50 look pass): darker blue-grey ground, streets and ice so Codex's pale facades have contrast.
    'Frostside': {'Ground': (0.30, 0.34, 0.40), 'Street': (0.19, 0.23, 0.29), 'Wall': (0.54, 0.58, 0.63),
                  'WallAlt': (0.40, 0.46, 0.55), 'Trim': (0.52, 0.58, 0.65), 'Door': (0.10, 0.14, 0.20),
                  'Water': (0.09, 0.15, 0.21), 'Stall': (0.30, 0.36, 0.45), 'Metal': (0.16, 0.19, 0.25),
                  'Tower': (0.44, 0.53, 0.64), 'Rail': (0.18, 0.22, 0.28), 'Canvas': (0.46, 0.52, 0.60)},
}
LAMP = {  # colour, candelas, radius m, every Nth lamp lit
    'Pewterside': ((0.82, 0.86, 0.92), 22.0, 13.0, 2),
    'Giltside': ((1.0, 0.60, 0.28), 55.0, 15.0, 1),
    'Frostside': ((0.50, 0.70, 1.0), 32.0, 12.0, 1),   # every brazier burns blue: the cold accents
}
FROST_TOWER_LIGHT = ((0.45, 0.66, 1.0), 24.0, 9.0)   # blue glow on each ramp landing inside the Frost Tower
PROPS = {  # role -> per-side mesh
    'lamp': {'Pewterside': 'Pewterside/Props/SM_Pewterside_CanalLamp', 'Giltside': 'Giltside/Props/SM_Giltside_ArchiveLantern',
             'Frostside': 'Frostside/Props/SM_Frostside_IronBrazier'},
    'crate': {'Pewterside': 'Pewterside/Props/SM_Pewterside_CanalCrate', 'Giltside': 'Giltside/Props/SM_Giltside_ArchiveCoffer',
              'Frostside': 'Frostside/Props/SM_Frostside_ProvisionCrate'},
    'bollard': {'Pewterside': 'Pewterside/Props/SM_Pewterside_CanalBollard', 'Giltside': 'Giltside/Props/SM_Giltside_MarbleUrn',
                'Frostside': 'Frostside/Props/SM_Frostside_RuneWaymarker'},
    'shrine': {'Pewterside': 'Pewterside/Props/SM_Pewterside_HandPump', 'Giltside': 'Giltside/Props/SM_Giltside_MirrorPedestal',
               'Frostside': 'Frostside/Props/SM_Frostside_MirrorShrine'},
    'column': {'Pewterside': 'Pewterside/Props/SM_Pewterside_CanalBollard', 'Giltside': 'Giltside/Props/SM_Giltside_MarbleUrn',
               'Frostside': 'Frostside/Props/SM_Frostside_BrokenColumn'},
    'desk': {'Pewterside': 'Pewterside/Props/SM_Pewterside_ArchiveDesk', 'Giltside': 'Giltside/Props/SM_Giltside_ReadingLectern',
             'Frostside': 'Frostside/Props/SM_Frostside_LookoutStandard'},
    'chair': {'Pewterside': 'Pewterside/Props/SM_Pewterside_ArchiveChair', 'Giltside': 'Giltside/Props/SM_Giltside_Grimoire',
              'Frostside': 'Frostside/Props/SM_Frostside_LookoutHelmet'},
    'shelf': {'Pewterside': 'Pewterside/Props/SM_Pewterside_ArchiveShelf', 'Giltside': 'Giltside/Props/SM_Giltside_OpenSpellbook',
              'Frostside': 'Frostside/Props/SM_Frostside_ProvisionCrate'},
}

# ---- Layout (metres) ---------------------------------------------------------------------------------------------
HALF = 150.0
X_STREETS = [-100.0, -40.0, 40.0, 100.0]
Y_STREETS = [105.0, 35.0, -60.0, -110.0]
COLS = [(-142.0, -105.0), (-95.0, -45.0), (-35.0, 35.0), (45.0, 95.0), (105.0, 142.0)]
ROWS = [(110.0, 142.0), (40.0, 100.0), (-9.0, 30.0), (-55.0, -31.0), (-105.0, -65.0), (-142.0, -115.0)]
CANAL = (-26.0, -14.0)
TOWER = (0.0, 70.0)          # Gilt Tower / Frost Tower / Pewterside stump
TOWER_HALF = 7.0
TOWER_H = 24.0
CROWN_EAST = 25.0            # Frost crown reaches this far east of the tower centre
ARENA = (13.0, 70.0)         # villain arena centre on the crown (10 m radius, clear of the stair slot)
WEIGH = (-95.0, -80.0, -9.0, 6.0)   # Weigh-House footprint
WEIGH_H = 10.0
LAMPLIGHT = (-35.0, -12.0, 2.0, 30.0)
ARCHIVE = (-95.0, -62.0, 48.0, 95.0)
OPEN = {(2, 1): 'TowerPlaza', (1, 2): 'BellSquare', (4, 1): 'MusterYard'}
RESERVED = [WEIGH, LAMPLIGHT, ARCHIVE, (-62.0, -45.0, 48.0, 95.0),  # archive terrace and steps
            (78.0, 95.0, -9.0, 10.0),      # yard with Sorrel's shed
            (121.0, 142.0, -9.0, 30.0),    # drifters' camp by the gate
            (-142.0, -105.0, -105.0, -65.0), (105.0, 142.0, -105.0, -65.0)]  # barracks

PLACES = {}  # place key -> (x, y, z, yaw) in metres, for the marker pass and the README

# ---- Codex's city kit (/Game/LanthorneAssets/<Side>/City) ----------------------------------------------------------
# Facade modules: 4 m wide (local X -2..2), 3.2 m tall, front faces local +Y, front-most detail at +0.29 m (ground) and
# +0.28 m (upper); the corner is a 4 x 4 m block detailed on its +X and +Y faces; the cornice is 0.63 m tall with its
# front at +0.45 m. Lamps are 4 m, pivot at the bounding-box centre.
# Each building keeps its old box as INVISIBLE collision (same footprint, so the nav mesh and the lanes hold), gets a
# visible core 0.6 m inside the facades that carries the Lumen bounce light, and its facades, cornices, roof slab and
# the side's lamps go on one 'CityKit_<Side>' actor as instanced meshes (out of the Lumen scene, no collision).
KIT_MODE = 'ism'           # 'ism' (instanced components) or 'actors' (one StaticMeshActor per piece, fallback)
KIT_CULL_CM = 60000        # instances past 600 m are culled (the other sides are 1.2 km+ away)
FLOOR_H = 3.2
KIT_FRONT = {'FacadeGround': 0.29, 'FacadeUpper': 0.28}
CORNICE_IN = 0.20          # cornice pivot inside the wall line; its front overhangs 0.25 m
FACE_YAW = {'N': 0.0, 'S': 180.0, 'E': 270.0, 'W': 90.0}
KIT_LAMP = {  # mesh, pole offset along the arm (m, mesh space), lamp head along the arm (m), head height (m)
    'Pewterside': ('GasLamp', 0.0, 0.0, 3.15),
    'Giltside': ('LanternPost', -0.36, 0.40, 2.95),
    'Frostside': ('BrazierStand', 0.0, 0.0, 3.7),
}


def modules(length):
    """Modules along a wall of this length: about 4 m each, at least the two corners."""
    return max(2, int(round(length / 4.0)))


def place(key, x, y, z=0.0, yaw=0.0):
    PLACES[key] = (x, y, z, yaw)


def log(msg):
    out['log'].append(msg)


def count(kind):
    out['counts'][kind] = out['counts'].get(kind, 0) + 1


def xf(loc_m, rot=(0, 0, 0), scale=(1, 1, 1)):
    """rot is (roll, pitch, yaw) in degrees. Build the Rotator by keyword: a plain list is read in FRotator field
    order (pitch, yaw, roll), which turned every intended yaw into a roll before 18:35 on Nov 14."""
    return unreal.Transform(location=[loc_m[0] * 100.0, loc_m[1] * 100.0, loc_m[2] * 100.0],
                            rotation=unreal.Rotator(roll=float(rot[0]), pitch=float(rot[1]), yaw=float(rot[2])),
                            scale=list(scale))


# Small or flat pieces stay out of the Lumen scene (surface cache atlas): they add cards and no bounce light.
NO_LUMEN = ('Door', 'Bldg_', 'Lamp_', 'Stall_', 'WeighHouse_Stair', 'WeighHouse_Parapet', 'WeighHouse_Drainpipe',
            'FishSteps', 'Archive_Steps', 'Archive_Salon', 'BridgeRail', 'TramRail', 'TramStop', 'Street_', 'CanalWalk',
            'Plaza_', 'Square_Paving', 'Quay_', 'CanalParapet', 'Tower_Rubble', 'Tower_Ramp', 'Tower_Landing',
            'Tower_Crack', 'Tower_Slot', 'Tower_CrownParapet', 'Camp_', 'Muster_', 'EdgeBlocker', 'GateBridge_Rail',
            'GateBridge_Blocker', 'Key_Pedestal', 'Bollard_', 'Yard_ShedDoor', 'Lamplight_Sign', 'Lamplight_CellarHatch',
            'Fountain_Column', 'CanalRiftPost', 'Gate_WatchPost', 'Barracks_West_Door', 'Barracks_East_Door')


def lumen_ok(label):
    if not label:
        return True
    if label.startswith('Bldg_') and not label.endswith('Cornice'):
        return True   # the building boxes themselves carry the city's bounce light
    return not label.startswith(NO_LUMEN)


class Side:
    def __init__(self, name, world):
        self.name = name
        self.world = world
        self.mats = {k: unreal.load_asset('%s/Materials/MI_Mock_%s_%s' % (ROOT, name, k)) for k in COLORS[name]}
        self.props = {}
        self.lamp_index = 0
        self.kit = {}      # kit piece key -> [Transform] (level space)

    def kit_add(self, key, loc_m, yaw, scale):
        self.kit.setdefault(key, []).append(xf(loc_m, (0.0, 0.0, yaw), scale))

    def spawn(self, cls, loc_m, rot=(0, 0, 0), scale=(1, 1, 1), label=None):
        actor = L.spawn_actor_into_world(self.world, cls, xf(loc_m, rot, scale))
        if actor is None:
            raise RuntimeError('spawn failed: %s' % cls)
        if label:
            actor.set_actor_label(label)
        count(cls.__name__ if hasattr(cls, '__name__') else str(cls))
        return actor

    def mesh(self, mesh, center_m, size_m, mat, label=None, rot=(0, 0, 0), collide=True, visible=True, base=100.0,
             shadow=True):
        a = self.spawn(unreal.StaticMeshActor, center_m, rot, (size_m[0] * 100.0 / base, size_m[1] * 100.0 / base,
                                                               size_m[2] * 100.0 / base), label)
        smc = a.static_mesh_component
        smc.set_static_mesh(mesh)
        if not visible or not lumen_ok(label):
            smc.set_editor_property('affect_dynamic_indirect_lighting', False)
            count('no_lumen')
        if not shadow:
            smc.set_editor_property('cast_shadow', False)
        if mat is not None:
            smc.set_material(0, self.mats[mat] if isinstance(mat, str) else mat)
        if not collide:
            smc.set_collision_profile_name('NoCollision')
        if not visible:
            smc.set_editor_property('visible', False)
            smc.set_editor_property('cast_shadow', False)
        return a

    def box(self, x0, x1, y0, y1, z0, z1, mat, label=None, **kw):
        return self.mesh(CUBE, ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), (x1 - x0, y1 - y0, z1 - z0), mat, label, **kw)

    def cbox(self, c, s, mat, label=None, **kw):
        return self.mesh(CUBE, c, s, mat, label, **kw)

    def prop(self, role, loc_m, yaw=0.0, label=None, scale=1.0):
        path = PROPS[role][self.name]
        if path not in self.props:
            self.props[path] = unreal.load_asset('/Game/LanthorneAssets/' + path)
        m = self.props[path]
        if m is None:
            return None
        a = self.spawn(unreal.StaticMeshActor, loc_m, (0, 0, yaw), (scale, scale, scale), label)
        a.static_mesh_component.set_static_mesh(m)
        a.static_mesh_component.set_editor_property('affect_dynamic_indirect_lighting', False)
        count('no_lumen')
        return a

    def light(self, loc_m, color, cd, radius_m, label=None, shadows=False):
        a = self.spawn(unreal.PointLight, loc_m, label=label)
        c = a.point_light_component
        c.set_editor_property('mobility', unreal.ComponentMobility.MOVABLE)
        c.set_editor_property('intensity_units', unreal.LightUnits.CANDELAS)
        c.set_editor_property('intensity', cd)
        c.set_editor_property('light_color', unreal.Color(int(color[0] * 255), int(color[1] * 255), int(color[2] * 255), 255))
        c.set_editor_property('attenuation_radius', radius_m * 100.0)
        c.set_editor_property('cast_shadows', shadows)
        return a

    def lamp(self, x, y, label, lit=None, face=(1.0, 0.0)):
        """A street lamp at the kerb: Codex's lamp (its arm or front toward `face`, usually the street centre) with
        its pole on (x, y), an invisible collision post, and a point light at the lamp head when lit."""
        color, cd, radius, every = LAMP[self.name]
        self.lamp_index += 1
        on = (self.lamp_index % every == 0) if lit is None else lit
        _, pole, head, head_z = KIT_LAMP[self.name]
        yaw = math.degrees(math.atan2(face[1], face[0]))
        c, sn = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        px, py = x - c * pole, y - sn * pole
        self.kit_add('Lamp', (px, py, 0.0), yaw, (1.0, 1.0, 1.0))
        self.cbox((x, y, 2.0), (0.25, 0.25, 4.0), 'Metal', label + '_Post', visible=False)
        if on:
            self.light((px + c * head, py + sn * head, head_z), color, cd, radius, label + '_Light')


def overlaps(a, b):
    return a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]


def building_lots():
    """Deterministic lots for every built-up block: (x0, x1, y0, y1, height, door side)."""
    rnd = random.Random(1914)
    lots = []
    for ci, (x0, x1) in enumerate(COLS):
        for ri, (y0, y1) in enumerate(ROWS):
            if (ci, ri) in OPEN:
                continue
            depth = y1 - y0
            rows = [(y0, y1, 'N' if ri <= 2 and y1 > 0 else 'S')]
            if depth > 28.0:
                mid = (y0 + y1) / 2.0
                rows = [(mid + 1.5, y1, 'N'), (y0, mid - 1.5, 'S')]
            elif ri in (2,):
                rows = [(y0, y1, 'N')]
            elif ri in (3,):
                rows = [(y0, y1, 'S')]
            for (ya, yb, door) in rows:
                x = x0
                while x < x1 - 6.0:
                    w = rnd.uniform(11.0, 17.0)
                    xb = min(x + w, x1)
                    if x1 - xb < 8.0:
                        xb = x1
                    lot = (x, xb, ya, yb)
                    h = rnd.choice([8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0])
                    if not any(overlaps(lot, r) for r in RESERVED):
                        lots.append((x, xb, ya, yb, h, door, rnd.random()))
                    x = xb + 3.0
    return lots


def stairs(s, x, y0, y1, z0, z1, width, mat, label):
    """Straight stairs along +Y (y0 low end) or -Y (y0 > y1), first step lowest, as solid columns."""
    n = max(1, int(round(abs(z1 - z0) / 0.25)))
    run = (y1 - y0) / n
    for i in range(n):
        top = z0 + (i + 1) * (z1 - z0) / n
        ya = y0 + i * run
        yb = ya + run
        s.box(x - width / 2, x + width / 2, min(ya, yb), max(ya, yb), min(z0, 0.0), top, mat, '%s_%02d' % (label, i))


def stairs_x(s, y, x0, x1, z0, z1, width, mat, label):
    """Straight stairs along X from x0 (low, z0) to x1 (high, z1), as solid columns from the ground."""
    n = max(1, int(round(abs(z1 - z0) / 0.25)))
    run = (x1 - x0) / n
    for i in range(n):
        top = z0 + (i + 1) * (z1 - z0) / n
        xa = x0 + i * run
        xb = xa + run
        s.box(min(xa, xb), max(xa, xb), y - width / 2, y + width / 2, 0.0, top, mat, '%s_%02d' % (label, i))


def skin_building(s, x0, x1, y0, y1, h, door, label, core='Wall', cornice=True, roof=True):
    """Codex facade modules round a box building (the caller keeps the box as invisible collision).
    Corners on every floor, door modules on the ground floor of the `door` face (N/S/E/W), window modules elsewhere,
    a cornice round the top, a roof slab, and a visible core just inside for Lumen."""
    W, D = x1 - x0, y1 - y0
    n, p = modules(W), modules(D)
    cw, cd = W / n, D / p
    floors = max(1, int(round(h / FLOOR_H)))
    fh = h / floors
    sz = fh / FLOOR_H
    corners = ((x1, y1, 0.0, 1, 1), (x0, y1, 90.0, -1, 1), (x0, y0, 180.0, -1, -1), (x1, y0, 270.0, 1, -1))
    for f in range(floors):
        z = f * fh
        for (cx, cy, yaw, sx, sy) in corners:
            sc = (cw / 4.0, cd / 4.0, sz) if yaw in (0.0, 180.0) else (cd / 4.0, cw / 4.0, sz)
            s.kit_add('FacadeCorner', (cx - sx * cw / 2.0, cy - sy * cd / 2.0, z), yaw, sc)
        for face in 'NSEW':
            key = 'FacadeGround' if (f == 0 and face == door) else 'FacadeUpper'
            fr = KIT_FRONT[key]
            if face in 'NS':
                yy = y1 - fr if face == 'N' else y0 + fr
                for k in range(1, n - 1):
                    s.kit_add(key, (x0 + cw * (k + 0.5), yy, z), FACE_YAW[face], (cw / 4.0, 1.0, sz))
            else:
                xx = x1 - fr if face == 'E' else x0 + fr
                for k in range(1, p - 1):
                    s.kit_add(key, (xx, y0 + cd * (k + 0.5), z), FACE_YAW[face], (cd / 4.0, 1.0, sz))
    if cornice:
        # North and south runs reach 0.25 m past the corners so the overhangs meet; east and west sit 5 mm higher.
        cwx = (W + 0.5) / n
        for face in 'NS':
            yy = y1 - CORNICE_IN if face == 'N' else y0 + CORNICE_IN
            for k in range(n):
                s.kit_add('FacadeCornice', (x0 - 0.25 + cwx * (k + 0.5), yy, h), FACE_YAW[face], (cwx / 4.0, 1.0, 1.0))
        for face in 'EW':
            xx = x1 - CORNICE_IN if face == 'E' else x0 + CORNICE_IN
            for k in range(p):
                s.kit_add('FacadeCornice', (xx, y0 + cd * (k + 0.5), h + 0.005), FACE_YAW[face], (cd / 4.0, 1.0, 1.0))
    if roof:
        s.kit_add('Roof', ((x0 + x1) / 2.0, (y0 + y1) / 2.0, h - 0.07), 0.0, (W - 0.6, D - 0.6, 0.12))
    s.box(x0 + 0.6, x1 - 0.6, y0 + 0.6, y1 - 0.6, 0.0, h - 0.15, core, label + '_Core', collide=False, shadow=False)
    count('skinned')


def flush_kit(s):
    """All of the side's kit pieces onto one 'CityKit_<Side>' actor: one instanced component per piece."""
    base = '/Game/LanthorneAssets/%s/City/SM_%s_' % (s.name, s.name)
    meshes = {k: unreal.load_asset(base + k) for k in ('FacadeGround', 'FacadeUpper', 'FacadeCorner', 'FacadeCornice')}
    meshes['Lamp'] = unreal.load_asset(base + KIT_LAMP[s.name][0])
    meshes['Roof'] = CUBE
    totals = {}
    if KIT_MODE == 'actors':
        for key, xfs in sorted(s.kit.items()):
            for i, t in enumerate(xfs):
                a = L.spawn_actor_into_world(s.world, unreal.StaticMeshActor, t)
                a.set_actor_label('Kit_%s_%04d' % (key, i))
                smc = a.static_mesh_component
                smc.set_static_mesh(meshes[key])
                if key == 'Roof':
                    smc.set_material(0, s.mats['Street'])
                smc.set_collision_profile_name('NoCollision')
                smc.set_editor_property('affect_dynamic_indirect_lighting', False)
            totals[key] = len(xfs)
        log('kit actors %s' % totals)
        return totals
    holder = s.spawn(unreal.StaticMeshActor, (0.0, 0.0, 0.0), label='CityKit_' + s.name)
    holder.static_mesh_component.set_collision_profile_name('NoCollision')
    # Components must be added the way the Details panel does (instance components), or they are not saved.
    sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    bfl = unreal.SubobjectDataBlueprintFunctionLibrary
    handles = sub.k2_gather_subobject_data_for_instance(holder)
    for key, xfs in sorted(s.kit.items()):
        m = meshes.get(key)
        if m is None or not xfs:
            log('kit: no mesh for %s' % key)
            continue
        out = sub.add_new_subobject(unreal.AddNewSubobjectParams(
            parent_handle=handles[0], new_class=unreal.HierarchicalInstancedStaticMeshComponent, blueprint_context=None))
        h = out[0] if isinstance(out, (tuple, list)) else out
        try:
            sub.rename_subobject(h, unreal.Text('Kit_' + key))
        except Exception as e:  # noqa: BLE001
            log('kit rename %s: %s' % (key, e))
        c = bfl.get_object(bfl.get_data(h))
        c.set_static_mesh(m)
        if key == 'Roof':
            c.set_material(0, s.mats['Street'])
        c.set_collision_profile_name('NoCollision')
        for prop, val in (('mobility', unreal.ComponentMobility.STATIC), ('can_ever_affect_navigation', False),
                          ('affect_dynamic_indirect_lighting', False), ('instance_end_cull_distance', KIT_CULL_CM)):
            try:
                c.set_editor_property(prop, val)
            except Exception as e:  # noqa: BLE001
                log('kit %s %s: %s' % (key, prop, e))
        c.add_instances(xfs, False, False)
        totals[key] = c.get_instance_count()
    log('kit instances %s' % totals)
    return totals


def build_common(s):
    """Everything identical across the three sides."""
    H = HALF
    # Ground: two slabs either side of the canal, the canal bed, the sea all round (no collision), invisible edge.
    s.box(-H, H, CANAL[1], H, -3.0, 0.0, 'Ground', 'Ground_North')
    s.box(-H, H, -H, CANAL[0], -3.0, 0.0, 'Ground', 'Ground_South')
    s.box(-H, H, CANAL[0], CANAL[1], -3.2, -2.5, 'Street', 'Canal_Bed')
    s.box(-500.0, 500.0, -500.0, 500.0, -1.6, -1.5, 'Water', 'Water', collide=False)
    for (x0, x1, y0, y1, lab) in [(-H - 1, -H, -H, H, 'W'), (H, H + 1, -H, 30.0, 'E1'), (H, H + 1, 40.0, H, 'E2'),
                                  (-H, H, H, H + 1, 'N'), (-H, H, -H - 1, -H, 'S')]:
        s.box(x0, x1, y0, y1, -3.0, 8.0, 'Trim', 'EdgeBlocker_' + lab, visible=False)
    # Quay parapet (low) round the island, gap at the Lantern Gate.
    for (x0, x1, y0, y1, lab) in [(-H, -H + 0.6, -H, H, 'W'), (H - 0.6, H, -H, 29.0, 'E1'), (H - 0.6, H, 41.0, H, 'E2'),
                                  (-H, H, H - 0.6, H, 'N'), (-H, H, -H, -H + 0.6, 'S')]:
        s.box(x0, x1, y0, y1, 0.0, 1.0, 'Trim', 'Quay_' + lab)
    # Streets (darker paving strips), canal walks, tram rails on Coal Lane.
    for x in X_STREETS:
        s.box(x - 5, x + 5, -H + 8, H - 8, 0.0, 0.02, 'Street', 'Street_X%d' % x, collide=False)
    for y in Y_STREETS:
        s.box(-H + 8, H - 8, y - 5, y + 5, 0.0, 0.02, 'Street', 'Street_Y%d' % y, collide=False)
    s.box(-H + 8, H - 8, CANAL[1], CANAL[1] + 5, 0.0, 0.02, 'Street', 'CanalWalk_North', collide=False)
    s.box(-H + 8, H - 8, CANAL[0] - 5, CANAL[0], 0.0, 0.02, 'Street', 'CanalWalk_South', collide=False)
    for dy in (-0.75, 0.75):
        s.box(-H + 8, H - 8, -60.0 + dy - 0.06, -60.0 + dy + 0.06, 0.02, 0.06, 'Rail', 'TramRail_%+.2f' % dy, collide=False)
    # Canal edge parapets with gaps for the bridges and the Fish Steps.
    gaps = [(x - 5.5, x + 5.5) for x in X_STREETS]
    for edge, (ya, yb) in (('N', (CANAL[1], CANAL[1] + 0.4)), ('S', (CANAL[0] - 0.4, CANAL[0]))):
        xs = [-H + 1] + [v for g in gaps for v in g] + [H - 1]
        if edge == 'S':
            xs = [-H + 1] + [v for g in gaps[:3] for v in g] + [59.5, 75.5] + [v for g in gaps[3:] for v in g] + [H - 1]
        for i in range(0, len(xs), 2):
            if xs[i + 1] - xs[i] > 0.5:
                s.box(xs[i], xs[i + 1], ya, yb, 0.0, 0.9, 'Trim', 'CanalParapet_%s_%d' % (edge, i))
    # Bridges over the canal.
    for x in X_STREETS:
        s.box(x - 5, x + 5, CANAL[0] - 1, CANAL[1] + 1, -0.8, 0.0, 'Trim', 'Bridge_X%d' % x)
        for dx in (-5.0, 4.7):
            s.box(x + dx, x + dx + 0.3, CANAL[0] - 1, CANAL[1] + 1, 0.0, 1.0, 'Trim', 'BridgeRail_X%d_%d' % (x, dx))
    # Fish Steps: down from the south canal walk to the canal bed.
    for i in range(10):
        top = -0.25 * (i + 1)
        s.box(60.0, 75.0, CANAL[0] + i * 0.4, CANAL[0] + (i + 1) * 0.4, -3.0, top, 'Trim', 'FishSteps_%02d' % i)
    place('FishSteps', 67.5, -27.5, 0.0, 90.0)
    place('CanalRift', 125.0, -11.0, 0.0, 270.0)
    s.box(124.0, 126.0, -12.5, -10.5, 0.0, 2.6, 'Metal', 'CanalRiftPost')

    # Buildings.
    lots = building_lots()
    doors = []
    for i, (x0, x1, y0, y1, h, door, r) in enumerate(lots):
        mat = 'Wall' if r < 0.55 else 'WallAlt'
        s.box(x0, x1, y0, y1, 0.0, h, mat, 'Bldg_%03d' % i, visible=False)
        skin_building(s, x0, x1, y0, y1, h, door, 'Bldg_%03d' % i, core=mat)
        dx = (x0 + x1) / 2.0
        dy = y1 + 0.08 if door == 'N' else y0 - 0.08
        doors.append((dx, dy + (1.2 if door == 'N' else -1.2), 0.0, 90.0 if door == 'N' else 270.0))
    out['doors'] = len(doors)
    PLACES['_doors'] = doors

    # Tower plaza: open paving, the tower footprint is per side (build_tower). Shrine + urns round it.
    px0, px1 = COLS[2]
    py0, py1 = ROWS[1]
    s.box(px0, px1, py0, py1, 0.0, 0.03, 'Street', 'Plaza_Paving', collide=False)
    for (x, y) in [(-22, 50), (22, 50), (-22, 90), (22, 90)]:
        s.prop('column', (x, y, 0.0), 0.0, 'Plaza_Column', 1.4)
    s.prop('shrine', (0.0, 52.0, 0.0), 0.0, 'Plaza_Shrine', 1.0)
    place('TowerFoot', 0.0, 60.5, 0.0, 90.0)
    place('TowerPlaza', 0.0, 50.0, 0.0, 90.0)

    # Bell Square with its dry fountain (the Cistern in Frostside); the Weigh-House on its south-west corner.
    bx0, bx1 = COLS[1]
    by0, by1 = ROWS[2]
    s.box(bx0, bx1, by0, by1, 0.0, 0.03, 'Street', 'Square_Paving', collide=False)
    s.mesh(CYL, (-65.0, 14.0, 0.4), (8.0, 8.0, 0.8), 'Trim', 'Fountain_Basin')
    s.mesh(CYL, (-65.0, 14.0, 1.6), (1.2, 1.2, 3.2), 'Trim', 'Fountain_Column')
    place('BellSquare', -65.0, 7.0, 0.0, 90.0)
    place('Fountain', -65.0, 14.0, 0.0, 0.0)
    wx0, wx1, wy0, wy1 = WEIGH
    s.box(wx0, wx1, wy0, wy1, 0.0, WEIGH_H, 'WallAlt', 'WeighHouse', visible=False)
    skin_building(s, wx0, wx1, wy0, wy1, WEIGH_H, 'N', 'WeighHouse', core='WallAlt', cornice=False)   # roof parapet
    for (x0, x1, y0, y1, lab) in [(wx0, wx1, wy0, wy0 + 0.4, 'S'), (wx0 + 3.0, wx1, wy1 - 0.4, wy1, 'N'),
                                  (wx1 - 0.4, wx1, wy0, wy1, 'E'), (wx0, wx0 + 0.4, wy0, wy1 - 3.0, 'W')]:
        s.box(x0, x1, y0, y1, WEIGH_H, WEIGH_H + 1.0, 'Trim', 'WeighHouse_Parapet_' + lab)
    # The stair goes up round the back (west side, in the street), by the drainpipe: 40 steps of 25 cm (27.5 cm
    # treads, 2.5 m wide) flush against the wall, then a 3 m landing level with the roof where the west parapet
    # leaves its gap. Playtest run 3 fix: the old top was one 34 cm step with a 10 cm gap to the roof, so the
    # navmesh never joined the roof to the street and a player had to perch across.
    stairs(s, wx0 - 1.25, wy0 + 1.0, wy1 - 3.0, 0.0, WEIGH_H, 2.5, 'Trim', 'WeighHouse_Stair')
    s.box(wx0 - 2.5, wx0, wy1 - 3.0, wy1, 0.0, WEIGH_H, 'Trim', 'WeighHouse_StairLanding')
    s.mesh(CYL, (wx0 + 0.4, wy0 - 0.15, WEIGH_H / 2), (0.25, 0.25, WEIGH_H), 'Metal', 'WeighHouse_Drainpipe')
    s.box(wx0 + 4.0, wx0 + 6.0, wy1 + 0.1, wy1 + 0.3, 0.0, 2.6, 'Door', 'WeighHouse_Door', collide=False)
    place('WeighHouseCorner', wx1 + 3.0, wy1 + 4.0, 0.0, 45.0)
    place('WeighHouseStair', wx0 - 2.5, wy0 - 0.5, 0.0, 90.0)
    place('WeighHouseRoof', (wx0 + wx1) / 2, (wy0 + wy1) / 2, WEIGH_H, 0.0)

    # The Lamplight inn (the Long Shelter in Frostside), front door on Bell Lane, cellar hatch at the side.
    lx0, lx1, ly0, ly1 = LAMPLIGHT
    s.box(lx0, lx1, ly0, ly1, 0.0, 12.0, 'Wall', 'Lamplight', visible=False)
    skin_building(s, lx0, lx1, ly0, ly1, 12.0, 'W', 'Lamplight', core='Wall')
    s.box(lx0 - 0.1, lx0 + 0.1, 14.0, 16.5, 0.0, 3.0, 'Door', 'Lamplight_Door', collide=False)
    s.box(lx0 + 6.0, lx0 + 8.0, ly0 - 1.6, ly0 - 0.1, 0.0, 0.25, 'Door', 'Lamplight_CellarHatch')
    s.cbox((lx0 - 0.5, 18.5, 3.4), (1.0, 2.6, 1.4), 'Stall', 'Lamplight_Sign', collide=False)
    place('Lamplight', lx0 - 2.0, 15.25, 0.0, 180.0)
    place('LamplightCellar', lx0 + 7.0, ly0 - 2.5, 0.0, 90.0)
    place('Intro', lx0 - 3.0, 11.0, 0.0, 57.0)
    place('BellLane', -40.0, 10.0, 0.0, 90.0)

    # The archive and its steps (the Ice Stairs in Frostside).
    ax0, ax1, ay0, ay1 = ARCHIVE
    s.box(ax0, ax1, ay0, ay1, 0.0, 16.0, 'WallAlt', 'Archive', visible=False)
    skin_building(s, ax0, ax1, ay0, ay1, 16.0, 'E', 'Archive', core='WallAlt')
    s.box(-62.0, -52.0, 55.0, 90.0, 0.0, 2.5, 'Trim', 'Archive_Terrace')
    stairs_x(s, 72.5, -45.0, -52.0, 0.0, 2.5, 35.0, 'Trim', 'Archive_Steps')
    s.box(ax1 - 0.1, ax1 + 0.1, 70.0, 75.0, 2.5, 7.0, 'Door', 'Archive_Door', collide=False)
    for i, y in enumerate((60.0, 66.0, 79.0, 85.0)):
        s.prop('desk' if i % 2 == 0 else 'chair', (-58.0, y, 2.5), 90.0, 'Archive_Salon_%d' % i)
    s.prop('shelf', (-60.5, 72.5, 2.5), 90.0, 'Archive_Salon_Shelf')
    place('ArchiveSteps', -43.0, 72.5, 0.0, 180.0)
    place('ArchiveTerrace', -57.0, 72.5, 2.5, 0.0)

    # Lantern Row (the Bone Market in Frostside): stalls along the north kerb of the y=35 street, x 46..136.
    for i, x in enumerate(range(50, 138, 11)):
        s.box(x - 1.6, x + 1.6, 38.4, 39.6, 0.0, 1.0, 'Stall', 'Stall_%02d_Counter' % i)
        s.box(x - 1.8, x + 1.8, 37.6, 40.0, 2.5, 2.62, 'Canvas', 'Stall_%02d_Canopy' % i, collide=False)
        for px in (x - 1.7, x + 1.7):
            s.box(px - 0.06, px + 0.06, 39.7, 39.86, 0.0, 2.5, 'Metal', 'Stall_%02d_Pole' % i, collide=False)
        if i % 2 == 0:
            s.prop('crate', (x + 2.4, 39.2, 0.0), 15.0 * i, 'Stall_%02d_Crate' % i)
    place('LanternRow', 70.0, 35.0, 0.0, 180.0)
    place('LanternRowEast', 110.0, 35.0, 0.0, 180.0)
    place('Furnace', 60.0, 29.0, 0.0, 90.0)
    place('ThraleShop', 75.0, 29.0, 0.0, 90.0)
    place('VaneAtelier', 62.0, 41.5, 0.0, 270.0)

    # The Lantern Gate and its bridge onto the river (the Frozen Gate in Frostside).
    s.box(144.0, 148.0, 26.0, 30.0, 0.0, 11.0, 'Trim', 'Gate_PillarS')
    s.box(144.0, 148.0, 40.0, 44.0, 0.0, 11.0, 'Trim', 'Gate_PillarN')
    s.box(144.0, 148.0, 26.0, 44.0, 8.5, 11.0, 'Trim', 'Gate_Lintel')
    s.box(150.0, 182.0, 30.0, 40.0, -0.8, 0.0, 'Trim', 'GateBridge_Deck')
    for (y0, y1, lab) in [(30.0, 30.4, 'S'), (39.6, 40.0, 'N')]:
        s.box(150.0, 182.0, y0, y1, 0.0, 1.0, 'Trim', 'GateBridge_Rail' + lab)
        s.box(150.0, 182.0, y0 - 0.5, y1 + 0.5, 1.0, 6.0, 'Trim', 'GateBridge_Blocker' + lab, visible=False)
    s.box(182.0, 184.0, 28.0, 42.0, 0.0, 5.0, 'WallAlt', 'GateBridge_FarWall')
    s.box(138.0, 141.0, 41.5, 44.5, 0.0, 3.0, 'WallAlt', 'Gate_WatchPost')
    place('LanternGate', 140.0, 35.0, 0.0, 180.0)
    place('GateBridge', 165.0, 35.0, 0.0, 180.0)
    place('WatchPost', 139.5, 40.5, 0.0, 270.0)
    # Drifters' camp under the gate (east part of the block south of Lantern Row).
    for i, (x, y) in enumerate([(126.0, 6.0), (133.0, 4.0), (139.0, 9.0), (128.0, 17.0), (136.0, 20.0)]):
        s.mesh(CONE, (x, y, 1.25), (3.4, 3.4, 2.5), 'Canvas', 'Camp_Tent_%d' % i)
    s.prop('crate', (131.0, 12.0, 0.0), 30.0, 'Camp_Crate')
    place('DrifterCamp', 131.0, 12.0, 0.0, 0.0)
    # Yard with Sorrel's shed (Frostside) behind the Row.
    s.box(84.0, 89.0, -4.0, 1.0, 0.0, 3.2, 'WallAlt', 'Yard_Shed')
    s.box(86.0, 87.5, 1.0, 1.2, 0.0, 2.2, 'Door', 'Yard_ShedDoor', collide=False)
    place('Shed', 86.5, 3.0, 0.0, 270.0)
    place('Yard', 85.0, 6.0, 0.0, 0.0)

    # Muster yard (walled, open to the street on the south).
    mx0, mx1 = COLS[4]
    my0, my1 = ROWS[1]
    for (x0, x1, y0, y1, lab) in [(mx0, mx1, my1 - 0.6, my1, 'N'), (mx0, mx0 + 0.6, my0, my1, 'W'), (mx1 - 0.6, mx1, my0, my1, 'E'),
                                  (mx0, mx0 + 12.0, my0, my0 + 0.6, 'SW'), (mx1 - 12.0, mx1, my0, my0 + 0.6, 'SE')]:
        s.box(x0, x1, y0, y1, 0.0, 3.0, 'WallAlt', 'Muster_Wall' + lab)
    for i in range(4):
        s.prop('crate', (mx0 + 4.0 + i * 2.2, my1 - 3.0, 0.0), 10.0 * i, 'Muster_Crate_%d' % i)
    place('MusterYard', (mx0 + mx1) / 2, (my0 + my1) / 2, 0.0, 270.0)
    place('IceWall', 0.0, 140.0, 0.0, 90.0)

    # Barracks (long low blocks).
    s.box(-140.0, -107.0, -100.0, -70.0, 0.0, 8.0, 'WallAlt', 'Barracks_West', visible=False)
    skin_building(s, -140.0, -107.0, -100.0, -70.0, 8.0, 'N', 'Barracks_West', core='WallAlt')
    s.box(-124.5, -122.5, -70.0 + 0.1, -69.7, 0.0, 2.6, 'Door', 'Barracks_West_Door', collide=False)
    s.box(107.0, 140.0, -100.0, -70.0, 0.0, 8.0, 'WallAlt', 'Barracks_East', visible=False)
    skin_building(s, 107.0, 140.0, -100.0, -70.0, 8.0, 'N', 'Barracks_East', core='WallAlt')
    s.box(122.5, 124.5, -70.0 + 0.1, -69.7, 0.0, 2.6, 'Door', 'Barracks_East_Door', collide=False)
    place('BarracksWest', -123.5, -67.0, 0.0, 90.0)
    place('BarracksEast', 123.5, -67.0, 0.0, 90.0)

    # Coal Lane (y=-60) tram stop and Hester's doorstep; the laundry; Wick Street infirmary.
    s.box(58.0, 62.0, -55.0, -54.4, 0.0, 2.6, 'Metal', 'TramStop_Back', collide=False)
    s.box(57.8, 62.2, -56.6, -54.2, 2.6, 2.75, 'Metal', 'TramStop_Roof', collide=False)
    s.box(58.3, 61.7, -55.6, -55.0, 0.0, 0.5, 'Stall', 'TramStop_Bench')
    place('CoalLaneStop', 60.0, -57.5, 0.0, 270.0)
    place('HesterDoorstep', 18.0, -57.0, 0.0, 90.0)
    place('CoalLaneLaundry', 75.0, -57.0, 0.0, 90.0)
    place('WickStreet', -70.0, -62.5, 0.0, 270.0)

    # Kerbside lamps along every street, the canal walks, the plaza and the square.
    li = 0
    for x in X_STREETS:
        for y in range(-130, 135, 24):
            if CANAL[0] - 2 < y < CANAL[1] + 2:
                continue
            if x == -40.0 and -10 < y < 32:      # Bell Lane has its own three lamps
                continue
            if x == -100.0 and -12 < y < 8:      # the Weigh-House stair is here
                continue
            off = 4.2 if (li % 2) else -4.2
            s.lamp(x + off, float(y), 'Lamp_X%d_%d' % (x, y), face=(-1.0 if off > 0 else 1.0, 0.0))
            li += 1
    for y in Y_STREETS:
        for x in range(-128, 134, 24):
            if any(abs(x - sx) < 6 for sx in X_STREETS):
                continue
            if y == 35.0 and x > 44:
                yy = 31.0
            else:
                yy = y + (4.2 if (li % 2) else -4.2)
            s.lamp(float(x), yy, 'Lamp_Y%d_%d' % (y, x), face=(0.0, 1.0 if y > yy else -1.0))
            li += 1
    for x in range(-130, 140, 20):
        if any(abs(x - sx) < 7 for sx in X_STREETS):
            continue
        s.lamp(float(x), CANAL[1] + 1.2, 'Lamp_CanalN_%d' % x, face=(0.0, 1.0))
        s.prop('bollard', (float(x) + 5.0, CANAL[1] + 0.9, 0.0), 0.0, 'Bollard_N_%d' % x)
    for (x, y) in [(-30.0, 45.0), (30.0, 45.0), (-30.0, 95.0), (30.0, 95.0)]:
        d = math.hypot(TOWER[0] - x, TOWER[1] - y)
        s.lamp(x, y, 'Lamp_Plaza_%d_%d' % (x, y), lit=True, face=((TOWER[0] - x) / d, (TOWER[1] - y) / d))
    # Bell Lane's three failing lamps (Spot_BellLaneLamp1..3), 8 m apart on the inn side.
    for i, y in enumerate((4.0, 12.0, 20.0)):
        s.lamp(-36.4, y, 'Lamp_BellLane_%d' % (i + 1), lit=False, face=(-1.0, 0.0))
        place('BellLaneLamp%d' % (i + 1), -37.6, y, 0.0, 0.0)
    place('Square_Cistern', -65.0, 9.5, 0.0, 90.0)


def build_tower(s):
    """Same footprint on every side: Pewterside's is a solid stump with rubble steps, Giltside's is hollow and
    sealed (page inside), Frostside's is hollow, door-less, with ramps up to the arena on its crown."""
    cx, cy = TOWER
    t, h = TOWER_HALF, TOWER_H
    w = 0.8
    if s.name == 'Pewterside':
        s.box(cx - t, cx + t, cy - t, cy + t, 0.0, 8.0, 'Tower', 'Tower_Stump')
        for i in range(20):   # rubble steps down the east side, so a hero who lands on top can climb down
            z = (i + 1) * 0.4
            s.box(cx + t, cx + t + 0.6 * (20 - i), cy - 2.0, cy + 2.0, 0.0, z, 'Trim', 'Tower_Rubble_%02d' % i)
        return
    for (x0, x1, y0, y1, lab) in [(cx - t, cx + t, cy + t - w, cy + t, 'N'), (cx - t, cx - t + w, cy - t, cy + t, 'W'),
                                  (cx + t - w, cx + t, cy - t, cy + t, 'E')]:
        s.box(x0, x1, y0, y1, 0.0, h, 'Tower', 'Tower_Wall' + lab)
    if s.name == 'Giltside':
        door_w, door_h = 3.0, 4.2
        s.box(cx - t, cx - door_w / 2, cy - t, cy - t + w, 0.0, h, 'Tower', 'Tower_WallS_L')
        s.box(cx + door_w / 2, cx + t, cy - t, cy - t + w, 0.0, h, 'Tower', 'Tower_WallS_R')
        s.box(cx - door_w / 2, cx + door_w / 2, cy - t, cy - t + w, door_h, h, 'Tower', 'Tower_Lintel')
        s.box(cx - t, cx + t, cy - t, cy + t, h, h + 0.6, 'Trim', 'Tower_Roof')
        s.box(cx - t - 0.5, cx + t + 0.5, cy - t - 0.5, cy + t + 0.5, h + 0.6, h + 1.4, 'Trim', 'Tower_Crown')
        door = s.spawn(unreal.ReflectionsSealedDoor, (cx, cy - t + w / 2, 0.0), (0, 0, 90.0), label='Tower_SealedDoor')
        door.set_editor_property('door_size', unreal.Vector(w * 100.0 + 10.0, door_w * 100.0, door_h * 100.0))
        door.set_editor_property('required_key', 'GiltTowerKey')
        return
    # Frostside: sealed shell, ramps up the inside, open crown platform (the villain arena).
    s.box(cx - t, cx + t, cy - t, cy - t + w, 0.0, h, 'Tower', 'Tower_WallS')
    inner = t - w          # 6.2
    lw = 2.5               # ramp and landing width
    rise = 3.0
    corners = {'SW': (-1, -1), 'SE': (1, -1), 'NE': (1, 1), 'NW': (-1, 1)}
    order = ['SW', 'SE', 'NE', 'NW']
    run = 2 * inner - 2 * lw
    for k in range(9):
        cname = order[k % 4]
        sx, sy = corners[cname]
        z = k * rise
        lx = cx + sx * (inner - lw / 2)
        ly = cy + sy * (inner - lw / 2)
        if k > 0:
            s.box(lx - lw / 2, lx + lw / 2, ly - lw / 2, ly + lw / 2, z - 0.4, z, 'Trim', 'Tower_Landing_%d' % k)
        col, cd_, rad = FROST_TOWER_LIGHT
        s.light((lx - sx * 0.6, ly - sy * 0.6, z + 2.2), col, cd_, rad, 'Tower_LandingGlow_%d' % k)
        if k == 8:
            break
        nxt = order[(k + 1) % 4]
        nx, ny = corners[nxt]
        # Ramp along the wall between this corner and the next.
        mx = cx + (sx + nx) / 2.0 * (inner - lw / 2) if sx == nx else cx
        my = cy + (sy + ny) / 2.0 * (inner - lw / 2) if sy == ny else cy
        length = math.hypot(run, rise)
        pitch = math.degrees(math.atan2(rise, run))
        if sy == ny:      # along X
            yaw = 0.0 if nx > sx else 180.0
        else:             # along Y
            yaw = 90.0 if ny > sy else 270.0
        s.mesh(CUBE, (mx, my, z + rise / 2 - 0.2), (length + 0.3, lw, 0.4), 'Trim', 'Tower_Ramp_%d' % k, rot=(0.0, pitch, yaw))
    # Crown: a wide platform with a slot over the last ramp (west wall) and its landing.
    top = h
    slot_x1 = cx - inner + lw
    s.box(slot_x1, cx + t, cy - t, cy + t, top - 0.5, top, 'Trim', 'Tower_CrownInner')
    # The crown reaches east past the tower so the arena (centre ARENA, 10 m radius) is flat and clear of the slot.
    ce = CROWN_EAST
    s.box(cx - 13.0, cx + ce, cy - 13.0, cy - t, top - 0.6, top, 'Trim', 'Tower_CrownS')
    s.box(cx - 13.0, cx + ce, cy + t, cy + 13.0, top - 0.6, top, 'Trim', 'Tower_CrownN')
    s.box(cx - 13.0, cx - t, cy - t, cy + t, top - 0.6, top, 'Trim', 'Tower_CrownW')
    s.box(cx + t, cx + ce, cy - t, cy + t, top - 0.6, top, 'Trim', 'Tower_CrownE')
    for (x0, x1, y0, y1, lab) in [(cx - 13.0, cx + ce, cy + 12.4, cy + 13.0, 'N'), (cx - 13.0, cx + ce, cy - 13.0, cy - 12.4, 'S'),
                                  (cx - 13.0, cx - 12.4, cy - 13.0, cy + 13.0, 'W'), (cx + ce - 0.6, cx + ce, cy - 13.0, cy + 13.0, 'E')]:
        s.box(x0, x1, y0, y1, top, top + 1.2, 'Trim', 'Tower_CrownParapet' + lab)
    # Rails round the open slot over the last ramp; the ramp comes up onto the south-west landing, which stays open.
    s.box(slot_x1, slot_x1 + 0.2, cy - inner + lw, cy + inner + 0.8, top, top + 1.1, 'Trim', 'Tower_SlotRailE')
    s.box(cx - inner - 0.2, cx - inner, cy - inner + lw, cy + inner + 0.8, top, top + 1.1, 'Trim', 'Tower_SlotRailW')
    s.box(cx - inner - 0.2, slot_x1 + 0.2, cy + inner + 0.6, cy + inner + 0.8, top, top + 1.1, 'Trim', 'Tower_SlotRailN')
    # Cracks: a few slipped wall chunks outside.
    for i, (x, y, z) in enumerate([(cx + t + 0.3, cy - 2.0, 9.0), (cx - t - 0.3, cy + 3.0, 15.0), (cx + 1.5, cy + t + 0.3, 5.0)]):
        s.cbox((x, y, z), (0.8, 2.2, 1.6), 'WallAlt', 'Tower_Crack_%d' % i, rot=(12.0 * (i + 1), 0.0, 0.0))


def build_side_specific(s):
    """Pickups, the key, side mood (fog), the anchor, the arena."""
    cx, cy = TOWER
    n = s.name
    anchor = s.spawn(unreal.ReflectionsWorldAnchor, (0.0, 0.0, 0.0), label='WorldAnchor_' + n)
    anchor.set_editor_property('world', WORLD_ENUM[n])

    def coin(world, loc, label):
        c = s.spawn(unreal.ReflectionsCoinPickup, loc, label=label)
        c.set_editor_property('coin_world', WORLD_ENUM[world])

    def page(pid, loc, label):
        p = s.spawn(unreal.ReflectionsBookPagePickup, loc, label=label)
        p.set_editor_property('page_id', pid)

    wx0, wx1, wy0, wy1 = WEIGH
    if n == 'Giltside':
        page('GiltTowerPage', (cx + 2.0, cy + 2.0, 1.0), 'Page_GiltTower')
        coin('Frostside', (cx - 2.5, cy + 2.5, 1.0), 'Shard_Frost_InGiltTower')
        coin('Pewterside', (-37.5, 6.0, 1.0), 'Shard_Pew_Start1')
        coin('Pewterside', (-38.5, 3.5, 1.0), 'Shard_Pew_Start2')
        coin('Pewterside', (-60.0, 6.0, 1.0), 'Shard_Pew_BellSquare')
        coin('Frostside', (96.0, 33.0, 1.0), 'Shard_Frost_LanternRow')
        s.cbox((139.5, 37.0, 0.5), (1.0, 1.0, 1.0), 'Trim', 'Key_Pedestal')
        s.spawn(unreal.ReflectionsKeyPickup, (139.5, 37.0, 1.6), label='Key_GiltTower')
    elif n == 'Pewterside':
        page('WeighHousePage', ((wx0 + wx1) / 2 + 2.0, (wy0 + wy1) / 2, WEIGH_H + 1.0), 'Page_WeighHouse')
        coin('Giltside', ((wx0 + wx1) / 2 - 2.0, (wy0 + wy1) / 2 + 2.0, WEIGH_H + 1.0), 'Shard_Gilt_WeighHouseRoof')
        coin('Giltside', (60.0, -57.0, 1.0), 'Shard_Gilt_CoalLane')
        coin('Giltside', (-62.0, 9.0, 1.0), 'Shard_Gilt_Square')
        coin('Frostside', (67.5, -29.0, 1.0), 'Shard_Frost_FishSteps')
    else:
        page('FrostTowerPage', (cx + 1.0, cy + 1.0, 1.0), 'Page_FrostTower')
        coin('Giltside', (cx - 2.0, cy - 2.0, 1.0), 'Shard_Gilt_InFrostTower')
        coin('Giltside', (cx - 2.0, cy - 10.0, TOWER_H + 1.0), 'Shard_Gilt_FrostCrown')
        coin('Giltside', (70.0, 33.0, 1.0), 'Shard_Gilt_BoneMarket')
        coin('Pewterside', (75.0, 33.0, 1.0), 'Shard_Pew_BoneMarket')
        arena_cls = getattr(unreal, 'ReflectionsVillainArena', None)
        if arena_cls:
            arena = s.spawn(arena_cls, (ARENA[0], ARENA[1], TOWER_H), (0, 0, 270.0), label='VillainArena_FrostCrown')
            try:
                arena.set_editor_property('arena_radius', 1000.0)   # flat, clear and inside the 1.2 m parapet
            except Exception as e:  # noqa: BLE001
                log('arena radius: %s' % e)
            log('arena placed')
    # Mood: a local fog volume over the city, if this engine has them.
    fog_cls = getattr(unreal, 'LocalFogVolume', None)
    if fog_cls:
        fog = s.spawn(fog_cls, (0.0, 0.0, 0.0), scale=(32.0, 32.0, 6.0), label='Mood_LocalFog')
        comp = fog.get_component_by_class(unreal.LocalFogVolumeComponent) if hasattr(unreal, 'LocalFogVolumeComponent') else None
        settings = {'Pewterside': (0.35, 0.25, (0.55, 0.57, 0.6)), 'Giltside': (0.2, 0.15, (0.9, 0.62, 0.35)),
                    'Frostside': (0.1, 0.06, (0.62, 0.74, 0.9))}[n]   # was 0.45 / 0.3: a white-out from the crown
        if comp:
            for prop, val in (('radial_fog_extinction', settings[0]), ('height_fog_extinction', settings[1]),
                              ('fog_albedo', unreal.LinearColor(*settings[2], 1.0))):
                try:
                    comp.set_editor_property(prop, val)
                except Exception as e:  # noqa: BLE001
                    log('fog %s: %s' % (prop, e))
        log('fog placed')
    # Giltside's warmth: a handful of extra lanterns round the square and the inn door.
    if n == 'Giltside':
        for i, (x, y) in enumerate([(-45.5, 0.0), (-45.5, 28.0), (-84.0, 29.0), (-36.5, 14.0)]):
            s.light((x, y, 3.2), (1.0, 0.58, 0.25), 40.0, 12.0, 'Lantern_Extra_%d' % i)


SQUADS = {  # side -> (label, formation, size, casters, speed, loop, halt s, points in local m)
    'Giltside': ('Gilt_LampCompany', 'COLUMN', 5, 2, 150.0, True, 0.0,
                 [(-100.0, 35.0), (100.0, 35.0), (100.0, -60.0), (-100.0, -60.0)]),
    'Frostside': ('Frost_WallCompany', 'LINE', 5, 2, 150.0, False, 3.0, [(-130.0, 105.0), (130.0, 105.0)]),
    'Pewterside': ('Pew_Constables', 'COLUMN_OF_TWOS', 4, 1, 130.0, False, 2.0, [(-130.0, -60.0), (130.0, -60.0)]),
}


def build_squads(s):
    """One patrol per side (squads session's spec): a route and its spawner in the same level. Peaceful until hit."""
    if not hasattr(unreal, 'ReflectionsSquadRoute') or not hasattr(unreal, 'ReflectionsSquad'):
        log('squads: classes missing')
        return
    label, form, size, casters, speed, loop, halt, pts = SQUADS[s.name]
    x0, y0 = pts[0]
    route = s.spawn(unreal.ReflectionsSquadRoute, (x0, y0, 1.0), label='SquadRoute_' + label)
    route.set_points([unreal.Vector(x * 100.0, y * 100.0, 100.0) for (x, y) in pts], loop)
    route.set_editor_property('halt_seconds', halt)
    squad = s.spawn(unreal.ReflectionsSquad, (x0, y0, 1.0), label='Squad_' + label)
    squad.set_editor_property('route', route)
    squad.set_editor_property('formation', getattr(unreal.ReflectionsSquadFormation, form))
    squad.set_editor_property('squad_size', size)
    squad.set_editor_property('caster_count', casters)
    squad.set_editor_property('march_speed', speed)
    if s.name != 'Frostside':   # Frost Wall Company keeps the squads defaults (spots the hero at 22 m)
        squad.set_editor_property('sight_radius', 0.0)
        squad.set_editor_property('alert_radius', 0.0)
    log('squad %s: %d points loop=%s' % (label, route.get_num_points(), loop))


def nav_bounds(s):
    """Nav mesh bounds over the island (needs SetVolumeBox from train #8; until then the marker pass adds it)."""
    if not hasattr(L, 'set_volume_box'):
        log('nav bounds: pending SetVolumeBox (after train #8)')
        return
    v = s.spawn(unreal.NavMeshBoundsVolume, (15.0, 0.0, 15.0), label='NavBounds_' + s.name)
    ok = L.set_volume_box(v, unreal.Vector(17000.0, 16000.0, 2500.0))
    log('nav bounds %s: %s' % (s.name, ok))


# ---- Story markers ------------------------------------------------------------------------------------------------
MARKER_SIDE = {'Pewterside': 'PEWTERSIDE', 'Giltside': 'GILTSIDE', 'Frostside': 'FROSTSIDE'}
NEAR = {  # people.json place keys -> layout places
    'LanternRow': 'LanternRow', 'LanternGate': 'LanternGate', 'Lamplight': 'Lamplight', 'BellLane': 'BellLane',
    'Archive': 'ArchiveSteps', 'Vane': 'VaneAtelier', 'BellSquare': 'BellSquare', 'GiltTower': 'TowerFoot',
    'Furnace': 'Furnace', 'Muster': 'MusterYard', 'CoalLane': 'CoalLaneStop', 'FishSteps': 'FishSteps',
    'WickStreet': 'WickStreet', 'WeighHouse': 'WeighHouseCorner', 'IceStairs': 'ArchiveSteps', 'BoneMarket': 'LanternRow',
    'FrozenGate': 'LanternGate', 'IceWall': 'IceWall', 'Hester': 'HesterDoorstep', 'Canal': 'CanalRift',
    'ThraleShop': 'ThraleShop', 'UnderGate': 'DrifterCamp', 'Sorrel': 'Shed', 'LongShelter': 'Lamplight',
}
# Named places: marker name -> (layout place or (x, y, z, yaw), radius cm, extra tags)
NAMED = {
    'Giltside': {
        'Mk_Gilt_Camp_UnderGate': ('DrifterCamp', 900, ['Home_kit_marrow', 'Home_fen_lowry']),
        'Mk_Gilt_Cellar_Lamplight': ('LamplightCellar', 300, ['Home_hal_fairweather']),
        'Mk_Gilt_Gate_LanternGate': ('LanternGate', 900, ['Mk_Gilt_Gate']),
        'Mk_Gilt_Home_Barracks': ('BarracksWest', 400, ['Home_sela_brask']),
        'Mk_Gilt_Home_WatchBarracks': ('BarracksEast', 400, ['Home_nell_bramley']),
        'Mk_Gilt_Inn_Lamplight': ('Lamplight', 500, ['Home_goldie_fairweather', 'Mk_Gilt_Inn', 'Haunt_Tavern']),
        'Mk_Gilt_Lane_BellLane': ('BellLane', 1000, []),
        'Mk_Gilt_Market_LanternRow': ('LanternRow', 1500, ['Mk_Gilt_Market', 'Haunt_Market']),
        'Mk_Gilt_Rift_Canal': ('CanalRift', 500, []),
        'Mk_Gilt_Square_BellSquare': ('BellSquare', 1200, ['Mk_Gilt_Square', 'Haunt_Square']),
        'Mk_Gilt_Steps_Archive': ('ArchiveSteps', 800, []),
        'Mk_Gilt_Tower_GiltTower': ('TowerFoot', 500, []),
        'Mk_Gilt_Workshop_Furnace': ('Furnace', 400, ['Mk_Gilt_Workshop']),
        'Mk_Gilt_Workshop_ThraleShop': ('ThraleShop', 400, []),
        'Mk_Gilt_Workshop_Vane': ('VaneAtelier', 400, []),
        'Mk_Gilt_Yard_Muster': ('MusterYard', 1200, []),
        'Haunt_Bridge': ('GateBridge', 600, []),
        'Item_Fiddle': ((-60.0, 16.0, 0.0, 0.0), 150, []),
        'CutsceneAnchor_Intro': ('Intro', 300, []),
        'CutsceneAnchor_BurningEyes': ((-71.0, 8.0, 0.0, 45.0), 300, []),
        'CutsceneAnchor_GiltTower': ((0.0, 61.5, 0.0, 90.0), 300, []),
        'Spot_BellLaneLamp1': ('BellLaneLamp1', 200, ['Mk_Gilt_Lane_BellLane_Lamp1']),
        'Spot_BellLaneLamp2': ('BellLaneLamp2', 200, ['Mk_Gilt_Lane_BellLane_Lamp2']),
        'Spot_BellLaneLamp3': ('BellLaneLamp3', 200, ['Mk_Gilt_Lane_BellLane_Lamp3']),
    },
    'Pewterside': {
        'Mk_Pew_Doorstep_Hester': ('HesterDoorstep', 500, ['Home_hester_quaile', 'Home_sid_kettle']),
        'Mk_Pew_Infirmary_WickStreet': ('WickStreet', 400, ['Mk_Pew_Infirmary']),
        'Mk_Pew_Laundry_CoalLane': ('CoalLaneLaundry', 400, ['Mk_Pew_Laundry']),
        'Mk_Pew_Square_WeighHouse': ('WeighHouseCorner', 1000, ['Mk_Pew_Square']),
        'Mk_Pew_Stair_WeighHouse': ('WeighHouseStair', 300, []),
        'Mk_Pew_Steps_FishSteps': ('FishSteps', 700, ['Mk_Pew_Market']),
        'Mk_Pew_Stop_CoalLane': ('CoalLaneStop', 500, ['Mk_Pew_Stop']),
        'CutsceneAnchor_FirstPage': ((-89.0, -1.5, 10.0, 0.0), 300, []),
    },
    'Frostside': {
        'Mk_Frost_Cistern': ('Square_Cistern', 800, ['Mk_Frost_Square']),
        'Mk_Frost_Gate_FrozenGate': ('LanternGate', 900, ['Mk_Frost_Gate']),
        'Mk_Frost_Market_BoneMarket': ('LanternRow', 1500, ['Mk_Frost_Market']),
        'Mk_Frost_Shed_Sorrel': ('Shed', 400, ['Home_sorrel_vey', 'Home_petra_lisle', 'Mk_Frost_Workshop']),
        'Mk_Frost_Shelter_LongShelter': ('Lamplight', 600, ['Home_marta_quarry', 'Mk_Frost_Inn']),
        'Mk_Frost_Stair_IceStairs': ('ArchiveSteps', 800, []),
        'Mk_Frost_Tower_FrostTower': ((0.0, 70.0, 0.0, 90.0), 500, []),
        'Mk_Frost_Wall_IceWall': ('IceWall', 1500, []),
        'CutsceneAnchor_MirrorWhole': ((1.0, 71.0, 0.0, 90.0), 300, []),
        'CutsceneAnchor_Ending': ((ARENA[0], ARENA[1], TOWER_H, 270.0), 1000, []),
    },
}
# Named homes that sit at a door near a place (marker name, near place, extra tags).
NAMED_HOMES = {
    'Giltside': [('Mk_Gilt_Home_IlseAttic', 'LanternRow', ['Home_ilse_varrow']),
                 ('Mk_Gilt_Home_ThraleShop', 'ThraleShop', ['Home_barnaby_thrale', 'Home_ros_thrale'])],
    'Pewterside': [('Mk_Pew_Home_Ada', 'FishSteps', ['Home_ada_pollard']),
                   ('Mk_Pew_Home_PrattShop', 'WeighHouseCorner', ['Home_horace_pratt'])],
    'Frostside': [('Mk_Frost_Home_Barracks', 'IceWall', ['Home_brenna_cold', 'Home_eskil_varn']),
                  ('Mk_Frost_Home_Rook', 'ArchiveSteps', ['Home_mother_rook', 'Home_tilly_frane'])],
}


SOLIDS = []


def is_free(x, y, margin=1.0):
    if not SOLIDS:
        SOLIDS.extend((a[0], a[1], a[2], a[3]) for a in building_lots())
        SOLIDS.extend([WEIGH, LAMPLIGHT, ARCHIVE, (-62.0, -45.0, 55.0, 90.0),
                       (WEIGH[0] - 2.5, WEIGH[0], WEIGH[2] + 1.0, WEIGH[3]),     # the Weigh-House stair and landing
                       (TOWER[0] - TOWER_HALF, TOWER[0] + TOWER_HALF, TOWER[1] - TOWER_HALF, TOWER[1] + TOWER_HALF),
                       (-140.0, -107.0, -100.0, -70.0), (107.0, 140.0, -100.0, -70.0), (84.0, 89.0, -4.0, 1.0),
                       (-200.0, 200.0, CANAL[0] - 0.5, CANAL[1] + 0.5)])
    for (x0, x1, y0, y1) in SOLIDS:
        if x0 - margin < x < x1 + margin and y0 - margin < y < y1 + margin:
            return False
    return abs(x) < HALF - 2.0 and abs(y) < HALF - 2.0


def build_markers(s, places, doors):
    data = json.load(open(MARKER_JSON, encoding='utf-8'))
    side_enum = getattr(unreal.ReflectionsMarkerSide, MARKER_SIDE[s.name])
    placed = {}

    def put(name, where, radius, tags, note=''):
        if isinstance(where, str):
            x, y, z, yaw = places[where]
        else:
            x, y, z, yaw = where
        m = s.spawn(unreal.ReflectionsStoryMarker, (x, y, z), (0, 0, yaw), label=name)
        m.set_editor_property('marker_name', name)
        m.set_editor_property('side', side_enum)
        m.set_editor_property('radius', float(radius))
        if note:
            m.set_editor_property('notes', note)
        if tags:
            m.set_editor_property('tags', [unreal.Name(t) for t in tags])
        placed[name] = (round(x, 1), round(y, 1), round(z, 1), yaw, tags)
        return m

    # Every alias the content uses for a canonical name rides along as a tag.
    aliases = {}
    for e in data:
        if e.get('alias_of'):
            aliases.setdefault(e['alias_of'], []).append(e['name'])
        for a in e.get('aliases', []) or []:
            if not a.startswith('Mk_') or a.startswith('Mk_Gilt_Lane_BellLane_Lamp'):
                aliases.setdefault(e['name'], []).append(a)
    for name, (where, radius, tags) in NAMED[s.name].items():
        extra = [a for a in aliases.get(name, []) if a not in tags and a != name]
        put(name, where, radius, list(dict.fromkeys(tags + extra)), 'Mock city: ' + (where if isinstance(where, str) else 'spot'))
    used_doors = set()

    def door_near(key, offset=0):
        px, py = places[key][0], places[key][1]
        order = sorted(range(len(doors)), key=lambda i: (doors[i][0] - px) ** 2 + (doors[i][1] - py) ** 2)
        for i in order:
            if i not in used_doors:
                used_doors.add(i)
                return tuple(doors[i])
        return places[key]

    for name, near, tags in NAMED_HOMES[s.name]:
        put(name, door_near(near), 300, tags, 'Home door near ' + near)
    taken = {t for v in placed.values() for t in v[4]} | set(placed)
    generic_tag = {'Giltside': 'Mk_Gilt_Home', 'Pewterside': 'Mk_Pew_Home', 'Frostside': 'Mk_Frost_Home'}[s.name]
    first_generic = True
    for e in data:
        if e['side'] != s.name or e.get('optional') or e.get('alias_of'):
            continue
        n = e['name']
        if n in taken:
            continue
        near = NEAR.get(e.get('near') or '', None) or NEAR.get(e.get('place') or '', None)
        if n.startswith('Home_'):
            tags = [generic_tag] if first_generic else []
            first_generic = False
            put(n, door_near(near or 'BellSquare'), 300, tags, 'Home door near %s' % near)
        elif n.startswith('QuestGiver_'):
            px, py, pz, yaw = places[near or 'BellSquare']
            k = sum(1 for v in placed if v.startswith('QuestGiver_'))
            spot = (px, py)
            for j in range(24):   # first free spot on a spiral round the place, clear of buildings and other givers
                ang = math.radians((k * 137.5 + j * 47.0) % 360.0)
                r = 2.5 + 0.5 * (j // 6)
                cand = (px + r * math.cos(ang), py + r * math.sin(ang))
                if is_free(cand[0], cand[1]) and all((cand[0] - v[0]) ** 2 + (cand[1] - v[1]) ** 2 > 2.0 ** 2 for v in placed.values()):
                    spot = cand
                    break
            put(n, (spot[0], spot[1], pz, yaw), 250, [], 'Quest giver near %s' % near)
        elif n not in placed:
            log('marker without a spot: ' + n)
    out['markers_%s' % s.name] = len(placed)
    return placed


MARKER_JSON = unreal.Paths.project_dir() + 'ArtDirection/MockCity/tools/mockcity_markers.json'


def fresh_world(name):
    path = '%s/%s' % (ROOT, name)
    if EAL.does_asset_exist(path):
        EAL.delete_asset(path)
    # A force delete purges the package but can leave the .umap on disk; the file is ours, so remove it.
    disk = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()),
                        ROOT[len('/Game/'):], name + '.umap')
    if os.path.exists(disk):
        os.remove(disk)
        log('removed leftover ' + disk)
    unreal.SystemLibrary.collect_garbage()
    unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous([ROOT], True)
    factory = unreal.WorldFactory()
    for prop in ('create_world_partition', 'b_create_world_partition'):
        try:
            factory.set_editor_property(prop, False)
        except Exception:  # noqa: BLE001
            pass
    world = AT.create_asset(name, ROOT, unreal.World, factory)
    if world is None:
        raise RuntimeError('could not create ' + path)
    return world


def make_mats():
    base = unreal.load_asset('/Engine/BasicShapes/BasicShapeMaterial')
    mif = unreal.MaterialInstanceConstantFactoryNew()
    made = 0
    for side, cols in COLORS.items():
        for part, c in cols.items():
            name = 'MI_Mock_%s_%s' % (side, part)
            path = '%s/Materials/%s' % (ROOT, name)
            mi = unreal.load_asset(path) if EAL.does_asset_exist(path) else AT.create_asset(
                name, ROOT + '/Materials', unreal.MaterialInstanceConstant, mif)
            mi.set_editor_property('parent', base)
            unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(mi, 'Color', unreal.LinearColor(c[0], c[1], c[2], 1.0))
            EAL.save_asset(path, only_if_is_dirty=False)
            made += 1
    log('materials: %d' % made)


def build_side(name):
    world = fresh_world('Lvl_MockCity_' + name)
    s = Side(name, world)
    build_common(s)
    build_tower(s)
    build_side_specific(s)
    try:
        nav_bounds(s)
    except Exception as e:  # noqa: BLE001
        log('nav error: %s' % e)
    try:
        build_squads(s)
    except Exception as e:  # noqa: BLE001
        log('squads error: %s' % e)
    out['kit'] = flush_kit(s)
    places = {k: v for k, v in PLACES.items() if not k.startswith('_')}
    placed = build_markers(s, places, PLACES.get('_doors', []))
    ok = EAL.save_asset(world.get_path_name().split('.')[0], only_if_is_dirty=False)
    log('built Lvl_MockCity_%s saved=%s' % (name, ok))
    with open(unreal.Paths.project_saved_dir() + 'MockCity_markers_%s.json' % name, 'w') as f:
        json.dump({'places': places, 'markers': placed}, f, indent=0)


# Sidewalk lane offsets from a block edge (m), per (col, row, side) where it must dodge lamps, stalls or stairs.
LANE_OFFSET = 2.6
LANE_OVERRIDE = {(1, 2, 'W'): 4.5, (2, 2, 'W'): 3.2, (3, 1, 'S'): 4.0, (4, 1, 'S'): 4.0,
                 (4, 2, 'E'): 1.2, (4, 1, 'E'): 1.2}
for _c in range(5):
    LANE_OVERRIDE[(_c, 2, 'S')] = 1.6     # the narrow north canal walk, inside its lamps


def lane_profile_struct():
    ref = unreal.ZoneLaneProfileRef()
    try:
        ref.import_text('(Name="CitySidewalk",ID=5C17E0A12B3D4E5F6A7B8C9D0E1F2A3B)')
    except Exception as e:  # noqa: BLE001
        log('lane profile import_text: %s' % e)
    return ref


def build_lanes(s):
    """One closed sidewalk loop per block (4 spline shapes: side midpoint -> corner -> next midpoint), for every side,
    at final world coordinates in the persistent level (built ZoneGraph data has no level-transform support)."""
    if not hasattr(unreal, 'ZoneShape'):
        log('lanes: ZoneShape class missing')
        return
    prof = lane_profile_struct()
    pt_sharp = unreal.FZoneShapePointType.SHARP
    pt_bez = unreal.FZoneShapePointType.AUTO_BEZIER
    made = 0
    first_check = None
    for side in SIDES:
        ox = OFFSET_X[side] / 100.0
        for ci, (x0, x1) in enumerate(COLS):
            for ri, (y0, y1) in enumerate(ROWS):
                off = {k: LANE_OVERRIDE.get((ci, ri, k), LANE_OFFSET) for k in 'NESW'}
                xa, xb = x0 - off['W'], x1 + off['E']
                ya, yb = y0 - off['S'], y1 + off['N']
                z = 0.03
                corners = [(xb, ya), (xb, yb), (xa, yb), (xa, ya)]          # SE, NE, NW, SW (counter-clockwise)
                mids = [((xa + xb) / 2, ya), (xb, (ya + yb) / 2), ((xa + xb) / 2, yb), (xa, (ya + yb) / 2)]  # S, E, N, W
                cx, cy = (xa + xb) / 2, (ya + yb) / 2
                for k in range(4):
                    seg = [mids[k], corners[k], mids[(k + 1) % 4]]
                    a = s.spawn(unreal.ZoneShape, (ox + cx, cy, z), label='%s_Lane_%d%d_%d' % ({'Pewterside': 'Gray', 'Giltside': 'Red', 'Frostside': 'White'}[side], ci, ri, k))
                    try:
                        a.set_folder_path('CrowdLanes')
                    except Exception:  # noqa: BLE001
                        pass
                    comp = a.get_component_by_class(unreal.ZoneShapeComponent)
                    pts = []
                    for j, (px_, py_) in enumerate(seg):
                        p = unreal.ZoneShapePoint()
                        p.set_editor_property('position', unreal.Vector((px_ - cx) * 100.0, (py_ - cy) * 100.0, 0.0))
                        p.set_editor_property('type', pt_bez if j == 1 else pt_sharp)
                        pts.append(p)
                    comp.set_editor_property('shape_type', unreal.FZoneShapeType.SPLINE)
                    comp.set_editor_property('points', pts)
                    try:
                        comp.set_editor_property('lane_profile', prof)
                    except Exception as e:  # noqa: BLE001
                        log('lane profile set: %s' % e)
                    if first_check is None:
                        try:
                            first_check = comp.get_editor_property('lane_profile').export_text()
                        except Exception as e:  # noqa: BLE001
                            first_check = 'read back failed: %s' % e
                    made += 1
    log('lanes: %d shapes, profile %s' % (made, first_check))


def build_persistent():
    world = fresh_world('Lvl_MockCity')
    s = Side('Giltside', world)
    sun = s.spawn(unreal.DirectionalLight, (150.0, 0.0, 50.0), (0, -24, -58), label='Sun')
    light = sun.get_component_by_class(unreal.DirectionalLightComponent)
    light.set_editor_property('mobility', unreal.ComponentMobility.MOVABLE)
    light.set_editor_property('atmosphere_sun_light', True)
    light.set_editor_property('intensity', 5.0)
    light.set_editor_property('light_color', unreal.Color(255, 214, 170, 255))
    sky = s.spawn(unreal.SkyLight, (150.0, 0.0, 60.0), label='SkyLight')
    sky_comp = sky.get_component_by_class(unreal.SkyLightComponent)
    sky_comp.set_editor_property('mobility', unreal.ComponentMobility.MOVABLE)
    sky_comp.set_editor_property('real_time_capture', True)
    s.spawn(unreal.SkyAtmosphere, (0.0, 0.0, 0.0), label='SkyAtmosphere')
    fog = s.spawn(unreal.ExponentialHeightFog, (0.0, 0.0, 0.0), label='HeightFog')
    fog.get_component_by_class(unreal.ExponentialHeightFogComponent).set_editor_property('fog_density', 0.006)
    # The game starts in Giltside, outside the Lamplight, facing the towers (CutsceneAnchor_Intro).
    gx = OFFSET_X['Giltside'] / 100.0
    lx0 = LAMPLIGHT[0]
    s.spawn(unreal.PlayerStart, (gx + lx0 - 3.0, 11.0, 1.0), (0, 0, 57.0), label='PlayerStart_Giltside')
    try:
        build_lanes(s)
    except Exception as e:  # noqa: BLE001
        log('lanes error: %s' % e)
    nav = s.spawn(unreal.RecastNavMesh, (0.0, 0.0, 0.0), label='RecastNavMesh_MockCity')
    try:
        nav.set_editor_property('runtime_generation', unreal.RuntimeGenerationType.DYNAMIC)
        # Recast's ledge-slope filter marks every 25 cm stair step as a ledge (neighbours span > ~30 cm), so the
        # Weigh-House stair never joined the roof. Drops still split the navmesh with the filter off.
        nav.set_editor_property('ledge_slope_filter_mode', unreal.NavigationLedgeSlopeFilterMode.NONE)
        log('navmesh runtime generation dynamic, ledge slope filter off')
    except Exception as e:  # noqa: BLE001
        log('navmesh rg: %s' % e)
    for name in SIDES:
        level = unreal.load_asset('%s/Lvl_MockCity_%s' % (ROOT, name))
        st = L.add_offset_sublevel(world, level, unreal.Transform(location=[OFFSET_X[name], 0.0, 0.0]))
        log('sublevel %s: %s' % (name, st is not None))
    try:
        settings = world.get_world_settings()
    except Exception:  # noqa: BLE001
        settings = None
    if settings:
        gm = unreal.load_class(None, '/Script/reflections.ReflectionsSampleGameMode')
        settings.set_editor_property('default_game_mode', gm)
    ok = EAL.save_asset(world.get_path_name().split('.')[0], only_if_is_dirty=False)
    log('built Lvl_MockCity saved=%s' % ok)


if unreal.EditorLevelLibrary.get_game_world() is not None:
    out['error'] = 'PIE is running; not building.'
else:
    what = ARGS[0] if ARGS else ''
    if what == 'mats':
        make_mats()
    elif what in SIDES:
        build_side(what)
    elif what == 'persistent':
        build_persistent()
    else:
        out['error'] = 'unknown arg ' + what
json.dumps(out)
