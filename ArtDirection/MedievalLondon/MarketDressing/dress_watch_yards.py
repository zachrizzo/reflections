"""Place existing medieval market and watch-yard meshes, or survey them first."""

import math
from pathlib import Path
import runpy

import unreal


HERE = Path(__file__).resolve().parent
GATES = runpy.run_path(str(HERE / 'place_watch_gates.py'))
DESTINATION = '/Game/GrayLondon/MedievalOpening/MarketDressing'
ACTOR_ROOT = GATES['ACTOR_ROOT']
PREFIX = 'GL1450_YardDetail_'
NAMES = {
    'Wing': 'SM_GL1450_WatchPalisadeWing',
    'Cask': 'SM_GL1450_CaskAndSack',
    'Crates': 'SM_GL1450_CratesAndBasket',
}
LANTERN = '/Game/LanthorneAssets/Giltside/Props/SM_Giltside_ArchiveLantern'
EAST_PILOT = (
    ('CityDetailPilot_3_Provisions', 'D/6C/YM9JUHP9OCRK9VQXK8O8F8', 'SM_GL_Shopfront_Provisions'),
    ('CityDetailPilot_4_Bookshop', 'D/M5/MJVZY7YBPCPG9BOKZNUI6P', 'SM_GL_Shopfront_Bookshop'),
    ('CityDetailPilot_Fascia_MarkLaneProvisions', '4/8R/ZCVPNTHJ6JT627RWSAU8C1', 'SM_GL_Fascia'),
    ('CityDetailPilot_Fascia_LanternRoom', '8/OP/O3G4RR4AR03HSEK6T7LGDH', 'SM_GL_Fascia'),
    ('CityDetailPilot_Dressing_CycleHoop1', '5/ZQ/SYUAI5OFNS0B27T2KUQ7AP', 'GenericCycleStand'),
    ('CityDetailPilot_Dressing_CycleHoop2', '6/A4/R7FXPFDQ02MNHE8FP6QGOQ', 'GenericCycleStand'),
)


def report_transform(x, y, yaw, dx, dy):
    angle = math.radians(yaw)
    return (x + dx * math.cos(angle) - dy * math.sin(angle),
            y + dx * math.sin(angle) + dy * math.cos(angle))


def props_for(names):
    props = []
    for site in names:
        if site == 'IntroMarket':
            props += [('IntroMarket_Crates', 'Crates', 329425, 30945, -14),
                      ('IntroMarket_Cask', 'Cask', 329596, 31512, 21)]
            continue
        x, y, _ = GATES['SITES'][site]
        props += [(site + '_NorthWing', 'Wing', x + 8, y + 442, 180),
                  (site + '_SouthWing', 'Wing', x + 8, y - 442, 180),
                  (site + '_SupplyCask', 'Cask', x - 102, y - 277, 24)]
    return props


def get_mesh(role):
    stem = NAMES.get(role)
    path = f'{DESTINATION}/{stem}/StaticMeshes/{stem}' if stem else LANTERN
    mesh = unreal.load_asset(path, unreal.StaticMesh)
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError(f'Missing mesh {path}.')
    return mesh


def survey(names=('SeethingYard', 'TrinitySquare', 'IntroMarket')):
    world = GATES['get_editor_world']()
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = actor_subsystem.get_all_level_actors()
    mesh_by_role = {role: get_mesh(role) for role in NAMES}
    result = []
    for name, role, x, y, yaw in props_for(names):
        info = mesh_by_role[role].get_bounding_box()
        low = info.get_editor_property('min')
        high = info.get_editor_property('max')
        points = [(0, 0), (low.x, low.y), (low.x, high.y),
                  (high.x, low.y), (high.x, high.y)]
        heights = []
        for dx, dy in points:
            wx, wy = report_transform(x, y, yaw, dx, dy)
            hit = GATES['trace'](world, unreal.Vector(wx, wy, 270), unreal.Vector(wx, wy, -70))
            heights.append(round(hit[0].z, 2) if hit else None)
        z = heights[0]
        overlaps = []
        solid_radius = max(abs(low.x), abs(low.y), abs(high.x), abs(high.y))
        for a in actors:
            position = a.get_actor_location()
            if a.get_actor_label().startswith('LT_') and math.hypot(position.x-x, position.y-y) < solid_radius + 55:
                overlaps.append(a.get_actor_label())
        box = unreal.Box()
        box.set_editor_properties({
            'min': unreal.Vector(x - 120, y - 120, -100),
            'max': unreal.Vector(x + 120, y + 120, 400),
            'is_valid': True,
        })
        descs = unreal.WorldPartitionBlueprintLibrary.get_intersecting_actor_descs(box) or []
        duplicate = any(str(d.get_editor_property('label')) == PREFIX + name for d in descs)
        result.append({
            'name': name, 'mesh': role, 'position': (x, y, z), 'yaw': yaw,
            'probed_z': heights, 'nearby_story_actor': overlaps, 'duplicate': duplicate,
            'ready': z is not None and z < 50 and all(v is not None and abs(v-z) < 4 for v in heights)
                     and not overlaps and not duplicate,
        })
    return result


def place_mesh(subsystem, label, mesh, xyz, yaw, scale=1):
    actor = subsystem.spawn_actor_from_object(mesh, unreal.Vector(*xyz), unreal.Rotator(0, 0, yaw))
    actor.set_actor_label(PREFIX + label)
    actor.set_folder_path('MedievalLondon/WatchAndMarketDressing')
    actor.set_actor_scale3d(unreal.Vector(scale, scale, scale))
    actor.set_actor_enable_collision(False)
    component = actor.get_components_by_class(unreal.StaticMeshComponent)[0]
    component.set_collision_profile_name('NoCollision')
    component.set_editor_property('can_ever_affect_navigation', False)
    return actor


