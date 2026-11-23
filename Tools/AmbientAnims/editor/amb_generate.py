# Press the Sequencer toolbar Generate button (Live Update is off, so keyed prompts alone generate nothing).
# While a generation runs, the same button cancels it, and a run keeps going after its sequence is closed. So first
# check the editor log: if a run (for example the previous category's leftovers) is still going, cancel it and wait
# for it to end, then start a fresh run. MODE='cancel' only stops a running generation.
import os
out = {}
assert not pie(), 'PIE running'
assert L.get_current_level_sequence() == obj(AC.seq_path(CI)), 'category sequence not open'
MODE = globals().get('MODE', 'start')


def gen_running():
    """True when the editor log's latest Kimodo clip start is newer than its latest end-of-run line."""
    d = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_log_dir())
    logs = [f for f in os.listdir(d) if f.endswith('.log') and not f.lower().startswith('cef')]
    fn = os.path.join(d, max(logs, key=lambda f: os.path.getmtime(os.path.join(d, f))))
    size = os.path.getsize(fn)
    with open(fn, 'rb') as fh:
        fh.seek(max(0, size - 600000))
        tail = fh.read().decode('utf-8', 'replace')
    start = tail.rfind('[Kimodo] Description:')
    end = max(tail.rfind('Animation generation results:'), tail.rfind('Generation cancelled by the editor'))
    return start > end


async def click():
    q = 'and(type(SButton), visible(true), under(tag(GenerateAllAnimations)))'
    r = await call_tool('WidgetFinder.WidgetFinderSubsystem.Query', request={'query': q, 'limit': 5, 'offset': 0})
    if 'service is stopped' in str(r.get('errorMessage', '')):
        unreal.SystemLibrary.execute_console_command(None, 'WidgetFinder.Start')
    live = []
    for _try in range(8):  # the finder needs a moment to index a freshly opened Sequencer
        live = [x for x in r.get('results', []) if not x.get('bDetached')]  # skip stale copies of closed Sequencers
        if len(live) == 1:
            break
        await asyncio.sleep(1.5)
        r = await call_tool('WidgetFinder.WidgetFinderSubsystem.Query', request={'query': q, 'limit': 5, 'offset': 0})
    assert len(live) == 1, r
    return await call_tool('SlateInspectorToolset.SlateInspectorToolset.Click', Ref=live[0]['ref'])


out['was_running'] = gen_running()
if out['was_running']:
    out['cancel'] = await click()
    for _ in range(60):
        await asyncio.sleep(0.5)
        if not gen_running():
            break
    out['still_running'] = gen_running()
    assert not out['still_running'], 'could not cancel the running generation'
    await asyncio.sleep(1.0)
if MODE == 'start':
    out['click'] = await click()
out['t'] = time.strftime('%H:%M:%S')
out
