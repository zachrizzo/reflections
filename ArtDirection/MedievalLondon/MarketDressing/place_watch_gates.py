"""Survey or place the two medieval visual watch gates in Gray London."""

import math

import unreal


MAP = '/Game/GrayLondon/Maps/GrayLondon_Geodata'
ACTOR_ROOT = '/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/'
MESH = ('/Game/GrayLondon/MedievalOpening/MarketDressing/SM_GL1450_WatchGate/'
        'StaticMeshes/SM_GL1450_WatchGate')
SITES = {
    'SeethingYard': (334760, 31170, 180),
    'TrinitySquare': (351100, 28700, 180),
}
# Feet, braces, both outer ends and ground under the clear portal.
SUPPORTS = ((0, 0), (0, -345), (0, 345), (-96, -335), (-96, 335),
            (32, -335), (32, 335), (-88, -260), (-88, 260),
            (-260, 0), (260, 0))


def get_editor_world():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if editor.get_game_world() or not world or world.get_path_name().split('.')[0] != MAP:
        raise RuntimeError('Open the Gray London editor world with PIE stopped.')
    return world


def position(site, local_x, local_y, z):
    x, y, yaw = site
    a = math.radians(yaw)
    return unreal.Vector(x + local_x * math.cos(a) - local_y * math.sin(a),
                         y + local_x * math.sin(a) + local_y * math.cos(a), z)


def trace(world, start, stop):
    hit = unreal.SystemLibrary.line_trace_single(
        world, start, stop, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [],
        unreal.DrawDebugTrace.NONE,
    )
    if not hit:
        return None
    row = hit.to_tuple()
    return row[4], row[9].get_actor_label()


def survey(names=('SeethingYard', 'TrinitySquare')):
    world = get_editor_world()
    editor_actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    result = {}
    for name in names:
        site = SITES[name]
        x, y, _ = site
        bounds = unreal.Box()
        bounds.set_editor_properties({
            'min': unreal.Vector(x - 430, y - 430, -100),
            'max': unreal.Vector(x + 430, y + 430, 400),
            'is_valid': True,
        })
        descs = unreal.WorldPartitionBlueprintLibrary.get_intersecting_actor_descs(bounds) or []
        existing = [str(d.get_editor_property('label')) for d in descs
                    if str(d.get_editor_property('label')).startswith('GL1450_WatchGate_')]
        feet = []
        for dx, dy in SUPPORTS:
            hit = trace(world, position(site, dx, dy, 450), position(site, dx, dy, -80))
            feet.append((round(hit[0].z, 2), hit[1]) if hit else None)
        center_z = feet[0][0] if feet[0] else 0
        approaches = []
        for dy in (-125, 0, 125):
            obstruction = trace(world, position(site, -420, dy, center_z + 125),
                                position(site, 420, dy, center_z + 125))
            approaches.append(obstruction[1] if obstruction else None)
        story = []
        for actor in editor_actors:
            if actor.get_actor_label().startswith('LT_'):
                spot = actor.get_actor_location()
                distance = math.hypot(spot.x - x, spot.y - y)
                if distance < 600:
                    story.append((actor.get_actor_label(), round(distance)))
        result[name] = {
            'site_cm': [x, y, center_z],
            'yaw': site[2],
            'feet': feet,
            'approach_obstructions': approaches,
            'story_objects_within_6m': story,
            'existing_gate': existing,
            'ready': (
                len(feet) == len(SUPPORTS) and all(p and abs(p[0] - center_z) <= 3 for p in feet)
                and not any(approaches) and not story and not existing
            ),
        }
    return result


def place(names=('SeethingYard', 'TrinitySquare')):
    sites = survey(names)
    if not all(sites[name]['ready'] for name in names):
        raise RuntimeError(f'Watch gate preflight failed: {sites}')
    mesh = unreal.load_asset(MESH, unreal.StaticMesh)
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError(f'Expected watch gate mesh at {MESH}')
    editor_actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    placed = []
    with unreal.ScopedEditorTransaction('Place medieval timber watch gates'):
        for name in names:
            site = sites[name]
            location = unreal.Vector(*site['site_cm'])
            gate = editor_actors.spawn_actor_from_object(mesh, location, unreal.Rotator(0, 0, site['yaw']))
            gate.set_actor_label('GL1450_WatchGate_' + name)
            gate.set_folder_path('MedievalLondon/WatchGates')
            gate.set_actor_enable_collision(False)
            component = gate.get_components_by_class(unreal.StaticMeshComponent)[0]
            component.set_collision_profile_name('NoCollision')
            component.set_editor_property('can_ever_affect_navigation', False)
            placed.append(gate)
    packages = [gate.get_package() for gate in placed]
    paths = [package.get_path_name() for package in packages]
    if any(not gate.is_package_external() for gate in placed) or any(not path.startswith(ACTOR_ROOT) for path in paths):
        raise RuntimeError(f'Unexpected actor packages: {paths}')
    if not unreal.EditorLoadingAndSavingUtils.save_packages(packages, False):
        raise RuntimeError(f'Could not save these gate actors: {paths}')
    if unreal.MultiUserClientStatics.get_multi_user_connection_status_detail() == unreal.MultiUserConnectionStatus.CONNECTED:
        unreal.MultiUserClientStatics.persist_specified_packages(paths)
    return {'packages': paths, 'survey': sites,
            'actor_collision': [gate.get_actor_enable_collision() for gate in placed]}
