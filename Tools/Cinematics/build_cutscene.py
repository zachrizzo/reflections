"""Builds a Reflections cutscene from a definition in cutscene_defs.py: the Level Sequence (spawnable cine cameras with
keyed moves, camera cuts) at /Game/Cinematics/Sequences/LS_Cutscene_<Name> and the data asset (cast, takes, lines,
cards, fades, cues) at /Game/Cinematics/Data/DA_Cutscene_<Name>, which the cutscene subsystem plays.

Every position in a definition is in ANCHOR SPACE, in cm: X = the anchor's forward (the way Wren faces when there is no
marker), Y = right, Z = up from the anchor's feet. At play time the subsystem uses the anchor as the sequence's
transform origin, so the same cutscene plays on any map.

Runs inside the editor via the MCP Python tool (top-level code, ARGS list):
  build <Name> [<Name> ...]   build/rebuild the sequence and data asset (never touches any level)
  list                        names defined in cutscene_defs.py
  preview <Name> <x> <y> <z> <yaw>
                              opens the sequence in Sequencer with that world transform as its origin (editor preview)
"""
import copy
import importlib
import math
import sys
from pathlib import Path

import unreal

TOOLS_DIR = Path(unreal.Paths.project_dir()).resolve() / 'Tools' / 'Cinematics'
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
import cutscene_defs  # noqa: E402
importlib.reload(cutscene_defs)

FPS = 30
SEQ_FOLDER = '/Game/Cinematics/Sequences'
DATA_FOLDER = '/Game/Cinematics/Data'
ASSET_TOOLS = unreal.AssetToolsHelpers.get_asset_tools()


def load(path):
    name = path.rsplit('/', 1)[1]
    return unreal.load_object(None, path + '.' + name)


def save(asset):
    return unreal.EditorLoadingAndSavingUtils.save_packages([asset.get_package()], False)


def look_rotation(src, dst, roll=0.0):
    dx, dy, dz = dst[0] - src[0], dst[1] - src[1], dst[2] - src[2]
    yaw = math.degrees(math.atan2(dy, dx))
    pitch = math.degrees(math.atan2(dz, math.hypot(dx, dy)))
    return (roll, pitch, yaw)


def unwrap(prev, value):
    while value - prev > 180.0:
        value -= 360.0
    while value - prev < -180.0:
        value += 360.0
    return value


def frame(t):
    return unreal.FrameNumber(int(round(t * FPS)))


