# Editor script (PARAMS: characters=[paths], wardrobe=path, slot, out): for each MetaHuman, assemble the
# wardrobe item on a transient probe and compare the body the outfit was resized to (TargetBody) with
# the body the character really has. Nothing is saved; the probe is destroyed.
from pathlib import Path
P = PARAMS
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_editor_world() and not ed.get_game_world(), "a play session is running"
s = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
df = unreal.get_editor_subsystem(unreal.DataflowScriptingSubsystem)
actor_util = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
library = unreal.ClothingFitLibrary
out = Path(P["out"]); out.mkdir(parents=True, exist_ok=True)

def asset(path):
    return unreal.load_object(None, path + "." + path.rsplit("/", 1)[-1])

def box(mesh):
    b = mesh.get_bounds()
    return {"origin": [round(v, 2) for v in b.origin.to_tuple()], "extent": [round(v, 2) for v in b.box_extent.to_tuple()]}

def attempt(fn):
    try:
        return fn()
    except Exception as error:
        return "error: " + str(error)[:160]

wardrobe = asset(P["wardrobe"])
report = {}
for path in P["characters"]:
    name = path.rsplit("/", 1)[-1]
    row = {}
    character = asset(path)
    was_editing = bool(s.is_object_added_for_editing(character))
    row["was_open_for_editing"] = was_editing
    assert was_editing or s.try_add_object_to_edit(character), name
    row["rig_state"] = attempt(lambda: str(s.get_rigging_state(character)))
    row["has_face_dna"] = attempt(lambda: bool(character.has_face_dna()))
    row["fixed_body_type"] = attempt(lambda: str(character.get_editor_property("fixed_body_type")))
    collection = s.get_preview_collection(character)
    inst = collection.get_default_instance()
    slot = P["slot"]
    prior = next((e.selected_item for e in inst.get_slot_selections() if str(e.slot_name) == slot), unreal.MetaHumanPaletteItemKey())
    keys = [k for k in collection.get_item_keys_for_wardrobe_item(wardrobe) if str(collection.get_item_slot_name(k)) == slot]
    key = keys[0] if keys else collection.try_add_item_from_wardrobe_item(slot, wardrobe)
    probe = None
    try:
        inst.set_single_slot_selection(slot, key)
        probe = s.spawn_meta_human_actor(character, keep_transient=True)
        probe.set_actor_label("Fitting body probe " + name, mark_dirty=False)
        probe.set_actor_location(unreal.Vector(-1295, -320, 8), False, True)
        probe.set_actor_rotation(unreal.Rotator(yaw=90), True)
        s.assemble_for_preview(character)
        await asyncio.sleep(.6)
        meshes = {part.get_name(): part for part in probe.get_components_by_class(unreal.SkeletalMeshComponent)}
        body = meshes["Body"]
        row["body_asset"] = body.get_skinned_asset().get_path_name()
        row["body_asset_bounds"] = box(body.get_skinned_asset())
        library.refresh_sample_pose(body)
        folder = out / name; folder.mkdir(exist_ok=True)
        assert library.write_posed_surface(body, str(folder / "standing_body.bin"))
        for cloth in probe.get_components_by_class(unreal.ChaosClothComponent):
            fitted = cloth.get_asset()
            if not fitted:
                continue
            info = {str(v.name): str(v.value) for v in df.get_dataflow_instance_info(fitted).variable_overrides}
            if P["marker"] not in info.get("ResizableOutfit", ""):
                continue
            row["target_body"] = info.get("TargetBody", "")
            target_path = row["target_body"].split("'")[1] if "'" in row["target_body"] else row["target_body"]
            target = unreal.load_object(None, target_path) if target_path else None
            row["target_loaded"] = bool(target)
            if target:
                row["target_bounds"] = box(target)
                row["target_bones"] = attempt(lambda: target.skeleton.get_path_name() if target.skeleton else None)
                # write the target body's own surface through a throwaway component so it can be compared vertex by vertex
                comp = unreal.SkeletalMeshComponent()
                comp.set_skinned_asset_and_update(target)
                row["target_surface_written"] = attempt(lambda: bool(library.write_posed_surface(comp, str(folder / "target_body.bin"))))
            assert library.write_posed_surface(cloth, str(folder / "standing_garment.bin"))
    finally:
        if probe:
            actor_util.destroy_actor(probe)
        inst.set_single_slot_selection(slot, prior)
        s.assemble_for_preview(character)
    report[name] = row
(out / "FittingBodyProbe.json").write_text(json.dumps(report, indent=1))
report
