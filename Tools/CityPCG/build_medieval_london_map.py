"""Generate the standalone 500 m Medieval London map through the Unreal MCP."""

import asyncio
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import random
import time

from apply_facade_pcg import cell_transform, make_point, populate_point_mesh_graph

MAP = '/Game/GrayLondon/Maps/MedievalLondon'
ROOT = '/Game/GrayLondon/MedievalOpening'
GRAPH_DIR = f'{ROOT}/Graphs'
GRAPH_NAME = 'PCG_MedievalLondon_Town'
HOUSES = {
    key: f'{ROOT}/WholeBuildings/WestMarkLane/SM_GLMedieval_MarkLane{suffix}'
    for key, suffix in [('merchants', 'MerchantsHouses'), ('workshop', 'Workshop'),
                        ('compound', 'TradingCompound')]
}
PROPS = {
    key: f'{ROOT}/MarketDressing/SM_GL1450_{suffix}/StaticMeshes/SM_GL1450_{suffix}'
    for key, suffix in [('gate', 'WatchGate'), ('wall', 'WatchPalisadeWing'),
                        ('stall', 'MarketStall'), ('crates', 'CratesAndBasket'),
                        ('cask', 'CaskAndSack')]
}
PAVING = f'{ROOT}/Ground/SM_GL1450_OpeningGround/StaticMeshes/SM_GL1450_OpeningGround'
ASSETS = {**HOUSES, **PROPS, 'paving': PAVING}
SOLID = {*HOUSES, 'wall'}


def layout(bounds):
    """Make rows of plots with clear cross streets and a central market."""
    randomizer = random.Random(1450)
    groups = defaultdict(list)
    cross = (-18300, -10900, -3700, 3600, 11300, 18900)
    axes = (-19400, -12400, -6200, 0, 6400, 12200, 19300)

    def place(key, center, yaw=0, scale=(1, 1, 1)):
        low, high = bounds[key]
        x = (low[0] + high[0]) * .5 * scale[0]
        y = (low[1] + high[1]) * .5 * scale[1]
        angle = math.radians(yaw)
        c, s = math.cos(angle), math.sin(angle)
        pivot = (center[0] - (c * x - s * y), center[1] - (s * x + c * y),
                 center[2] - low[2] * scale[2])
        groups[key].append((pivot, yaw, scale, randomizer.randrange(1, 2**30)))

    for lane in axes:
        main = lane == 0
        openings = [(road - 790, road + 790) for road in cross]
        if main:
            openings = [o for o in openings if o[1] < -4680 or o[0] > 4650]
            openings.append((-4680, 4650))
        borders = [-22700, *[x for opening in sorted(openings) for x in opening], 23200]
        for side in (-1, 1):
            for left, right in zip(borders[::2], borders[1::2]):
                x = left + randomizer.uniform(10, 130)
                while right - x >= 580:
                    key = randomizer.choices(tuple(HOUSES), (4, 6, 2))[0]
                    low, high = bounds[key]
                    mesh_width, mesh_depth = high[1] - low[1], high[0] - low[0]
                    # Fit the last house too, while keeping normal roof height on tight lots.
                    width = min(mesh_width * randomizer.uniform(.78, 1.1), 1270, right - x)
                    depth = min(mesh_depth * randomizer.uniform(.72, .97), 2010)
                    height = randomizer.uniform(.78, 1.10)
                    half_width = 620 if main else 360
                    bend = 95 * math.sin(x / 4400)
                    y = lane + bend + side * (half_width + depth * .5 + randomizer.uniform(6, 70))
                    place(key, (x + width * .5, y, 0), -side * 90,
                          (depth / mesh_depth, width / mesh_width, height))
                    x += width + randomizer.uniform(34, 105)

    # Opening walls and streets run east from PlayerStart before reaching the market.
    for x in range(-23800, 24400, 1450):
        place('paving', (x, 0, 0), 0, (1, 1.45, .16))
    for lane in axes:
        if lane:
            for x in range(-22800, 22900, 1940):
                place('paving', (x, lane, -2), 0, (1.35, .82, .15))
    for x in cross:
        for y in range(-22500, 22600, 1400):
            place('paving', (x, y, -3), 90, (1, .8, .11))
    for x in range(-2900, 3100, 1400):
        for y in (-2400, -1200, 1200, 2400):
            place('paving', (x, y, -1), 0, (1, 1.08, .15))

    for x in (-24200, 24200):
        place('gate', (x, 0, 0), 0 if x < 0 else 180, (1.25, 1.6, 1.35))
        for y in range(-24000, 24200, 242):
            if abs(y) >= 630:
                place('wall', (x, y, 0), 0, (1, 1.33, 1.45))
    for y in (-24200, 24200):
        for x in range(-24000, 24200, 242):
            place('wall', (x, y, 0), 90, (1, 1.33, 1.45))

    for x in (-21400, -19500, -16500, -13400, -8000, -2900, -2200, -1200, 400, 1600, 2600):
        for side in (-1, 1):
            edge = 2200 if abs(x) < 3100 else 470
            place('stall', (x, side * edge, 4), -side * 90)
            place('crates', (x + 185, side * (edge + 70), 4), randomizer.randrange(360))
            place('cask', (x - 185, side * (edge + 70), 4), randomizer.randrange(360))

    # A second defended yard is visible at the far end of the market route.
    place('gate', (14900, 2400, 0), 0, (1.1, 1.2, 1.1))
    for y in (1680, 1910, 2890, 3120):
        place('wall', (14900, y, 0), 0, (1, 1.3, 1.2))
    return dict(groups)


