"""Import Blender refits and apply them to the six existing NPCs in the crowd test map."""
import json
import shutil
from pathlib import Path

import unreal


PROJECT = Path(unreal.Paths.project_dir()).resolve()
OUTPUT = PROJECT / "Intermediate/NpcMovement"
WARDROBE = OUTPUT / "Wardrobe"
MAP = "/Game/Characters/Hero/Sample/Lvl_HeroSampleCrowd"
DESTINATION = "/Game/Characters/CrowdMotion/WardrobeRefit"
SPECS = {
    "BP_BridgeGuard": ("BridgeGuard", "BridgeGuard_"),
    "Crowd Preview - Red 01": ("ArchiveApprentice", "ArchiveApprentice"),
    "Crowd Preview - Red 02": ("CoinClerk", "CoinClerk"),
    "Crowd Preview - Red 03": ("FestivalDrummer", "FestivalDrummer_"),
    "Crowd Preview - White 01": ("Iven", "Iven"),
    "Crowd Preview - White 02": ("WhiteGuard", "WhiteGuard"),
}


def import_mesh(filename, destination, skeleton, source_slots):
    library = unreal.EditorAssetLibrary
    name = filename.stem.replace("_Refit", "_BindingRefit") if "WhiteGuard" in filename.stem else filename.stem
    mesh = library.load_asset(f"{destination}/{name}") if library.does_asset_exist(f"{destination}/{name}") else None
    if mesh is None:
        options = unreal.FbxImportUI()
        options.automated_import_should_detect_type = False
        options.mesh_type_to_import = unreal.FBXImportType.FBXIT_SKELETAL_MESH
        options.import_as_skeletal = True
        options.import_mesh = True
        options.import_animations = False
        options.import_materials = False
        options.import_textures = False
        options.create_physics_asset = False
        options.skeleton = skeleton
        options.skeletal_mesh_import_data.import_mesh_lods = False
        options.skeletal_mesh_import_data.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
        task = unreal.AssetImportTask()
        task.filename = str(filename)
        task.automated = True
        task.destination_path = destination
        task.destination_name = name
        task.replace_existing = False
        task.options = options
        try:
            unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        except RuntimeError:
            if not task.get_objects() and not library.does_asset_exist(f"{destination}/{name}"):
                raise
        mesh = next((obj for obj in task.get_objects() if isinstance(obj, unreal.SkeletalMesh)), None)
        mesh = mesh or library.load_asset(f"{destination}/{name}")
    if mesh is None or mesh.get_editor_property("skeleton") != skeleton:
        raise RuntimeError(f"Skeleton mismatch for {name}")
    slots = mesh.get_editor_property("materials")
    if len(slots) != len(source_slots):
        raise RuntimeError(f"Material slot mismatch for {name}: {len(slots)} versus {len(source_slots)}")
    by_name = {str(slot.material_slot_name): slot.material_interface for slot in source_slots}
    for index, slot in enumerate(slots):
        slot.material_interface = by_name.get(str(slot.material_slot_name), source_slots[index].material_interface)
        slots[index] = slot
    mesh.set_editor_property("materials", slots)
    if not library.save_loaded_asset(mesh, False):
        raise RuntimeError(f"Save failed for {name}")
    return mesh


def actor_inventory():
    world_subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if world_subsystem.get_game_world() or not world_subsystem.get_editor_world().get_path_name().startswith(MAP + "."):
        raise RuntimeError("Open the default crowd map outside Play before importing")
    all_actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    actors = {actor.get_actor_label(): actor for actor in all_actors if actor.actor_has_tag("NPC_Reactive")}
    if set(actors) != set(SPECS):
        raise RuntimeError(f"Unexpected test crowd: {list(actors)}")
    return actors


def stage_all(actors):
    staged = {}
    for label, actor in actors.items():
        identity, prefix = SPECS[label]
        data = json.loads((WARDROBE / f"{identity}_metrics.json").read_text(encoding="utf-8"))
        components = {component.get_name(): component for component in actor.get_components_by_class(unreal.SkeletalMeshComponent)}
        leader = components["Body"]
        skeleton = leader.get_skeletal_mesh_asset().get_editor_property("skeleton")
        entries = []
        for key, spec in data["edits"].items():
            garment = components[prefix + key]
            source = garment.get_skeletal_mesh_asset()
            source_slots = source.get_editor_property("materials")
            if not garment.get_editor_property("visible") or garment.get_editor_property("leader_pose_component") != leader:
                raise RuntimeError(f"Unexpected attachment for {garment.get_path_name()}")
            overrides = list(garment.get_editor_property("override_materials"))
            mesh = import_mesh(WARDROBE / spec["fbx"], f"{DESTINATION}/{identity}", skeleton, source_slots)
            entries.append((garment, mesh, overrides))
        staged[label] = (leader, entries)
    return staged


def apply(staged, actors):
    report = {}
    map_file = PROJECT / "Content" / (MAP.removeprefix("/Game/") + ".umap")
    backup = OUTPUT / "Lvl_HeroSampleCrowd.before-npc-refit.umap"
    if not backup.exists():
        shutil.copy2(map_file, backup)
    with unreal.ScopedEditorTransaction("Refit test crowd wardrobe and enable sample locomotion"):
        for label, actor in actors.items():
            leader, entries = staged[label]
            actor.modify()
            tags = list(actor.get_editor_property("tags"))
            if "NPC_SampleLocomotion" not in [str(tag) for tag in tags]:
                actor.set_editor_property("tags", tags + [unreal.Name("NPC_SampleLocomotion")])
            paths = []
            for garment, mesh, overrides in entries:
                garment.modify()
                garment.set_skeletal_mesh_asset(mesh)
                garment.set_leader_pose_component(leader, True, False)
                garment.set_editor_property("override_materials", overrides)
                paths.append(mesh.get_path_name())
            report[label] = paths
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        raise RuntimeError("Could not save the test crowd level")
    report_name = "wardrobe_import.json" if any(report.values()) else "movement_enabled.json"
    report_path = OUTPUT / report_name
    previous = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    previous.update(report)
    report_path.write_text(json.dumps(previous, indent=2), encoding="utf-8")
    return report


def run():
    actors = actor_inventory()
    staged = stage_all(actors)
    return apply(staged, actors)


def enable_movement():
    actors = actor_inventory()
    return apply({label: (None, []) for label in actors}, actors)


def repair_white_guard_binding():
    actors = actor_inventory()
    label = "Crowd Preview - White 02"
    actor = actors[label]
    staged = stage_all({label: actor})
    return apply(staged, {label: actor})
