"""Hero coat and cloak textures -> LOD group Character (packaging caps World-group textures at 1024; Character keeps 2048).

Editor Python, no PIE, in a queue slot. Walks the garment components of BP_HeroTravelVisual (TravelDrape, TravelSleeves,
TravelBoots, TravelShirt, TravelTrousers, HeroCoat, HeroTails), collects every texture their materials use (component
overrides, else the mesh's slots), sets lod_group = TEXTUREGROUP_CHARACTER where it is not already, and saves only those
texture packages. Nothing else is changed. RESULT lists each texture with its old and new group.
"""
import unreal

BP = '/Game/Characters/Hero/TravelCloak/BP_HeroTravelVisual'
COMPS = ('TravelDrape', 'TravelSleeves', 'TravelBoots', 'TravelShirt', 'TravelTrousers', 'HeroCoat', 'HeroTails')
MEL = unreal.MaterialEditingLibrary
RESULT = {'changed': [], 'already': [], 'materials': []}

if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world():
    RESULT = 'PIE running: nothing changed'
else:
    bp = unreal.load_asset(BP)
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    SDL = unreal.SubobjectDataBlueprintFunctionLibrary
    mats = []
    for h in sds.k2_gather_subobject_data_for_blueprint(bp):
        d = SDL.get_data(h)
        o = SDL.get_object(d)
        if not isinstance(o, unreal.SkeletalMeshComponent) or str(SDL.get_variable_name(d)) not in COMPS:
            continue
        over = [m for m in o.get_editor_property('override_materials') if m]
        mesh = o.get_editor_property('skeletal_mesh_asset')
        slots = [s.material_interface for s in mesh.get_editor_property('materials')] if mesh else []
        mats += over or [m for m in slots if m]
    seen = set()
    for m in mats:
        if m.get_path_name() in seen:
            continue
        seen.add(m.get_path_name())
        RESULT['materials'].append(m.get_path_name().split('.')[0])
        base = m.get_base_material() if hasattr(m, 'get_base_material') else m
        texs = set(MEL.get_used_textures(base)) if base else set()
        if isinstance(m, unreal.MaterialInstance):
            for tp in m.get_editor_property('texture_parameter_values'):
                if tp.get_editor_property('parameter_value'):
                    texs.add(tp.get_editor_property('parameter_value'))
        for t in texs:
            if not isinstance(t, unreal.Texture2D) or t.get_path_name().startswith('/Engine/'):
                continue
            old = t.get_editor_property('lod_group')
            if old == unreal.TextureGroup.TEXTUREGROUP_CHARACTER:
                RESULT['already'].append(t.get_path_name().split('.')[0])
                continue
            t.set_editor_property('lod_group', unreal.TextureGroup.TEXTUREGROUP_CHARACTER)
            ok = unreal.EditorAssetLibrary.save_loaded_asset(t, only_if_is_dirty=False)
            RESULT['changed'].append([t.get_path_name().split('.')[0], str(old), ok])
