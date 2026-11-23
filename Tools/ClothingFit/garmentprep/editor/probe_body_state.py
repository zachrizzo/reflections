# Read-only experiment (nothing saved): when does a MetaHuman's editing body reach its real shape, and does the
# body the outfit is resized to (TargetBody) follow it? PARAMS: character, wardrobe, slot, marker, out.
from pathlib import Path
P = PARAMS
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), "a play session is running"
s = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
df = unreal.get_editor_subsystem(unreal.DataflowScriptingSubsystem)
actor_util = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

def asset(path):
    return unreal.load_object(None, path + "." + path.rsplit("/", 1)[-1])

def extent(mesh):
    """Height and width of LOD 0 of a skeletal mesh (source model), plus the top of its body part."""
    lod = unreal.GeometryScriptMeshReadLOD(lod_type=unreal.GeometryScriptLODType.SOURCE_MODEL, lod_index=0)
    dyn, outcome = unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(mesh, unreal.DynamicMesh(), unreal.GeometryScriptCopyMeshFromAssetOptions(), lod)
    if outcome != unreal.GeometryScriptOutcomePins.SUCCESS:
        return "copy failed"
    box = unreal.GeometryScript_MeshQueries.get_mesh_bounding_box(dyn)
    return {"vertices": dyn.get_vertex_count(), "min": [round(v, 1) for v in box.min.to_tuple()], "max": [round(v, 1) for v in box.max.to_tuple()]}

character = asset(P["character"])
wardrobe = asset(P["wardrobe"])
steps = {}
was_editing = bool(s.is_object_added_for_editing(character))
if was_editing and P.get("reopen"):
    s.remove_object_to_edit(character)
    was_editing = False
assert was_editing or s.try_add_object_to_edit(character)
collection = s.get_preview_collection(character)
inst = collection.get_default_instance()
slot = P["slot"]
prior = next((e.selected_item for e in inst.get_slot_selections() if str(e.slot_name) == slot), unreal.MetaHumanPaletteItemKey())
keys = [k for k in collection.get_item_keys_for_wardrobe_item(wardrobe) if str(collection.get_item_slot_name(k)) == slot]
key = keys[0] if keys else collection.try_add_item_from_wardrobe_item(slot, wardrobe)
probe = None

def look(tag):
    row = {}
    meshes = {part.get_name(): part for part in probe.get_components_by_class(unreal.SkeletalMeshComponent)}
    row["body"] = extent(meshes["Body"].get_skinned_asset())
    row["face"] = extent(meshes["Face"].get_skinned_asset())
    row["head_bone_z"] = {n: round(c.get_socket_location("head").z - probe.get_actor_location().z, 1) for n, c in meshes.items() if n in ("Body", "Face")}
    for cloth in probe.get_components_by_class(unreal.ChaosClothComponent):
        fitted = cloth.get_asset()
        if not fitted:
            continue
        info = {str(v.name): str(v.value) for v in df.get_dataflow_instance_info(fitted).variable_overrides}
        if P["marker"] not in info.get("ResizableOutfit", ""):
            continue
        path = info.get("TargetBody", "").split("'")[1] if "'" in info.get("TargetBody", "") else ""
        target = unreal.load_object(None, path) if path else None
        row["target_path"] = path
        row["target"] = extent(target) if target else None
        b = cloth.get_local_bounds() if hasattr(cloth, "get_local_bounds") else None
        row["garment_bounds_z"] = [round(cloth.bounds.origin.z - cloth.bounds.box_extent.z - probe.get_actor_location().z, 1), round(cloth.bounds.origin.z + cloth.bounds.box_extent.z - probe.get_actor_location().z, 1)] if hasattr(cloth, "bounds") else None
    steps[tag] = row

try:
    inst.set_single_slot_selection(slot, key)
    probe = s.spawn_meta_human_actor(character, keep_transient=True)
    probe.set_actor_location(unreal.Vector(-1295, -320, 8), False, True)
    s.assemble_for_preview(character)
    await asyncio.sleep(.5)
    look("1 right after opening and assembling")
    await asyncio.sleep(3.)
    look("2 three seconds later")
    s.assemble_for_preview(character)
    await asyncio.sleep(.6)
    look("3 assembled again")
    constraints = list(s.get_body_constraints(character))
    steps["constraints"] = {str(c.name): [bool(c.is_active), round(float(c.target_measurement), 1)] for c in constraints if c.is_active}
    s.set_body_constraints(character, constraints)
    await asyncio.sleep(.6)
    look("4 body constraints re-applied (not committed)")
    s.assemble_for_preview(character)
    await asyncio.sleep(.8)
    look("5 assembled after re-applying")
finally:
    if probe:
        actor_util.destroy_actor(probe)
    inst.set_single_slot_selection(slot, prior)
    if not was_editing:
        try:
            s.remove_object_to_edit(character)       # drops the uncommitted editing state
        except Exception as error:
            steps["close_error"] = str(error)[:160]
    else:
        s.assemble_for_preview(character)
Path(P["out"]).write_text(json.dumps(steps, indent=1))
steps
