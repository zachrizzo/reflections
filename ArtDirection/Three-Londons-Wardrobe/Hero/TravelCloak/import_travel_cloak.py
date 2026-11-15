"""Import the travel outfit and assign it to the default playable hero."""

import json
import traceback
from pathlib import Path

import unreal


ROOT = Path(unreal.Paths.project_intermediate_dir()).resolve() / 'TravelCloak'
ASSETS = unreal.EditorAssetLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
MATERIALS = unreal.MaterialEditingLibrary
SUBOBJECTS = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
DATA = unreal.SubobjectDataBlueprintFunctionLibrary
BASE = '/Game/Characters/Hero/TravelCloak'
OLD_VISUAL = '/Game/Characters/Hero/Sample/BP_HeroSampleVisual'
PLAYER = '/Game/Characters/Hero/Sample/BP_HeroSampleCleanTest'
VISUAL = BASE + '/BP_HeroTravelVisual'


def save(asset):
    assert ASSETS.save_loaded_asset(asset, False), asset.get_path_name()


def components(blueprint):
    return {str(DATA.get_variable_name(DATA.get_data(handle))): (handle, DATA.get_object(DATA.get_data(handle)))
            for handle in SUBOBJECTS.k2_gather_subobject_data_for_blueprint(blueprint)}


def get_or_copy(old_path, new_path):
    return ASSETS.load_asset(new_path) if ASSETS.does_asset_exist(new_path) else ASSETS.duplicate_asset(old_path, new_path)


def do_import(source_name, folder, asset_name, options=None):
    task = unreal.AssetImportTask()
    task.filename = str(ROOT / source_name)
    task.destination_path = BASE + '/' + folder
    task.destination_name = asset_name
    task.automated = True
    task.replace_existing = True
    task.options = options
    TOOLS.import_asset_tasks([task])
    asset = ASSETS.load_asset(task.destination_path + '/' + asset_name)
    assert asset, asset_name
    return asset


def skinned(part, skeleton, surface, revision):
    source_name = 'SK_HeroTravel_' + part
    name = source_name + revision
    path = BASE + '/Clothing/' + name
    mesh = ASSETS.load_asset(path) if ASSETS.does_asset_exist(path) else None
    if mesh is None:
        settings = unreal.FbxImportUI()
        settings.automated_import_should_detect_type = False
        settings.mesh_type_to_import = unreal.FBXImportType.FBXIT_SKELETAL_MESH
        settings.import_as_skeletal = True
        settings.import_mesh = True
        settings.import_materials = False
        settings.import_textures = False
        settings.import_animations = False
        settings.create_physics_asset = False
        settings.skeleton = skeleton
        settings.skeletal_mesh_import_data.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
        mesh = do_import(source_name + '.fbx', 'Clothing', name, settings)
    assert mesh.get_editor_property('skeleton') == skeleton, part
    slots = mesh.get_editor_property('materials')
    assert len(slots) == 1, (part, len(slots))
    slot = slots[0]
    slot.material_interface = surface
    slots[0] = slot
    mesh.set_editor_property('materials', slots)
    save(mesh)
    return mesh


def material(part, rgb, roughness, revision):
    name = 'M_Travel_' + part + revision
    path = BASE + '/Materials/' + name
    mat = ASSETS.load_asset(path) if ASSETS.does_asset_exist(path) else TOOLS.create_asset(
        name, BASE + '/Materials', unreal.Material, unreal.MaterialFactoryNew())
    if not MATERIALS.get_num_material_expressions(mat):
        color = MATERIALS.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -500, -100)
        color.set_editor_property('constant', unreal.LinearColor(*rgb, 1))
        if part == 'Drape':
            back = MATERIALS.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -500, 0)
            back.set_editor_property('constant', unreal.LinearColor(.022, .006, .008, 1))
            sign = MATERIALS.create_material_expression(mat, unreal.MaterialExpressionTwoSidedSign, -700, 125)
            alpha = MATERIALS.create_material_expression(mat, unreal.MaterialExpressionSaturate, -500, 125)
            mix = MATERIALS.create_material_expression(mat, unreal.MaterialExpressionLinearInterpolate, -260, -60)
            MATERIALS.connect_material_expressions(sign, '', alpha, 'Input')
            MATERIALS.connect_material_expressions(back, '', mix, 'A')
            MATERIALS.connect_material_expressions(color, '', mix, 'B')
            MATERIALS.connect_material_expressions(alpha, '', mix, 'Alpha')
            color = mix
        rough = MATERIALS.create_material_expression(mat, unreal.MaterialExpressionConstant, -260, 100)
        rough.set_editor_property('r', roughness)
        spec = MATERIALS.create_material_expression(mat, unreal.MaterialExpressionConstant, -260, 250)
        spec.set_editor_property('r', .17 if part != 'Boots' else .24)
        assert MATERIALS.connect_material_property(color, '', unreal.MaterialProperty.MP_BASE_COLOR)
        assert MATERIALS.connect_material_property(rough, '', unreal.MaterialProperty.MP_ROUGHNESS)
        assert MATERIALS.connect_material_property(spec, '', unreal.MaterialProperty.MP_SPECULAR)
        mat.set_editor_property('two_sided', True)
        MATERIALS.set_material_usage(mat, unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH)
        if part == 'Drape':
            MATERIALS.set_material_usage(mat, unreal.MaterialUsage.MATUSAGE_CLOTHING)
        MATERIALS.recompile_material(mat)
        save(mat)
    return mat


