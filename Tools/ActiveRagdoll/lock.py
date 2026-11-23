"""lock.py take [purpose] [hold_s] | refresh [hold_s] | release | show"""
import json, sys, time
from pathlib import Path
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_client import Mcp
LOCK = Path(r'C:\Users\zachc\Documents\Unreal Projects\reflections\Saved\PIE_LOCK.json')
ME = 'active-ragdoll local_6fe2a304'
def read():
    try: return json.loads(LOCK.read_text(encoding='utf-8'))
    except Exception: return None
def pie_running():
    try:
        m = Mcp("http://127.0.0.1:8019/mcp", 60); m.open()
        r = m.call("tools/call", {"name": "call_tool", "arguments": {"toolset_name": "EditorToolset.EditorAppToolset", "tool_name": "IsPIERunning", "arguments": {}}})
        t = json.dumps(r)
        return 'true' in t.lower() and 'false' not in t.lower()
    except Exception:
        return True
def write(purpose, hold):
    now = time.time()
    LOCK.write_text(json.dumps({'owner': ME, 'purpose': purpose, 'acquired_epoch': int(now), 'expires_epoch': int(now + hold),
                                'expires_local': time.strftime('%H:%M:%S', time.localtime(now + hold))}, indent=2), encoding='utf-8')
cmd = sys.argv[1]
if cmd == 'show':
    print(read(), 'pie_running', pie_running()); sys.exit(0)
if cmd == 'take':
    purpose = sys.argv[2] if len(sys.argv) > 2 else 'active-ragdoll prototype: short Simulate run on L_TestTown'
    hold = float(sys.argv[3]) if len(sys.argv) > 3 else 240
    deadline = time.time() + float(sys.argv[4] if len(sys.argv) > 4 else 1800)
    while time.time() < deadline:
        l = read(); now = time.time()
        free = l is None or l.get('owner') == ME or float(l.get('expires_epoch', 0)) <= now
        if free and not pie_running():
            write(purpose, hold); time.sleep(1.5)
            c = read()
            if c and c.get('owner') == ME:
                print('ACQUIRED until', c['expires_local'], flush=True); sys.exit(0)
        time.sleep(10)
    print('TIMEOUT', read()); sys.exit(1)
if cmd == 'refresh':
    l = read()
    if l and l.get('owner') == ME:
        hold = float(sys.argv[2]) if len(sys.argv) > 2 else 240
        l['expires_epoch'] = int(time.time() + hold); l['expires_local'] = time.strftime('%H:%M:%S', time.localtime(time.time() + hold))
        LOCK.write_text(json.dumps(l, indent=2), encoding='utf-8'); print('REFRESHED', l['expires_local'])
    else:
        print('NOT MINE', l); sys.exit(1)
if cmd == 'release':
    l = read()
    if l and l.get('owner') == ME:
        LOCK.unlink(); print('RELEASED')
    else:
        print('NOT MINE (left alone)', l)
if cmd == 'mine':
    l = read(); print('MINE' if (l and l.get('owner') == ME and float(l.get('expires_epoch',0)) > time.time()) else 'NO'); 
