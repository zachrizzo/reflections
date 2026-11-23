# Read-only: compare the geometry of the body an outfit is resized TO (TargetBody) with the source body
# and with known-good full-body meshes. PARAMS: characters, wardrobe, slot, marker, out, assets.
from pathlib import Path
import struct
P = PARAMS
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), "a play session is running"
s = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
df = unreal.get_editor_subsystem(unreal.DataflowScriptingSubsystem)
actor_util = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
out = Path(P["out"]); out.mkdir(parents=True, exist_ok=True)

def asset(path):
    return unreal.load_object(None, path + "." + path.rsplit("/", 1)[-1])

def dump(mesh, path):
    """Vertex positions of LOD 0 of a skeletal mesh, in its own space."""
    info = {"path": mesh.get_path_name(), "lods": mesh.get_lod_num() if hasattr(mesh, "get_lod_num") else None}
    for kind in (unreal.GeometryScriptLODType.SOURCE_MODEL, unreal.GeometryScriptLODType.RENDER_DATA):
        try:
            lod = unreal.GeometryScriptMeshReadLOD(lod_type=kind, lod_index=0)
            dyn, outcome = unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(mesh, unreal.DynamicMesh(), unreal.GeometryScriptCopyMeshFromAssetOptions(), lod)
            if outcome != unreal.GeometryScriptOutcomePins.SUCCESS:
                info[str(kind)] = "copy failed"
                continue
            count = dyn.get_vertex_count()
            info[str(kind)] = {"vertices": count, "triangles": dyn.get_triangle_count()}
            positions = unreal.GeometryScript_MeshQueries.get_all_vertex_positions(dyn, False)
            pts = next(x for x in (positions if isinstance(positions, tuple) else (positions,)) if hasattr(x, "convert_vector_list_to_array"))
            arr = pts.convert_vector_list_to_array()
            with open(str(path) + "_" + ("source" if kind == unreal.GeometryScriptLODType.SOURCE_MODEL else "render") + ".bin", "wb") as stream:
                stream.write(struct.pack("<I", len(arr)))
                for v in arr:
                    stream.write(struct.pack("<fff", v.x, v.y, v.z))
            info[str(kind)]["written"] = len(arr)
        except Exception as error:
            info[str(kind) + "_error"] = str(error)[:200]
    return info

report = {"assets": {}}
for path in P.get("assets", []):
    mesh = asset(path)
    report["assets"][path.rsplit("/", 1)[-1]] = dump(mesh, out / path.rsplit("/", 1)[-1]) if mesh else "missing"
wardrobe = asset(P["wardrobe"])
for path in P["characters"]:
    name = path.rsplit("/", 1)[-1]
    character = asset(path)
    was_editing = bool(s.is_object_added_for_editing(character))
    assert was_editing or s.try_add_object_to_edit(character), name
    collection = s.get_preview_collection(character)
    inst = collection.get_default_instance()
    slot = P["slot"]
    prior = next((e.selected_item for e in inst.get_slot_selections() if str(e.slot_name) == slot), unreal.MetaHumanPaletteItemKey())
    keys = [k for k in collection.get_item_keys_for_wardrobe_item(wardrobe) if str(collection.get_item_slot_name(k)) == slot]
    key = keys[0] if keys else collection.try_add_item_from_wardrobe_item(slot, wardrobe)
    probe = None
    row = {}
    try:
        inst.set_single_slot_selection(slot, key)
        probe = s.spawn_meta_human_actor(character, keep_transient=True)
        probe.set_actor_location(unreal.Vector(-1295, -320, 8), False, True)
        s.assemble_for_preview(character)
        await asyncio.sleep(.5)
        meshes = {part.get_name(): part for part in probe.get_components_by_class(unreal.SkeletalMeshComponent)}
        row["body_mesh"] = dump(meshes["Body"].get_skinned_asset(), out / (name + "_body"))
        row["face_mesh"] = dump(meshes["Face"].get_skinned_asset(), out / (name + "_face"))
        for cloth in probe.get_components_by_class(unreal.ChaosClothComponent):
            fitted = cloth.get_asset()
            if not fitted:
                continue
            info = {str(v.name): str(v.value) for v in df.get_dataflow_instance_info(fitted).variable_overrides}
            if P["marker"] not in info.get("ResizableOutfit", ""):
                continue
            row["overrides"] = info
            target_path = info.get("TargetBody", "").split("'")[1] if "'" in info.get("TargetBody", "") else info.get("TargetBody", "")
            target = unreal.load_object(None, target_path) if target_path else None
            if target:
                row["target_body"] = dump(target, out / (name + "_target"))
    finally:
        if probe:
            actor_util.destroy_actor(probe)
        inst.set_single_slot_selection(slot, prior)
        if not was_editing:
            try:
                s.remove_object_to_edit(character)
            except Exception as error:
                row["close_error"] = str(error)[:160]
        else:
            s.assemble_for_preview(character)
    report[name] = row
(out / "TargetMeshProbe.json").write_text(json.dumps(report, indent=1))
report
