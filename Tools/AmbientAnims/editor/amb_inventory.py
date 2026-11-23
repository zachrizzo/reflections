# Read-only check of the whole library: per category, which catalog clips have a saved AnimSequence, which carry
# the catalog metadata, and any asset in the folder that the catalog doesn't know. CI is ignored.
out = {'cats': {}}
E = unreal.EditorAssetLibrary
total = 0
for ci, (name, _d, clips) in enumerate(AC.CATEGORIES):
    folder = AC.folder(ci)
    on_disk = {p.rsplit('/', 1)[1].split('.')[0] for p in E.list_assets(folder, recursive=False)}
    want = {AC.asset_name(ci, c): c for c in clips}
    missing = sorted(set(want) - on_disk)
    extra = sorted(on_disk - set(want))
    bad_meta, keys = [], set()
    for an, c in want.items():
        if an not in on_disk:
            continue
        a = obj(folder + '/' + an)
        keys.add(a.data_model_interface.get_number_of_keys())
        if E.get_metadata_tag(a, 'Ambient.Clip') != c['id'] or a.get_editor_property('enable_root_motion'):
            bad_meta.append(an)
    total += len(want) - len(missing)
    out['cats'][name] = {'have': len(want) - len(missing), 'of': len(want), 'missing': missing, 'extra': extra,
                         'bad_meta': bad_meta, 'keys': sorted(keys)}
    await asyncio.sleep(0)
out['total'] = total
out['dirty'] = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
                if p.get_name().startswith(AC.ROOT) or 'skel' in p.get_name().lower()]
json.dumps(out)
