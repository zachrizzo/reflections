"""Kimodo body takes for the cutscenes, from the 'takes' in cutscene_defs.py. Adapted from the spell-crafting session's
Tools/SpellCrafting/author_conversion_kimodo.py (same queuing rules).

Every take is retargeted once onto the UEFN mannequin (SK_UEFN_Mannequin), the skeleton of the hidden locomotion
drivers that BOTH Wren (BP_HeroSample's CharacterMesh0) and the crowd NPCs use. The cutscene subsystem plays a take
single-node on the first mesh in the cast member's hierarchy with that skeleton, so the visible MetaHuman follows
through its own retarget: one clip works for every identity.

Runs inside the editor via the MCP Python tool. ARGS: stage cutscene
  source <Cutscene>   add the generator sections to /Game/Cinematics/Takes/Source/LS_Takes_<Cutscene>, open it
  arm <Cutscene>      with that sequence open and PIE idle: re-apply every prompt in finished transactions (queues Kimodo)
  status <Cutscene>   which takes have finished generating
  close               close Sequencer (do this whenever not generating: the spawnable mannequin joins PIE)
  retarget <Cutscene> retarget the finished takes to the UEFN mannequin -> /Game/Cinematics/Takes/AS_<Cutscene>_<Role>_<t>
Hold the shared PIE lock (Saved/PIE_LOCK.json) while arming and generating: a PIE start cancels generation.
Set AnimGenOffline.RetiredAnimationGC.Enabled 0 first (source and arm do).
"""
import importlib
import json
import sys
import time
from pathlib import Path

import unreal

TOOLS_DIR = Path(unreal.Paths.project_dir()).resolve() / 'Tools' / 'Cinematics'
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
import cutscene_defs  # noqa: E402
importlib.reload(cutscene_defs)

ROOT = Path(unreal.Paths.project_intermediate_dir()).resolve() / 'CinematicsTakes'
ROOT.mkdir(exist_ok=True)
FOLDER = '/Game/Cinematics/Takes'
QUINN = '/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple'
UEFN = '/Game/Characters/UEFN_Mannequin/Meshes/SKM_UEFN_Mannequin'
RTG = '/Game/Villain/Conversion/Rigs/RTG_Mannequin_to_UEFN'
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
FPS = 30
FAR = unreal.Vector(0.0, 0.0, -200000.0)


def find_asset(path):
    name = path.rsplit('/', 1)[1]
    return unreal.find_object(None, path + '.' + name) or unreal.load_object(None, path + '.' + name)


def save(asset):
    return unreal.EditorLoadingAndSavingUtils.save_packages([asset.get_package()], False)


def source_path(cutscene):
    return '%s/Source/LS_Takes_%s' % (FOLDER, cutscene)


def entries(cutscene):
    offset = 0
    for take in cutscene_defs.CUTSCENES[cutscene].get('takes', []):
        if take.get('anim') or not take.get('prompt'):
            continue
        yield dict(take, offset=offset)
        offset += take['frames'] + 12


def load_source(cutscene):
    unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous([FOLDER], True)
    path = source_path(cutscene)
    return unreal.load_object(None, path + '.' + path.rsplit('/', 1)[1])


def mixer_of(source):
    return next(t for t in source.get_bindings()[0].get_tracks() if isinstance(t, unreal.MovieSceneAnimationMixerTrack))


def create_source(cutscene):
    unreal.SystemLibrary.execute_console_command(None, 'AnimGenOffline.RetiredAnimationGC.Enabled 0')
    for sub in ('', '/Source'):
        unreal.EditorAssetLibrary.make_directory(FOLDER + sub)
    path = source_path(cutscene)
    source = load_source(cutscene) or TOOLS.create_asset(path.rsplit('/', 1)[1], FOLDER + '/Source', unreal.LevelSequence,
                                                         unreal.LevelSequenceFactoryNew())
    defs = list(entries(cutscene))
    end = defs[-1]['offset'] + defs[-1]['frames']
    source.set_display_rate(unreal.FrameRate(FPS, 1))
    source.set_playback_start(0)
    source.set_playback_end(end)
    if source.get_bindings():
        mixer = mixer_of(source)
    else:
        binding = source.add_spawnable_from_class(unreal.SkeletalMeshActor)
        binding.set_display_name('Quinn | ' + cutscene)
        template = binding.get_object_template()
        template.get_editor_property('skeletal_mesh_component').set_editor_property('skeletal_mesh_asset', find_asset(QUINN))
        # Never in a game world: hidden in game, and far below the map so an open Sequencer can't drop it into PIE.
        template.set_actor_hidden_in_game(True)
        template.set_actor_location(FAR, False, False)
        mixer = binding.add_track(unreal.MovieSceneAnimationMixerTrack)
    save(source)
    generator = unreal.load_class(None, '/Script/Kimodo.KimodoPoseGenerator')
    state = {'request': None, 'i': 0, 'start': time.monotonic()}

    def tick(delta):
        try:
            if time.monotonic() - state['start'] > 240:
                raise TimeoutError('section insertion timed out')
            index = state['i']
            if index == len(defs):
                save(source)
                (ROOT / ('%s-sections.json' % cutscene)).write_text(json.dumps([d['id'] for d in defs]))
                unreal.unregister_slate_post_tick_callback(state['handle'])
                return
            data = defs[index]
            if state['request'] is not None and not state['request'].is_complete:
                return
            sections = mixer.get_sections()
            if len(sections) <= index:
                state['request'] = unreal.AnimGenOfflineMixerExtensions.add_generated_animation_section_async(mixer, index, data['offset'], generator)
                return
            section = sections[index]
            section.set_range(data['offset'], data['offset'] + data['frames'])
            g = section.get_editor_property('pose_generator')
            g.set_editor_property('RandomSeed', data['seed'])
            g.set_editor_property('movement_source', unreal.AnimGenOfflineMovementSource.GENERATED_ANIMATION)
            state['i'] += 1
            state['request'] = None
        except Exception as error:
            (ROOT / ('%s-source-error.txt' % cutscene)).write_text(repr(error))
            unreal.unregister_slate_post_tick_callback(state['handle'])
            raise

    state['handle'] = unreal.register_slate_post_tick_callback(tick)
    return 'adding %d sections to %s' % (len(defs), path)