def ensure_sequence(name, length):
    path = SEQ_FOLDER + '/LS_Cutscene_' + name
    unreal.EditorAssetLibrary.make_directory(SEQ_FOLDER)
    seq = load(path)
    if seq is None:
        seq = ASSET_TOOLS.create_asset('LS_Cutscene_' + name, SEQ_FOLDER, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    # Start clean: remove every binding and track (the asset keeps its path, so the data asset's reference holds).
    for binding in list(seq.get_bindings()):
        binding.remove()
    for track in list(seq.get_tracks()):
        seq.remove_track(track)
    seq.set_display_rate(unreal.FrameRate(FPS, 1))
    seq.set_tick_resolution(unreal.FrameRate(24000, 1))
    seq.set_playback_start_seconds(0.0)
    seq.set_playback_end_seconds(length)
    seq.set_view_range(-0.5, length + 0.5)
    seq.set_work_range(-0.5, length + 0.5)
    return seq


def add_camera(seq, shot, index):
    binding = seq.add_spawnable_from_class(unreal.CineCameraActor)
    binding.set_display_name('Cam %02d %s' % (index + 1, shot.get('label', '')))
    template = binding.get_object_template()
    cam = template.get_editor_property('camera_component')
    filmback = cam.get_editor_property('filmback')
    filmback.set_editor_property('sensor_width', 36.0)
    filmback.set_editor_property('sensor_height', 20.25)
    cam.set_editor_property('filmback', filmback)
    cam.set_editor_property('constrain_aspect_ratio', False)
    cam.set_editor_property('current_focal_length', float(shot.get('focal', 35.0)))
    cam.set_editor_property('current_aperture', float(shot.get('aperture', 8.0)))
    focus = cam.get_editor_property('focus_settings')
    if shot.get('focus'):
        focus.set_editor_property('focus_method', unreal.CameraFocusMethod.MANUAL)
        focus.set_editor_property('manual_focus_distance', float(shot['focus']))
    else:
        focus.set_editor_property('focus_method', unreal.CameraFocusMethod.DISABLE)
    cam.set_editor_property('focus_settings', focus)
    # Cinematic exposure: a touch of motion blur and no auto-exposure surprises between cuts.
    pp = cam.get_editor_property('post_process_settings')
    pp.set_editor_property('override_motion_blur_amount', True)
    pp.set_editor_property('motion_blur_amount', 0.35)
    if 'vignette' in shot:
        pp.set_editor_property('override_vignette_intensity', True)
        pp.set_editor_property('vignette_intensity', float(shot['vignette']))
    cam.set_editor_property('post_process_settings', pp)

    track = binding.add_track(unreal.MovieScene3DTransformTrack)
    section = track.add_section()
    section.set_range_seconds(shot['start'], shot['end'] + 0.1)
    channels = section.get_all_channels()
    prev_yaw = None
    for key in shot['keys']:
        t, pos = key['t'], key['pos']
        rot = key.get('rot') or look_rotation(pos, key['look'], key.get('roll', 0.0))
        yaw = rot[2] if prev_yaw is None else unwrap(prev_yaw, rot[2])
        prev_yaw = yaw
        values = (pos[0], pos[1], pos[2], rot[0], rot[1], yaw)
        interp = unreal.MovieSceneKeyInterpolation.AUTO if key.get('smooth', True) else unreal.MovieSceneKeyInterpolation.LINEAR
        for channel, value in zip(channels[:6], values):
            channel.add_key(frame(t), float(value), 0.0, unreal.MovieSceneTimeUnit.DISPLAY_RATE, interp)
    return binding


def build_sequence(name, defn):
    length = defn['length']
    seq = ensure_sequence(name, length)
    cut_track = seq.add_track(unreal.MovieSceneCameraCutTrack)
    for index, shot in enumerate(defn['shots']):
        binding = add_camera(seq, shot, index)
        cut = cut_track.add_section()
        cut.set_range_seconds(shot['start'], shot['end'])
        cut.set_camera_cut_binding(binding) if hasattr(cut, 'set_camera_cut_binding') else \
            unreal.MovieSceneSectionExtensions.set_camera_cut_binding(cut, binding)
    for index, light in enumerate(defn.get('lights', [])):
        add_light(seq, light, index, length)
    # A Hero binding (possessable placeholder) is only needed when the sequence animates him; takes go in the asset.
    save(seq)
    return seq


def add_light(seq, light, index, length):
    """A spawnable point light in anchor space (a glow from a doorway, from cupped hands). Intensity keys fade it."""
    binding = seq.add_spawnable_from_class(unreal.PointLight)
    binding.set_display_name('Light %02d %s' % (index + 1, light.get('label', '')))
    template = binding.get_object_template()
    comp = template.get_editor_property('point_light_component')
    r, g, b = light.get('color', (1.0, 0.8, 0.5))
    comp.set_editor_property('light_color', unreal.Color(int(r * 255), int(g * 255), int(b * 255), 255))
    comp.set_editor_property('attenuation_radius', float(light.get('radius', 600.0)))
    comp.set_editor_property('source_radius', float(light.get('source_radius', 20.0)))
    comp.set_editor_property('cast_shadows', bool(light.get('shadows', False)))
    comp.set_editor_property('intensity_units', unreal.LightUnits.CANDELAS)
    comp.set_editor_property('intensity', float(light.get('intensity', 40.0)))
    track = binding.add_track(unreal.MovieScene3DTransformTrack)
    section = track.add_section()
    section.set_range_seconds(0.0, length)
    channels = section.get_all_channels()
    for channel, value in zip(channels[:3], light['pos']):
        channel.add_key(frame(0.0), float(value))
    # Spawn only for its window.
    spawn = binding.add_track(unreal.MovieSceneSpawnTrack)
    spawn_section = spawn.add_section()
    spawn_section.set_range_seconds(light.get('start', 0.0), light.get('end', length))
    spawn_channel = spawn_section.get_all_channels()[0]
    spawn_channel.add_key(frame(light.get('start', 0.0)), True)
    return binding


def make_struct(struct_type, values):
    s = struct_type()
    for key, value in values.items():
        s.set_editor_property(key, value)
    return s


MISSING = []
FALLBACKS_USED = []


def soft(path):
    """The asset at path, or None (recorded in MISSING) when it doesn't exist yet: takes and voices land later."""
    if not path:
        return None
    # does_asset_exist reads the asset registry, which flickers while another session imports; loading is the truth.
    name = path.rsplit('/', 1)[1]
    asset = unreal.find_object(None, path + '.' + name) or unreal.load_object(None, path + '.' + name)
    if asset is None:
        MISSING.append(path)
    return asset


def build_data(name, defn, seq):
    path = DATA_FOLDER + '/DA_Cutscene_' + name
    unreal.EditorAssetLibrary.make_directory(DATA_FOLDER)
    asset = load(path)
    if asset is None:
        asset = ASSET_TOOLS.create_asset('DA_Cutscene_' + name, DATA_FOLDER, unreal.ReflectionsCutsceneAsset, unreal.DataAssetFactory())
    asset.set_editor_property('sequence', seq)
    asset.set_editor_property('anchor_name', defn.get('anchor', name))
    asset.set_editor_property('length', float(defn.get('length', 0.0)))
    for key in ('letterbox_aspect', 'hand_off_blend_seconds', 'hand_off_pitch', 'skip_hold_seconds'):
        if key in defn:
            asset.set_editor_property(key, float(defn[key]))
    for key in ('letterbox', 'skippable', 'hand_off_behind_hero', 'snap_anchor_to_ground'):
        if key in defn:
            asset.set_editor_property(key, bool(defn[key]))  # bLetterbox -> 'letterbox' in Python
    cast = []
    for member in defn.get('cast', []):
        values = {'role': member['role'], 'is_hero': member.get('hero', False), 'place_at_mark': member.get('place', False),
                  'restore_transform': member.get('restore', False), 'hidden': member.get('hidden', False)}
        if member.get('tag'):
            values['find_tag'] = member['tag']
        if member.get('stand_in'):
            values['stand_in_class'] = unreal.load_class(None, member['stand_in'])
        if member.get('person'):
            values['person_id'] = member['person']
        if member.get('stand_in_archetype'):
            values['stand_in_archetype'] = member['stand_in_archetype']
        if member.get('nearest'):
            values['fallback_to_nearest_npc'] = True
            values['search_radius'] = float(member.get('radius', 4000.0))
        if member.get('prefer_infected'):
            values['prefer_infected'] = True
        if member.get('infect'):
            values['infect_on_start'] = True
        if member.get('keep'):
            values['keep_stand_in'] = True
        if member.get('mark'):
            x, y, z, yaw = member['mark']
            values['mark'] = unreal.Transform(unreal.Vector(x, y, z), unreal.Rotator(0.0, 0.0, yaw), unreal.Vector(1, 1, 1))
        cast.append(make_struct(unreal.ReflectionsCutsceneCastMember, values))
    asset.set_editor_property('cast', cast)
    takes = []
    for take in defn.get('takes', []):
        anim = soft(take_path(take))
        loops = int(take.get('loops', 1))
        if anim is None and take['id'] in getattr(cutscene_defs, 'FALLBACK', {}):
            # No Kimodo take yet: an existing project clip plays the beat.
            MISSING.pop()  # the Kimodo path is expected to be missing while the fallback stands in
            anim = soft(cutscene_defs.FALLBACK[take['id']])
            loops = cutscene_defs.FALLBACK_LOOPS.get(take['id'], loops)
            FALLBACKS_USED.append(take['id'])
        if anim is None:
            continue
        values = {'role': take['role'], 'start_time': float(take['t']), 'animation': anim,
                  'play_rate': float(take.get('rate', 1.0)), 'blend_in': float(take.get('blend_in', 0.3)),
                  'blend_out': float(take.get('blend_out', 0.4)), 'loop_count': loops}
        if take.get('full_body'):
            values['full_body'] = True
        if take.get('slot'):
            values['slot'] = take['slot']
        if take.get('face'):
            values['face_role'] = take['face']
        takes.append(make_struct(unreal.ReflectionsCutscenePerformance, values))
    asset.set_editor_property('performances', takes)
    lines = []
    for line in defn.get('lines', []):
        values = {'start_time': float(line['t']), 'duration': float(line.get('dur', 0.0)),
                  'speaker': unreal.Text(line.get('speaker', '')), 'text': unreal.Text(line.get('text', ''))}
        voice = soft(line.get('voice'))
        if voice:
            values['voice'] = voice
        if line.get('role'):
            values['speaker_role'] = line['role']
        if line.get('only_with'):
            values['only_with_role'] = line['only_with']
        if line.get('only_without'):
            values['only_without_role'] = line['only_without']
        if line.get('side'):
            values['only_in_side'] = line['side']
        lines.append(make_struct(unreal.ReflectionsCutsceneLine, values))
    asset.set_editor_property('lines', lines)
    styles = {'title': unreal.ReflectionsCutsceneCardStyle.TITLE, 'caption': unreal.ReflectionsCutsceneCardStyle.CAPTION,
              'location': unreal.ReflectionsCutsceneCardStyle.LOCATION}
    cards = [make_struct(unreal.ReflectionsCutsceneCard, {
        'start_time': float(c['t']), 'duration': float(c['dur']), 'style': styles[c.get('style', 'caption')],
        'text': unreal.Text(c.get('text', '')), 'sub_text': unreal.Text(c.get('sub', '')),
        'only_in_side': c.get('side', '')}) for c in defn.get('cards', [])]
    asset.set_editor_property('cards', cards)
    fades = [make_struct(unreal.ReflectionsCutsceneFade, {
        'start_time': float(f['t']), 'duration': float(f['dur']), 'from': float(f['from']), 'to': float(f['to'])})
        for f in defn.get('fades', [])]
    asset.set_editor_property('fades', fades)
    cues = []
    for c in defn.get('cues', []):
        values = {'time': float(c['t']), 'cue': c['cue']}
        if c.get('attacker'):
            values.update({'attacker_role': c['attacker'], 'victim_role': c['victim'], 'hold_at': float(c.get('hold_at', -1.0))})
            fallback = soft(c.get('fallback_take'))
            if fallback:
                values['fallback_victim_take'] = fallback
        cues.append(make_struct(unreal.ReflectionsCutsceneCue, values))
    asset.set_editor_property('cues', cues)
    music = soft(defn.get('music'))
    asset.set_editor_property('music', music)
    save(asset)
    return asset


TAKES_FOLDER = '/Game/Cinematics/Takes'


def take_path(take):
    """A take's clip: 'anim' if given, else the Kimodo take built by kimodo_takes.py (AS_<Cutscene>_<Role>_<t>)."""
    return take.get('anim') or '%s/%s' % (TAKES_FOLDER, take['id'])


def voice_seconds(path):
    voice = soft(path) if path else None
    if voice is None:
        return 0.0
    try:
        return float(voice.get_editor_property('duration'))
    except Exception:
        return 0.0


def scaled(defn, f):
    """A copy of defn with every time multiplied by f (shots, keys, takes, cards, fades, cues, lights, line times)."""
    out = copy.deepcopy(defn)
    out['length'] = defn['length'] * f
    for shot in out['shots']:
        shot['start'] *= f
        shot['end'] *= f
        for key in shot['keys']:
            key['t'] *= f
    for group in ('takes', 'lines', 'fades', 'cues'):
        for item in out.get(group, []):
            item['t'] *= f
            if 'hold_at' in item and item['hold_at'] >= 0:
                item['hold_at'] *= f
    for card in out.get('cards', []):
        card['t'] *= f
        card['dur'] *= f
    for fade in out.get('fades', []):
        fade['dur'] *= f
    for light in out.get('lights', []):
        light['start'] = light.get('start', 0.0) * f
        light['end'] = light.get('end', defn['length']) * f
    return out


def fit_lines(defn, gap=0.25, tail=0.8):
    """The recorded voices decide the timing. Each line starts at its scripted time, or right after the previous
    line ends if that is later. If the last line then runs past the end, only the final shot is held longer (the scene's
    end cues, fades and cards move with it). Lines at the same scripted time with only_with / only_without are
    alternatives (one plays), so they count once, at the longest."""
    out = copy.deepcopy(defn)
    durations = {line['id']: voice_seconds(line.get('voice')) for line in out.get('lines', []) if line.get('voice')}
    groups = {}
    for line in out.get('lines', []):
        groups.setdefault(round(line['t'], 3), []).append(line)
    cursor, pushed = 0.0, 0
    for t in sorted(groups):
        start = max(t, cursor)
        pushed += start > t + 0.01
        longest = 0.0
        for line in groups[t]:
            line['t'] = start
            longest = max(longest, durations.get(line['id'], 0.0) or float(line.get('dur', 3.0) or 3.0))
        cursor = start + longest + gap
    last_end = cursor - gap
    delta = max(0.0, last_end + tail - out['length'])
    if delta > 0.0:
        last = out['shots'][-1]
        tail_start = last['start']
        old_length = out['length']
        out['length'] += delta
        last['end'] += delta
        last['keys'][-1]['t'] += delta
        for group in ('fades', 'cues', 'cards'):
            for item in out.get(group, []):
                if item['t'] >= tail_start - 0.01:
                    item['t'] += delta
        for light in out.get('lights', []):
            if light.get('end', old_length) >= old_length - 0.01:
                light['end'] = light.get('end', old_length) + delta
    out['fit'] = {'pushed_lines': pushed, 'last_line_end': round(last_end, 2), 'tail_added': round(delta, 2),
                  'length': round(out['length'], 2)}
    return out


def build(name):
    del MISSING[:]
    del FALLBACKS_USED[:]
    defn = fit_lines(cutscene_defs.CUTSCENES[name])
    seq = build_sequence(name, defn)
    out = {'sequence': seq.get_path_name()}
    if hasattr(unreal, 'ReflectionsCutsceneAsset'):
        out['data'] = build_data(name, defn, seq).get_path_name()
    else:
        out['data'] = 'skipped: UReflectionsCutsceneAsset not in this editor build yet'
    out['missing'] = sorted(set(MISSING))
    out['fit'] = defn.get('fit')
    out['fallback_takes'] = list(FALLBACKS_USED)
    return out


def preview(name, x, y, z, yaw):
    seq = load(SEQ_FOLDER + '/LS_Cutscene_' + name)
    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
    return 'opened %s (origin %s, yaw %s: set the transform origin in Sequencer to preview in place)' % (name, (x, y, z), yaw)


RESULT = None
_args = list(globals().get('ARGS', []) or [])
if _args:
    cmd = _args[0]
    if cmd == 'build':
        RESULT = {n: build(n) for n in _args[1:]}
    elif cmd == 'list':
        RESULT = sorted(cutscene_defs.CUTSCENES)
    elif cmd == 'preview':
        RESULT = preview(_args[1], *map(float, _args[2:6]))
    print(RESULT)
