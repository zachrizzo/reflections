"""Install the three-piece Red London outfits in the playable crowd map."""
import json
import runpy
from pathlib import Path

import unreal


ART = Path(__file__).resolve().parent
PROJECT = ART.parents[3]
STAGING = PROJECT / "Intermediate/NpcMovement/SimpleRed"
LEVEL = "/Game/Characters/Hero/Sample/Lvl_HeroSampleCrowd"
DEST = "/Game/Characters/CrowdMotion/SimpleRed"
LEGACY = runpy.run_path(str(PROJECT / "ArtDirection/NPC_Reactions/import_crowd_wardrobe.py"))
PALETTE = {
    "BridgeGuard": (0.46, 0.26, 0.20),
    "ArchiveApprentice": (0.38, 0.24, 0.20),
    "CoinClerk": (0.50, 0.31, 0.22),
    "FestivalDrummer": (0.41, 0.23, 0.24),
}
SOLIDS = {"Boots": (0.36, 0.26, 0.18), "Trousers": (0.67, 0.61, 0.53)}
SPECS = {
    "BP_BridgeGuard": ("BridgeGuard", {"Tunic": "BridgeGuard_Gambeson", "Trousers": "BridgeGuard_Trousers", "Boots": "BridgeGuard_Boots"}),
    "Crowd Preview - Red 01": ("ArchiveApprentice", {"Tunic": "ArchiveApprenticeCoat", "Trousers": "ArchiveApprenticeTrousers", "Boots": "ArchiveApprenticeBoots"}),
    "Crowd Preview - Red 02": ("CoinClerk", {"Tunic": "CoinClerkCoat", "Trousers": "CoinClerkTrousers", "Boots": "CoinClerkBoots"}),
    "Crowd Preview - Red 03": ("FestivalDrummer", {"Tunic": "FestivalDrummer_Blouse", "Trousers": "FestivalDrummer_Trousers", "Boots": "FestivalDrummer_Boots"}),
}
SKIN_SLOTS = {
    "BridgeGuard": "BridgeGuard_Armor",
    "ArchiveApprentice": "ArchiveApprenticeWaistcoat",
    "CoinClerk": "CoinClerkWaistcoat",
    "FestivalDrummer": "FestivalDrummer_Capelet",
}


def textured_material(kind, name, source, destination, tint, rebuild=False):
    ea = unreal.EditorAssetLibrary
    path = f"{destination}/{name}"
    material = ea.load_asset(path) if ea.does_asset_exist(path) else None
    if material is not None and unreal.MaterialEditingLibrary.get_num_material_expressions(material) and not rebuild:
        return material
    if material is None:
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, destination, unreal.Material, unreal.MaterialFactoryNew())
    graph = unreal.MaterialEditingLibrary
    graph.delete_all_material_expressions(material)
    tint_node = graph.create_material_expression(material, unreal.MaterialExpressionConstant3Vector, -500, 200)
    tint_node.set_editor_property("constant", unreal.LinearColor(*tint, 1))
    source_path = f"{DEST}/Textures/T_RedLondon_{kind}"
    texture = ea.load_asset(source_path) if ea.does_asset_exist(source_path) else None
    if texture is None:
        task = unreal.AssetImportTask()
        task.filename = str(source)
        task.destination_path = f"{DEST}/Textures"
        task.destination_name = f"T_RedLondon_{kind}"
        task.automated = True
        task.replace_existing = False
        task.save = True
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        texture = ea.load_asset(source_path)
    if texture is None:
        raise RuntimeError(f"Texture import failed for {kind}")
    sampler = graph.create_material_expression(material, unreal.MaterialExpressionTextureSample, -500, 0)
    sampler.set_editor_property("texture", texture)
    multiply = graph.create_material_expression(material, unreal.MaterialExpressionMultiply, -220, 0)
    graph.connect_material_expressions(sampler, "RGB", multiply, "A")
    graph.connect_material_expressions(tint_node, "", multiply, "B")
    graph.connect_material_property(multiply, "", unreal.MaterialProperty.MP_BASE_COLOR)
    roughness = graph.create_material_expression(material, unreal.MaterialExpressionConstant, -230, 160)
    roughness.set_editor_property("r", 0.66 if kind == "Boots" else 0.85)
    graph.connect_material_property(roughness, "", unreal.MaterialProperty.MP_ROUGHNESS)
    material.set_editor_property("two_sided", True)
    graph.recompile_material(material)
    if not ea.save_loaded_asset(material, False):
        raise RuntimeError(f"Material save failed for {name}")
    return material


