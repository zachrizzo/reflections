"""Generate a reviewed facade-plan cell with native Unreal 5.9 PCG.

Run in the editor's async Python tool after adding this file's directory to
sys.path. `await run(plan_path)` is read-only. `await run(plan_path,
mode='save', cell_id='x16_y1')` generates and saves one new World Partition
cell. Existing graphs and actors are deliberately rejected.
"""

import asyncio
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re
import time


LEVEL = '/Game/GrayLondon/Maps/GrayLondon_Geodata'
DESTINATION = '/Game/GrayLondon/CityPCG'
MESH_ROOT = f'{DESTINATION}/Kit'
MEDIEVAL_DESTINATION = '/Game/GrayLondon/MedievalOpening'
ACTOR_PACKAGES = '/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/'
NAME = re.compile(r'[A-Za-z0-9_]+\Z')


def name(value):
    if not isinstance(value, str) or not NAME.fullmatch(value) or len(value) > 80:
        raise ValueError(f'Invalid Unreal identifier: {value!r}')
    return value


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f'Expected a finite JSON number, got {value!r}')
    return float(value)


def vector(values):
    if not isinstance(values, list) or len(values) != 3:
        raise ValueError(f'Expected three coordinates, got {values!r}')
    return tuple(number(value) for value in values)


def read_plan(plan_path):
    plan = json.loads(Path(plan_path).read_text(encoding='utf-8-sig'))
    if plan.get('coordinate_system') != 'ue_cm':
        raise ValueError('The plan must use Unreal world centimetres (ue_cm).')
    cells = {}
    coordinates = set()
    for cell in plan['cells']:
        identifier = name(cell['id'])
        if identifier in cells or not cell['points']:
            raise ValueError(f'Duplicate or empty cell: {identifier}')
        groups = defaultdict(list)
        for row in cell['points']:
            mesh_id = name(row['mesh_id'])
            location = vector(row['location_cm'])
            yaw = number(row['yaw_deg']) % 360
            scale = vector(row['scale'])
            seed = row['seed']
            if min(scale) <= 0 or type(seed) is not int or not -(2**31) <= seed < 2**31:
                raise ValueError(f'Invalid scale or signed 32-bit seed for {mesh_id} in {identifier}')
            key = (mesh_id, location, yaw, scale)
            if key in coordinates:
                raise ValueError(f'Duplicate mesh transform at {location}: {mesh_id}')
            coordinates.add(key)
            groups[mesh_id].append((location, yaw, scale, seed))
        cells[identifier] = dict(groups)
    if not cells:
        raise ValueError('The plan contains no cells.')
    return cells


def verify_editor(unreal):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if editor.get_game_world() or not world or world.get_path_name().split('.')[0] != LEVEL:
        raise RuntimeError(f'Open {LEVEL} in the editor and stop PIE before saving a facade cell.')
    lock = Path(unreal.Paths.project_saved_dir()) / 'PIE_LOCK.json'
    if lock.is_file():
        try:
            lease = json.loads(lock.read_text(encoding='utf-8-sig'))
            expires = float(lease['expires_epoch'])
        except (ValueError, KeyError, OSError) as error:
            raise RuntimeError(f'Cannot verify the editor lease in {lock}.') from error
        if not math.isfinite(expires) or expires > time.time():
            raise RuntimeError(f'The editor has an active lease held by {lease.get("owner", "another task")}.')


def graph_name(cell_id):
    return f'PCG_GL_Facades_{cell_id}'


def make_transform(unreal, location, yaw=0, scale=(1, 1, 1)):
    return unreal.Transform(location=unreal.Vector(*location),
                            rotation=unreal.Rotator(0, 0, yaw),
                            scale=unreal.Vector(*scale))


def make_point(unreal, row):
    location, yaw, scale, seed = row
    point = unreal.PCGPoint()
    point.set_editor_properties({
        'transform': make_transform(unreal, location, yaw, scale),
        'seed': seed,
        'density': 1.0,
        'bounds_min': unreal.Vector(-1, -1, -1),
        'bounds_max': unreal.Vector(1, 1, 1),
    })
    return point


def configure_spawner(unreal, settings, mesh):
    settings.set_mesh_selector_type(unreal.PCGMeshSelectorWeighted)
    selector = settings.get_editor_property('mesh_selector_parameters')
    descriptor = unreal.PCGSoftISMComponentDescriptor()
    body = descriptor.get_editor_property('body_instance')
    body.set_editor_property('collision_profile_name', 'NoCollision')
    body.set_editor_property('collision_enabled', unreal.CollisionEnabled.NO_COLLISION)
    descriptor.set_editor_properties({
        'body_instance': body,
        'use_default_collision': False,
        'can_ever_affect_navigation': False,
        'generate_overlap_events': False,
        'component_class': unreal.InstancedStaticMeshComponent,
        'static_mesh': mesh,
    })
    entry = unreal.PCGMeshSelectorWeightedEntry()
    entry.set_editor_properties({'descriptor': descriptor, 'weight': 1})
    selector.set_editor_property('mesh_entries', [entry])


