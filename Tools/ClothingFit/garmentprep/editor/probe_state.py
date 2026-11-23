# Read-only: what is the editor doing, and is the pilot ready to be re-imported and captured?
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
s = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
def asset(path):
    return unreal.load_object(None, path + "." + path.rsplit("/", 1)[-1])
out = {"world": world.get_path_name() if world else None, "play_session": bool(ed.get_game_world())}
try:
    seq = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
    out["open_sequence"] = seq.get_path_name() if seq else None
except Exception as error:
    out["open_sequence"] = "error: " + str(error)
char = asset("/Game/Characters/Lanthorne/People/GiltBarnaby/MHC_GiltBarnaby")
out["barnaby_loaded"] = bool(char)
if char:
    out["barnaby_editing"] = bool(s.is_object_added_for_editing(char))
actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor) if world else []
folders = {}
for a in actors:
    f = str(a.get_folder_path())
    if f.startswith("Preview"):
        folders.setdefault(f, []).append(a.get_actor_label())
out["preview_actors"] = {k: len(v) for k, v in folders.items()}
out["has_library"] = hasattr(unreal, "ClothingFitLibrary")
for name in ("SM_", "CA_", "OA_", "WI_"):
    p = "/Game/Characters/Clothing/VillageWardrobe/MeshRetargetJerkin/" + name + "MeshRetargetJerkin"
    out[name] = unreal.EditorAssetLibrary.does_asset_exist(p)
dirty = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()] + [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
out["dirty_packages"] = dirty[:40]
out
