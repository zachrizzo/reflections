# Editor script (PARAMS: path, measurements): create a NEW MetaHuman with the given body measurements,
# to test a wardrobe item on a body nothing was fitted on. Saves only that new character package.
P = PARAMS
s = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
package, name = P["path"].rsplit("/", 1)
existing = unreal.EditorAssetLibrary.does_asset_exist(P["path"])
character = unreal.load_object(None, P["path"] + "." + name) if existing else unreal.AssetToolsHelpers.get_asset_tools().create_asset(
    name, package, unreal.MetaHumanCharacter, unreal.MetaHumanCharacterFactoryNew())
assert character, P["path"]
assert s.is_object_added_for_editing(character) or s.try_add_object_to_edit(character)
measures = list(s.get_body_constraints(character))
wanted = P["measurements"]
seen = []
for measure in measures:
    key = str(measure.name)
    seen.append(key)
    measure.is_active = key in wanted
    if measure.is_active:
        measure.target_measurement = float(wanted[key])
s.set_body_constraints(character, measures)
s.commit_body_state(character)
assert unreal.EditorLoadingAndSavingUtils.save_packages([character.get_outermost()], False)
{"character": character.get_path_name(), "created": not existing, "requested_cm": wanted, "available_measurements": seen}
