"""Place the reviewed image-to-3D well in the Medieval London market."""

import asyncio
import time

from apply_facade_pcg import cell_transform, configure_spawner, populate_point_mesh_graph
from build_medieval_london_map import require_town_editor


ROOT = '/Game/GrayLondon/MedievalOpening/MarketDressing/TripoSR'
NAME = 'PCG_MedievalLondon_MarketWell'
LABEL = 'Medieval London | Market well'
COLLISION_LABEL = 'Medieval London | Well masonry collision'
CENTER = (-3100, 780, 4)


def tune_material(unreal, material):
    """Keep the source colors but account for their bright baked illumination."""
    edit = unreal.MaterialEditingLibrary
    base_color = unreal.MaterialProperty.MP_BASE_COLOR
    original = edit.get_material_property_input_node(material, base_color)
    if isinstance(original, unreal.MaterialExpressionPower):
        return
    if not isinstance(original, unreal.MaterialExpressionVertexColor):
        raise RuntimeError('Expected vertex colors on the reviewed well material.')
    power = edit.create_material_expression(material, unreal.MaterialExpressionPower, -180, -100)
    power.set_editor_property('const_exponent', 1.8)
    if (not edit.connect_material_expressions(original, '', power, 'Base') or
            not edit.connect_material_property(power, '', base_color)):
        raise RuntimeError('Could not connect the well color correction.')
    edit.recompile_material(material)


async def run():
    import unreal

    _, world = require_town_editor(unreal)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    existing = {actor.get_actor_label(): actor for actor in actors.get_all_level_actors()
                if actor.get_actor_label() in (LABEL, COLLISION_LABEL)}
    mesh = unreal.EditorAssetLibrary.load_asset(f'{ROOT}/Meshes/SM_GLMarket_MarketWell')
    material = unreal.EditorAssetLibrary.load_asset(f'{ROOT}/Materials/M_GLMarket_VertexColor_MarketWell')
    if not isinstance(mesh, unreal.StaticMesh) or not material or mesh.get_material(0) != material:
        raise RuntimeError('The reviewed well mesh and vertex-color material are required.')
    tune_material(unreal, material)

    x, y, z = CENTER
    hit = unreal.SystemLibrary.line_trace_single(
        world, unreal.Vector(x, y, z + 140), unreal.Vector(x, y, z - 35),
        unreal.TraceTypeQuery.ECC_VISIBILITY, True, [], unreal.DrawDebugTrace.NONE, False,
    )
    if not hit or not hit.to_tuple()[9] or hit.to_tuple()[9].get_actor_label() != 'Ground | City footprint 500 m':
        raise RuntimeError('The market well needs a clear patch of supported ground.')

    b = mesh.get_bounding_box()
    scale = 253.0 / (b.max.z - b.min.z)
    position = (x - (b.min.x + b.max.x) * scale * .5,
                y - (b.min.y + b.max.y) * scale * .5, z - b.min.z * scale)
    groups = {'Well': [(position, 0, (scale, scale, scale), 1500)]}
    pcg = unreal.get_editor_subsystem(unreal.PCGEditorSubsystem)
    graph = unreal.EditorAssetLibrary.load_asset(f'{ROOT}/Graphs/{NAME}')
    volume = existing.get(LABEL)
    if (graph is None) != (volume is None):
        raise RuntimeError('The well graph and its volume must either both be present or both be absent.')
    if not graph:
        graph = pcg.create_graph(NAME, f'{ROOT}/Graphs')
        populate_point_mesh_graph(unreal, pcg, graph, groups, {'Well': mesh})
        info = pcg.spawn_graph_instance(graph, LABEL, cell_transform(unreal, groups))
        volume = info.get_editor_property('actor')
    else:
        # Update the single owned spawner when retrying generation.
        spawner, = (node.get_settings() for node in graph.get_editor_property('nodes')
                    if isinstance(node.get_settings(), unreal.PCGStaticMeshSpawnerSettings))
        graph.modify()
        spawner.modify()
        configure_spawner(unreal, spawner, mesh)
    component = volume.get_component_by_class(unreal.PCGComponent)
    component.set_editor_properties({'generation_trigger': unreal.PCGComponentGenerationTrigger.GENERATE_ON_DEMAND,
                                     'generate_on_drop_when_trigger_on_demand': False,
                                     'regenerate_in_editor': False, 'is_component_partitioned': False})
    pending = (pcg.wait_for_graph_instance(component) if component.get_editor_property('generation_in_progress')
               else pcg.execute_graph_instance(component))
    deadline = time.monotonic() + 25
    while not pending.get_editor_property('is_complete'):
        if time.monotonic() > deadline:
            raise RuntimeError('Well generation timed out before any package save.')
        await asyncio.sleep(.15)
    if pending.get_editor_property('error'):
        raise RuntimeError(pending.get_editor_property('error'))
    ism, = volume.get_components_by_class(unreal.InstancedStaticMeshComponent)
    if ism.get_instance_count() != 1 or ism.get_editor_property('static_mesh') != mesh:
        raise RuntimeError('The well did not generate with the expected visual mesh.')
    ism.set_collision_profile_name('NoCollision')
    ism.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)

    # Give the stone basin a blocking footprint without sealing the open wood roof.
    collision = existing.get(COLLISION_LABEL)
    if not collision:
        collision = actors.spawn_actor_from_class(unreal.BlockingVolume, unreal.Vector(x, y, z + 40))
        if not collision:
            raise RuntimeError('Could not create the well basin collision.')
        collision.set_actor_label(COLLISION_LABEL)
    collision.set_actor_scale3d(unreal.Vector(1.02, 1.02, .42))
    if not unreal.ReflectionsWorldLibrary.set_volume_box(collision, unreal.Vector(100, 100, 100)):
        raise RuntimeError('Could not size the well basin collision.')
    brush = collision.get_component_by_class(unreal.BrushComponent)
    brush.set_collision_profile_name('BlockAll')
    blocking = unreal.SystemLibrary.line_trace_single(
        world, unreal.Vector(x - 200, y, 65), unreal.Vector(x, y, 65),
        unreal.TraceTypeQuery.ECC_VISIBILITY, False, [], unreal.DrawDebugTrace.NONE, False,
    )
    if not blocking or blocking.to_tuple()[9] != collision:
        raise RuntimeError('The placed well did not block the confirmation trace.')
    unreal.SystemLibrary.execute_console_command(world, 'RebuildNavigation')
    require_town_editor(unreal)
    owned = [world.get_package(), graph.get_package(), material.get_package()]
    expected = ['/Game/GrayLondon/Maps/MedievalLondon', f'{ROOT}/Graphs/{NAME}',
                f'{ROOT}/Materials/M_GLMarket_VertexColor_MarketWell']
    if ([package.get_name() for package in owned] != expected or
            not unreal.EditorLoadingAndSavingUtils.save_packages(owned, only_dirty=False)):
        raise RuntimeError('Could not save the exact owned well packages.')
    return {'packages': expected, 'center_cm': CENTER, 'height_cm': 253, 'blocking_trace': True}