def arm(cutscene):
    unreal.SystemLibrary.execute_console_command(None, 'AnimGenOffline.RetiredAnimationGC.Enabled 0')
    source = load_source(cutscene)
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() != source:
        unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(source)
        return 'opened; call arm again'
    armed = []
    for data, section in zip(entries(cutscene), mixer_of(source).get_sections()):
        with unreal.ScopedEditorTransaction('Generate ' + data['id']):
            section.modify()
            section.get_editor_property('pose_generator').set_editor_property('AnimDescriptionOverride', data['prompt'] + ' ')
        with unreal.ScopedEditorTransaction('Generate ' + data['id'] + ' (prompt)'):
            section.modify()
            section.get_editor_property('pose_generator').set_editor_property('AnimDescriptionOverride', data['prompt'])
        armed.append(data['id'])
    return armed


def section_anim(section):
    prefix = section.get_path_name() + '.AnimSequence_'
    best, best_index = None, -1
    for anim in unreal.ObjectIterator(unreal.AnimSequence):
        path = anim.get_path_name()
        if path.startswith(prefix) and path[len(prefix):].isdigit() and int(path[len(prefix):]) > best_index:
            best, best_index = anim, int(path[len(prefix):])
    return best


def close():
    """Sequencer must not stay open on a take sequence: its spawnable mannequin would join every PIE."""
    unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
    return 'closed'


def status(cutscene):
    out = {}
    for data, section in zip(entries(cutscene), mixer_of(load_source(cutscene)).get_sections()):
        inline = section_anim(section)
        out[data['id']] = bool(inline) and inline.data_model_interface.get_num_bone_tracks() >= 20
    return out


def retarget(cutscene):
    quinn, uefn, rtg = find_asset(QUINN), find_asset(UEFN), find_asset(RTG)
    out = {}
    for data, section in zip(entries(cutscene), mixer_of(load_source(cutscene)).get_sections()):
        inline = section_anim(section)
        if not inline or inline.data_model_interface.get_num_bone_tracks() < 20:
            out[data['id']] = 'pending'
            continue
        src_name = data['id'] + '_Kimodo'
        src = unreal.load_object(None, '%s/Source/%s.%s' % (FOLDER, src_name, src_name)) or TOOLS.duplicate_asset(src_name, FOLDER + '/Source', inline)
        save(src)
        spec = unreal.IKRetargetBatchOperationInputs(
            assets_to_retarget=[unreal.AssetRegistryHelpers.create_asset_data(src)], source_mesh=quinn, target_mesh=uefn,
            ik_retarget_asset=rtg, target_path=FOLDER, use_source_path=False, include_referenced_assets=False,
            overwrite_existing_files=True, suffix='')
        clip = unreal.IKRetargetBatchOperation.run_batch_retarget(spec)[0].get_asset()
        if clip.get_name() != data['id']:
            unreal.EditorAssetLibrary.delete_asset(FOLDER + '/' + data['id']) if unreal.EditorAssetLibrary.does_asset_exist(FOLDER + '/' + data['id']) else None
            unreal.EditorAssetLibrary.rename_asset(clip.get_path_name().split('.')[0], FOLDER + '/' + data['id'])
            clip = unreal.load_object(None, '%s/%s.%s' % (FOLDER, data['id'], data['id']))
        clip.set_preview_skeletal_mesh(uefn)
        clip.set_editor_property('enable_root_motion', False)
        save(clip)
        out[data['id']] = {'clip': clip.get_path_name(), 'seconds': round(clip.get_play_length(), 2)}
    (ROOT / ('%s-retarget.json' % cutscene)).write_text(json.dumps(out, indent=2))
    if all(v != 'pending' for v in out.values()):
        close()
    return out


_args = list(globals().get('ARGS', []) or ['status', 'Intro'])
RESULT = json.dumps({'source': create_source, 'arm': arm, 'status': status, 'retarget': retarget,
                     'close': lambda _name: close()}[_args[0]](_args[1] if len(_args) > 1 else ''),
                    default=str, indent=1)
print(RESULT)
