# Editor script (run through ue.py with PARAMS): import a prepared garment FBX and (re)build its
# Cloth Asset, Resizable Outfit and Wardrobe Item. Saves only those four packages (and T_/M_ for a new garment).
# PARAMS["hidden_face_map"] (PNG): imported as T_<Name>_BodyHiddenFaces and set as the item's body hidden-face map.
# PARAMS["mask_only"]: only that (saves T_<Name>_BodyHiddenFaces and WI_<Name>, nothing else).
from pathlib import Path
P = PARAMS
fbx = Path(P.get("fbx", ""))
package = P["package"]                      # e.g. /Game/Characters/Clothing/VillageWardrobe/MeshRetargetJerkin
name = P["name"]                            # e.g. MeshRetargetJerkin
df = unreal.get_editor_subsystem(unreal.DataflowScriptingSubsystem)
editors = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
tools = unreal.AssetToolsHelpers.get_asset_tools()
progress = Path(P["progress"])

def note(step, **extra):
    progress.write_text(json.dumps(dict(step=step, **extra)))

def resource(path):
    return unreal.load_object(None, path + "." + path.rsplit("/", 1)[-1])

def save(asset):
    assert unreal.EditorLoadingAndSavingUtils.save_packages([asset.get_outermost()], False), asset.get_path_name()

assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(), "a play session is running"
if not P.get("mask_only"):
    material = resource(P["material"])
    if not material and P.get("texture"):
        # a new garment: import its generated colour texture and make a plain two-sided cloth material from it
        image = unreal.AssetImportTask()
        image.filename = P["texture"]
        image.destination_path = package
        image.destination_name = "T_" + name + "_BaseColor"
        image.automated = True
        image.replace_existing = True
        image.save = True
        tools.import_asset_tasks([image])
        texture = resource(package + "/T_" + name + "_BaseColor")
        assert texture, "texture import failed: " + P["texture"]
        folder, material_name = P["material"].rsplit("/", 1)
        material = tools.create_asset(material_name, folder, unreal.Material, unreal.MaterialFactoryNew())
        ml = unreal.MaterialEditingLibrary
        sample = ml.create_material_expression(material, unreal.MaterialExpressionTextureSample, -405, -85)
        sample.set_editor_property("texture", texture)
        virtual = texture.get_editor_property("virtual_texture_streaming")
        sample.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_VIRTUAL_COLOR if virtual else unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
        assert ml.connect_material_property(sample, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
        rough = ml.create_material_expression(material, unreal.MaterialExpressionConstant, -400, 205)
        rough.set_editor_property("r", float(P.get("roughness", .8)))
        assert ml.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
        material.set_editor_property("two_sided", True)
        material.set_editor_property("used_with_skeletal_mesh", True)
        material.set_editor_property("used_with_clothing", True)
        ml.recompile_material(material)
        save(texture)
        save(material)
        note("material", texture=texture.get_path_name())
    body = resource(P["source_body"])
    weight_source = resource(P.get("weight_source") or P["source_body"])
    assert material and body and weight_source and fbx.is_file(), (str(material), str(body), str(weight_source), fbx.is_file())
    settings = unreal.FbxImportUI()
    settings.automated_import_should_detect_type = False
    settings.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
    settings.import_as_skeletal = False
    settings.import_materials = False
    settings.import_textures = False
    settings.static_mesh_import_data.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
    settings.static_mesh_import_data.combine_meshes = True
    settings.static_mesh_import_data.auto_generate_collision = False
    settings.static_mesh_import_data.generate_lightmap_u_vs = False
    task = unreal.AssetImportTask()
    task.filename = str(fbx)
    task.destination_path = package
    task.destination_name = "SM_" + name
    task.save = True
    task.automated = True
    task.replace_existing = True
    task.replace_existing_settings = True
    task.options = settings
    flag = "Interchange.FeatureFlags.Import.FBX"
    before = unreal.SystemLibrary.get_console_variable_bool_value(flag)
    try:
        unreal.SystemLibrary.execute_console_command(None, flag + " 0")
        tools.import_asset_tasks([task])
    finally:
        unreal.SystemLibrary.execute_console_command(None, flag + (" 1" if before else " 0"))
    mesh = resource(package + "/SM_" + name)
    assert isinstance(mesh, unreal.StaticMesh), str(task.get_objects())
    for i, slot in enumerate(mesh.static_materials):
        mesh.set_material(i, material)
    save(mesh)
    note("static mesh", triangles=mesh.get_num_triangles(0), box=str(mesh.get_bounding_box()))

    path = package + "/CA_" + name
    ca = resource(path) or df.create_asset_with_dataflow(unreal.ChaosClothAsset, path, "")
    assert ca
    graph = df.get_dataflow_from_asset(ca)
    old_nodes = {str(node.path) for node in df.get_graph_info(graph, "").nodes}
    for kind, label, x in [("FChaosClothAssetStaticMeshImportNode_v2", "StaticMeshImport", 0),
                           ("FChaosClothAssetTransferSkinWeightsNode", "TransferSkinWeights", 330),
                           ("FChaosClothAssetTerminalNode_v2", "ClothAssetTerminal", 700)]:
        if label not in old_nodes:
            df.add_node(graph, "", kind, label, unreal.Vector2D(x, 0))
    df.set_node_properties(graph, "StaticMeshImport", {"StaticMesh": mesh.get_path_name(), "bImportSimMesh": "False"})
    transfer = {"TargetMeshType": "Render", "RenderMeshSourceType": "SkeletalMesh", "SkeletalMesh": weight_source.get_path_name(),
                "TransferMethod": P.get("transfer_method", "ClosestPointOnSurface")}
    transfer.update(P.get("transfer_properties", {}))
    df.set_node_properties(graph, "TransferSkinWeights", transfer)
    if not old_nodes:
        df.add_link(graph, "StaticMeshImport.Collection", "TransferSkinWeights.Collection")
        pin = next(str(p.path) for p in df.get_node_info(graph, "ClothAssetTerminal").pins if str(p.direction) == "Input")
        df.add_link(graph, "TransferSkinWeights.Collection", pin)
    df.set_dataflow_terminal(ca, "ClothAssetTerminal")
    assert editors.open_editor_for_assets([ca]), path
    try:
        df.set_node_properties(graph, "StaticMeshImport", {"StaticMesh": "None"})
        df.set_node_properties(graph, "StaticMeshImport", {"StaticMesh": mesh.get_path_name()})
        await asyncio.sleep(1.2)
        save(ca)
    finally:
        editors.close_all_editors_for_asset(ca)
    note("cloth asset")

    path = package + "/OA_" + name
    outfit = resource(path) or df.create_asset_with_dataflow(unreal.ChaosOutfitAsset, path, "/ChaosOutfitAsset/MakeResizableOutfitTemplate.MakeResizableOutfitTemplate")
    assert outfit
    assert editors.open_editor_for_assets([outfit]), path
    try:
        source = f'((SizeName="{P.get("size_name", "Source")}",SourceAsset={ca.get_path_name()},SourceBodyParts=({body.get_path_name()}),NumResizingInterpolationPoints={P.get("interpolation_points", 1750)}))'
        df.set_variable_override(outfit, "SizedOutfitSource", "()")
        await asyncio.sleep(.3)
        df.set_variable_override(outfit, "SizedOutfitSource", source)
        await asyncio.sleep(2.0)
        save(outfit)
    finally:
        editors.close_all_editors_for_asset(outfit)
    note("outfit")

path = package + "/WI_" + name
item = resource(path)
if not P.get("mask_only"):
    item = item or tools.create_asset("WI_" + name, package, unreal.MetaHumanWardrobeItem, unreal.MetaHumanWardrobeItemFactory())
    assert item
    pipeline = item.get_pipeline()
    if not pipeline:
        item.set_pipeline_from_class(unreal.MetaHumanOutfitPipeline)
        pipeline = item.get_pipeline()
        pipeline.set_editor_property("editor_pipeline", unreal.new_object(unreal.AnimatedOutfitEditorPipeline, outer=pipeline))
    principal = item.get_editor_property("principal_asset")
    principal.set_editor_property("asset", outfit)
    item.set_editor_property("principal_asset", principal)
    if P.get("thumbnail_name"):
        item.set_editor_property("thumbnail_name", P["thumbnail_name"])
assert item, path
result = {"wardrobe": item.get_path_name()}
mask_png = P.get("hidden_face_map")
if mask_png and Path(mask_png).is_file():
    # Body hidden-face map (made by garmentprep/hidden_face_map.py): body triangles under the garment are removed
    # when a character wearing this item is built. Linear, no mips; the build reads the texture's source pixels.
    image = unreal.AssetImportTask()
    image.filename = mask_png
    image.destination_path = package
    image.destination_name = "T_" + name + "_BodyHiddenFaces"
    image.automated = True
    image.replace_existing = True
    image.save = False
    tools.import_asset_tasks([image])
    mask = resource(package + "/T_" + name + "_BodyHiddenFaces")
    assert isinstance(mask, unreal.Texture2D), "hidden face map import failed: " + mask_png
    mask.set_editor_property("srgb", False)
    mask.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_GRAYSCALE)
    mask.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    mask.set_editor_property("never_stream", True)
    save(mask)
    editor_pipeline = item.get_pipeline().get_editor_property("editor_pipeline")
    value = editor_pipeline.get_editor_property("body_hidden_face_map_texture")
    value.set_editor_property("texture", mask)
    mask_settings = value.get_editor_property("settings")
    mask_settings.set_editor_property("max_shrink_distance", float(P.get("max_shrink", 0.)))   # grey band of the map: skin pushed in, not removed
    value.set_editor_property("settings", mask_settings)
    item.modify()
    editor_pipeline.set_editor_property("body_hidden_face_map_texture", value)
    check = editor_pipeline.get_editor_property("body_hidden_face_map_texture")
    settings = check.get_editor_property("settings")
    result["body_hidden_face_map"] = {"texture": check.get_editor_property("texture").get_path_name(), "size": [mask.blueprint_get_size_x(), mask.blueprint_get_size_y()],
                                      "max_cull": settings.get_editor_property("max_cull_value"), "min_keep": settings.get_editor_property("min_keep_value"),
                                      "max_shrink": settings.get_editor_property("max_shrink_distance")}
save(item)
if not P.get("mask_only"):
    test = unreal.ChaosClothComponent()
    test.set_asset(outfit)
    result.update({"mesh": mesh.get_path_name(), "bone_count": test.get_num_bones(),
                   "material_ok": test.get_material(0).get_path_name() == material.get_path_name(),
                   "triangles": mesh.get_num_triangles(0), "box": str(mesh.get_bounding_box())})
note("done", **result)
result