def skin_mask():
    name = 'T_HeroTravel_BodyMask'
    mask = do_import(name + '.png', 'Materials', name)
    mask.set_editor_property('srgb', False)
    mask.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_MASKS)
    mask.set_editor_property('mip_gen_settings', unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    mask.set_editor_property('never_stream', True)
    mask.set_editor_property('virtual_texture_streaming', False)
    save(mask)
    original = '/Game/Characters/Hero/SimplePreview/Materials/MI_HeroSimple_Skin_1'
    masked = get_or_copy(original, BASE + '/Materials/MI_HeroTravel_MaskedSkin')
    assert masked
    assert MATERIALS.set_material_instance_texture_parameter_value(masked, 'ClothingHideMask', mask)
    MATERIALS.update_material_instance(masked)
    save(masked)
    return masked


def attach(blueprint, name, mesh):
    nodes = components(blueprint)
    if name not in nodes:
        handle, error = SUBOBJECTS.add_new_subobject(unreal.AddNewSubobjectParams(
            parent_handle=nodes['Body'][0], new_class=unreal.SkeletalMeshComponent, blueprint_context=blueprint))
        component = DATA.get_object(DATA.get_data(handle))
        assert component, str(error)
        assert SUBOBJECTS.rename_subobject(handle, unreal.Text(name))
        SUBOBJECTS.rename_subobject_member_variable(blueprint, handle, name)
    else:
        component = nodes[name][1]
    component.set_skeletal_mesh_asset(mesh)
    component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    component.set_leader_pose_component(nodes['Body'][1], True, False)
    component.set_editor_property('use_bounds_from_leader_pose_component', name != 'TravelDrape')
    if name == 'TravelDrape':
        component.set_editor_property('bounds_scale', 1.7)
        component.set_cloth_max_distance_scale(.35)


def run(apply=False, revision=''):
    try:
        assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(), 'Stop PIE before importing'
        visual = get_or_copy(OLD_VISUAL, VISUAL)
        assert visual
        nodes = components(visual)
        native_body = nodes['Body'][1]
        body_mesh = native_body.get_skeletal_mesh_asset()
        skeleton = body_mesh.get_editor_property('skeleton')
        physics = body_mesh.get_editor_property('physics_asset')
        assert skeleton and physics and nodes['Face'][1].get_skeletal_mesh_asset()
        native_body.set_material(0, skin_mask())
        mesh_paths = {}
        for part, (rgb, roughness) in {
            'Shirt': ((.011, .012, .013), .97),
            'Trousers': ((.007, .008, .010), .97),
            'Boots': ((.016, .013, .011), .79),
            'Sleeves': ((.014, .016, .019), .95),
            'Drape': ((.014, .016, .019), .95),
        }.items():
            mesh = skinned(part, skeleton, material(part, rgb, roughness, revision), revision)
            if part == 'Drape':
                mesh.set_editor_property('physics_asset', physics)
                assert unreal.ReflectionsHeroClothTools.build_coat_tail_simulation(mesh, physics)
                save(mesh)
            attach(visual, 'Travel' + part, mesh)
            mesh_paths[part] = mesh.get_path_name()
        for name in ('HeroCoat', 'HeroTails'):
            if name in nodes:
                old = nodes[name][1]
                old.set_skeletal_mesh_asset(None)
                old.set_visibility(False)
                old.set_editor_property('hidden_in_game', True)
        unreal.BlueprintEditorLibrary.compile_blueprint(visual)
        save(visual)
        if apply:
            player = ASSETS.load_asset(PLAYER)
            assert player and ASSETS.does_asset_exist(OLD_VISUAL)
            holder = components(player)['HeroVisual'][1]
            assert isinstance(holder, unreal.ChildActorComponent)
            holder.set_child_actor_class(unreal.BlueprintEditorLibrary.generated_class(visual))
            unreal.BlueprintEditorLibrary.compile_blueprint(player)
            save(player)
        (ROOT / 'unreal_import.json').write_text(json.dumps({
            'visual': VISUAL, 'original_visual': OLD_VISUAL, 'assigned_player': PLAYER if apply else None,
            'physics_asset': physics.get_path_name(), 'meshes': mesh_paths,
        }, indent=2))
    except BaseException:
        (ROOT / 'unreal_import_error.txt').write_text(traceback.format_exc())
        raise


def update_drape(revision, material_revision):
    assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(), 'Stop PIE before importing'
    visual = ASSETS.load_asset(VISUAL)
    body_mesh = components(visual)['Body'][1].get_skeletal_mesh_asset()
    skeleton = body_mesh.get_editor_property('skeleton')
    physics = body_mesh.get_editor_property('physics_asset')
    mesh = skinned('Drape', skeleton, material('Drape', (.014, .016, .019), .95, material_revision), revision)
    mesh.set_editor_property('physics_asset', physics)
    assert unreal.ReflectionsHeroClothTools.build_coat_tail_simulation(mesh, physics)
    save(mesh)
    attach(visual, 'TravelDrape', mesh)
    unreal.BlueprintEditorLibrary.compile_blueprint(visual)
    save(visual)
    report_path = ROOT / 'unreal_import.json'
    report = json.loads(report_path.read_text())
    report['meshes']['Drape'] = mesh.get_path_name()
    report_path.write_text(json.dumps(report, indent=2))


def update_mantle_and_boots():
    assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(), 'Stop PIE before importing'
    visual = ASSETS.load_asset(VISUAL)
    body_mesh = components(visual)['Body'][1].get_skeletal_mesh_asset()
    skeleton = body_mesh.get_editor_property('skeleton')
    physics = body_mesh.get_editor_property('physics_asset')
    drape = skinned('Drape', skeleton, material('Drape', (.014, .016, .019), .95, '_Refit'), '_Mantle')
    drape.set_editor_property('physics_asset', physics)
    assert unreal.ReflectionsHeroClothTools.build_coat_tail_simulation(drape, physics)
    save(drape)
    boots = skinned('Boots', skeleton, material('Boots', (.011, .012, .013), .73, '_Generated'), '_Generated')
    attach(visual, 'TravelDrape', drape)
    attach(visual, 'TravelBoots', boots)
    unreal.BlueprintEditorLibrary.compile_blueprint(visual)
    save(visual)
    report_path = ROOT / 'unreal_import.json'
    report = json.loads(report_path.read_text())
    report['meshes']['Drape'] = drape.get_path_name()
    report['meshes']['Boots'] = boots.get_path_name()
    report_path.write_text(json.dumps(report, indent=2))


def update_generated_layers():
    assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(), 'Stop PIE before importing'
    visual = ASSETS.load_asset(VISUAL)
    body_mesh = components(visual)['Body'][1].get_skeletal_mesh_asset()
    skeleton = body_mesh.get_editor_property('skeleton')
    report_path = ROOT / 'unreal_import.json'
    report = json.loads(report_path.read_text())
    for part, rgb, roughness in (
        ('Shirt', (.011, .012, .013), .97),
        ('Trousers', (.007, .008, .010), .97),
        ('Sleeves', (.014, .016, .019), .95),
    ):
        mesh = skinned(part, skeleton, material(part, rgb, roughness, '_Refit'), '_GeneratedSurface')
        attach(visual, 'Travel' + part, mesh)
        report['meshes'][part] = mesh.get_path_name()
    unreal.BlueprintEditorLibrary.compile_blueprint(visual)
    save(visual)
    report_path.write_text(json.dumps(report, indent=2))
