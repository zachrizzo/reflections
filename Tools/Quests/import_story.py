"""Build /Game/Quests/DA_QuestPack_Story from JSON (run in the editor's Python, e.g. through unreal-mcp).

Inputs (project-relative, override with QUESTS_JSON / PEOPLE_JSON globals before running):
  ArtDirection/Story/quests.json               quests (the story bible's), schema in ArtDirection/Quests/README.md
  ArtDirection/Story/people.json               the story bible's people book (falls back to Tools/CrowdLooks/people.json)
The asset keeps the JSON text too (SourceJson / PeopleJson), so the Import Json button re-parses it in the editor.
Prints the import report; the asset is saved only if parsing produced quests.
"""
import os
import unreal

PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
PACK_PATH = '/Game/Quests/DA_QuestPack_Story'

def _read(rel):
    path = rel if os.path.isabs(rel) else os.path.join(PROJECT, rel)
    if not os.path.exists(path):
        return None, path
    with open(path, 'r', encoding='utf-8') as f:
        return f.read(), path

quests_rel = globals().get('QUESTS_JSON', 'ArtDirection/Story/quests.json')
people_rel = globals().get('PEOPLE_JSON', 'ArtDirection/Story/people.json')
quests_text, quests_path = _read(quests_rel)
people_text, people_path = _read(people_rel)
if people_text is None:
    people_text, people_path = _read('Tools/CrowdLooks/people.json')

eal = unreal.EditorAssetLibrary
if eal.does_asset_exist(PACK_PATH):
    pack = unreal.load_asset(PACK_PATH)
else:
    factory = unreal.DataAssetFactory()
    factory.set_editor_property('data_asset_class', unreal.ReflectionsQuestPack)
    pack = unreal.AssetToolsHelpers.get_asset_tools().create_asset('DA_QuestPack_Story', '/Game/Quests', unreal.ReflectionsQuestPack, factory)

if quests_text is not None:
    pack.set_editor_property('source_json', quests_text)
if people_text is not None:
    pack.set_editor_property('people_json', people_text)
ok = pack.import_json()

# Scenes other systems start (game flow: Intro; villain: MirrorWhole, Ending). A quest step naming one only waits
# for it: the cutscene field is dropped and a short timeout keeps PIE (where the intro is gated) from blocking.
EXTERNAL_SCENES = {'intro', 'mirrorwhole', 'ending'}
quests_arr = pack.get_editor_property('quests')
patched = []
for qi in range(len(quests_arr)):
    q = quests_arr[qi]
    steps = q.get_editor_property('steps')
    for si in range(len(steps)):
        st = steps[si]
        scene = str(st.get_editor_property('cutscene'))
        waits_external = any(str(o.get_editor_property('target')) == 'CutsceneDone' and str(o.get_editor_property('spell')).lower() in EXTERNAL_SCENES
                             for o in st.get_editor_property('objectives'))
        if waits_external and scene.lower() not in EXTERNAL_SCENES and st.get_editor_property('timeout_seconds') <= 0.0:
            st.set_editor_property('timeout_seconds', 4.0)
            steps[si] = st
            patched.append('%s/%s (timeout only)' % (q.get_editor_property('id'), st.get_editor_property('id')))
        if scene.lower() in EXTERNAL_SCENES:
            st.set_editor_property('cutscene', 'None')
            if st.get_editor_property('timeout_seconds') <= 0.0:
                st.set_editor_property('timeout_seconds', 4.0)
            steps[si] = st
            patched.append('%s/%s (%s)' % (q.get_editor_property('id'), st.get_editor_property('id'), scene))
    q.set_editor_property('steps', steps)
    quests_arr[qi] = q
pack.set_editor_property('quests', quests_arr)
print('waits only (not started by quests):', patched)
report = pack.get_editor_property('import_report')
quests = pack.get_editor_property('quests')
people = pack.get_editor_property('people')
print('quest pack import ok=%s quests=%d people=%d\n%s' % (ok, len(quests), len(people), report))
print('sources: %s | %s' % (quests_path, people_path))
if len(quests) > 0 or len(people) > 0:
    eal.save_loaded_asset(pack, only_if_is_dirty=False)
    print('saved', PACK_PATH)

# ---- Markers the content needs (for the map designer) ------------------------------------------------------
import json as _json

