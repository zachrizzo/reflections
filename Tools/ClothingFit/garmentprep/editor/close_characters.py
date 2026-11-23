# Editor script (PARAMS: characters): stop editing the given MetaHumans so their uncommitted editing state is
# dropped. Nothing is saved.
s = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
closed = {}
for path in PARAMS["characters"]:
    character = unreal.load_object(None, path + "." + path.rsplit("/", 1)[-1])
    if character and s.is_object_added_for_editing(character):
        s.remove_object_to_edit(character)
        closed[path.rsplit("/", 1)[-1]] = True
    else:
        closed[path.rsplit("/", 1)[-1]] = False
closed
