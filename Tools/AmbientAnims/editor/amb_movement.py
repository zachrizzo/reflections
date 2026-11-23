# Set every section of the category to the given movement source (global MS: 'SEQUENCER' or 'GENERATED_ANIMATION').
# SEQUENCER constrains Kimodo to the actor's own (stationary) transform track, so it generates in-place motion with
# planted feet; GENERATED_ANIMATION lets it wander and moves the travel onto a generated actor transform track.
assert not pie(), 'PIE running'
seq = obj(AC.seq_path(CI))
assert L.get_current_level_sequence() == seq, 'category sequence not open'
src = getattr(unreal.AnimGenOfflineMovementSource, MS)
for s in sorted_sections(mixer_of(seq)):
    with unreal.ScopedEditorTransaction('Ambient movement source'):
        s.modify()
        s.get_editor_property('pose_generator').set_editor_property('movement_source', src)
save_mine(seq)
tracks = []
for t in body_binding(seq).get_tracks():
    if isinstance(t, unreal.MovieScene3DTransformTrack):
        tracks.append([str(t.get_display_name()), [c.get_num_keys() for c in t.get_sections()[0].get_all_channels()[:3]],
                       [round(c.get_default(), 1) if c.has_default() else None for c in t.get_sections()[0].get_all_channels()[:6]]])
{'movement': MS, 'transform_tracks': tracks, 't': time.strftime('%H:%M:%S')}
