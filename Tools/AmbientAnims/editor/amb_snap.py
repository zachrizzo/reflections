# Record the Kimodo take each clip in ONLY holds now, so a redo can tell when its new take has arrived
# (amb_status with REDO=True). Writes Saved/KimodoAmbient/redo/<NN>_<Category>.json.
out = {}
seq = obj(AC.seq_path(CI))
anims = section_anims(sorted_sections(mixer_of(seq)))
snap = {clip['id']: (anims[i].get_path_name() if i in anims else '')
        for i, (clip, _s, _d) in enumerate(AC.layout(CI)) if clip['id'] in ONLY}
assert len(snap) == len(ONLY), 'unknown clip ids: %s' % sorted(set(ONLY) - set(snap))
import os
d = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()) + 'KimodoAmbient/redo'
os.makedirs(d, exist_ok=True)
fn = '%s/%02d_%s.json' % (d, CI + 1, AC.CATEGORIES[CI][0])
with open(fn, 'w') as fh:
    json.dump(snap, fh, indent=1)
out['file'] = fn
out['snap'] = snap
json.dumps(out)
