# Housekeeping after pose captures: destroy leftover capture probes and unload MetaHuman Character packages
# that the captures loaded, then collect garbage. A character is left alone if it is open for editing, open
# (which includes the MetaHuman Character editor), or has unsaved changes. PARAMS: unload (bool), only (list of package names, optional).
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), "a play session is running"
s = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editors = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
out = {"probes_destroyed": 0, "unloaded": [], "kept": {}}
for actor in actors.get_all_level_actors():
    if actor.get_actor_label().startswith("Garment fit probe"):
        actors.destroy_actor(actor)
        out["probes_destroyed"] += 1
registry = unreal.AssetRegistryHelpers.get_asset_registry()
packages = []
dirty = {str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
out["dirty_packages_in_editor"] = sorted(dirty)
# the QA copies are this pipeline's own: an in-session body commit leaves them changed, so save them
for name in sorted(dirty):
    if "/VillageWardrobe/Generated/QA/" in name and PARAMS.get("save_own"):
        out.setdefault("saved_own", []).append(name)
        unreal.EditorAssetLibrary.save_asset(name, only_if_is_dirty=True)
dirty = {str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
for data in registry.get_assets_by_class(unreal.TopLevelAssetPath("/Script/MetaHumanCharacter", "MetaHumanCharacter"), True):
    name = str(data.package_name)
    if not data.is_asset_loaded() or (PARAMS.get("only") and name not in PARAMS["only"]):
        continue
    character = data.get_asset()
    package = character.get_outermost()
    if s.is_object_added_for_editing(character):
        out["kept"][name] = "open for editing"
    elif hasattr(editors, "find_editors_for_asset") and editors.find_editors_for_asset(character):
        out["kept"][name] = "open in an asset editor"
    elif name in dirty:
        out["kept"][name] = "unsaved changes"
    else:
        packages.append(package)
        out["unloaded"].append(name)
character = package = None
if PARAMS.get("unload") and packages:
    result = unreal.EditorLoadingAndSavingUtils.unload_packages(packages)
    out["unload_result"] = str(result)[:300]
packages = None
unreal.SystemLibrary.collect_garbage()
await asyncio.sleep(1.5)
out
