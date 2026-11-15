"""Import garments fitted by fit_codex_garments.py into Unreal as skeletal meshes on their body's skeleton.

Run in the editor (Python), in a PIE-free moment and outside any SAVE FREEZE. Globals in:
    ITEMS = [{
        'fbx': 'Intermediate/ClothingFit2026_11_14/Out/<id>/<Name>.fbx',     # project-relative
        'dest': '/Game/Characters/Lanthorne/Clothing/Giltside/CivilianWorker',
        'body': '/Game/Characters/RedLondon/FerryPilot/Assembled/FerryPilot/Body/SKM_MHC_FerryPilot_BodyMesh',
        'textures': {'BaseColor': 'ArtDirection/.../x_BaseColor.png', 'Normal': '...', 'ORM': '...'},   # optional
        'tint': [1, 1, 1],                                                     # optional
        'body_copy': False,   # True for the outfit's hidden-skin body: copies the body's materials, physics asset
                              # and post-process anim BP instead of making a garment material
    }, ...]
    REPLACE = False     # True re-imports over an existing asset of the same name

Per item: imports the FBX with the legacy FBX importer (as the hero coat was), onto the body mesh's own skeleton,
imports its textures at <= 2K (normal map and ORM linear), makes a material instance of M_LanthorneGarment
(BaseColor x Tint, Normal, ORM = AO/Roughness/Metallic, two-sided), checks bounds and skeleton, and saves.
Nothing else is touched: no Blueprint, level or existing asset. RESULT holds per-item results.
"""
import os

import unreal

A = unreal.EditorAssetLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
MEL = unreal.MaterialEditingLibrary
PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
MASTER = '/Game/Characters/Lanthorne/Clothing/Materials/M_LanthorneGarment'
REPLACE = globals().get('REPLACE', False)
RESULT = {'items': []}