def create_graph(unreal, pcg, identifier, groups, meshes, destination):
    graph = pcg.create_graph(graph_name(identifier), f'{destination}/Graphs')
    if not graph or graph.get_name() != graph_name(identifier):
        raise RuntimeError(f'Could not create the exact graph name for {identifier}.')
    output = graph.get_output_node()
    for index, (mesh_id, rows) in enumerate(sorted(groups.items())):
        source, settings = graph.add_node_of_type(unreal.PCGCreatePointsSettings)
        settings.set_editor_properties({
            'coordinate_space': unreal.PCGCoordinateSpace.WORLD,
            'cull_points_outside_volume': False,
            'points_to_create': [make_point(unreal, row) for row in rows],
        })
        source.set_editor_property('node_title', f'Points {mesh_id}')
        source.set_node_position(0, index * 180)
        spawner, settings = graph.add_node_of_type(unreal.PCGStaticMeshSpawnerSettings)
        configure_spawner(unreal, settings, meshes[mesh_id])
        spawner.set_editor_property('node_title', mesh_id)
        spawner.set_node_position(360, index * 180)
        if not pcg.try_add_edge(source, 'Out', spawner, 'In') or not pcg.try_add_edge(spawner, 'Out', output, 'Out'):
            raise RuntimeError(f'Could not connect the PCG branch for {mesh_id}.')
    output.set_node_position(720, 0)
    return graph


def cell_transform(unreal, groups):
    positions = [row[0] for rows in groups.values() for row in rows]
    minimum = tuple(min(point[axis] for point in positions) for axis in range(3))
    maximum = tuple(max(point[axis] for point in positions) for axis in range(3))
    center = tuple((lo + hi) * .5 for lo, hi in zip(minimum, maximum))
    # SpawnGraphInstance builds a 200 cm brush; pad the measured point bounds.
    scale = tuple((hi - lo + 2 * padding) / 200
                  for lo, hi, padding in zip(minimum, maximum, (500, 500, 600)))
    return make_transform(unreal, center, scale=scale)


async def generate(unreal, pcg, graph, identifier, groups):
    info = pcg.spawn_graph_instance(graph, graph_name(identifier), cell_transform(unreal, groups))
    actor = info.get_editor_property('actor')
    if not actor or not actor.get_package().get_name().startswith(ACTOR_PACKAGES):
        raise RuntimeError(f'{identifier} did not get its own Gray London external actor package.')
    actor.set_folder_path('CityPCG/Facades')
    actor.set_editor_property('is_spatially_loaded', True)
    actor.set_actor_enable_collision(False)
    component = actor.get_component_by_class(unreal.PCGComponent)
    component.set_editor_properties({
        'generation_trigger': unreal.PCGComponentGenerationTrigger.GENERATE_ON_DEMAND,
        'generate_on_drop_when_trigger_on_demand': False,
        'regenerate_in_editor': False,
        'is_component_partitioned': False,
    })
    pending = (pcg.wait_for_graph_instance(component) if component.get_editor_property('generation_in_progress')
               else pcg.execute_graph_instance(component))
    deadline = time.monotonic() + 25
    while not pending.get_editor_property('is_complete'):
        if time.monotonic() > deadline:
            raise RuntimeError(f'Generation exceeded 25 s; {identifier} was not saved.')
        await asyncio.sleep(.1)
    error = pending.get_editor_property('error')
    if error:
        raise RuntimeError(f'{identifier}: {error}')
    generated = Counter()
    for ism in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
        mesh = ism.get_editor_property('static_mesh')
        if str(ism.get_collision_profile_name()) != 'NoCollision' or ism.get_editor_property('can_ever_affect_navigation'):
            raise RuntimeError(f'Generated collision/navigation is enabled on {ism.get_name()}.')
        generated[mesh.get_name()] += ism.get_instance_count()
    if generated != {mesh_id: len(rows) for mesh_id, rows in groups.items()}:
        raise RuntimeError(f'Unexpected generated instance counts for {identifier}: {dict(generated)}')
    return actor, dict(generated)


