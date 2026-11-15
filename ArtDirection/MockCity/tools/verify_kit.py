"""Unload each mock side level and reload it from disk: the CityKit actor's instanced components and counts, the
story markers, and how many boxes are invisible collision vs visible."""
import json
import unreal

res = {}
for side in ('Pewterside', 'Giltside', 'Frostside'):
    path = '/Game/MockCity/Lvl_MockCity_' + side
    w = unreal.load_asset(path)
    if w:
        unreal.EditorLoadingAndSavingUtils.unload_packages([w.get_outermost()])
    w = unreal.load_asset(path)
    row = {}
    kit = [a for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.StaticMeshActor)
           if a.get_actor_label().startswith('CityKit_')]
    row['kit_actors'] = len(kit)
    if kit:
        row['kit'] = {c.get_name(): [c.get_instance_count(), c.static_mesh.get_name() if c.static_mesh else None,
                                     c.get_editor_property('instance_end_cull_distance'),
                                     str(c.get_collision_profile_name()),
                                     c.get_editor_property('affect_dynamic_indirect_lighting')]
                      for c in kit[0].get_components_by_class(unreal.HierarchicalInstancedStaticMeshComponent)}
    sm = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.StaticMeshActor)
    inv = [a for a in sm if not a.static_mesh_component.get_editor_property('visible')]
    row['sm_actors'] = len(sm)
    row['invisible'] = len(inv)
    row['invisible_bldg'] = len([a for a in inv if a.get_actor_label().startswith('Bldg_')])
    row['cores'] = len([a for a in sm if a.get_actor_label().endswith('_Core')])
    row['lumen_on_visible'] = len([a for a in sm if a.static_mesh_component.get_editor_property('visible') and
                                   a.static_mesh_component.get_editor_property('affect_dynamic_indirect_lighting')])
    row['markers'] = len(unreal.GameplayStatics.get_all_actors_of_class(w, unreal.ReflectionsStoryMarker))
    res[side] = row
json.dumps(res)
