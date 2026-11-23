"""build_browser.py: build the review page for the ambient library.

Writes Saved/KimodoAmbient/browser/index.html (from browser_page.html) and library.json (one clip per line:
catalog data, review scores and joint positions at 15 fps in cm) from ambient_catalog.py and
Saved/KimodoAmbient/analysis/*.json. Publish the folder as one artifact.
"""
import glob
import json
import os
import shutil

import ambient_catalog as AC
from review_sheets import BASE, score, flags

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'browser')


def main():
    os.makedirs(OUT, exist_ok=True)
    data = {}
    for fn in glob.glob(os.path.join(BASE, 'analysis', '[0-9][0-9]_*.json')):
        d = json.load(open(fn))
        data[d['category']] = d
    rows = []
    pending = AC.pending_redo()
    for ci, (name, desc, clips) in enumerate(AC.CATEGORIES):
        d = data.get(name)
        for clip in clips:
            c = d['clips'].get(clip['id']) if d else None
            rec = {'cat': name, 'catNo': ci + 1, 'catDesc': desc, 'id': clip['id'], 'asset': AC.asset_name(ci, clip),
                   'path': '%s/%s' % (AC.folder(ci), AC.asset_name(ci, clip)), 'kind': clip['kind'],
                   'sec': round(clip['frames'] / AC.FPS, 1), 'props': clip['props'], 'jobs': clip['jobs'],
                   'beats': [[o / AC.FPS, s] for o, s in clip['prompts']], 'still': clip['still'],
                   'rev': clip['rev'], 'pending': (name, clip['id']) in pending}
            if c:
                s = score(c, d['bones'], d['fps'], d['step'])
                s['flags'] = flags(s, clip['kind'], clip['still'])
                rec['score'] = s
                rec['fps'] = d['fps'] / d['step']
                rec['f'] = [round(v) for fr in c['frames'] for b in fr for v in b]
            rows.append(rec)
    with open(os.path.join(OUT, 'library.json'), 'w') as fh:
        fh.write('[\n' + ',\n'.join(json.dumps(r, separators=(',', ':')) for r in rows) + '\n]\n')
    shutil.copy(os.path.join(HERE, 'browser_page.html'), os.path.join(OUT, 'index.html'))
    print(OUT, sum(1 for r in rows if 'f' in r), 'of', len(rows), 'clips with motion',
          round(os.path.getsize(os.path.join(OUT, 'library.json')) / 1e6, 2), 'MB')


if __name__ == '__main__':
    main()
