"""Writes ArtDirection/MockCity/MARKERS.md from a mock build's Saved/MockCity_markers_<Side>.json files."""
import json
import os

PROJ = r'C:\Users\zachc\Documents\Unreal Projects\reflections'
SAVED = os.path.join(PROJ, 'Saved')
data = json.load(open(os.path.join(PROJ, 'ArtDirection', 'MockCity', 'tools', 'mockcity_markers.json'), encoding='utf-8'))
info = {e['name']: e for e in data}
OFFSET = {'Pewterside': 0, 'Giltside': 150000, 'Frostside': 300000}
KIND_ORDER = ['Tower', 'Mk', 'Spot', 'Item', 'CutsceneAnchor', 'QuestGiver', 'Home', 'Haunt']

lines = ['# Story markers in the mock Lanthorne', '',
         'Generated from the mock build (`tools/mockcity_build.py`). Every row is one **Reflections Story Marker** actor in',
         'that side\'s level. *Also answers to* lists the extra names on the same marker (actor Tags). Quests, NPC',
         'lives and cutscenes look markers up by any of these names, so the real map needs the same names on the same',
         'side. Positions are local to the side level, in metres (+X east, +Y north; see `plan.png`). Add the side\'s',
         'level offset for world space: Pewterside 0, Giltside +1500 m X, Frostside +3000 m X.', '',
         'Fastest swap: select a mock side level\'s markers, copy, paste into your side level, and move each one to',
         'the real spot. In PIE, `Story.Markers` must then report no auto-placed names.', '']
total = 0
for side in ('Giltside', 'Pewterside', 'Frostside'):
    f = os.path.join(SAVED, 'MockCity_markers_%s.json' % side)
    if not os.path.exists(f):
        lines += ['## %s' % side, '', '(not built yet)', '']
        continue
    mk = json.load(open(f))['markers']
    total += len(mk)
    lines += ['## %s (%d markers)' % (side, len(mk)), '', '| Marker | Also answers to | Where (local m) | Yaw | What it is |', '|---|---|---|---|---|']

    def key(n):
        k = n.split('_')[0]
        return (KIND_ORDER.index(k) if k in KIND_ORDER else 99, n.lower())
    for name in sorted(mk, key=key):
        x, y, z, yaw, tags = mk[name]
        e = info.get(name, {})
        note = (e.get('note') or '').replace('|', '/')
        if not note and tags:
            note = (info.get(tags[0], {}).get('note') or '').replace('|', '/')
        lines.append('| `%s` | %s | %.1f, %.1f, %.1f | %d | %s |' % (
            name, ', '.join('`%s`' % t for t in tags) or '', x, y, z, int(yaw), note[:110]))
    lines.append('')
lines += ['## Not story markers', '',
          '- `VillainArena` is a **Reflections Villain Arena** actor (Frostside, on the Frost Tower crown, arena radius 11.5 m).',
          '  Without one, the villain falls back to `Tower_Frostside`.',
          '- Optional generic fallbacks (`Mk_<Side>_<Kind>`, `Haunt_Square/Market/Tavern/Bridge`) ride as tags on the',
          '  named places above where one fits. The rest fall back to a navmesh point near the side anchor.',
          '- Test-quest names (`Item_TestLedger`, `Spot_TestBrazier`) are not placed.', '']
open(os.path.join(PROJ, 'ArtDirection', 'MockCity', 'MARKERS.md'), 'w', encoding='utf-8').write('\n'.join(lines))
print('MARKERS.md rows:', total)