def place_light(subsystem, x, y, z):
    light = subsystem.spawn_actor_from_class(unreal.PointLight, unreal.Vector(x, y, z))
    light.set_actor_label(PREFIX + 'SeethingYard_LanternGlow')
    light.set_folder_path('MedievalLondon/WatchAndMarketDressing')
    component = light.get_components_by_class(unreal.PointLightComponent)[0]
    component.set_mobility(unreal.ComponentMobility.MOVABLE)
    component.set_editor_properties({
        'intensity_units': unreal.LightUnits.LUMENS,
        'intensity': 15.0,
        'attenuation_radius': 180.0,
        'use_temperature': True,
        'temperature': 2500.0,
        'source_radius': 4.0,
        'cast_shadows': False,
    })
    return light


def place(names=('SeethingYard', 'TrinitySquare', 'IntroMarket'), warm_light=True):
    plan = survey(names)
    if any(not prop['ready'] for prop in plan):
        raise RuntimeError(f'Dressing preflight failed: {[p for p in plan if not p["ready"]]}')
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    by_role = {role: get_mesh(role) for role in {p['mesh'] for p in plan}}
    portable_lantern = get_mesh('Lantern')
    actors = []
    with unreal.ScopedEditorTransaction('Dress medieval London market and watch yards'):
        for prop in plan:
            x, y, z = prop['position']
            yaw = prop['yaw']
            actors.append(place_mesh(subsystem, prop['name'], by_role[prop['mesh']], (x, y, z), yaw))
            if prop['name'].endswith('_SupplyCask'):
                lx, ly = report_transform(x, y, yaw, -15, -9)
                actors.append(place_mesh(subsystem, prop['name'].replace('_SupplyCask', '_Lantern'),
                                         portable_lantern, (lx, ly, z + 58), yaw - 8, .78))
                if warm_light and prop['name'].startswith('SeethingYard_'):
                    actors.append(place_light(subsystem, lx, ly, z + 74))
    packages = [a.get_package() for a in actors]
    paths = [p.get_path_name() for p in packages]
    if any(not a.is_package_external() for a in actors) or any(not p.startswith(ACTOR_ROOT) for p in paths):
        raise RuntimeError(f'Unexpected package(s): {paths}')
    if not unreal.EditorLoadingAndSavingUtils.save_packages(packages, False):
        raise RuntimeError(f'Explicit save failed for {paths}')
    if unreal.MultiUserClientStatics.get_multi_user_connection_status_detail() == unreal.MultiUserConnectionStatus.CONNECTED:
        unreal.MultiUserClientStatics.persist_specified_packages(paths)
    return [(a.get_actor_label(), a.get_actor_location().export_text(), path)
            for a, path in zip(actors, paths, strict=True)]


def hide_east_pilot():
    GATES['get_editor_world']()
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    bounds = unreal.Box()
    bounds.set_editor_properties({
        'min': unreal.Vector(330100, 30880, -100),
        'max': unreal.Vector(330620, 32220, 500),
        'is_valid': True,
    })
    descs = unreal.WorldPartitionBlueprintLibrary.get_intersecting_actor_descs(bounds) or []
    by_path = {str(d.get_editor_property('actor_package')): d for d in descs}
    guids = []
    for label, suffix, _ in EAST_PILOT:
        path = ACTOR_ROOT + suffix
        desc = by_path.get(path)
        if not desc or str(desc.get_editor_property('label')) != label:
            raise RuntimeError(f'Expected original pilot actor {label} at {path}.')
        guids.append(desc.get_editor_property('guid'))
    unreal.WorldPartitionBlueprintLibrary.load_actors(guids)
    by_path = {a.get_package().get_path_name(): a for a in subsystem.get_all_level_actors()
               if a.get_actor_label().startswith('CityDetailPilot_')}
    targets = []
    for label, suffix, mesh_name in EAST_PILOT:
        path = ACTOR_ROOT + suffix
        actor = by_path.get(path)
        if not actor or actor.get_actor_label() != label:
            raise RuntimeError(f'Original pilot actor {label} unavailable after loading {path}.')
        components = actor.get_components_by_class(unreal.StaticMeshComponent)
        mesh = components[0].get_editor_property('static_mesh') if len(components) == 1 else None
        if not mesh or mesh.get_name() != mesh_name:
            raise RuntimeError(f'Unexpected mesh for {label}: {mesh}')
        if not actor.get_editor_property('hidden') or actor.get_actor_enable_collision():
            targets.append(actor)
    if not targets:
        return []
    with unreal.ScopedEditorTransaction('Hide overlapping modern east opening pilot details'):
        for actor in targets:
            actor.modify()
            actor.set_actor_hidden_in_game(True)
            actor.set_actor_enable_collision(False)
    packages = [actor.get_package() for actor in targets]
    paths = [p.get_path_name() for p in packages]
    if not unreal.EditorLoadingAndSavingUtils.save_packages(packages, False):
        raise RuntimeError(f'Explicit east pilot save failed for {paths}')
    if unreal.MultiUserClientStatics.get_multi_user_connection_status_detail() == unreal.MultiUserConnectionStatus.CONNECTED:
        unreal.MultiUserClientStatics.persist_specified_packages(paths)
    return [(a.get_actor_label(), path, a.get_editor_property('hidden'), a.get_actor_enable_collision())
            for a, path in zip(targets, paths, strict=True)]