async def run(plan_path, mode='preview', cell_id=None, destination=DESTINATION):
    import unreal

    if mode not in ('preview', 'save') or (mode == 'save' and cell_id is None):
        raise ValueError('Use preview or explicitly request save with one cell_id.')
    if destination not in (DESTINATION, MEDIEVAL_DESTINATION):
        raise ValueError('Choose a Gray London facade kit destination.')
    cells = read_plan(plan_path)
    if cell_id is not None:
        cells = {cell_id: cells[cell_id]}
    needed = sorted({mesh_id for groups in cells.values() for mesh_id in groups})
    paths = {mesh_id: f'{destination}/Kit/{mesh_id}' for mesh_id in needed}
    missing = [path for path in paths.values() if not unreal.EditorAssetLibrary.does_asset_exist(path)]
    summary = {identifier: {mesh_id: len(rows) for mesh_id, rows in groups.items()}
               for identifier, groups in cells.items()}
    if mode == 'preview':
        return {'cells': summary, 'missing_mesh_asset_paths': missing, 'saved_packages': []}

    verify_editor(unreal)
    if missing:
        raise RuntimeError(f'Import and verify the missing kit meshes first: {missing}')
    graph_path = f'{destination}/Graphs/{graph_name(cell_id)}'
    level_editor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    labels = {str(desc.get_editor_property('label')) for desc in unreal.WorldPartitionBlueprintLibrary.get_actor_descs() or []}
    labels.update(actor.get_actor_label() for actor in level_editor.get_all_level_actors())
    if graph_name(cell_id) in labels or unreal.EditorAssetLibrary.does_asset_exist(graph_path):
        raise RuntimeError(f'{cell_id} already has a graph or actor. Existing work was not overwritten.')
    meshes = {mesh_id: unreal.EditorAssetLibrary.load_asset(path) for mesh_id, path in paths.items()}
    if any(not isinstance(mesh, unreal.StaticMesh) for mesh in meshes.values()):
        raise RuntimeError('Every kit path must resolve to a static mesh.')

    pcg = unreal.get_editor_subsystem(unreal.PCGEditorSubsystem)
    groups = cells[cell_id]
    graph = create_graph(unreal, pcg, cell_id, groups, meshes, destination)
    actor, counts = await generate(unreal, pcg, graph, cell_id, groups)
    verify_editor(unreal)
    packages = [graph.get_package(), actor.get_package()]
    names = [package.get_name() for package in packages]
    if names[0] != graph_path or not names[1].startswith(ACTOR_PACKAGES):
        raise RuntimeError(f'Unexpected package paths. Nothing saved: {names}')
    if not unreal.EditorLoadingAndSavingUtils.save_packages(packages, only_dirty=False):
        raise RuntimeError(f'Could not save the requested packages: {names}')
    multi_user = unreal.MultiUserClientStatics
    if multi_user.get_multi_user_connection_status_detail() == unreal.MultiUserConnectionStatus.CONNECTED:
        multi_user.persist_specified_packages(names)
    return {'actor': actor.get_actor_label(), 'instances': counts, 'saved_packages': names}


async def save_reviewed_cells(plan_path, cell_ids):
    """Generate a reviewed selection, with each cell saved as its own package pair."""
    import unreal

    identifiers = list(cell_ids)
    planned = read_plan(plan_path)
    if not identifiers or len(set(identifiers)) != len(identifiers):
        raise ValueError('Supply a nonempty list of distinct, reviewed cell IDs.')
    if any(identifier not in planned for identifier in identifiers):
        raise ValueError('One or more cell IDs are missing from the plan.')
    verify_editor(unreal)
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    labels = {str(desc.get_editor_property('label'))
              for desc in unreal.WorldPartitionBlueprintLibrary.get_actor_descs() or []}
    labels.update(actor.get_actor_label() for actor in subsystem.get_all_level_actors())
    existing = [identifier for identifier in identifiers if graph_name(identifier) in labels
                or unreal.EditorAssetLibrary.does_asset_exist(f'{DESTINATION}/Graphs/{graph_name(identifier)}')]
    needed = {mesh_id for identifier in identifiers for mesh_id in planned[identifier]}
    missing = sorted(mesh_id for mesh_id in needed
                     if not unreal.EditorAssetLibrary.does_asset_exist(f'{MESH_ROOT}/{mesh_id}'))
    if existing or missing:
        raise RuntimeError(f'Batch preflight failed. Existing cells: {existing}. Missing kit meshes: {missing}.')
    completed = {}
    for identifier in identifiers:
        try:
            completed[identifier] = await run(plan_path, mode='save', cell_id=identifier)
        except Exception as error:
            raise RuntimeError(f'Failed at {identifier}. Saved cells: {list(completed)}. {error}') from error
        await asyncio.sleep(0)
    return completed
