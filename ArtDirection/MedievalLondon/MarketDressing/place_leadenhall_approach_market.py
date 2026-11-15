"""Place a compact period market cluster outside the south Leadenhall route."""

import math
from pathlib import Path
import runpy

import unreal


HERE = Path(__file__).resolve().parent
YARDS = runpy.run_path(str(HERE / 'dress_watch_yards.py'))
GATES = YARDS['GATES']
PREFIX = 'GL1450_LeadenhallApproach_'
FOLDER = 'MedievalLondon/LeadenhallApproachMarket'
STALL_STEM = 'SM_GL1450_MarketStall'
PORTAL_CENTER = (306787.375, 57652.058)
PORTAL_YAW = -18.18671
PLACEMENTS = (
    ('DryGoodsStall', 'Stall', 306856, 57250, PORTAL_YAW, .88),
    ('PackedCrates', 'Crates', 306928, 57433, -6, .9),
    ('SupplierCask', 'Cask', 306860, 57075, 24, 1),
)


def get_mesh(role):
    if role != 'Stall':
        return YARDS['get_mesh'](role)
    path = f'{YARDS["DESTINATION"]}/{STALL_STEM}/StaticMeshes/{STALL_STEM}'
    mesh = unreal.load_asset(path, unreal.StaticMesh)
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError(f'Missing existing stall at {path}.')
    return mesh


def trace(world, a, b):
    return GATES['trace'](world, unreal.Vector(*a), unreal.Vector(*b))


def survey():
    world = GATES['get_editor_world']()
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = subsystem.get_all_level_actors()
    if not any(a.get_actor_label() == 'OSM Tile_p03_p01' for a in actors):
        raise RuntimeError('Load the exact Leadenhall source tile before surveying the market approach.')
    bounds = unreal.Box()
    bounds.set_editor_properties({
        'min': unreal.Vector(306730, 56930, -100),
        'max': unreal.Vector(307150, 57520, 400),
        'is_valid': True,
    })
    descs = unreal.WorldPartitionBlueprintLibrary.get_intersecting_actor_descs(bounds) or []
    existing = [str(d.get_editor_property('label')) for d in descs
                if str(d.get_editor_property('label')).startswith(PREFIX)]

    props = []
    for name, role, x, y, yaw, scale in PLACEMENTS:
        bounds = get_mesh(role).get_bounding_box()
        low = bounds.get_editor_property('min') * scale
        high = bounds.get_editor_property('max') * scale
        feet = []
        for dx in (low.x, 0, high.x):
            for dy in (low.y, 0, high.y):
                px, py = YARDS['report_transform'](x, y, yaw, dx, dy)
                hit = trace(world, (px, py, 280), (px, py, -65))
                feet.append({'z': round(hit[0].z, 2), 'surface': hit[1]} if hit else None)
        center = feet[4]
        z = center['z'] if center else None
        story = []
        radius = max(abs(low.x), abs(low.y), abs(high.x), abs(high.y)) + 55
        for actor in actors:
            if actor.get_actor_label().startswith('LT_'):
                spot = actor.get_actor_location()
                if math.hypot(spot.x - x, spot.y - y) < radius:
                    story.append(actor.get_actor_label())
        props.append({'name': name, 'mesh': role, 'position': [x, y, z], 'yaw': yaw,
                      'scale': scale, 'feet': feet, 'nearby_story': story,
                      'ready': z is not None and abs(z - 10) <= .5 and not story
                               and all(f and abs(f['z'] - z) < .5 for f in feet)})

    roadway = [trace(world, (307200 + offset, 57030, 148), (307200 + offset, 57970, 148))
               for offset in (-70, 0, 70)]
    portal = []
    for offset in (-125, 0, 125):
        start = YARDS['report_transform'](*PORTAL_CENTER, PORTAL_YAW, 87, offset)
        end = YARDS['report_transform'](*PORTAL_CENTER, PORTAL_YAW, 505, offset)
        portal.append(trace(world, (*start, 145), (*end, 145)))
    return {'props': props, 'duplicate': existing,
            'main_route_obstructions': [hit[1] if hit else None for hit in roadway],
            'portal_route_obstructions': [hit[1] if hit else None for hit in portal],
            'ready': not existing and all(p['ready'] for p in props)
                     and not any(roadway) and not any(portal)}


def place():
    design = survey()
    if not design['ready']:
        raise RuntimeError(f'Leadenhall approach preflight failed: {design}')
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    props = {}
    meshes = {p['mesh']: get_mesh(p['mesh']) for p in design['props']}
    meshes['Lantern'] = get_mesh('Lantern')
    with unreal.ScopedEditorTransaction('Dress the south Leadenhall market approach'):
        for p in design['props']:
            props[p['name']] = YARDS['place_mesh'](subsystem, p['name'], meshes[p['mesh']],
                                                    p['position'], p['yaw'], p['scale'])
            if p['name'] == 'SupplierCask':
                x, y, z = p['position']
                lx, ly = YARDS['report_transform'](x, y, p['yaw'], -15, -9)
                props['CaskLantern'] = YARDS['place_mesh'](subsystem, 'CaskLantern', meshes['Lantern'],
                                                           (lx, ly, z + 58), p['yaw'] - 8, .78)
        for name, actor in props.items():
            actor.set_actor_label(PREFIX + name)
            actor.set_folder_path(FOLDER)
    packages = [actor.get_package() for actor in props.values()]
    paths = [p.get_path_name() for p in packages]
    if any(not a.is_package_external() for a in props.values()) or any(not p.startswith(YARDS['ACTOR_ROOT']) for p in paths):
        raise RuntimeError(f'Unexpected external packages: {paths}')
    if not unreal.EditorLoadingAndSavingUtils.save_packages(packages, False):
        raise RuntimeError(f'Failed to save only the Leadenhall approach packages: {paths}')
    if unreal.MultiUserClientStatics.get_multi_user_connection_status_detail() == unreal.MultiUserConnectionStatus.CONNECTED:
        unreal.MultiUserClientStatics.persist_specified_packages(paths)
    return [(actor.get_actor_label(), actor.get_actor_location().export_text(), path)
            for actor, path in zip(props.values(), paths, strict=True)]
