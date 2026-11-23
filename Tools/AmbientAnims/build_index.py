"""build_index.py: write ArtDirection/AmbientAnims/Library.md, the browsable index of the ambient clip library,
from ambient_catalog.py plus the review scores in Saved/KimodoAmbient/analysis/scores.json (if present)."""
import json
import os

import ambient_catalog as AC

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, '..', '..'))
SCORES = os.path.join(PROJECT, 'Saved', 'KimodoAmbient', 'analysis', 'scores.json')
OUT = os.path.join(PROJECT, 'ArtDirection', 'AmbientAnims', 'Library.md')


def main():
    scores = json.load(open(SCORES)) if os.path.exists(SCORES) else {}
    pending = AC.pending_redo()
    n_baked = sum(1 for c in AC.CATEGORIES for clip in c[2] if '%s/%s' % (c[0], clip['id']) in scores)
    lines = [
        '# Ambient NPC animation library',
        '',
        'Generated with UE 5.9 Kimodo (model `nvidia/Kimodo-SOMA-RP-v1.1`, licensed for commercial use) on a MetaHuman '
        '(BP_Kellan, `/Game/MetaHumans/Common` `metahuman_base_skel`), then baked in place (no root motion) to one '
        'AnimSequence per clip.',
        '',
        '- %d clips in %d categories, %d baked and reviewed.' % (AC.total(), len(AC.CATEGORIES), n_baked),
        '- Assets: `%s/<NN>_<Category>/AS_Amb_<Category>_<Clip>`.' % AC.ROOT,
        '- Generation sequences (re-generate or tweak a take there): `%s/LS_Amb_<NN>_<Category>`.' % AC.GEN,
        '- Source of truth for prompts, props and jobs: `Tools/AmbientAnims/ambient_catalog.py`. Each baked clip also '
        'carries this data as asset metadata (`Ambient.*`, `Kimodo.*` tags).',
        '- Review sheets (stick figures every ~1 s, plus scores): `Saved/KimodoAmbient/sheets/`.',
        '',
        '**Kinds.** `loop`: a repeating activity. Clips do not loop seamlessly; chain takes with a 0.3-0.5 s crossfade. '
        '`action`: a one-shot beat that starts and ends near a relaxed stand.',
        '',
        '**Props.** Kimodo is not prop-aware and the SOMA body has no fingers, so hands stay open. Attach the prop to '
        'the `hand_r` / `hand_l` socket at runtime; some grips will need a per-clip offset.',
        '',
        '**Seated clips** sit on an invisible seat at the default seat height. Place the NPC on a bench or stool.',
        '',
        '**Flags.** FROZEN? = the prompt asked for an action but the take is a held pose; SLIDE = a planted foot '
        'skates (over 25 cm/s); SEAM = a loop ends over 20 cm from its start. Clips meant to be a quiet held pose '
        '(standing guard, dozing on the ground) are marked *held pose* and never flagged FROZEN?. *Redo queued* '
        'means a better prompt is parked in `Tools/AmbientAnims/PENDING_REDO.md`; the current take is usable as a '
        'placeholder.',
        '',
    ]
    for ci, (name, desc, clips) in enumerate(AC.CATEGORIES):
        lines += ['## %02d %s' % (ci + 1, name), '', desc + '.', '',
                  '| Clip | Kind | Length | Props | Used by | Beats (frame: prompt) | Review |',
                  '|---|---|---|---|---|---|---|']
        for clip in clips:
            s = scores.get('%s/%s' % (name, clip['id']))
            review = ('energy %.0f, slide %.0f%s%s' % (s['energy'], s['foot_slide'],
                                                       ', *held pose*' if clip['still'] else '',
                                                       (', **%s**' % ' '.join(s['flags'])) if s['flags'] else '')
                      + (', *redo queued*' if (name, clip['id']) in pending else '')
                      if s else 'not baked')
            beats = '<br>'.join('%d: %s' % (o, t) for o, t in clip['prompts'])
            lines.append('| `%s` | %s | %.1f s | %s | %s | %s | %s |' % (
                AC.asset_name(ci, clip), clip['kind'], clip['frames'] / AC.FPS, ', '.join(clip['props']) or '-',
                ', '.join(clip['jobs']), beats, review))
        lines.append('')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines))
    print(OUT, n_baked, 'baked')


if __name__ == '__main__':
    main()
