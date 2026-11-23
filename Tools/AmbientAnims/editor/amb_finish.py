# End of a batch: cancel any Kimodo run still going (a run keeps regenerating a closed sequence's untouched
# sections), save every dirty package under the library root (generation sequences that leftover runs touched),
# close Sequencer, and report anything still dirty. Never saves a skeleton or anything outside AC.ROOT.
import os
out = {}
assert not pie(), 'PIE running'


def gen_running():
    d = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_log_dir())
    logs = [f for f in os.listdir(d) if f.endswith('.log') and not f.lower().startswith('cef')]
    fn = os.path.join(d, max(logs, key=lambda f: os.path.getmtime(os.path.join(d, f))))
    with open(fn, 'rb') as fh:
        fh.seek(max(0, os.path.getsize(fn) - 600000))
        tail = fh.read().decode('utf-8', 'replace')
    return tail.rfind('[Kimodo] Description:') > max(tail.rfind('Animation generation results:'),
                                                       tail.rfind('Generation cancelled by the editor'))


out['was_running'] = gen_running()
if out['was_running']:
    seq = obj(AC.seq_path(CI))
    if L.get_current_level_sequence() != seq:
        cur = L.get_current_level_sequence()
        assert cur is None or cur.get_path_name().startswith(AC.ROOT), 'another sequence open: ' + cur.get_path_name()
        if cur is not None:
            L.close_level_sequence()
            await asyncio.sleep(0.3)
        L.open_level_sequence(seq)
        await asyncio.sleep(2.0)
    q = 'and(type(SButton), visible(true), under(tag(GenerateAllAnimations)))'
    live = []
    for _try in range(8):
        r = await call_tool('WidgetFinder.WidgetFinderSubsystem.Query', request={'query': q, 'limit': 5, 'offset': 0})
        if 'service is stopped' in str(r.get('errorMessage', '')):
            unreal.SystemLibrary.execute_console_command(None, 'WidgetFinder.Start')
        live = [x for x in r.get('results', []) if not x.get('bDetached')]
        if len(live) == 1:
            break
        await asyncio.sleep(1.5)
    assert len(live) == 1, r
    out['cancel'] = await call_tool('SlateInspectorToolset.SlateInspectorToolset.Click', Ref=live[0]['ref'])
    for _ in range(60):
        await asyncio.sleep(0.5)
        if not gen_running():
            break
    out['still_running'] = gen_running()
    await asyncio.sleep(1.0)
dirty = [p for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() if p.get_name().startswith(AC.ROOT)]
out['saved'] = [p.get_name() for p in dirty]
if dirty:
    out['save_ok'] = bool(unreal.EditorLoadingAndSavingUtils.save_packages(dirty, False))
if L.get_current_level_sequence() is not None and L.get_current_level_sequence().get_path_name().startswith(AC.ROOT):
    L.close_level_sequence()
out['dirty_after'] = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
                      if p.get_name().startswith(AC.ROOT) or 'skel' in p.get_name().lower()]
out['t'] = time.strftime('%H:%M:%S')
json.dumps(out)
