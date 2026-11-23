# Shared prelude for the ambient-library editor snippets. run_in_editor.py prepends "CI = <category index>"
# and this file to each snippet before sending it to the editor's execute_python.
import importlib, json, math, sys, time
_TOOLS = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()) + 'Tools/AmbientAnims'
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)
import ambient_catalog as AC
importlib.reload(AC)
ACTOR_BP = '/Game/MetaHumans/Kellan/BP_Kellan'
SPOT, SPOT_YAW, FPS = (700.0, 0.0, 8.0), 180.0, AC.FPS
L = unreal.LevelSequenceEditorBlueprintLibrary


def obj(path):
    name = path.rsplit('/', 1)[1]
    return unreal.find_object(None, path + '.' + name) or unreal.load_object(None, path + '.' + name)


def exists(path):
    return unreal.EditorAssetLibrary.does_asset_exist(path)


def save_mine(asset):
    pkg = asset.get_package()
    assert pkg.get_name().startswith(AC.ROOT), pkg.get_name()
    return unreal.EditorLoadingAndSavingUtils.save_packages([pkg], False)


def pie():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None


def body_binding(seq):
    for b in seq.get_bindings():
        if str(b.get_display_name()) == 'Body':
            return b
    return None


def mixer_of(seq):
    b = body_binding(seq)
    t = b.find_tracks_by_exact_type(unreal.MovieSceneAnimationMixerTrack) if b else []
    return t[0] if t else None


def sorted_sections(mixer):
    return sorted(mixer.get_sections(), key=lambda s: s.get_start_frame())


def section_anims(secs):
    """Latest inline AnimSequence Kimodo wrote under each section, by section index."""
    best = {}
    pres = [s.get_path_name() + '.AnimSequence_' for s in secs]
    for anim in unreal.ObjectIterator(unreal.AnimSequence):
        p = anim.get_path_name()
        for i, pre in enumerate(pres):
            if p.startswith(pre) and p[len(pre):].isdigit():
                n = int(p[len(pre):])
                if n >= best.get(i, (-1, None))[0]:
                    best[i] = (n, anim)
    return {i: v[1] for i, v in best.items()}


def generated(anims, i):
    return i in anims and anims[i].data_model_interface.get_num_bone_tracks() >= 20
