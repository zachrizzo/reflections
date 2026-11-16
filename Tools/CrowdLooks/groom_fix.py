"""Fix NPC grooms on every look Blueprint (user, 15 Nov 15:58: "fix the grooms on all of the npcs"). Top-level await.

Cause (groom_lods.json, 16:10): each look's LODSync maps body LOD -> groom LOD ([3,5,7] or [5,7]); groom LODs are
strands 0-1, CARDS 2-4, MESHES ("helmet") 5-7, and brow/beard/moustache mesh LODs are hidden. Since my 22:20 MinLOD 1
the body never uses LOD 0, so hair sat on the helmet LODs and brows/beards were hidden at every distance. On some looks
the Eyebrows were not in the LODSync list at all and ran their own LOD (strands up close).

Fix, per look, LODSync only (body/face/clothes keep ForcedLOD -1 / MinLOD 1):
- every groom component with an asset is in ComponentsToSync as PASSIVE;
- its mapping is [near, near, far] (3 LODs) or [near, near] (2 LODs): near = the groom's cards LOD (3) when it has cards
  data, else its best mesh LOD; far = its coarsest mesh LOD (hidden for brows/beards), or near if it has none;
- groom tick group TG_POST_UPDATE_WORK (hair follows the moving head).
Saves ONLY the look's own package; Body bone 0 must be 'root' before and after; a compile that dirties a shared
Common asset or skeleton is not saved (look reloaded). Globals: LOOKS (paths), DRY_RUN (default True), OUT_JSON.
"""
import json

eal = unreal.EditorAssetLibrary
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
SDL = unreal.SubobjectDataBlueprintFunctionLibrary
DIRS = ['/Game/Characters/Lanthorne/Looks', '/Game/Characters/Lanthorne/Looks/Pewterside',
        '/Game/Characters/Lanthorne/Looks/Soldiers']
DRY = globals().get('DRY_RUN', True)
exec(open(PROJECT + 'Tools/CrowdLooks/skel_guard.py', encoding='utf-8').read(), globals())


async def bone0(path):
    if '.' not in path.split('/')[-1]:
        path = path + '.' + path.split('/')[-1]
    r = await call_tool('EditorToolset.SkeletalMeshToolset.GetBoneNames', mesh={'refPath': path})
    bones = r.get('returnValue', r) if isinstance(r, dict) else r
    return bones[0] if bones else None


def dirty_set():
    return set(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())


def groom_layout(g):
    """(cards LODs with cards data, mesh LODs with mesh data, per-LOD [type, visible in any group])."""
    cards, meshes, table = [], [], []
    try:
        cards = sorted(set(int(x.get_editor_property('lod_index')) for x in g.get_editor_property('hair_groups_cards')))
    except Exception:
        pass
    try:
        meshes = sorted(set(int(x.get_editor_property('lod_index')) for x in g.get_editor_property('hair_groups_meshes')))
    except Exception:
        pass
    try:
        groups = [list(grp.get_editor_property('lo_ds')) for grp in g.get_editor_property('hair_groups_lod')]
        for i in range(max(len(x) for x in groups)):
            types = [str(x[i].get_editor_property('geometry_type')).split('.')[-1].split(':')[0] for x in groups if i < len(x)]
            vis = any(bool(x[i].get_editor_property('visible')) for x in groups if i < len(x))
            table.append([types[0], vis])
    except Exception:
        pass
    if not table:
        table = [['STRANDS', True]] * 2 + [['CARDS', True]] * 3 + [['MESHES', True]] * 3
    return cards, meshes, table


def target_mapping(g, count, old):
    """[near]*(count-1) + [far]. near: cards LOD with data (3 preferred) > visible mesh LOD with data > the cheaper
    strands LOD (grooms that only have strands, e.g. Eyebrows_M_Dense). far: the coarsest mesh LOD with data, else the
    last LOD (hidden for brows and most facial hair)."""
    cards, meshes, table = groom_layout(g)
    n = len(table)
    ok_cards = [i for i in cards if i < n and table[i][0] == 'CARDS' and table[i][1]]
    ok_mesh = [i for i in meshes if i < n and table[i][0] == 'MESHES' and table[i][1]]
    strands = [i for i in range(n) if table[i][0] == 'STRANDS' and table[i][1]]
    if ok_cards:
        near = 3 if 3 in ok_cards else ok_cards[0]
    elif ok_mesh:
        near = ok_mesh[0]
    elif strands:
        near = strands[-1]
    else:
        near = old[0] if old else min(3, n - 1)
    far = ok_mesh[-1] if ok_mesh else n - 1
    if count <= 2:
        return [near] * max(count, 1)
    return [near] * (count - 1) + [far]


looks = globals().get('LOOKS')
if not looks:
    looks = []
    for d in DIRS:
        for p in eal.list_assets(d, recursive=False):
            path = p.split('.')[0]
            if path.split('/')[-1].startswith(('BP_Look_', 'PewLook_', 'GiltSoldier_', 'FrostSoldier_')):
                looks.append(path)
