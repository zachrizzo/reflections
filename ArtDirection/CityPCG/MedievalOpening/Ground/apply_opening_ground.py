"""Import and place the clean cosmetic ground overlay in the Unreal Editor."""

import json
from pathlib import Path

import unreal


ROOT = Path(__file__).resolve().parent / 'Source'
MESH = 'SM_GL1450_OpeningGround'
DESTINATION = '/Game/GrayLondon/MedievalOpening/Ground'
LEVEL = '/Game/GrayLondon/Maps/GrayLondon_Geodata'
EXTERNAL_ACTORS = '/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/'
ACTOR = 'GL_1450_Opening_PackedEarthAndCobbles'


def checked_editor_world():
    world_manager = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = world_manager.get_editor_world()
    if not world or world.get_path_name().split('.')[0] != LEVEL:
        raise RuntimeError(f'Open {LEVEL} in the editor first')
    if world_manager.get_game_world():
        raise RuntimeError('The editor is in Play In Editor')
    return world


def load_assets():
    paths = unreal.EditorAssetLibrary.list_assets(DESTINATION, recursive=True, include_folder=False)
    if not paths:
        task = unreal.AssetImportTask()
        task.set_editor_properties({
            'filename': str(ROOT / f'{MESH}.glb'),
            'destination_path': DESTINATION,
            'destination_name': MESH,
            'automated': True,
            'save': False,
            'replace_existing': False,
        })
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        assets = list(task.get_objects())
    else:
        assets = [unreal.load_asset(path) for path in paths]

    if not assets or any(not asset or not asset.get_package().get_name().startswith(f'{DESTINATION}/')
                         for asset in assets):
        raise RuntimeError('Ground draft import requires owned destination packages')
    mesh, = (asset for asset in assets if isinstance(asset, unreal.StaticMesh) and asset.get_name() == MESH)
    textures = [asset for asset in assets if isinstance(asset, unreal.Texture2D)]
    if len(textures) != 3:
        raise RuntimeError(f'Expected color, normal and roughness textures: {textures}')

    editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    description = mesh.get_static_mesh_description(0)
    box = mesh.get_bounding_box()
    minimum, maximum = box.get_editor_property('min'), box.get_editor_property('max')
    if description.get_triangle_count() != 10 or editor.get_num_uv_channels(mesh, 0) != 1:
        raise RuntimeError('Unexpected ground topology or UV channel count')
    if (abs(minimum.x + 405) > 1 or abs(maximum.x - 1107) > 1 or
            abs(minimum.y + 462) > 1 or abs(maximum.y - 751) > 1 or
            abs(minimum.z - 10.7) > .1 or abs(maximum.z - 28.7) > .1):
        raise RuntimeError(f'Unexpected axis conversion or placement: {minimum}, {maximum}')
    if editor.get_simple_collision_count(mesh):
        editor.remove_collisions(mesh)
    return mesh, assets


def place_actor(mesh):
    report = json.loads((ROOT / 'opening_ground_report.json').read_text(encoding='utf-8'))
    anchor = unreal.Vector(*report['base_actor_position_cm'])
    editor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    selection = editor.get_selected_level_actors()
    previous = [actor for actor in editor.get_all_level_actors() if actor.get_actor_label() == ACTOR]
    if len(previous) > 1:
        raise RuntimeError(f'Found duplicate {ACTOR} actors')

    try:
        with unreal.ScopedEditorTransaction('Place medieval opening ground overlay'):
            actor = previous[0] if previous else editor.spawn_actor_from_object(mesh, anchor, unreal.Rotator())
            if not actor or not actor.get_package().get_name().startswith(EXTERNAL_ACTORS):
                raise RuntimeError('Placement requires a new Gray London external actor package')
            actor.modify()
            actor.set_actor_label(ACTOR)
            actor.set_folder_path('Gray London/Medieval Opening/Ground')
            actor.set_actor_location(anchor, False, True)
            component = actor.get_component_by_class(unreal.StaticMeshComponent)
            component.modify()
            component.set_collision_profile_name('NoCollision')
            component.set_editor_property('cast_shadow', False)
            actor.set_actor_enable_collision(False)
            if (not component or str(component.get_collision_profile_name()) != 'NoCollision' or
                    actor.get_actor_enable_collision()):
                raise RuntimeError('Ground overlay could block the player')
            return actor
    finally:
        editor.set_selected_level_actors(selection)


def main():
    checked_editor_world()
    mesh, assets = load_assets()
    actor = place_actor(mesh)
    actor_package = actor.get_package()
    packages = [asset.get_package().get_name() for asset in assets]
    for path in packages:
        if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            raise RuntimeError(f'Could not save {path}')
    if not unreal.EditorLoadingAndSavingUtils.save_packages([actor_package], only_dirty=False):
        raise RuntimeError(f'Could not save {actor_package.get_name()}')
    packages.append(actor_package.get_name())
    if unreal.MultiUserClientStatics.get_multi_user_connection_status_detail() == unreal.MultiUserConnectionStatus.CONNECTED:
        unreal.MultiUserClientStatics.persist_specified_packages([unreal.Name(path) for path in packages])
    return {'actor': actor.get_actor_label(), 'saved_packages': packages}


if __name__ == '__main__':
    unreal.log(str(main()))
