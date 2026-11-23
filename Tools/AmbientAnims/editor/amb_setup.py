# Create (or reuse) the category's generation sequence: one Kimodo section per clip on mixer row 0, prompts keyed
# on the AnimDescriptionChannel (Override left empty), then open it in Sequencer.
out = {}
assert not pie(), 'PIE running'
name, desc, clips = AC.CATEGORIES[CI]
path = AC.seq_path(CI)
cur = L.get_current_level_sequence()
assert cur is None or cur.get_path_name().startswith(AC.ROOT), 'another sequence open: ' + cur.get_path_name()
for d in (AC.ROOT, AC.GEN, AC.folder(CI)):
    unreal.EditorAssetLibrary.make_directory(d)
tools = unreal.AssetToolsHelpers.get_asset_tools()
seq = obj(path) if exists(path) else tools.create_asset(path.rsplit('/', 1)[1], AC.GEN, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
lay = AC.layout(CI)
end = lay[-1][1] + lay[-1][0]['frames']
seq.set_display_rate(unreal.FrameRate(FPS, 1)); seq.set_playback_start(0); seq.set_playback_end(end)
b = body_binding(seq)
if b is None:
    b = seq.add_spawnable_from_class(unreal.EditorAssetLibrary.load_blueprint_class(ACTOR_BP))
    b.set_display_name('Body')
b.get_object_template().set_actor_hidden_in_game(True)
tr = b.find_tracks_by_exact_type(unreal.MovieScene3DTransformTrack)
tr = tr[0] if tr else b.add_track(unreal.MovieScene3DTransformTrack)
tsec = tr.get_sections()[0] if tr.get_sections() else tr.add_section()
tsec.set_start_frame_bounded(False); tsec.set_end_frame_bounded(False)
for c, v in zip(tsec.get_all_channels()[:9], [SPOT[0], SPOT[1], SPOT[2], 0.0, 0.0, SPOT_YAW, 1.0, 1.0, 1.0]):
    c.set_default(v)
mixer = mixer_of(seq) or b.add_track(unreal.MovieSceneAnimationMixerTrack)
save_mine(seq)
unreal.SystemLibrary.execute_console_command(None, 'AnimGenOffline.RetiredAnimationGC.Enabled 0')
if cur is not None and cur != seq:
    L.close_level_sequence()
    await asyncio.sleep(0.3)
if L.get_current_level_sequence() != seq:
    L.open_level_sequence(seq)
for _ in range(5):
    L.set_current_time(1)
    await asyncio.sleep(0.15)
gen_cls = unreal.load_class(None, '/Script/Kimodo.KimodoPoseGenerator')
while len(mixer.get_sections()) < len(lay):
    start = lay[len(mixer.get_sections())][1]
    req = unreal.AnimGenOfflineMixerExtensions.add_generated_animation_section_async(mixer, 0, start, gen_cls)
    for _ in range(150):
        if req.is_complete:
            break
        await asyncio.sleep(0.1)
    assert req.is_complete, 'section add timed out at %d' % start
for (clip, start, seed), s in zip(lay, sorted_sections(mixer)):
    with unreal.ScopedEditorTransaction('Ambient %s %s' % (name, clip['id'])):
        s.modify()
        s.set_row_index(0)
        s.set_range(start, start + clip['frames'])
        g = s.get_editor_property('pose_generator')
        g.set_editor_property('RandomSeed', seed)
        # SEQUENCER: constrained to the actor's fixed spot, so the motion stays in place with planted feet.
        g.set_editor_property('movement_source', unreal.AnimGenOfflineMovementSource.SEQUENCER)
        g.set_editor_property('AnimDescriptionOverride', '')
        ch = [c for c in s.get_all_channels() if c.get_name().startswith('AnimDescriptionChannel')][0]
        for k in list(ch.get_keys()):
            ch.remove_key(k)
        for off, text in clip['prompts']:
            ch.add_key(unreal.FrameNumber(start + off), text)
save_mine(seq)
out['seq'] = path
out['sections'] = [(s.get_start_frame(), s.get_end_frame(), s.get_row_index(),
                    s.get_editor_property('pose_generator').get_editor_property('RandomSeed')) for s in sorted_sections(mixer)]
out['t'] = time.strftime('%H:%M:%S')
out