report = {}
for path in sorted(looks):
    name = path.split('/')[-1]
    row = {'grooms': {}}
    before = dirty_set()
    bp = unreal.load_asset(path)
    lodsync, body, grooms = None, None, {}
    seen = set()
    for h in sds.k2_gather_subobject_data_for_blueprint(bp):
        d = SDL.get_data(h)
        o = SDL.get_object(d)
        n = str(SDL.get_variable_name(d))
        if o is None or n in seen:
            continue
        seen.add(n)
        cls = o.get_class().get_name()
        if cls == 'LODSyncComponent':
            lodsync = o
        elif cls == 'GroomComponent':
            if o.get_editor_property('groom_asset') is not None:
                grooms[n] = o
        elif n == 'Body' and isinstance(o, unreal.SkeletalMeshComponent):
            m = o.get_editor_property('skeletal_mesh_asset')
            body = m.get_path_name().split('.')[0] if m else None
    if lodsync is None or body is None:
        report[name] = dict(row, skipped='no LODSync or Body')
        continue
    sync = list(lodsync.get_editor_property('components_to_sync'))
    synced = {str(c.get_editor_property('name')): c for c in sync}
    mapping = dict(lodsync.get_editor_property('custom_lod_mapping').items())
    old_maps = {str(k): list(v.get_editor_property('mapping')) for k, v in mapping.items()}
    count = lodsync.get_editor_property('num_lods')
    if count is None or count <= 0:
        lens = [len(v) for k, v in old_maps.items() if k in grooms] or [len(v) for v in old_maps.values()]
        count = max(lens) if lens else 2
    row['num_lods'] = count
    row['lodsync'] = [lodsync.get_editor_property('forced_lod'), lodsync.get_editor_property('min_lod')]
    changed = False
    for gname, comp in grooms.items():
        g = comp.get_editor_property('groom_asset')
        old = old_maps.get(gname)
        new = target_mapping(g, count, old)
        cards, meshes, table = groom_layout(g)
        info = {'asset': g.get_name(), 'cards': cards, 'meshes': meshes, 'was': old, 'now': new,
                'lods': ''.join((t[0][0] if t[1] else t[0][0].lower()) for t in table),
                'was_synced': gname in synced}
        tick_ok = None
        try:
            tf = comp.get_editor_property('primary_component_tick')
            tick_ok = tf.get_editor_property('tick_group') == unreal.TickingGroup.TG_POST_UPDATE_WORK
            info['tick_post_update'] = tick_ok
        except Exception as e:
            info['tick_err'] = str(e)[:80]
        row['grooms'][gname] = info
        if old != new or gname not in synced or tick_ok is False:
            changed = True
            if not DRY:
                if gname not in synced:
                    cs = unreal.ComponentSync()
                    cs.set_editor_property('name', unreal.Name(gname))
                    cs.set_editor_property('sync_option', unreal.SyncOption.PASSIVE)
                    sync.append(cs)
                    synced[gname] = cs
                md = unreal.LODMappingData()
                md.set_editor_property('mapping', new)
                mapping[unreal.Name(gname)] = md
                for k in [k for k in mapping if str(k) == gname and k != unreal.Name(gname)]:
                    del mapping[k]
                if tick_ok is False:
                    tf.set_editor_property('tick_group', unreal.TickingGroup.TG_POST_UPDATE_WORK)
                    comp.set_editor_property('primary_component_tick', tf)
    row['changed'] = changed
    if DRY or not changed:
        report[name] = row
        continue
    row['bone0_before'] = await bone0(body)
    if row['bone0_before'] != 'root':
        report[name] = dict(row, skipped='Body bone 0 not root')
        continue
    lodsync.set_editor_property('components_to_sync', sync)
    lodsync.set_editor_property('custom_lod_mapping', mapping)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    extra = sorted(p for p in dirty_set() - before if p != path)
    if extra:
        row['extra_dirty'] = extra
        row['skel_reloaded'] = skel_guard()
        if any('/Common/' in p or 'skel' in p.lower() for p in extra):
            unreal.EditorLoadingAndSavingUtils.reload_packages(
                [bp.get_outermost()], unreal.ReloadPackagesInteractionMode.ASSUME_POSITIVE)
            report[name] = dict(row, skipped='compile dirtied a shared asset; look reloaded, not saved')
            continue
    row['saved'] = bool(eal.save_asset(path, only_if_is_dirty=False))
    row['bone0_after'] = await bone0(body)
    report[name] = row
    if globals().get('OUT_JSON'):
        open(OUT_JSON, 'w', encoding='utf-8').write(json.dumps(report, indent=1))
report['_dirty_after'] = sorted(dirty_set())
RESULT = json.dumps(report)
if globals().get('OUT_JSON'):
    open(OUT_JSON, 'w', encoding='utf-8').write(json.dumps(report, indent=1))