def require_town_editor(unreal):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    saved = Path(unreal.Paths.project_saved_dir())
    lease = json.loads((saved / 'PIE_LOCK.json').read_text(encoding='utf-8-sig'))
    if (not world or world.get_package().get_name() != MAP or editor.get_game_world() or
            lease.get('owner') != 'codex-gray-london' or lease['expires_epoch'] < time.time() + 120):
        raise RuntimeError('Open the owned Medieval London map outside Play under the authoring lease.')
    return editor, world


def load_layout(unreal):
    meshes = {key: unreal.EditorAssetLibrary.load_asset(path) for key, path in ASSETS.items()}
    if any(not isinstance(mesh, unreal.StaticMesh) for mesh in meshes.values()):
        raise RuntimeError('A required existing London static mesh is missing.')
    bounds = {}
    for key, mesh in meshes.items():
        box = mesh.get_bounding_box()
        bounds[key] = tuple(tuple(getattr(v, a) for a in 'xyz') for v in (box.min, box.max))
    return meshes, layout(bounds)


async def run():
    import unreal

    editor, world = require_town_editor(unreal)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if any(a.get_actor_label() == 'Medieval London | Market Street' for a in actors.get_all_level_actors()):
        raise RuntimeError('The town has already been placed.')

    meshes, groups = load_layout(unreal)

    def spawn(cls, label, location, rotation=(0, 0, 0)):
        actor = actors.spawn_actor_from_class(cls, unreal.Vector(*location), unreal.Rotator(*rotation))
        if not actor:
            raise RuntimeError(f'Could not create {label}.')
        actor.set_actor_label(label)
        return actor

    floor = spawn(unreal.StaticMeshActor, 'Ground | City footprint 500 m', (0, 0, -55))
    floor_mesh = floor.get_component_by_class(unreal.StaticMeshComponent)
    floor_mesh.set_static_mesh(unreal.EditorAssetLibrary.load_asset('/Engine/BasicShapes/Cube'))
    floor.set_actor_scale3d(unreal.Vector(500, 500, 1))
    floor_mesh.set_collision_profile_name('BlockAll')
    cobbles = unreal.EditorAssetLibrary.load_asset(f'{ROOT}/Ground/SM_GL1450_OpeningGround/Materials/M_GL1450_WornCobblesAndEarth')
    if cobbles:
        floor_mesh.set_material(0, cobbles)

    start = spawn(unreal.PlayerStart, 'Player Start | Watch Gate to Market', (-24080, 0, 100))
    start.set_editor_property('player_start_tag', 'Lanthorne')
    light = spawn(unreal.DirectionalLight, 'Daylight | Morning', (0, 0, 600), (0, -34, -125))
    light_component = light.get_component_by_class(unreal.DirectionalLightComponent)
    light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    light_component.set_editor_property('intensity', 5.0)
    spawn(unreal.SkyAtmosphere, 'Sky | London', (0, 0, 0))
    sky = spawn(unreal.SkyLight, 'Sky fill', (0, 0, 500))
    sky_component = sky.get_component_by_class(unreal.SkyLightComponent)
    sky_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    sky_component.set_editor_property('real_time_capture', True)

    pcg = unreal.get_editor_subsystem(unreal.PCGEditorSubsystem)
    graph = unreal.EditorAssetLibrary.load_asset(f'{GRAPH_DIR}/{GRAPH_NAME}')
    if not graph:
        graph = pcg.create_graph(GRAPH_NAME, GRAPH_DIR)
        populate_point_mesh_graph(unreal, pcg, graph, groups, meshes, solid_meshes=SOLID)
    info = pcg.spawn_graph_instance(graph, 'Medieval London | Market Street', cell_transform(unreal, groups))
    volume = info.get_editor_property('actor')
    component = volume.get_component_by_class(unreal.PCGComponent)
    component.set_editor_properties({'generation_trigger': unreal.PCGComponentGenerationTrigger.GENERATE_ON_DEMAND,
                                     'generate_on_drop_when_trigger_on_demand': False,
                                     'regenerate_in_editor': False, 'is_component_partitioned': False})
    return await generate_and_save(unreal, editor, world, pcg, graph, volume, meshes, groups)


