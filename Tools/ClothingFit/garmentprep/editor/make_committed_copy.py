# Make a QA copy of a MetaHuman Character whose saved body state lacks its evaluated body measurements
# (the body comes back with default proportions and a default skeleton when the character is opened),
# re-apply the copy's own body measurements, COMMIT the body state (this is what rebuilds the skeleton)
# and save the copy. The original character is only read. PARAMS: character, copy, out.
from pathlib import Path
P = PARAMS
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), "a play session is running"
s = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
lib = unreal.EditorAssetLibrary
result = {"character": P["character"], "copy": P["copy"]}
if not lib.does_asset_exist(P["copy"]):
    assert lib.duplicate_asset(P["character"], P["copy"]), "duplicate failed"
    result["created"] = True
copy = unreal.load_object(None, P["copy"] + "." + P["copy"].rsplit("/", 1)[-1])
assert copy, "copy did not load"
was_editing = bool(s.is_object_added_for_editing(copy))
assert was_editing or s.try_add_object_to_edit(copy)
try:
    constraints = list(s.get_body_constraints(copy))
    result["constraints"] = {str(c.name): round(float(c.target_measurement), 1) for c in constraints if c.is_active}
    s.set_body_constraints(copy, constraints)
    await asyncio.sleep(.4)
    s.commit_body_state(copy)
    await asyncio.sleep(.6)
finally:
    if not was_editing:
        s.remove_object_to_edit(copy)
result["saved"] = bool(lib.save_asset(P["copy"], only_if_is_dirty=False))
Path(P["out"]).write_text(json.dumps(result, indent=1))
result
