"""Checks that every marker the story quests ask for exists in a map's marker list (no auto-placed fallbacks).

Plain Python, no editor:  python Tools/Quests/check_markers.py [ArtDirection/WorldJump/graylondon_markers.json | a MARKERS.md]

Mirrors the runtime lookups in UReflectionsQuestWorldSubsystem / UReflectionsStoryMarkerSubsystem:
  person   QuestGiver_<id> exactly, else the people book's markers.work / haunt / home
  goTo, protect, spellHit at a place   the objective's marker or target name
  collect  the objective's marker, else Item_<item>
  spawnMarker on objectives
A name resolves when a marker has it (its name or a tag), or people.json markers.story_names maps it to one that
does. "stand-in" means only a same-side Mk_<Side>_<Kind> generic place matched (works, but not the exact spot).
Exit code 1 when anything would be auto-placed.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLACE = ('Spot_', 'Tower_', 'Item_', 'Mk_', 'Home_', 'Work_', 'Haunt_', 'QuestGiver_', 'CutsceneAnchor_')


def map_names(md):
    """Every name a marker answers to: a MARKERS.md table, or a JSON list of {name, tags} (graylondon_markers.json)."""
    names = set()
    if md.suffix.lower() == '.json':
        for m in json.loads(md.read_text(encoding='utf-8')):
            names.add(m['name'])
            names.update(m.get('tags') or [])
        return names
    for line in md.read_text(encoding='utf-8').splitlines():
        if not line.startswith('| `'):
            continue
        cells = line.split('|')
        names.update(re.findall(r'`([^`]+)`', cells[1] + cells[2]))
    return names


def main():
    md = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'ArtDirection' / 'WorldJump' / 'graylondon_markers.json'
    quests = json.loads((ROOT / 'ArtDirection' / 'Story' / 'quests.json').read_text(encoding='utf-8'))['quests']
    book = json.loads((ROOT / 'ArtDirection' / 'Story' / 'people.json').read_text(encoding='utf-8'))
    people = {p['id']: p for p in book.get('people', []) if 'id' in p}
    aliases = {}  # Spot_ -> Mk_
    for k, v in (book.get('markers', {}).get('story_names') or {}).items():
        for n in (v if isinstance(v, list) else [v]):
            aliases[n] = k
    have = map_names(md)

    def resolve(name):
        if name in have:
            return 'exact'
        if name in aliases and aliases[name] in have:
            return 'alias ' + aliases[name]
        m = re.match(r'(Mk_(?:Pew|Gilt|Frost)_[A-Za-z]+)', name)
        if m and m.group(1) in have:
            return 'stand-in ' + m.group(1)
        return None

    rows = []

    def need(q, name, why):
        rows.append((q, name, why, resolve(name)))

    def person(q, pid, why):
        if pid in ('wren_hale', 'narrator', 'the_tarnish', 'Infected', 'Anyone', ''):
            return
        if resolve('QuestGiver_' + pid) == 'exact':
            rows.append((q, 'QuestGiver_' + pid, why, 'exact'))
            return
        mk = (people.get(pid) or {}).get('markers') or {}
        spawn = mk.get('work') or mk.get('haunt') or mk.get('home')
        if spawn:
            rows.append((q, spawn, why + ' (people book, no QuestGiver_%s)' % pid, resolve(spawn)))
        else:
            rows.append((q, 'QuestGiver_' + pid, why + ' (not in the people book)', resolve('QuestGiver_' + pid)))

    for q in quests:
        qid = q.get('id', '?')
        if q.get('giver'):
            person(qid, q['giver'], 'giver')
        for s in q.get('steps', []):
            for o in s.get('objectives', []):
                t = str(o.get('type', '')).lower()
                target = str(o.get('target') or '').split(':', 1)[-1]
                marker = str(o.get('marker') or '').split(':', 1)[-1]
                for key in ('spawnMarker', 'spawnAt'):
                    if o.get(key):
                        need(qid, o[key], 'spawn for ' + s.get('id', '?'))
                if marker.startswith(PLACE):
                    need(qid, marker, '%s %s' % (t, s.get('id', '?')))
                if t in ('collect', 'pickup', 'find'):
                    if not marker:
                        need(qid, 'Item_' + (o.get('item') or target), 'collect ' + s.get('id', '?'))
                elif target.startswith(PLACE):
                    need(qid, target, '%s %s' % (t, s.get('id', '?')))
                elif t in ('talkto', 'talk', 'deliver', 'give', 'spellhit', 'protect', 'defeat') and target:
                    person(qid, target, '%s %s' % (t, s.get('id', '?')))
                if o.get('fallbackTarget'):
                    person(qid, o['fallbackTarget'], 'fallback ' + s.get('id', '?'))

    seen, missing, standin = set(), [], []
    print('| Quest | Marker | For | Resolves |\n|---|---|---|---|')
    for r in rows:
        if (r[0], r[1]) in seen:
            continue
        seen.add((r[0], r[1]))
        print('| %s | `%s` | %s | %s |' % (r[0], r[1], r[2], r[3] or '**AUTO-PLACED**'))
        if r[3] is None:
            missing.append(r)
        elif r[3].startswith('stand-in'):
            standin.append(r)
    print('\n%d names, %d auto-placed, %d stand-ins (%s)' % (len(seen), len(missing), len(standin), md.name))
    for r in missing:
        print('MISSING', r[0], r[1], r[2])
    return 1 if missing else 0


if __name__ == '__main__':
    sys.exit(main())
