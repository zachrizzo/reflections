"""Read-only proof for the three saved Gray London facade cells.

Load from the Unreal Python scripting tool and call `audit()` after a tester
starts the game normally. Call `audit(use_editor_world=True)` to compare with
the editor scene. This does not start PIE, move a camera, or save packages.
"""

from collections import Counter
import math


EXPECTED = {
    'x19_y2': (179, '/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/6/TI/H6C3VPIZH4C8OZOR2J4B7A'),
    'x20_y2': (125, '/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/7/H7/75C2FNPIUKJPRAQ8KQX7GO'),
    'x21_y2': (229, '/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/8/R9/8MIZ7LKKEYYDETP4IMGS83'),
}
PREFIX = 'PCG_GL_Facades_'
GRAPH_ROOT = '/Game/GrayLondon/CityPCG/Graphs/'
KIT_ROOT = '/Game/GrayLondon/CityPCG/Kit/'


def vec(point):
    return [round(point.x, 2), round(point.y, 2), round(point.z, 2)]


def distance(a, b):
    return math.dist((a.x, a.y, a.z), (b.x, b.y, b.z))


def read_cook_dependencies(unreal):
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    runtime_refs = unreal.AssetRegistryDependencyOptions()
    runtime_refs.set_editor_properties({
        'include_hard_package_references': True,
        'include_soft_package_references': True,
        'include_game_package_references': True,
        'include_editor_only_package_references': False,
    })
    result = {}
    for cell_id, (_, package) in EXPECTED.items():
        graph = GRAPH_ROOT + PREFIX + cell_id
        actor_dependencies = {str(dep) for dep in registry.get_dependencies(package, runtime_refs) or []}
        graph_dependencies = {str(dep) for dep in registry.get_dependencies(graph, runtime_refs) or []}
        meshes = actor_dependencies | graph_dependencies
        result[cell_id] = {
            'actor_package': package,
            'graph_package': graph,
            'actor_has_runtime_graph_reference': graph in actor_dependencies,
            'actor_kit_refs': sorted(dep for dep in actor_dependencies if dep.startswith(KIT_ROOT)),
            'graph_kit_refs': sorted(dep for dep in graph_dependencies if dep.startswith(KIT_ROOT)),
            'kit_asset_count': sum(dep.startswith(KIT_ROOT) for dep in meshes),
        }
    return result


def inspect_actor(unreal, actor, expected_count, camera):
    instances = Counter()
    nearest = None
    rendered = []
    hidden = []
    blockers = []
    for ism in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
        mesh = ism.get_editor_property('static_mesh')
        count = ism.get_instance_count()
        name = mesh.get_name() if mesh else 'MISSING_MESH'
        instances[name] += count
        if not ism.is_visible() or ism.get_editor_property('hidden_in_game'):
            hidden.append(ism.get_name())
        if str(ism.get_collision_profile_name()) != 'NoCollision' or ism.get_editor_property('can_ever_affect_navigation'):
            blockers.append(ism.get_name())
        if camera is not None and ism.was_recently_rendered(0.5):
            rendered.append(ism.get_name())
        if camera is not None:
            for index in range(count):
                transform = ism.get_instance_transform(index, True)
                if transform is not None:
                    point = transform.get_editor_property('translation')
                    new_distance = distance(point, camera)
                    nearest = new_distance if nearest is None else min(nearest, new_distance)
    total = sum(instances.values())
    pcg = actor.get_component_by_class(unreal.PCGComponent)
    graph = pcg.get_graph() if pcg else None
    origin, extent = actor.get_actor_bounds(False)
    return {
        'actor': actor.get_path_name(),
        'graph': graph.get_path_name() if graph else None,
        'spatial': actor.get_editor_property('is_spatially_loaded'),
        'actor_hidden_in_game': actor.get_editor_property('hidden'),
        'pcg_generation_trigger': str(pcg.get_editor_property('generation_trigger')) if pcg else None,
        'pcg_generated': pcg.get_editor_property('generated') if pcg else None,
        'bounds_origin_cm': vec(origin),
        'bounds_extent_cm': vec(extent),
        'instances': dict(instances),
        'instance_count': total,
        'matches_plan': total == expected_count and 'MISSING_MESH' not in instances,
        'nearest_instance_to_camera_m': round(nearest / 100, 2) if nearest is not None else None,
        'recently_rendered_components': rendered,
        'hidden_components': hidden,
        'unexpected_collision_or_nav': blockers,
    }


def audit(use_editor_world=False):
    import unreal

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world() if use_editor_world else editor.get_game_world()
    result = {'requested_world': 'editor' if use_editor_world else 'PIE',
              'world': world.get_path_name() if world else None,
              'cook_dependencies': read_cook_dependencies(unreal)}
    if not world or not result['world'].endswith('GrayLondon_Geodata.GrayLondon_Geodata'):
        result['status'] = 'No active requested Gray London world.'
        return result

    eye = None
    wp = unreal.get_world_subsystem(world, unreal.WorldPartitionSubsystem)
    result['streaming_completed'] = wp.is_all_streaming_completed() if wp else None
    if not use_editor_world:
        player = unreal.GameplayStatics.get_player_pawn(world, 0)
        camera = unreal.GameplayStatics.get_player_camera_manager(world, 0)
        game = unreal.GameplayStatics.get_game_instance(world)
        jump_subsystem = getattr(unreal, 'ReflectionsWorldJumpSubsystem', None)
        jump = unreal.get_game_instance_subsystem(game, jump_subsystem) if game and jump_subsystem else None
        eye = camera.get_camera_location() if camera else None
        result['player_location_cm'] = vec(player.get_actor_location()) if player else None
        result['camera_location_cm'] = vec(eye) if eye is not None else None
        result['camera_rotation'] = str(camera.get_camera_rotation()) if camera else None
        result['world_side'] = str(jump.get_current_world()) if jump else None

    actors = {a.get_actor_label(): a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.PCGVolume)
              if a.get_actor_label().startswith(PREFIX)}
    result['cells'] = {
        identifier: (inspect_actor(unreal, actors[PREFIX + identifier], count, eye)
                     if PREFIX + identifier in actors else {'status': 'Currently not loaded.', 'expected_instances': count})
        for identifier, (count, _) in EXPECTED.items()
    }
    return result
