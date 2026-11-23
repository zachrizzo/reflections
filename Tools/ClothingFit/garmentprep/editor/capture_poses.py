# Editor script (run through ue.py with PARAMS): put Wardrobe Items on one MetaHuman in the
# L_TestTown EDITOR world (no play session), sample poses with cloth physics off and write the
# posed surfaces. The probe actor is transient and destroyed at the end; nothing is saved.
import struct
from array import array
from pathlib import Path
P = PARAMS
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and not ed.get_game_world(), "a play session is running"
s = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
df = unreal.get_editor_subsystem(unreal.DataflowScriptingSubsystem)
actor_util = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
library = unreal.ClothingFitLibrary
out = Path(P["out"]); out.mkdir(parents=True, exist_ok=True)
progress = out / "progress.json"

def asset(path):
    return unreal.load_object(None, path + "." + path.rsplit("/", 1)[-1])

def cloth_reference(c):
    fitted = c.get_asset()
    if not fitted:
        return ""
    return {str(v.name): str(v.value) for v in df.get_dataflow_instance_info(fitted).variable_overrides}.get("ResizableOutfit", "")

def key_for(collection, slot, item):
    keys = [k for k in collection.get_item_keys_for_wardrobe_item(item) if str(collection.get_item_slot_name(k)) == slot]
    return keys[0] if keys else collection.try_add_item_from_wardrobe_item(slot, item)

character = asset(P["character"])
assert character, P["character"]
was_editing = bool(s.is_object_added_for_editing(character))
assert was_editing or s.try_add_object_to_edit(character), "cannot open the character for editing"
refreshed = False
committed = False
if P.get("commit_refresh"):
    # A character whose saved body lacks its evaluated measurements opens with a default body AND a default
    # skeleton. Re-applying the measurements rebuilds the mesh only; the skeleton is rebuilt by a body-state
    # commit. That changes the character asset, so it is done on QA copies only, before anything is assembled.
    assert "/Generated/QA/" in P["character"], "commit_refresh is for QA copies only"
    s.set_body_constraints(character, list(s.get_body_constraints(character)))
    await asyncio.sleep(.4)
    s.commit_body_state(character)
    await asyncio.sleep(.8)
    committed = True
collection = s.get_preview_collection(character)
inst = collection.get_default_instance()
wear = {slot: asset(path) for slot, path in P["wear"].items()}          # slot name -> wardrobe item path
assert all(wear.values()), P["wear"]
slots = list(dict.fromkeys(list(P.get("clear_slots", [])) + list(wear)))
prior = {k: next((e.selected_item for e in inst.get_slot_selections() if str(e.slot_name) == k), unreal.MetaHumanPaletteItemKey()) for k in slots}
JOINTS = P.get("joints") or ["pelvis", "spine_01", "spine_02", "spine_03", "spine_04", "spine_05", "neck_01", "neck_02", "head",
                              "clavicle_l", "upperarm_l", "lowerarm_l", "hand_l", "clavicle_r", "upperarm_r", "lowerarm_r", "hand_r",
                              "thigh_l", "calf_l", "foot_l", "thigh_r", "calf_r", "foot_r"]
clips = {k: (asset(v["animation"]), v["frames"]) for k, v in P["clips"].items()}
assert all(isinstance(c, unreal.AnimSequence) for c, _ in clips.values())
probe = None
camera_before = ed.get_level_viewport_camera_info()
shots = {}

async def photo(path, direction):
    # direction: front | back | left | right, relative to the probe (which faces world -X)
    if ed.get_game_world():
        return False
    aim = probe.get_actor_location() + unreal.Vector(0, 0, P.get("aim_height", 117))
    reach = P.get("camera_distance", 170)
    offset = {"front": unreal.Vector(-reach, -24, 2), "back": unreal.Vector(reach, 24, 2),
              "left": unreal.Vector(0, -reach, 2), "right": unreal.Vector(0, reach, 2)}[direction]
    pos = aim + offset
    path = Path(path); path.unlink(missing_ok=True)
    ed.set_level_viewport_camera_info(pos, unreal.MathLibrary.find_look_at_rotation(pos, aim))
    await asyncio.sleep(.3)
    unreal.AutomationLibrary.take_high_res_screenshot(*P.get("shot_size", [820, 940]), str(path), delay=.05, force_game_view=True)
    for _ in range(40):
        if path.is_file() and path.stat().st_size > 12000:
            return True
        await asyncio.sleep(.1)
    return False

