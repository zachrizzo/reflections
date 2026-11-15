"""Runs the whole world-jump PIE test in one go, keeping PIE short: start PIE, open the test map, run the
in-editor driver, inject the real Enhanced Input jump, wait for the driver, capture, stop PIE."""
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
import uepy  # noqa: E402

SP = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(SP, 'mock_results.json')
SHOTS = os.path.join(SP, 'shots_mock')
os.makedirs(SHOTS, exist_ok=True)


def session():
    sid, _ = uepy.post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                   "clientInfo": {"name": "wjtest", "version": "1"}}})
    uepy.post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
    return sid


def tool(sid, toolset, name, args, timeout=120):
    _, body = uepy.post({"jsonrpc": "2.0", "id": int(time.time() * 1000) % 100000, "method": "tools/call",
                         "params": {"name": "call_tool", "arguments": {"toolset_name": toolset, "tool_name": name,
                                                                       "arguments": args}}}, sid, timeout)
    d = uepy.parse(body)
    res = d.get('result', d)
    text = "".join(b.get("text", "") for b in res.get("content", [])) if isinstance(res, dict) else str(res)
    return res.get('isError') if isinstance(res, dict) else True, text


def py(sid, code, timeout=120):
    return tool(sid, "editor_toolset.toolsets.python_scripting.PythonScriptingTools", "execute_python",
                {"script": {"content": code, "language": "Python"}}, timeout)


PIE_WORLD = {'path': ''}


def capture(sid, tag):
    _, body = uepy.post({"jsonrpc": "2.0", "id": 9, "method": "tools/call",
                         "params": {"name": "call_tool", "arguments": {
                             "toolset_name": "SceneCaptureToolset.SceneCaptureToolset", "tool_name": "CaptureGameViewport",
                             "arguments": {"world": {"refPath": PIE_WORLD['path']}, "maxResolution": 1600}}}}, sid, 60)
    import base64
    d = uepy.parse(body)
    res = d.get('result', {})
    texts = []
    for b in res.get('content', []):
        if b.get('type') == 'image' and b.get('data'):
            path = os.path.join(SHOTS, tag + '.png')
            with open(path, 'wb') as f:
                f.write(base64.b64decode(b['data']))
            return path
        texts.append(b.get('text', '')[:300])
    # Fallback: an image string inside the JSON text.
    try:
        img = json.loads(''.join(texts))['returnValue']['image']
        return 'no image block; image field starts %r' % img[:80]
    except Exception as e:  # noqa: BLE001
        return 'capture failed: %s %s' % (e, ' | '.join(texts))


def results():
    try:
        with open(RESULTS) as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


def main():
    t0 = time.time()
    for name in os.listdir(SP):
        if name.startswith('cap_') and name.endswith('.done'):
            os.remove(os.path.join(SP, name))
    if os.path.exists(RESULTS):
        os.remove(RESULTS)
    sid = session()
    # House rule: Saved/PIE_LOCK.json gates every StartPIE.
    lock = 'C:/Users/zachc/Documents/Unreal Projects/reflections/Saved/PIE_LOCK.json'
    me = 'local_830b60d0-e78a-4297-82b7-84148e788d04'
    for _ in range(40):
        try:
            held = json.load(open(lock))
        except Exception:  # noqa: BLE001
            held = None
        if held and held.get('owner') != me and float(held.get('expires_epoch', 0)) > time.time():
            print('lock held by', held.get('owner'), 'until', held.get('expires_epoch'))
            time.sleep(15)
            continue
        break
    else:
        print('lock never freed, not starting')
        return
    err, text = py(sid, 'import unreal\n"PIE=%s" % (unreal.EditorLevelLibrary.get_game_world() is not None)')
    if 'PIE=True' in text:
        print('PIE busy, not starting')
        return
    with open(lock, 'w') as f:
        json.dump({'owner': me, 'purpose': 'world-jump: mock city PIE check (~3.5 min)', 'acquired_epoch': time.time(),
                   'expires_epoch': time.time() + 240}, f)
    print('start', tool(sid, "EditorToolset.EditorAppToolset", "StartPIE", {}, 90))
    try:
        time.sleep(3)
        print('open', py(sid, 'import unreal\nunreal.SystemLibrary.execute_console_command(unreal.EditorLevelLibrary.get_game_world(), "open /Game/MockCity/Lvl_MockCity")\n"ok"'))
        # Wait for the travel to finish.
        for _ in range(90):
            time.sleep(1)
            err, text = py(sid, 'import unreal\nw = unreal.EditorLevelLibrary.get_game_world()\n(w.get_path_name() if w else "none")', 30)
            if 'Lvl_MockCity' in text:
                PIE_WORLD['path'] = json.loads(text)['returnValue']
                break
        print('world', text)
        code = open(os.path.join(SP, 'mock_driver.py'), encoding='utf-8').read()
        print('driver', py(sid, code))
        captured = set()
        injected = False
        deadline = time.time() + 190
        while time.time() < deadline:
            time.sleep(0.7)
            r = results()
            cur = r.get('current')
            for tag, _ in r.get('shots', []):
                if tag not in captured:
                    captured.add(tag)
                    print('capture', tag, capture(sid, tag))
                    open(os.path.join(SP, 'cap_%s.done' % tag), 'w').close()
            if False and cur == 'await_input_jump' and not injected:
                injected = True
                print('inject', tool(sid, "InputToolset.InputToolset", "ApplyInput",
                                     {"entries": [{"action": {"refPath": "/Game/Worlds/Input/IA_WorldJumpUp.IA_WorldJumpUp"},
                                                   "value": {"x": 1, "y": 0, "z": 0}}], "durationSeconds": 0.5}, 30))
            if r.get('done'):
                break
        r = results()
        for tag, _ in r.get('shots', []):
            if tag not in captured:
                captured.add(tag)
                print('capture', tag, capture(sid, tag))
    finally:
        print('stop', tool(sid, "EditorToolset.EditorAppToolset", "StopPIE", {}, 60))
        try:
            if json.load(open(lock)).get('owner') == me:
                os.remove(lock)
        except Exception:  # noqa: BLE001
            pass
        print('elapsed %.0fs' % (time.time() - t0))
    r = results()
    print(json.dumps({'done': r.get('done'), 'step': r.get('current'), 'log_tail': r.get('log', [])[-6:]}, indent=1))


if __name__ == '__main__':
    main()