STORY_KINDS = ('Home_', 'Work_', 'Haunt_', 'QuestGiver_', 'CutsceneAnchor_', 'Tower_', 'Spot_', 'Item_', 'Mk_')

def _markers_needed(quests_text):
    try:
        root = _json.loads(quests_text)
    except Exception:
        return []
    qs = root.get('quests', root) if isinstance(root, dict) else root
    rows = []
    for q in qs if isinstance(qs, list) else []:
        qid = q.get('id', '?')
        if q.get('giver'):
            rows.append((qid, 'QuestGiver_%s' % q['giver'], 'where %s waits with the quest' % q['giver']))
        for s in q.get('steps', []):
            for o in s.get('objectives', []):
                t = str(o.get('type', '')).lower()
                target = o.get('target') or ''
                marker = o.get('marker') or ''
                for name in (target, marker):
                    if name and name.startswith(STORY_KINDS):
                        rows.append((qid, name, '%s: %s' % (t, o.get('text', ''))))
                if t in ('collect', 'pickup', 'find') and not marker:
                    rows.append((qid, 'Item_%s' % (target or o.get('item', '')), 'collect: %s' % o.get('text', '')))
                if t in ('talkto', 'talk', 'deliver', 'give') and target and not target.startswith(STORY_KINDS):
                    rows.append((qid, 'QuestGiver_%s' % target, 'where %s can be found' % target))
    seen, out = set(), []
    for r in rows:
        if (r[0], r[1]) not in seen:
            seen.add((r[0], r[1]))
            out.append(r)
    return out

if quests_text is not None:
    rows = _markers_needed(quests_text)
    lines = ['# Story markers the quests need', '',
             'Generated by Tools/Quests/import_story.py from %s. Drop a' % os.path.relpath(quests_path, PROJECT).replace(os.sep, '/'),
             '**Reflections Story Marker** with each name (see ArtDirection/Quests/README.md). Missing ones are auto-placed',
             'near the right side until you do, and `Story.Markers` in PIE lists which. Check a map marker list',
             'without the editor: `python Tools/Quests/check_markers.py ArtDirection/MockCity/MARKERS.md`.', '',
             '| Quest | Marker name | Used for |', '|---|---|---|']
    lines += ['| %s | `%s` | %s |' % r for r in rows]
    lines += ['', 'Main quest (built in): `Tower_Pewterside`, `Tower_Giltside`, `Tower_Frostside` (else the page pickups), and the',
              'villain arena (`Reflections Villain Arena`, else `Tower_Frostside`).']
    out_path = os.path.join(PROJECT, 'ArtDirection', 'Quests', 'markers-needed.md')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print('wrote', out_path, len(rows), 'markers')

# ---- Item meshes: Codex's props (/Game/LanthorneAssets/Quest), mapped by item id; else SM_<ItemId> if it exists ---
ITEM_MESHES = {
    'Letter': 'SM_NellsLetter',
    'TicketStub': 'SM_TramTicket',
    'Fiddle': 'SM_JorysFiddle',
    'Eyeglass': 'SM_GlaziersEyeglass',
    'LampOil': 'SM_LampOilBarrel',
    'Wool': 'SM_BoltOfWool',
    'Shears': 'SM_BarnabysShears',
}
items = pack.get_editor_property('items') if hasattr(pack, 'get_editor_property') else []
changed = False
try:
    for idx in range(len(items)):
        item = items[idx]
        item_id = str(item.get_editor_property('id'))
        mesh_path = '/Game/LanthorneAssets/Quest/' + ITEM_MESHES.get(item_id, 'SM_' + item_id)
        has_mesh = not item.get_editor_property('mesh').is_null() if hasattr(item.get_editor_property('mesh'), 'is_null') else bool(item.get_editor_property('mesh'))
        if not has_mesh and eal.does_asset_exist(mesh_path):
            item.set_editor_property('mesh', unreal.load_asset(mesh_path))
            items[idx] = item
            changed = True
            print('item mesh', item.get_editor_property('id'), '->', mesh_path)
    if changed:
        pack.set_editor_property('items', items)
        eal.save_loaded_asset(pack, only_if_is_dirty=False)
except Exception as ex:  # the running build may predate the Mesh field
    print('item meshes skipped:', ex)
