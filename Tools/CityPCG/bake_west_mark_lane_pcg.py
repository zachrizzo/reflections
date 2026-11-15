"""Generate PCG placements and bake them into the existing West Mark Lane pilot.

After the saved geometry, live source and visual checks, run through Unreal
MCP with the codex-gray-london editor lease. `await run()` validates generation
and removes its scratch volume. `await run(save=True)` also saves the one
replacement actor. The pilot's existing runtime switch controls activation.
"""

import asyncio
from pathlib import Path
import time

from apply_facade_pcg import cell_transform, populate_point_mesh_graph
import place_west_mark_lane_replacement as pilot


async def run(*, save=False):
    import unreal

    world = pilot.require_lease_and_editor(unreal)
    saved_dir = Path(unreal.Paths.project_saved_dir())
    lease = pilot.read_json(saved_dir / 'PIE_LOCK.json')
    if float(lease['expires_epoch']) - time.time() < 120:
        raise RuntimeError('The Gray London lease must have at least two minutes remaining.')
    project = Path(unreal.Paths.project_dir()).resolve()
    rows = pilot.checked_plan(project)
    groups = {row['asset']: [(row['world_cm'], row['yaw_deg'], (1, 1, 1), seed)]
              for seed, row in enumerate(rows, 1)}
    meshes = {path: unreal.EditorAssetLibrary.load_asset(path) for path in groups}
    if any(not isinstance(mesh, unreal.StaticMesh) or
           mesh.get_path_name().split('.')[0] != path for path, mesh in meshes.items()):
        raise RuntimeError('The reviewed West Mark Lane meshes must resolve without redirects.')

    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    pcg = unreal.get_editor_subsystem(unreal.PCGEditorSubsystem)
    graph = unreal.new_object(unreal.PCGGraph)
    if graph.get_package().get_name() != '/Engine/Transient':
        raise RuntimeError('Could not create the PCG graph in the transient package.')
    populate_point_mesh_graph(unreal, pcg, graph, groups, meshes)

    def check_editor():
        if (pilot.require_lease_and_editor(unreal) != world or
                pilot.read_json(saved_dir / 'PIE_LOCK.json') != lease):
            raise RuntimeError('The editor world or lease changed during PCG generation.')

    selection = actors.get_selected_level_actors()
    scratch = None
    placements = {}
    try:
        check_editor()
        info = pcg.spawn_graph_instance(graph, 'WestMarkLane_PCG_Bake', cell_transform(unreal, groups))
        scratch = info.get_editor_property('actor')
        if not scratch:
            raise RuntimeError('Could not spawn the scratch PCG volume.')
        scratch.set_is_temporarily_hidden_in_editor(True)
        scratch.set_actor_enable_collision(False)
        component = scratch.get_component_by_class(unreal.PCGComponent)
        component.set_editor_properties({
            'generation_trigger': unreal.PCGComponentGenerationTrigger.GENERATE_ON_DEMAND,
            'generate_on_drop_when_trigger_on_demand': False,
            'regenerate_in_editor': False,
            'is_component_partitioned': False,
        })
        if component.get_editor_property('generation_in_progress'):
            pending = pcg.wait_for_graph_instance(component)
        else:
            pending = pcg.execute_graph_instance(component)
        deadline = time.monotonic() + 25
        while not pending.get_editor_property('is_complete'):
            if time.monotonic() >= deadline:
                raise RuntimeError('West Mark Lane PCG generation timed out.')
            check_editor()
            await asyncio.sleep(.25)
        error = pending.get_editor_property('error')
        if error:
            raise RuntimeError(f'West Mark Lane PCG generation failed: {error}')
        for message in pending.get_editor_property('value'):
            if str(message.get_editor_property('severity')).lower() in ('fatal', 'error', 'warning'):
                raise RuntimeError(str(message.get_editor_property('message')))

        paths = {mesh.get_path_name(): path for path, mesh in meshes.items()}
        for ism in scratch.get_components_by_class(unreal.InstancedStaticMeshComponent):
            mesh = ism.get_editor_property('static_mesh')
            path = paths.get(mesh.get_path_name()) if mesh else None
            if (not path or path in placements or ism.get_instance_count() != 1 or
                    str(ism.get_collision_profile_name()) != 'NoCollision' or
                    ism.get_editor_property('can_ever_affect_navigation')):
                raise RuntimeError('Unexpected mesh, instance count, or collision in the scratch PCG output.')
            transform = ism.get_instance_transform(0, world_space=True)
            if transform is None:
                raise RuntimeError(f'PCG produced no readable transform for {path}.')
            rotation = transform.get_editor_property('rotation').rotator()
            placements[path] = (pilot.vector(transform.get_editor_property('translation')),
                                (rotation.roll, rotation.pitch, rotation.yaw),
                                pilot.vector(transform.get_editor_property('scale3d')))
        buildings = pilot.checked_pcg_placements(rows, placements)
    finally:
        if scratch:
            try:
                if not actors.destroy_actor(scratch):
                    raise RuntimeError('Could not remove the scratch PCG volume. No pilot package was saved.')
            finally:
                actors.set_selected_level_actors(selection)

    check_editor()
    if save:
        return pilot.run(pcg_placements=placements)
    return {'buildings': buildings, 'saved_packages': []}
