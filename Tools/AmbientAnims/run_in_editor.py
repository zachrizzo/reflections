"""run_in_editor.py <snippet> <category index> [--set NAME=PYEXPR ...] [--wait SEC]

Runs editor/amb_common.py + editor/<snippet>.py in the shared editor through its own MCP server
(127.0.0.1:8019), with CI set to the 0-based category index from ambient_catalog.py, and prints the snippet's
last expression. --set adds a global before the snippet, e.g. --set "ONLY=['ChopWood']".
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from mcp_client import Mcp  # noqa: E402

args = sys.argv[1:]
wait = 100.0
extra = []
while '--wait' in args or '--set' in args:
    flag = '--wait' if '--wait' in args else '--set'
    i = args.index(flag)
    if flag == '--wait':
        wait = float(args[i + 1])
    else:
        extra.append(args[i + 1])
    del args[i:i + 2]
snippet, ci = args[0], int(args[1])


def read(name):
    with open(os.path.join(HERE, 'editor', name + '.py'), encoding='utf-8') as f:
        return f.read()


code = 'CI = %d\n%s\n%s\n%s' % (ci, '\n'.join(extra), read('amb_common'), read(snippet))
t0 = time.time()
while True:
    m = Mcp('http://127.0.0.1:8019/mcp', 900)
    m.open()
    r = m.call('tools/call', {'name': 'call_tool', 'arguments': {
        'toolset_name': 'editor_toolset.toolsets.python_scripting.PythonScriptingTools',
        'tool_name': 'execute_python', 'arguments': {'script': {'content': code, 'language': 'python'}}}})
    if 'running a slow task' in json.dumps(r) and time.time() - t0 < wait:
        time.sleep(5)
        continue
    # Snippets refuse to run during PIE/Simulate (other sessions' test runs); wait it out, up to 20 minutes.
    if 'AssertionError: PIE running' in json.dumps(r) and time.time() - t0 < 1200 and snippet != 'amb_status':
        time.sleep(10)
        continue
    break
if 'error' in r:
    print('RPCERR', json.dumps(r['error'])[:4000])
    sys.exit(1)
for part in r['result'].get('content', []):
    if part.get('type') == 'text':
        t = part['text']
        try:
            j = json.loads(t)
            if isinstance(j, dict) and 'returnValue' in j:
                rv = j['returnValue']
                print(rv if isinstance(rv, str) else json.dumps(rv, indent=1))
                continue
        except Exception:
            pass
        print(t[:6000])
if r['result'].get('isError'):
    sys.exit(1)