async def repack():
    """Apply revised plots to the saved town while preserving its gameplay actors."""
    import unreal

    editor, world = require_town_editor(unreal)
    graph = unreal.EditorAssetLibrary.load_asset(f'{GRAPH_DIR}/{GRAPH_NAME}')
    volume, = (actor for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.PCGVolume)
               if actor.get_actor_label() == 'Medieval London | Market Street')
    meshes, groups = load_layout(unreal)
    sources = {str(node.get_editor_property('node_title')).removeprefix('Points '): node.get_settings()
               for node in graph.get_editor_property('nodes')
               if isinstance(node.get_settings(), unreal.PCGCreatePointsSettings)}
    if set(sources) != set(groups):
        raise RuntimeError('The saved town graph no longer matches the placement groups.')
    pcg = unreal.get_editor_subsystem(unreal.PCGEditorSubsystem)
    was_paused = pcg.is_graph_automatic_regeneration_paused(graph)
    pcg.set_graph_automatic_regeneration_paused(graph, True)
    try:
        graph.modify()
        for key, settings in sources.items():
            settings.modify()
            settings.set_editor_property('points_to_create', [make_point(unreal, row) for row in groups[key]])
    finally:
        pcg.set_graph_automatic_regeneration_paused(graph, was_paused)
    start, = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.PlayerStart)
    start.set_actor_location(unreal.Vector(-24080, 0, 100), False, True)
    return await generate_and_save(unreal, editor, world, pcg, graph, volume, meshes, groups)


async def generate_and_save(unreal, editor, world, pcg, graph, volume, meshes, groups):
    component = volume.get_component_by_class(unreal.PCGComponent)
    pending = (pcg.wait_for_graph_instance(component) if component.get_editor_property('generation_in_progress')
               else pcg.execute_graph_instance(component))
    deadline = time.monotonic() + 40
    while not pending.get_editor_property('is_complete'):
        if time.monotonic() > deadline:
            raise RuntimeError('Town PCG generation did not finish.')
        await asyncio.sleep(.15)
    if pending.get_editor_property('error'):
        raise RuntimeError(pending.get_editor_property('error'))

    reverse = {mesh.get_path_name(): key for key, mesh in meshes.items()}
    counts = Counter()
    for ism in volume.get_components_by_class(unreal.InstancedStaticMeshComponent):
        mesh = ism.get_editor_property('static_mesh')
        key = reverse[mesh.get_path_name()]
        if key in SOLID and str(ism.get_collision_profile_name()) != 'BlockAll':
            raise RuntimeError(f'Generated {key} has no blocking collision.')
        counts[key] += ism.get_instance_count()
    if counts != {key: len(points) for key, points in groups.items()}:
        raise RuntimeError(f'Town PCG instances did not match the plan: {dict(counts)}')

    editor.set_level_viewport_camera_info(unreal.Vector(-23700, 0, 210), unreal.Rotator(0, -2, 0))
    packages = [world.get_package(), graph.get_package()]
    if [p.get_name() for p in packages] != [MAP, f'{GRAPH_DIR}/{GRAPH_NAME}']:
        raise RuntimeError('Unexpected packages for the new map and town graph.')
    if not unreal.EditorLoadingAndSavingUtils.save_packages(packages, only_dirty=False):
        raise RuntimeError('Could not save the new map and town graph.')
    return {'map': MAP, 'graph': packages[1].get_name(), 'instances': dict(counts),
            'buildings': sum(counts[key] for key in HOUSES), 'size_m': 500}
