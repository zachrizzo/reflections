# Remove keys from the Body's transform track (left behind by a GENERATED_ANIMATION pass), keeping its defaults
# (the fixed spot), so a SEQUENCER-movement generation is constrained to stand still.
assert not pie(), 'PIE running'
seq = obj(AC.seq_path(CI))
removed = 0
for t in body_binding(seq).get_tracks():
    if isinstance(t, unreal.MovieScene3DTransformTrack):
        for s in t.get_sections():
            s.modify()
            for c, v in zip(s.get_all_channels()[:9], [SPOT[0], SPOT[1], SPOT[2], 0.0, 0.0, SPOT_YAW, 1.0, 1.0, 1.0]):
                for k in list(c.get_keys()):
                    c.remove_key(k)
                    removed += 1
                c.set_default(v)
save_mine(seq)
{'removed': removed, 't': time.strftime('%H:%M:%S')}
