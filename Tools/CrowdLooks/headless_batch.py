"""Build several new people in a separate headless editor, so a build can't take the shared editor down.

  UnrealEditor-Cmd.exe reflections.uproject -ExecutePythonScript="<this file>" -unattended -nosplash -stdout
Ids come from Saved/CrowdLooks/headless_ids.json; the log goes to Saved/CrowdLooks/headless.log; per-person results go to
pipeline.json (person_sync.py). Writes only under /Game/Characters/Lanthorne/. No PIE in this process.
"""
import json
import os
import time
import traceback

import unreal

PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()).replace('\\', '/')
if not PROJECT.endswith('/'):
    PROJECT += '/'
TOOLS = PROJECT + 'Tools/CrowdLooks/'
LOG = PROJECT + 'Saved/CrowdLooks/headless.log'


def log(msg):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write('%s %s\n' % (time.strftime('%H:%M:%S'), msg))


ids = json.load(open(PROJECT + 'Saved/CrowdLooks/headless_ids.json'))
log('start %s' % ids)
for pid in ids:
    try:
        g = {'unreal': unreal, '__name__': 'crowdlooks', 'PROJECT': PROJECT, 'PID': pid}
        exec(compile(open(TOOLS + 'person_sync.py', encoding='utf-8').read(), TOOLS + 'person_sync.py', 'exec'), g)
        log('%s %s' % (pid, g.get('RESULT', '')[:400]))
    except Exception:
        log('%s EXC %s' % (pid, traceback.format_exc()[-800:]))
log('done')
