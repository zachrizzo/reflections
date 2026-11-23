# Editor script (run through ue.py with PARAMS): write the UV0 layout of a MetaHuman body mesh, together with a
# standing capture of the same body component, so the layout can be matched to the triangles of the capture files.
# PARAMS: character (QA character path), out (folder), commit_refresh (QA Dwarf/Elf/Orc copies only).
# The probe actor is transient and destroyed; nothing is saved.
import struct
from array import array
from pathlib import Path
P = PARAMS
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_editor_world() and not ed.get_game_world(), "a play session is running"
s = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
G = unreal.GeometryScript_AssetUtils
Q = unreal.GeometryScript_MeshQueries
L = unreal.GeometryScript_List
out = Path(P["out"]); out.mkdir(parents=True, exist_ok=True)
path = P["character"]
character = unreal.load_object(None, path + "." + path.rsplit("/", 1)[-1])
assert character and "/QA/" in path, path
was_editing = bool(s.is_object_added_for_editing(character))
assert was_editing or s.try_add_object_to_edit(character)
result = {"character": path}

def first(value, type_name):
    if isinstance(value, tuple):
        return next(v for v in value if type(v).__name__ == type_name)
    return value

probe = None
try:
    if P.get("commit_refresh"):
        s.set_body_constraints(character, list(s.get_body_constraints(character)))
        await asyncio.sleep(.4)
        s.commit_body_state(character)
        await asyncio.sleep(.8)
    probe = s.spawn_meta_human_actor(character, keep_transient=True)
    probe.set_actor_location(unreal.Vector(-1295, -320, 8), False, True)
    probe.set_actor_rotation(unreal.Rotator(yaw=90), True)
    s.assemble_for_preview(character)
    await asyncio.sleep(.7)
    body = {c.get_name(): c for c in probe.get_components_by_class(unreal.SkeletalMeshComponent)}["Body"]
    unreal.ClothingFitLibrary.refresh_sample_pose(body)
    assert unreal.ClothingFitLibrary.write_posed_surface(body, str(out / "standing_body.bin"))
    mesh = body.get_skinned_asset()
    result["mesh"] = mesh.get_path_name()
    for kind in ("RENDER_DATA", "SOURCE_MODEL"):
        dm = unreal.DynamicMesh()
        lod = unreal.GeometryScriptMeshReadLOD()
        lod.lod_type = getattr(unreal.GeometryScriptLODType, kind)
        lod.lod_index = 0
        try:
            dm, outcome = G.copy_mesh_from_skeletal_mesh(mesh, dm, unreal.GeometryScriptCopyMeshFromAssetOptions(), lod)
        except Exception as error:
            result[kind] = "error: " + str(error)[:200]
            continue
        if str(outcome).endswith("FAILURE"):
            result[kind] = str(outcome)
            continue
        positions = first(Q.get_all_vertex_positions(dm, False), "GeometryScriptVectorList")
        positions = L.convert_vector_list_to_array(positions)
        triangles = first(Q.get_all_triangle_indices(dm, False), "GeometryScriptTriangleList")
        triangles = L.convert_triangle_list_to_array(triangles)
        uvs = array("f")
        for t in range(len(triangles)):
            value = Q.get_triangle_u_vs(dm, 0, t)
            corners = [v for v in value if hasattr(v, "x") and hasattr(v, "y") and not hasattr(v, "z")]
            flags = [v for v in value if isinstance(v, bool)]
            a, b, c = corners[:3]
            ok = flags[0] if flags else True
            uvs.extend((a.x, a.y, b.x, b.y, c.x, c.y) if ok else (-1., -1., -1., -1., -1., -1.))
        xyz = array("f")
        for v in positions:
            xyz.extend((v.x, v.y, v.z))
        tri = array("I")
        for t in triangles:
            tri.extend((t.x, t.y, t.z))
        with open(out / f"body_uv_{kind.lower()}.bin", "wb") as stream:
            stream.write(struct.pack("<II", len(positions), len(triangles)))
            xyz.tofile(stream); tri.tofile(stream); uvs.tofile(stream)
        result[kind] = {"vertices": len(positions), "triangles": len(triangles), "num_uv_sets": Q.get_num_uv_sets(dm)}
finally:
    if probe:
        actors.destroy_actor(probe)
    if not was_editing:
        try:
            s.remove_object_to_edit(character)
        except Exception as error:
            result["close_error"] = str(error)[:200]
(out / "dump_result.json").write_text(json.dumps(result, indent=1))
result