def stage(actor, identity, components):
    components = {**components, "Exposed": SKIN_SLOTS[identity]}
    saved = {c.get_name(): c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent)}
    body = saved["Body"]
    skeleton = body.get_skeletal_mesh_asset().get_editor_property("skeleton")
    destination = f"{DEST}/{identity}"
    meshes = {}
    for part in ("Tunic", "Trousers", "Boots", "Exposed"):
        slot = unreal.SkeletalMaterial()
        if part == "Exposed":
            slot.material_interface = body.get_material(0)
        else:
            slot.material_interface = textured_material(
                part, f"M_{identity}_{part}", ART / f"Red{part}_Atlas.png",
                destination, PALETTE[identity] if part == "Tunic" else SOLIDS[part],
            )
        meshes[part] = LEGACY["import_mesh"](STAGING / f"SK_{identity}_{part}_SimpleRed.fbx", destination, skeleton, [slot])
    return body, saved, meshes, components


def run():
    import shutil
    actors = LEGACY["actor_inventory"]()
    level = PROJECT / "Content" / (LEVEL.removeprefix("/Game/") + ".umap")
    backup = STAGING / "Lvl_HeroSampleCrowd.before-simple-red.umap"
    if not backup.exists():
        shutil.copy2(level, backup)
    staged = {label: stage(actors[label], *data) for label, data in SPECS.items()}
    report = {}
    ea = unreal.EditorAssetLibrary
    subobjects = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    data_api = unreal.SubobjectDataBlueprintFunctionLibrary
    actor_api = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    new_classes = {}
    for label, (body, _, meshes, _) in staged.items():
        identity = SPECS[label][0]
        cname = f"BP_{identity}_SimpleRed"
        new_path = f"{DEST}/{identity}/{cname}"
        old = actors[label].get_class().get_path_name().split(".")[0]
        bp = ea.load_asset(new_path) if ea.does_asset_exist(new_path) else ea.duplicate_asset(old, new_path)
        if bp is None:
            raise RuntimeError(f"Could not duplicate visual for {identity}")
        handles = subobjects.k2_gather_subobject_data_for_blueprint(bp)
        by_name = {str(data_api.get_variable_name(data_api.get_data(h))): h for h in handles}
        leader = data_api.get_object(data_api.get_data(by_name["Body"]))
        m = body.get_material(0)
        for name, handle in by_name.items():
            c = data_api.get_object(data_api.get_data(handle))
            if not isinstance(c, unreal.SkeletalMeshComponent) or name in {"Body", "Face"} or name.startswith("SimpleRed"):
                continue
            c.set_skeletal_mesh_asset(None)
            c.set_visibility(False, False)
            c.set_hidden_in_game(True)
        leader.set_visibility(False, False)
        leader.set_hidden_in_game(True, False)
        for part, mesh in meshes.items():
            name = f"SimpleRed{part}"
            handle = by_name.get(name)
            if handle is None:
                handle, error = subobjects.add_new_subobject(
                    unreal.AddNewSubobjectParams(parent_handle=by_name["Body"],
                                                 new_class=unreal.SkeletalMeshComponent,
                                                 blueprint_context=bp))
                if not data_api.get_object(data_api.get_data(handle)):
                    raise RuntimeError(str(error))
                subobjects.rename_subobject(handle, unreal.Text(name))
                subobjects.rename_subobject_member_variable(bp, handle, name)
            garment = data_api.get_object(data_api.get_data(handle))
            garment.set_skeletal_mesh_asset(mesh)
            garment.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
            garment.set_editor_property("use_bounds_from_leader_pose_component", True)
            garment.set_leader_pose_component(leader, True, False)
            if part == "Exposed":
                garment.set_material(0, m)
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
        if not ea.save_loaded_asset(bp, False):
            raise RuntimeError(f"Could not save visual for {identity}")
        new_classes[label] = bp.generated_class()
        report[label] = {"actor_blueprint": new_classes[label].get_path_name(),
                         **{part: mesh.get_path_name() for part, mesh in meshes.items()}}

    with unreal.ScopedEditorTransaction("Install fitted single-layer Red London clothing"):
        for label, visual in new_classes.items():
            old = actors[label]
            if old.get_class() == visual:
                continue
            replacement = actor_api.spawn_actor_from_class(visual, old.get_actor_location(), old.get_actor_rotation())
            if replacement is None:
                raise RuntimeError(f"Could not spawn {label}")
            replacement.set_actor_scale3d(old.get_actor_scale3d())
            replacement.set_editor_property("tags", list(old.get_editor_property("tags")))
            replacement.set_folder_path(old.get_folder_path())
            if not actor_api.destroy_actor(old):
                raise RuntimeError(f"Could not replace {label}")
            replacement.set_actor_label(label)
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        raise RuntimeError("Failed to save playable map")
    (STAGING / "unreal_import.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def tune_materials():
    for identity in PALETTE:
        for part in ("Tunic", "Trousers", "Boots"):
            textured_material(
                part, f"M_{identity}_{part}", ART / f"Red{part}_Atlas.png",
                f"{DEST}/{identity}", PALETTE[identity] if part == "Tunic" else SOLIDS[part],
                rebuild=True,
            )