def master_material():
    if A.does_asset_exist(MASTER):
        return unreal.load_asset(MASTER)
    folder, name = MASTER.rsplit('/', 1)
    mat = TOOLS.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property('two_sided', True)
    base = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D, -700, -200)
    base.set_editor_property('parameter_name', 'BaseColor')
    tint = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -700, 50)
    tint.set_editor_property('parameter_name', 'Tint')
    tint.set_editor_property('default_value', unreal.LinearColor(1, 1, 1, 1))
    mul = MEL.create_material_expression(mat, unreal.MaterialExpressionMultiply, -350, -150)
    MEL.connect_material_expressions(base, 'RGB', mul, 'A')
    MEL.connect_material_expressions(tint, '', mul, 'B')
    MEL.connect_material_property(mul, '', unreal.MaterialProperty.MP_BASE_COLOR)
    nrm = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D, -700, 250)
    nrm.set_editor_property('parameter_name', 'Normal')
    nrm.set_editor_property('sampler_type', unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    nrm.set_editor_property('texture', unreal.load_asset('/Engine/EngineMaterials/DefaultNormal'))
    MEL.connect_material_property(nrm, 'RGB', unreal.MaterialProperty.MP_NORMAL)
    orm = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D, -700, 550)
    orm.set_editor_property('parameter_name', 'ORM')
    orm.set_editor_property('sampler_type', unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    orm.set_editor_property('texture', unreal.load_asset('/Engine/EngineResources/WhiteSquareTexture'))
    MEL.connect_material_property(orm, 'R', unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
    MEL.connect_material_property(orm, 'G', unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(orm, 'B', unreal.MaterialProperty.MP_METALLIC)
    MEL.recompile_material(mat)
    A.save_loaded_asset(mat, only_if_is_dirty=False)
    return mat


def import_texture(path, dest, kind):
    full = path if os.path.isabs(path) else os.path.join(PROJECT, path)
    name = 'T_' + os.path.splitext(os.path.basename(full))[0]
    task = unreal.AssetImportTask()
    task.filename = full
    task.destination_path = dest + '/Textures'
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = False
    TOOLS.import_asset_tasks([task])
    tex = unreal.load_asset(dest + '/Textures/' + name)
    if kind == 'Normal':
        tex.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_NORMALMAP)
        tex.set_editor_property('srgb', False)
    elif kind == 'ORM':
        tex.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_MASKS)
        tex.set_editor_property('srgb', False)
    tex.set_editor_property('max_texture_size', 2048)
    tex.set_editor_property('lod_group', unreal.TextureGroup.TEXTUREGROUP_CHARACTER)
    A.save_loaded_asset(tex, only_if_is_dirty=False)
    return tex


def bounds(mesh):
    b = mesh.get_bounds()
    o, e = b.origin, b.box_extent
    return [round(o.x - e.x, 1), round(o.x + e.x, 1), round(o.y - e.y, 1), round(o.y + e.y, 1),
            round(o.z - e.z, 1), round(o.z + e.z, 1)]


def import_one(item):
    out = {'fbx': item['fbx']}
    fbx = item['fbx'] if os.path.isabs(item['fbx']) else os.path.join(PROJECT, item['fbx'])
    name = os.path.splitext(os.path.basename(fbx))[0]
    dest = item['dest']
    path = dest + '/' + name
    body = unreal.load_asset(item['body'])
    skeleton = body.get_editor_property('skeleton')
    out['skeleton'] = skeleton.get_path_name()
    if not os.path.exists(fbx):
        out['error'] = 'fbx missing'
        return out
    if A.does_asset_exist(path) and not REPLACE:
        out['error'] = 'asset exists; pass REPLACE=True to re-import'
        return out
    s = unreal.FbxImportUI()
    s.automated_import_should_detect_type = False
    s.mesh_type_to_import = unreal.FBXImportType.FBXIT_SKELETAL_MESH
    s.import_as_skeletal = True
    s.import_mesh = True
    s.import_materials = False
    s.import_textures = False
    s.import_animations = False
    s.create_physics_asset = False
    s.skeleton = skeleton
    s.skeletal_mesh_import_data.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
    s.skeletal_mesh_import_data.set_editor_property('import_morph_targets', False)
    s.skeletal_mesh_import_data.set_editor_property('import_uniform_scale', 1.0)
    s.skeletal_mesh_import_data.set_editor_property('convert_scene', True)
    s.skeletal_mesh_import_data.set_editor_property('convert_scene_unit', True)
    task = unreal.AssetImportTask()
    task.filename = fbx
    task.destination_path = dest
    task.destination_name = name
    task.automated = True
    task.replace_existing = bool(REPLACE)
    task.save = False
    task.options = s
    cv = 'Interchange.FeatureFlags.Import.FBX'
    prev = unreal.SystemLibrary.get_console_variable_bool_value(cv)
    try:
        unreal.SystemLibrary.execute_console_command(None, cv + ' 0')
        TOOLS.import_asset_tasks([task])
    finally:
        unreal.SystemLibrary.execute_console_command(None, cv + (' 1' if prev else ' 0'))
    mesh = unreal.load_asset(path)
    if mesh is None:
        out['error'] = 'import failed'
        return out
    out['asset'] = path
    out['skeleton_ok'] = mesh.get_editor_property('skeleton') == skeleton
    out['bounds_cm_xyz_minmax'] = bounds(mesh)
    out['body_bounds_cm_xyz_minmax'] = bounds(body)
    if item.get('body_copy'):
        # The outfit's body with covered skin removed: it must behave exactly like the body it replaces.
        src = body.get_editor_property('materials')
        slots = mesh.get_editor_property('materials')
        for i in range(min(len(src), len(slots))):
            sl = slots[i]
            sl.material_interface = src[i].material_interface
            slots[i] = sl
        mesh.set_editor_property('materials', slots)
        for prop in ('physics_asset', 'post_process_anim_blueprint', 'shadow_physics_asset'):
            try:
                mesh.set_editor_property(prop, body.get_editor_property(prop))
            except Exception as e:
                out.setdefault('copy_skipped', []).append(prop)
        out['slots'] = [len(src), len(slots)]
        out['saved'] = unreal.EditorLoadingAndSavingUtils.save_packages([mesh.get_package()], False)
        return out
    # Materials: one instance per slot. 'slot_info' (from the fit report) gives each slot's texture file or flat
    # colour; without it, every slot gets the piece's 'textures'.
    info = item.get('slot_info') or {}
    white = unreal.load_asset('/Engine/EngineResources/WhiteSquareTexture')
    slots = mesh.get_editor_property('materials')
    made = []
    for i in range(len(slots)):
        sl = slots[i]
        sname = str(sl.get_editor_property('material_slot_name'))
        si = info.get(sname)
        suffix = ('_' + sname.split('_')[-1]) if (len(slots) > 1 and si is not None) else ''
        mi_path = dest + '/Materials/MI_' + name.replace('SK_', '') + suffix
        if A.does_asset_exist(mi_path):
            mi = unreal.load_asset(mi_path)
        else:
            mi = TOOLS.create_asset(mi_path.rsplit('/', 1)[1], dest + '/Materials', unreal.MaterialInstanceConstant,
                                    unreal.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(mi, master_material())
        if si is not None:
            if si.get('texture'):
                MEL.set_material_instance_texture_parameter_value(mi, 'BaseColor', import_texture(si['texture'], dest, 'BaseColor'))
                col = [1, 1, 1]
            else:
                MEL.set_material_instance_texture_parameter_value(mi, 'BaseColor', white)
                col = si.get('color') or [0.5, 0.5, 0.5]
            MEL.set_material_instance_vector_parameter_value(mi, 'Tint', unreal.LinearColor(col[0], col[1], col[2], 1))
        else:
            for kind, p in (item.get('textures') or {}).items():
                MEL.set_material_instance_texture_parameter_value(mi, kind, import_texture(p, dest, kind))
        tint = item.get('tint')
        if tint:
            MEL.set_material_instance_vector_parameter_value(mi, 'Tint', unreal.LinearColor(tint[0], tint[1], tint[2], 1))
        MEL.update_material_instance(mi)
        A.save_loaded_asset(mi, only_if_is_dirty=False)
        sl.material_interface = mi
        slots[i] = sl
        made.append([sname, mi.get_path_name().split('.')[0]])
    mesh.set_editor_property('materials', slots)
    out['materials'] = made
    out['slots'] = len(slots)
    out['saved'] = unreal.EditorLoadingAndSavingUtils.save_packages([mesh.get_package()], False)
    return out


for it in ITEMS:
    try:
        RESULT['items'].append(import_one(it))
    except Exception as e:  # report and carry on with the next piece
        RESULT['items'].append({'fbx': it.get('fbx'), 'error': repr(e)})
