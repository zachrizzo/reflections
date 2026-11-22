"""Restore the fitted, temporary Wayfarer's Tunic preview in an open Test Town."""
import json
from pathlib import Path

import unreal


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if not world or not world.get_path_name().startswith("/Game/Maps/TestTown/L_TestTown."):
        raise ValueError("Open Test Town in the editor to show the tunic lineup")
    project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
    arrangement = json.loads((project / "ArtDirection/WayfarersTunic/Lineup.json").read_text())
    subsystem = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
    wardrobe = unreal.load_asset("/Game/Characters/Clothing/OA_WayfarersTunic/WI_WayfarersTunic")
    if not wardrobe:
        raise ValueError("Missing Wayfarer's Tunic Wardrobe Item")
    existing = {(str(a.get_folder_path()), a.get_actor_label()): a
                for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)}

    for slot in arrangement:
        character = unreal.load_asset(slot["character"])
        if not character:
            raise ValueError(f"Cannot load {slot['character']}")
        if not subsystem.is_object_added_for_editing(character):
            if not subsystem.try_add_object_to_edit(character):
                raise ValueError(f"Cannot edit {slot['character']}")
        actor = existing.get((slot["folder"], slot["label"]))
        if actor is None:
            actor = subsystem.spawn_meta_human_actor(character, keep_transient=True)
            actor.set_actor_label(slot["label"], mark_dirty=False)
            actor.set_folder_path(unreal.Name(slot["folder"]))
        actor.set_actor_location(unreal.Vector(*slot["location_cm"]), sweep=False, teleport=True)
        actor.set_actor_rotation(unreal.Rotator(yaw=slot["yaw"]), teleport_physics=True)
        collection = subsystem.get_preview_collection(character)
        keys = collection.get_item_keys_for_wardrobe_item(wardrobe)
        key = keys[0] if keys else collection.try_add_item_from_wardrobe_item("Outfits", wardrobe)
        if not key:
            raise ValueError(f"Cannot select tunic on {slot['label']}")
        collection.get_default_instance().set_single_slot_selection("Outfits", key)
        subsystem.assemble_for_preview(character)
        if not any(c.get_material(0) and c.get_material(0).get_name() == "M_WayfarersLinen"
                   for c in actor.get_components_by_class(unreal.ChaosClothComponent)):
            raise ValueError(f"Missing assembled tunic on {slot['label']}")
    editor.set_level_viewport_camera_info(unreal.Vector(-2050, -230, 830), unreal.Rotator(pitch=-27))
    unreal.log(f"Showing {len(arrangement)} fitted MetaHumans in Test Town")


if __name__ == "__main__":
    main()