result = {}
try:
    for slot in P.get("clear_slots", []):
        inst.set_single_slot_selection(slot, unreal.MetaHumanPaletteItemKey())
    for slot, item in wear.items():
        inst.set_single_slot_selection(slot, key_for(collection, slot, item))
    probe = s.spawn_meta_human_actor(character, keep_transient=True)
    assert probe
    probe.set_actor_label("Garment fit probe " + P.get("label", ""), mark_dirty=False)
    probe.set_folder_path(unreal.Name("Preview/Clothing QA"))
    probe.set_actor_location(unreal.Vector(*P.get("location", [-1295, -320, 8])), False, True)
    probe.set_actor_rotation(unreal.Rotator(yaw=90), True)
    s.assemble_for_preview(character)
    await asyncio.sleep(.7)
    meshes = {part.get_name(): part for part in probe.get_components_by_class(unreal.SkeletalMeshComponent)}
    body, face = meshes["Body"], meshes["Face"]

    def neck_overlap():
        # How far the head mesh reaches down into the body mesh at the neck (cm), from the posed surfaces.
        # A character whose saved body state did not come back on load shows a gap, or a head sunk deep.
        tops = {}
        for tag, comp in (("body", body), ("face", face)):
            library.refresh_sample_pose(comp)
            path = out / f"_check_{tag}.bin"
            assert library.write_posed_surface(comp, str(path))
            with open(path, "rb") as stream:
                count, _ = struct.unpack("<II", stream.read(8))
                values = array("f"); values.fromfile(stream, count * 3)
            path.unlink()
            heights = values[2::3]
            tops[tag] = (min(heights), max(heights))
        return tops["body"][1] - tops["face"][0]

    overlap_before = neck_overlap()
    if P.get("refresh_body", True) and not (2. <= overlap_before <= 18.):
        # The body Unreal shows (and the cached merged body outfits are resized to) does not belong to this
        # character's head and skeleton. Re-applying the character's own body measurements makes Unreal
        # rebuild both. Not committed, not saved.
        s.set_body_constraints(character, list(s.get_body_constraints(character)))
        await asyncio.sleep(.5)
        s.assemble_for_preview(character)
        await asyncio.sleep(.7)
        meshes = {part.get_name(): part for part in probe.get_components_by_class(unreal.SkeletalMeshComponent)}
        body, face = meshes["Body"], meshes["Face"]
        refreshed = True
    overlap_after = neck_overlap() if refreshed else overlap_before
    by_outfit = {cloth_reference(c): c for c in probe.get_components_by_class(unreal.ChaosClothComponent)}
    surfaces = {"body": body, "face": face}
    targets = {}
    for tag, marker in P["surfaces"].items():                            # file tag -> text that identifies the outfit asset path
        comp = next((c for ref, c in by_outfit.items() if marker in ref), None)
        assert comp, (tag, marker, list(by_outfit))
        surfaces[tag] = comp
        fitted = comp.get_asset()
        info = {str(v.name): str(v.value) for v in df.get_dataflow_instance_info(fitted).variable_overrides}
        targets[tag] = info.get("TargetBody", "")
        assert library.get_dynamic_cloth_particle_count(comp) == 0, (tag, "cloth simulation is on")
    to_local = probe.get_actor_transform().inverse_transform_location

    def snapshot(frame):
        for tag, component in surfaces.items():
            assert library.write_posed_surface(component, str(out / f"{frame}_{tag}.bin")), (frame, tag)
        return {j: list(to_local(body.get_socket_location(j)).to_tuple()) for j in JOINTS}

    library.refresh_sample_pose(body)
    library.refresh_sample_pose(face)
    manifest = {"character": character.get_path_name(), "wear": P["wear"], "target_body": targets, "particles": 0, "body_state_refreshed": refreshed, "neck_overlap_cm_before_after": [round(overlap_before, 1), round(overlap_after, 1)],
                "body_mesh": body.get_skinned_asset().get_path_name(), "rest": snapshot("standing"), "clips": {},
                "body_state_committed_in_session": committed}
    progress.write_text(json.dumps({"step": "standing"}))
    for view in P.get("standing_views", []):
        shots[f"standing_{view}"] = await photo(out / f"Standing_{view}.png", view)
    face.set_leader_pose_component(body, True)
    body.set_update_animation_in_editor(True)
    for section, (clip, frames) in clips.items():
        body.play_animation(clip, False)
        body.stop()
        duration = clip.get_play_length()
        rows = []
        for index in frames:
            t = duration * index / 24
            label = f"{section}_{index:02}"
            body.set_position(t, fire_notifies=False)
            library.refresh_sample_pose(body)
            await asyncio.sleep(.045)
            rows.append({"label": label, "time_s": t, "joints": snapshot(label)})
            if index in P.get("photo_frames", {}).get(section, []):
                for view in P.get("pose_views", []):
                    shots[f"{label}_{view}"] = await photo(out / f"{label}_{view}.png", view)
        travel = max(sum((f["joints"][b][a] - rows[0]["joints"][b][a]) ** 2 for a in range(3)) ** .5 for b in ("hand_l", "hand_r") for f in rows)
        assert len(rows) < 2 or travel > 10, (section, travel)
        manifest["clips"][section] = {"animation": clip.get_path_name(), "duration_s": duration, "frames": rows}
        progress.write_text(json.dumps({"step": section, "frames": len(rows)}))
    manifest["screenshots"] = shots
    (out / "Manifest.json").write_text(json.dumps(manifest, indent=1))
    result = {"out": str(out), "samples": 1 + sum(len(c["frames"]) for c in manifest["clips"].values()), "screenshots": shots, "target_body": targets}
finally:
    if probe:
        if not ed.get_game_world():
            actor_util.destroy_actor(probe)
            ed.set_level_viewport_camera_info(*camera_before)
        else:
            probe.destroy_actor()
    for slot, key in prior.items():
        inst.set_single_slot_selection(slot, key)
    if P.get("close_after") and not was_editing:
        try:
            s.remove_object_to_edit(character)        # frees the character's editing data again
        except Exception as error:
            result["close_error"] = str(error)[:200]
    else:
        s.assemble_for_preview(character)
result
