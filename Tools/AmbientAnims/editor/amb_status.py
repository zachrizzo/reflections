# Which clips of the category Kimodo has finished generating.
# With REDO=True it only counts the clips recorded by amb_snap.py, and only once each holds a new take.
out = {}
seq = obj(AC.seq_path(CI)) if exists(AC.seq_path(CI)) else None
lay = AC.layout(CI)
if seq is None:
    out['state'] = 'no sequence'
else:
    anims = section_anims(sorted_sections(mixer_of(seq)))
    if globals().get('REDO'):
        fn = '%sKimodoAmbient/redo/%02d_%s.json' % (
            unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), CI + 1, AC.CATEGORIES[CI][0])
        old = json.load(open(fn))
        want = [(i, clip['id']) for i, (clip, _s, _d) in enumerate(lay) if clip['id'] in old]
        done = [cid for i, cid in want if generated(anims, i) and anims[i].get_path_name() != old[cid]]
        out['redo'] = True
        out['of'] = len(want)
        out['missing'] = [cid for _i, cid in want if cid not in done]
    else:
        done = [clip['id'] for i, (clip, _s, _d) in enumerate(lay) if generated(anims, i)]
        out['of'] = len(lay)
        out['missing'] = [clip['id'] for clip, _s, _d in lay if clip['id'] not in done]
    out['done'] = len(done)
    out['open'] = L.get_current_level_sequence() == seq
out['pie'] = pie()
out['t'] = time.strftime('%H:%M:%S')
json.dumps(out)
