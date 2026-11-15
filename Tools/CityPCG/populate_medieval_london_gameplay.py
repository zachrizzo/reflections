"""Transfer existing story marker names and navigation to the new town."""

from collections import Counter
import json
from pathlib import Path

from build_medieval_london_map import MAP, ROOT


# Points are on the main street, market square, or cross streets. Map each old
# named destination once so aliases and variants still refer to the same place.
LOCATIONS = {
    'Intro': (-23300, 0), 'LanternGate': (-23600, 350), 'GateBridge': (-22900, -360),
    'LanternRow': (-21500, 460), 'Lamplight': (-20200, -530), 'LamplightCellar': (-19600, -430),
    'BellLane': (-15300, 330), 'BellSquare': (-1200, 600), 'Fountain': (400, 800),
    'Square_Cistern': (400, 800), 'DrifterCamp': (-18300, -9200), 'CanalRift': (-18300, -16300),
    'WeighHouseCorner': (-11500, 430), 'WeighHouseRoof': (-10800, -310), 'WeighHouseStair': (-10800, -670),
    'ArchiveSteps': (3600, 3850), 'ArchiveTerrace': (3600, 5200), 'ThraleShop': (-6800, 520),
    'VaneAtelier': (-5400, -530), 'WickStreet': (11300, -5900), 'Furnace': (11300, -12200),
    'CoalLaneLaundry': (18900, -12600), 'CoalLaneStop': (18900, -8600),
    'BarracksEast': (18900, 3200), 'BarracksWest': (11300, 4700), 'MusterYard': (14800, 2400),
    'TowerFoot': (19300, 340), 'TowerPlaza': (19900, -400), 'IceWall': (22600, 500),
    'HesterDoorstep': (3600, -5700), 'FishSteps': (-3700, -18800),
    'Shed': (-10900, -18100), 'Yard': (11400, 1100),
}


def run():
    import unreal

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if not world or world.get_package().get_name() != MAP or editor.get_game_world():
        raise RuntimeError('Open Medieval London outside Play before adding its gameplay actors.')
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if any(a.get_actor_label() == 'Town Navigation | Streets and squares' for a in actors.get_all_level_actors()):
        raise RuntimeError('The gameplay pass is already present.')
    project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
    markers = json.loads((project / 'ArtDirection/WorldJump/graylondon_markers.json').read_text(encoding='utf-8-sig'))
    unknown = {row['place'] for row in markers} - LOCATIONS.keys()
    if unknown:
        raise RuntimeError(f'Unmapped story destinations: {sorted(unknown)}')

    def spawn(cls, label, x, y, z, yaw=0):
        actor = actors.spawn_actor_from_class(cls, unreal.Vector(x, y, z), unreal.Rotator(0, 0, yaw))
        if not actor:
            raise RuntimeError(f'Could not create {label}.')
        actor.set_actor_label(label)
        return actor

    visits = Counter()
    for row in markers:
        x, y = LOCATIONS[row['place']]
        index = visits[row['place']]
        visits[row['place']] += 1
        if 'CutsceneAnchor_' not in row['name']:
            x += (index % 4) * 120
        marker = spawn(unreal.ReflectionsStoryMarker, row['name'], x, y, 15, row['yaw'])
        marker.set_editor_properties({'marker_name': row['name'], 'radius': float(row['radius']),
                                      'side': getattr(unreal.ReflectionsMarkerSide, row['side'].upper()),
                                      'tags': row['tags']})

    # Give the market its own tall visual marker using the existing Guildhall portal.
    portal = unreal.EditorAssetLibrary.load_asset(f'{ROOT}/Kit/SM_GLMedieval_Guildhall_Portal')
    if portal:
        arch = spawn(unreal.StaticMeshActor, 'Guildhall | Market landmark', 2500, 3130, 0, 180)
        component = arch.get_component_by_class(unreal.StaticMeshComponent)
        component.set_static_mesh(portal)
        component.set_collision_profile_name('NoCollision')

    nav_data = spawn(unreal.RecastNavMesh, 'Town Recast NavMesh', 0, 0, 0)
    nav_data.set_editor_property('runtime_generation', unreal.RuntimeGenerationType.STATIC)
    nav = spawn(unreal.NavMeshBoundsVolume, 'Town Navigation | Streets and squares', 0, 0, 300)
    # The editor volume factory supplies a 200 cm brush. Match its cooked
    # body to that brush and scale both with the actor transform.
    if not unreal.ReflectionsWorldLibrary.set_volume_box(nav, unreal.Vector(100, 100, 100)):
        raise RuntimeError('Could not size the town navigation volume.')
    nav.set_actor_scale3d(unreal.Vector(242, 242, 9.8))
    nav_system = unreal.NavigationSystemV1.get_navigation_system(world)
    if nav_system:
        nav_system.on_navigation_bounds_updated(nav)
    unreal.SystemLibrary.execute_console_command(world, 'RebuildNavigation')
    if not unreal.EditorLoadingAndSavingUtils.save_packages([world.get_package()], only_dirty=False):
        raise RuntimeError('Could not save the new town gameplay actors.')
    return {'map': MAP, 'story_markers': len(markers), 'destinations': len(visits), 'navigation_requested': True}
